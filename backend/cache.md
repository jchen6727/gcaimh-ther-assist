# Cache Optimization Session Bootstrap — `therapy-analysis-function`

**Project:** gcaimh — AI-assisted therapy session supervision platform  
**Working directory:** `/Users/jchen/dev/gcaimh`  
**Prerequisite reading:** `backend/CACHE_ANALYSIS_REPORT.md` (investigation already complete — do not re-derive)  
**Your task:** Implement cache fixes in priority order defined in §3 below.

---

## 1. What Has Already Been Established

A full end-to-end analysis of both caching systems in `backend/therapy-analysis-function/main.py`
was completed. The findings are settled facts — do not re-investigate unless a specific
function is ambiguous.

### Finding A — Gemini context cache is permanently disabled

`handle_comprehensive_analysis()` (line 1344) always passes a non-empty `rag_tools`
list. Line 1375:

```python
cached_content_name = None if rag_tools else _get_or_refresh_cached_content()
```

The Gemini API forbids `tools` and `cached_content` in the same request. Result:
`context_cache_hit` is always `False`, and the ~75% Pro model input token savings
the cache was designed to provide are never realized.

### Finding B — RAG prefetch cache has ~0% hit rate

`prefetch_rag_context()` (line 562) caches Discovery Engine passages keyed by
`(session_type, transcript_hash)` with a 25-second TTL. Two bugs make this unreachable
in normal conversation:

1. **Hash mismatch:** `transcript_hash = str(hash(transcript_text[-500:]))`. At
   130–150 wpm ≈ 14 chars/second, the last 500 chars represents ~36 seconds of speech.
   Every analysis call is triggered by a new completed utterance, which always shifts
   the last 500 chars → hash miss on every call.

2. **TTL too short:** Therapeutic utterances run 20–90 seconds. Most inter-call
   intervals exceed 25 s → TTL fails independently of the hash check.

3. **Secondary flaw:** The actual query sent to Discovery Engine uses the last 200
   words (~86 s of speech, line 587). The cache key (last 500 chars, ~36 s) changes
   faster than the query, causing redundant fetches even when retrieved passages would
   be identical.

4. **Execution is synchronous:** `prefetch_rag_context()` is called at line 1028 and
   blocks via `t.join(timeout=10)` on all 4 datastore threads before the prompt is
   built. Actual realtime latency: 3–11 s per call, not the stated 2–4 s.

---

## 2. Key Code Locations

All in `backend/therapy-analysis-function/main.py`:

| Symbol | Line(s) | Role |
|--------|---------|------|
| `RAG_CACHE_TTL_SECONDS` | 503 | TTL constant — change to 90 |
| `_rag_cache` | 501 | Module-level cache dict |
| `_rag_cache_lock` | 500 | Threading lock for cache dict |
| `prefetch_rag_context()` | 562–628 | Cache lookup + Discovery Engine fetch |
| `transcript_hash` computation | 569 | The bug: should hash `query_text`, not `transcript_text[-500:]` |
| `query_text` computation | 586–587 | Last 200 words — what should drive the hash |
| `handle_realtime_analysis_with_retry()` | 1018–1342 | Calls `prefetch_rag_context()` at line 1028 |
| `_get_or_refresh_cached_content()` | 287–323 | Gemini context cache — blocked by `rag_tools` |
| Context cache gate | 1375 | `cached_content_name = None if rag_tools else ...` |
| `handle_comprehensive_analysis()` | 1344–1545 | Comprehensive path — Pro model |
| `build_diagnostics()` | 160–215 | Diagnostics builder — needs `prefetch_meta` arg |

Related constants in `backend/therapy-analysis-function/constants.py`:
- `MODEL_NAME` — Flash model (realtime path)
- `MODEL_NAME_PRO` — Pro model (comprehensive path)
- `COMPREHENSIVE_ANALYSIS_PROMPT` — the prompt being cached (context cache)

---

## 3. Task Priority Order

Implement in this order. Each task is independent of the others unless noted.

### Task 1 — Remove transcript hash from cache key + raise TTL (15 min, no risk)

⚠️ **Prior version of this task was incorrect.** It proposed changing the hash input
from `transcript_text[-500:]` to the last-200-word query window. That change does not
produce cache hits: any window computed over the tail of a growing transcript string
changes on every trigger because new speech always appends at the tail. The correct
fix is to remove the hash check entirely, leaving TTL as the sole invalidation
mechanism. See `AUTOPSY_CACHE_FIX.md` for the full explanation.

**Files:** `main.py` lines 503, 569, 575, and 622.

```python
# Line 503: change
RAG_CACHE_TTL_SECONDS = 25
# to
RAG_CACHE_TTL_SECONDS = 90

# Line 569: DELETE this line entirely
transcript_hash = str(hash(transcript_text[-500:] if len(transcript_text) > 500 else transcript_text))

# Line 575: change the hit condition from
if age < RAG_CACHE_TTL_SECONDS and cached["transcript_hash"] == transcript_hash:
# to
if age < RAG_CACHE_TTL_SECONDS:

# Line 622: remove "transcript_hash" from the cache write dict
# Change:
_rag_cache[session_type] = {
    "passages": formatted_context,
    "timestamp": time.time(),
    "transcript_hash": transcript_hash,
}
# to:
_rag_cache[session_type] = {
    "passages": formatted_context,
    "timestamp": time.time(),
}
```

### Task 2 — Instrument `prefetch_rag_context()` to return metadata (1 h)

This is Tier 2 Step 3 from `SESSION_BOOTSTRAP.md`. Change the function signature and
return type, then thread the metadata into `build_diagnostics()`.

