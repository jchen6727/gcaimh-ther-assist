# Cache Effectiveness Analysis — `therapy-analysis-function`

**Date:** 2026-06-06  
**Scope:** `backend/therapy-analysis-function/main.py` — two distinct caching systems  
**Status:** Investigation complete; no code changes made yet  

---

## Executive Summary

Two caching mechanisms exist in `therapy-analysis-function/main.py`. Neither delivers
value in production under normal operating conditions. One is permanently disabled by a
code-level API conflict. The other has an expected hit rate of ~0% due to a mismatch
between the cache key design and the data flow of a live therapy conversation at
conversational speaking speed (130–150 wpm). Both issues are fixable but require
different interventions, analyzed below.

---

## System 1 — Gemini Context Cache (Comprehensive Path Only)

**Purpose:** Upload the static portion of `COMPREHENSIVE_ANALYSIS_PROMPT` once to the
Gemini API as a `CachedContent` resource. Subsequent requests reference it by name,
paying reduced cached-token rates and skipping re-tokenization server-side. Stated
savings: ~75% reduction in Pro model input token costs.

**Code:** `_get_or_refresh_cached_content()` (lines 287–323); consumed at line 1375.

**Status: Permanently disabled. No cached tokens are ever billed at the discount rate.**

The disabling line:

```python
# main.py:1375
cached_content_name = None if rag_tools else _get_or_refresh_cached_content()
```

`handle_comprehensive_analysis()` always receives a non-empty `rag_tools` list (from
`get_rag_tools_for_session()`). The Gemini API prohibits `tools` and `cached_content`
in the same request config. Therefore `cached_content_name` is always `None`,
`using_cache` is always `False`, and `_diagnostics.context_cache_hit` is always
`False`. The 30-minute TTL refresh logic and the `_cached_content_resource` global run
correctly but are never consulted.

**Cost impact:** The comprehensive path (Gemini 2.5 Pro, `thinking_budget=8192–16384`)
is the most expensive path per request. Context caching was designed to cut ~75% of
input token costs on that path. It is providing zero savings.

---

## System 2 — RAG Prefetch Cache (Realtime Path Only)

**Purpose:** Cache Discovery Engine passages as pre-formatted text so the realtime
(Flash) path can inject clinical evidence directly into the prompt rather than using
inline tool calls during generation. Stated latency benefit: 2–4s vs. 8–12s with
inline tools.

**Code:** `_rag_cache` dict + `prefetch_rag_context()` (lines 500–628); called
synchronously at line 1028.

**Status: ~0% cache hit rate in production. Every call is a cold query.**

### Cache hit condition

```python
# main.py:575
age < RAG_CACHE_TTL_SECONDS          # 25 seconds since last call
AND cached["transcript_hash"] == transcript_hash
```

Where the hash is computed as:

```python
# main.py:569
transcript_hash = str(hash(transcript_text[-500:]))
```

### Why both conditions fail in a live conversation

**Condition A — TTL (25 s):**

Each `analyze_segment` request is triggered by a completed STT utterance (one call per
speaker turn). At 130–150 wpm, typical therapeutic utterances run 20–90 seconds
depending on speaker and content. The inter-call interval exceeds the 25 s TTL for
most turns independently of the hash check.

**Condition B — transcript hash:**

At 140 wpm × ~6 chars/word ≈ 840 chars/min ≈ 14 chars/second, the last 500 characters
of the transcript represents approximately **36 seconds of speech**.

Every analysis call is triggered because a new utterance just completed and was
appended to the transcript. Even the shortest turn — `"[00:45] Therapist: I see."` —
adds ~28 characters, shifting the 500-char window and producing a different hash. A
patient statement of 30–60 words adds 200–360 characters.

**The hash condition cannot be satisfied in a flowing conversation.** For the last 500
characters to be identical between two successive calls, no new speech could have
occurred — which is exactly the precondition that prevents a new analysis call from
being triggered.

### Secondary observation — cache key and query window are internally inconsistent

The actual Discovery Engine query uses a wider window:

```python
# main.py:586–587
words = transcript_text.split()
query_text = " ".join(words[-200:]) if len(words) > 200 else transcript_text
```

The hash is computed over `transcript_text[-500:]` while the query uses the last 200
words. These are different windows, which is internally inconsistent. However, **fixing
this inconsistency by aligning the hash to the 200-word window does not resolve cache
misses.** The 200-word window also includes the tail of the growing transcript string.
Every trigger appends new words at the tail; those new words fall inside any window
computed over the end of the string, regardless of how wide it is. The hash changes on
every trigger whether the window is 500 chars or 200 words.

This is a cosmetic inconsistency. It is not the root cause of the ~0% hit rate.

### Actual realtime latency

`prefetch_rag_context()` is called **synchronously** at the top of
`handle_realtime_analysis_with_retry()` and blocks via `t.join(timeout=10)` on all
datastore threads. On every cache miss (which is every call):

```
realtime latency = RAG parallel fetch (2–8 s) + Flash generation (1–3 s) = 3–11 s
```

The stated "2–4 s" is only achievable on cache hits, which do not occur. The genuine
architectural win is the parallel fetch (4 datastores concurrently) vs. sequential
inline tool calls on the comprehensive path — this is real and worth keeping. The cache
layer itself adds code complexity with no production benefit.

---

## Options

### Option 1 — Remove the transcript hash from the cache key (15 min, low risk)

⚠️ **Correction from prior analysis:** An earlier version of this document proposed
aligning the hash with the 200-word query window. That fix does not work. Any hash
computed over the tail of a growing transcript string changes on every trigger because
new speech always appends at the tail — whether the window is 500 chars or 200 words.
The correct fix is to remove the hash check entirely.

Remove the `transcript_hash` computation and comparison from `prefetch_rag_context()`.
Let the TTL alone control invalidation:

```python
# main.py:569 — remove this line entirely:
transcript_hash = str(hash(transcript_text[-500:] if len(transcript_text) > 500 else transcript_text))

# main.py:575 — change the hit condition from:
if age < RAG_CACHE_TTL_SECONDS and cached["transcript_hash"] == transcript_hash:
# to:
if age < RAG_CACHE_TTL_SECONDS:
```

Also remove `"transcript_hash": transcript_hash` from the cache write at line 622.

The cache is then keyed solely by `session_type` with a TTL. The EBT corpus is static
clinical documents; passages retrieved 25 seconds ago remain clinically valid. This
is the minimal change that produces real cache hits.

---

### Option 2 — Increase TTL to match conversational cadence (5 min, low risk)

Raise `RAG_CACHE_TTL_SECONDS` from 25 to 90. EBT corpus content is static; 90-second-old
passages are clinically equivalent to fresh ones for realtime guidance purposes.

```python
# main.py:503
RAG_CACHE_TTL_SECONDS = 90   # was 25
```

Combined with Option 1, this is the **minimal viable fix** that produces measurable
cache hits on sustained conversations without topic shifts.

**Clinical risk:** A patient shifting topics abruptly within the TTL window receives
RAG passages for the preceding topic. Acceptable because: (a) the deterministic safety
scanner (`detect_safety_keywords()`) runs independently and is never RAG-gated; (b)
the safety RAG corpus is always included regardless of modality.

---

### Option 3 — True background prefetch (1–2 days, architectural change)

Trigger the Discovery Engine query when STT partial results arrive, before the analysis
request is sent. By the time `analyze_segment` is called, the RAG result is already
cached. Approaches:

- **A:** Add a `/prefetch` endpoint to the analysis function; have the STT service call
  it on each partial transcript event (non-blocking fire-and-forget).
- **B:** Move the prefetch into the STT service itself, caching results keyed by
  session_id and writing them to a shared cache (Redis, Memorystore, or a Firestore
  doc the analysis function reads).

**Impact:** Near-zero RAG overhead on all realtime calls regardless of TTL or hash.  
**Effort:** Cross-service coordination required.

---

### Option 4 — Remove cache, keep parallel fetch (30 min, simplification)

The lock, TTL, and hash logic add maintenance burden with zero measured benefit. The
parallel fetch itself is the valid optimization. Removing the cache makes the latency
profile honest: always 3–8 s per realtime call, no false "2–4 s" claim.

This is the right choice if Options 1+2 are not pursued and no background prefetch is
planned.

---

### Option 5 — Fix the Gemini context cache for the comprehensive path (2–4 h)

Pre-fetch RAG passages as text (identical to the realtime approach) and inject them
into the comprehensive prompt, removing the `rag_tools` parameter from the API call.
This unblocks `_get_or_refresh_cached_content()`.

**Impact:** ~75% reduction in Pro model input token costs for the comprehensive path.
Highest ROI if comprehensive analysis is called frequently.

**Tradeoff:** Inline tool calls on the comprehensive path currently populate
`grounding_metadata` → citations. Switching to text injection loses this. Citations on
the comprehensive path would need to be handled separately (e.g., appended as a
structured field from the prefetch metadata, or dropped and acknowledged in the UI).

---

## Recommended Priority

| # | Action | Effort | Expected impact |
|---|--------|--------|-----------------|
| 1 | Options 1 + 2: remove transcript hash from cache key + raise TTL to 90 s | 15 min | Produces real hits on sustained conversations |
| 2 | Instrument `_diagnostics.grounding` with `cache_hit`, `prefetch_age_seconds`, `rag_latency_ms` (Tier 2 Step 3) | 1 h | Makes cache behavior observable in the eval harness |
| 3 | Option 5: fix Gemini context cache (inject RAG as text, drop inline tools on comprehensive path) | 2–4 h | Highest cost savings; eliminates Pro model input token waste |
| 4 | Option 3: true background prefetch | 1–2 days | Best realtime latency ceiling |

Items 1 and 2 can be done in a single session with minimal risk. Item 3 is a larger
change with a citation tradeoff that warrants a design decision before implementation.
Item 4 requires architectural coordination.

---

## Files Requiring Changes

| File | Line | Change |
|------|------|--------|
| `therapy-analysis-function/main.py` | 503 | `RAG_CACHE_TTL_SECONDS = 90` |
| `therapy-analysis-function/main.py` | 569, 575, 622 | Remove `transcript_hash`; change hit condition to TTL-only; remove hash from cache write |
| `therapy-analysis-function/main.py` | 562–628 | Return `(context, prefetch_meta)` tuple; thread metadata into `build_diagnostics()` (Tier 2 Step 3) |
| `therapy-analysis-function/main.py` | 1375 | Unblock context cache by removing inline tools on comprehensive path (Option 5 — requires design decision) |

---

## Related Documents

- `backend/SESSION_BOOTSTRAP.md` — unit testing + instrumentation session (Tier 2 Step 3 is the instrumentation task)
- `backend/UNIT_TESTING_SPEC.md` — §4.2.1 (RAG instrumentation), §4.4 step 7 (context cache decision tree)
- `backend/cache.md` — dedicated session bootstrap for implementing the cache fixes