**Step 2a:** Change `prefetch_rag_context()` return type from `str` to `tuple[str, dict]`:

```python
prefetch_meta = {
    "rag_latency_ms": round(prefetch_elapsed),       # already computed at line 607
    "rag_query_words": len(query_text.split()),
    "passages_by_store": {ds_id: len(v) for ds_id, v in results_by_store.items()},
    "cache_hit": False,                               # set to True on cache hit path
    "prefetch_age_seconds": 0,                        # set to round(age) on cache hit
}
return formatted_context, prefetch_meta
```

On the cache-hit path (line 577), return:
```python
return cached["passages"], {
    "rag_latency_ms": 0,
    "cache_hit": True,
    "prefetch_age_seconds": round(age),
    "passages_by_store": {},
    "rag_query_words": 0,
}
```

**Step 2b:** Update the call site at line 1028:
```python
_rag_context, _rag_prefetch_meta = prefetch_rag_context(session_context, transcript_text)
```

**Step 2c:** Add `prefetch_meta` parameter to `build_diagnostics()` (line 160) and
include it in the returned dict under `grounding.prefetch`:

```python
# in build_diagnostics() return value, inside "grounding":
"grounding": {
    "chunks_retrieved": len(grounding_sources),
    "sources": [...],
    "prefetch": prefetch_meta or {},   # new field
}
```

Pass `prefetch_meta=_rag_prefetch_meta` (or `None` for comprehensive path) at all
`build_diagnostics()` call sites in `try_analysis_with_prompt()`.

### Task 3 — Fix Gemini context cache on comprehensive path (2–4 h, requires decision)

**Prerequisite decision:** Switching the comprehensive path from inline `tools=rag_tools`
to pre-fetched text injection **loses** the `grounding_metadata` that populates
citations in the response. Before implementing, confirm with the team whether:

- **A)** Citations on comprehensive analysis can be dropped (simplified output), or
- **B)** Citations should be carried forward from the prefetch metadata as a structured
  field (requires augmenting `_query_datastore()` to return source titles + page info),
  or
- **C)** This task should be deferred pending a citation design decision.

If cleared to proceed:

1. Replace `tools=rag_tools` in `handle_comprehensive_analysis()` config (line 1404)
   with text injection (same pattern as the realtime path: call `prefetch_rag_context()`
   and prepend to the prompt).
2. Remove the `rag_tools` parameter from `handle_comprehensive_analysis()` signature,
   or pass it only for tool-name logging.
3. This unblocks `_get_or_refresh_cached_content()` at line 1375 — no other change needed.
4. Verify `_diagnostics.context_cache_hit` becomes `True` on the second and subsequent
   requests within the 30-minute cache window.

### Task 4 — True background prefetch (1–2 days, architectural, defer if uncertain)

Not a single-file change. Do not start this task without explicit direction.
Design options are in `CACHE_ANALYSIS_REPORT.md` §Options/Option 3.

---

## 4. Tests to Write Alongside Changes

For Tasks 1 and 2, add to `backend/therapy-analysis-function/tests/test_rag_cache.py`
(new file, follows spec §3.3 patterns):

```
test_cache_hit_within_ttl_any_transcript:
  - Mock `_rag_cache[session_type]` with a fresh entry (age < 90 s), any passage.
  - Mock `_query_datastore` to raise AssertionError if called.
  - Call `prefetch_rag_context()` twice with DIFFERENT transcript_text.
  - Assert second call returns cached passages WITHOUT calling `_query_datastore`.
  - Assert returned `prefetch_meta["cache_hit"] == True`.
  → Verifies TTL-only invalidation: transcript content does not affect hit/miss.

test_cache_miss_on_expired_ttl:
  - Mock `_rag_cache` with a stale entry (age > 90 s).
  - Mock `_query_datastore` to return a fixed passage.
  - Call `prefetch_rag_context()` — assert `_query_datastore` was called.
  - Assert returned `prefetch_meta["cache_hit"] == False`.

test_cache_hit_rate_at_conversational_pace:
  - Simulate 10 consecutive calls with transcript growing by 8 words each call
    (matching the frontend 8-word trigger threshold).
  - First call populates cache. Calls 2–10 arrive within 90 s of call 1.
  - Assert calls 2–10 all return cache_hit == True.
  → The scenario that previously produced 0% hit rate must now produce ~100%.
```

---

## 5. Definition of Done

- [ ] `RAG_CACHE_TTL_SECONDS = 90` in `main.py`
- [ ] `transcript_hash` computation removed from `prefetch_rag_context()` (line 569 deleted)
- [ ] Hit condition is `age < RAG_CACHE_TTL_SECONDS` only — no hash comparison (line 575)
- [ ] Cache write dict no longer stores `transcript_hash` (line 622)
- [ ] `prefetch_rag_context()` returns `(str, dict)` — call sites updated
- [ ] `build_diagnostics()` accepts and emits `prefetch_meta` under `grounding.prefetch`
- [ ] `_diagnostics.grounding.prefetch.cache_hit` appears in realtime responses
- [ ] Unit tests in `tests/test_rag_cache.py` pass (`pytest tests/test_rag_cache.py -v`)
- [ ] Task 3 decision documented and either implemented or deferred with a comment

---

## 6. Absolute Constraints (carry over from SESSION_BOOTSTRAP.md)

1. Do not modify `test_phase1_e2e.py`.
2. Do not add mocks inside production code — all mocking in `conftest.py` and test files.
3. Do not call real GCP endpoints from unit tests.
4. Safety recall must remain 1.0 — no change to `detect_safety_keywords()` or the
   safety prompt injection path.
