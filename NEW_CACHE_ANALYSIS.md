# RAG Prefetch Cache Analysis

## Overview

This document traces the complete data flow for `transcript_text` from the frontend through
`prefetch_rag_context` in `backend/therapy-analysis-function/main.py`, explains why the
cache hit rate is effectively zero in normal conversation, and evaluates whether the commonly
suggested fix — "hash the last-200-word query window; extend TTL to 90 seconds" — resolves
the root cause.

---

## End-to-End Data Flow

### 1. Frontend: trigger and window construction

**File:** `frontend/components/NewTherSession.tsx:855-884` (NewSession.tsx mirrors this at `:384-439`)

Every new final (non-interim) transcript entry increments a word accumulator. At **8 words**
(NewTherSession) / **10 words** (NewSession), the trigger fires and builds a sliding window:

```ts
const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
const recentTranscript = transcript
  .filter(t => !t.is_interim && new Date(t.timestamp) > fiveMinutesAgo)
  .map(t => ({ speaker: t.speaker || 'conversation', text: t.text, timestamp: t.timestamp }));
```

This is a **sliding 5-minute window** — always the most recent 5 minutes of finalized utterances.
Both the realtime and comprehensive calls for the same trigger cycle receive the identical window.

A separate time-based fallback (`NewTherSession.tsx:887`) fires after 20 seconds of inactivity if
the word threshold hasn't been reached.

### 2. Hook: serializes to HTTP payload

**File:** `frontend/hooks/useTherapyAnalysis.ts:82-90`

```ts
const requestPayload = {
  action: 'analyze_segment',
  transcript_segment: transcriptSegment,   // the 5-min window array
  is_realtime: is_realtime || false,
  previous_alert: previousAlert || null,
  job_id: jobId || null,
};
```

The hook sends one POST per analysis type (realtime Flash + comprehensive Pro) with the same
`transcript_segment` for both.

### 3. Backend entrypoint: string conversion

**File:** `backend/therapy-analysis-function/main.py:873-874`

```python
transcript_text = format_transcript_segment(transcript_segment)
```

`format_transcript_segment` joins each `{speaker, text, timestamp}` entry into lines:

```
[2025-01-01T00:03:15] Client: I've been feeling really anxious lately
[2025-01-01T00:03:28] Therapist: What kind of anxiety are you experiencing?
```

The resulting string grows monotonically: new utterances are always appended at the tail.

### 4. Route split: only realtime calls `prefetch_rag_context`

**File:** `main.py:898-924`

```python
if is_realtime:
    return handle_realtime_analysis_with_retry(
        transcript_segment, transcript_text, ..., session_context=session_context
    )
else:
    # COMPREHENSIVE: embeds transcript_text directly in prompt + uses inline RAG tools
    analysis_prompt = constants.COMPREHENSIVE_ANALYSIS_PROMPT.format(..., transcript_text=transcript_text)
    return handle_comprehensive_analysis(analysis_prompt, rag_tools=rag_tools, ...)
```

`prefetch_rag_context` is **only called on the realtime path.** The comprehensive path embeds
`transcript_text` directly into the Gemini prompt and relies on Vertex AI Search inline tools
attached to `GenerateContentConfig.tools`.

### 5. `prefetch_rag_context`: the cache logic

**File:** `main.py:562-628`

```python
session_type = (session_context or {}).get("session_type", "CBT")
transcript_hash = str(hash(transcript_text[-500:] if len(transcript_text) > 500 else transcript_text))

with _rag_cache_lock:
    cached = _rag_cache.get(session_type)
    if cached:
        age = time.time() - cached["timestamp"]
        if age < RAG_CACHE_TTL_SECONDS and cached["transcript_hash"] == transcript_hash:
            return cached["passages"]   # HIT
```

**Cache key:** `session_type` (a single string, e.g. `"CBT"`).

**Hit conditions — both must be simultaneously true:**

| Condition | Value |
|---|---|
| `age < RAG_CACHE_TTL_SECONDS` | age < 25 seconds |
| `cached["transcript_hash"] == transcript_hash` | `hash(transcript_text[-500:])` must match |

On a miss, the function queries 4 Discovery Engine datastores in parallel threads, formats the
retrieved passages into a context string, stores it in `_rag_cache[session_type]`, and returns it.
The context is injected into the realtime Flash prompt as a `CLINICAL EVIDENCE` section.

---

## Why Cache Hits Are Effectively Zero in Normal Conversation

The two hit conditions are structurally opposed.

### Condition 1 (age < 25s) is easily satisfied

At normal conversational pace (~130 words/minute), 8 new words arrive every ~3.7 seconds.
Each trigger cycle sends a new realtime request to the backend. Multiple requests land within
any 25-second window — typically 5-7 per 25-second span.

### Condition 2 (hash match) is defeated by every trigger

The hash is computed over `transcript_text[-500:]` — the last 500 characters of the formatted
transcript string.

At ~5.5 characters per word plus formatting (speaker label, timestamp, newline ≈ 35 chars of
overhead per utterance), 8 new words contribute roughly **79-85 characters** of new content at
the tail of `transcript_text`. This is well within the 500-character slice.

**Every trigger adds new content within the hashed window. The hash changes on every single
trigger cycle regardless of TTL.**

The result: condition 2 fails on every call during active speech. The 25-second TTL is never
leveraged. Every realtime analysis call fires a fresh 4-datastore Discovery Engine query (~200-500ms),
defeating the stated purpose of the cache.

### The only scenarios where hits can occur

| Scenario | Mechanism |
|---|---|
| Speech pause long enough for two triggers to fire with no new transcript entries between them | Transcript tail is frozen; hash repeats |
| Time-based fallback (20s) fires, then word threshold fires before any new speech | Both calls see the same tail |
| Frontend re-render triggers `useEffect` without a new transcript entry (React reconciliation) | `transcript` reference changes but entries are unchanged |
| Test / demo mode replaying the same audio segment | Deliberate content repetition |

None of these represent normal clinical conversation.

---

## The Gemini Context Cache Is Also Disabled for Comprehensive Analysis

There is a separate `_get_or_refresh_cached_content()` mechanism
(`main.py:287-323`) that caches the static system prompt portion of
`COMPREHENSIVE_ANALYSIS_PROMPT` as a Gemini context cache object with a 30-minute TTL.
However:

```python
# main.py:1375
cached_content_name = None if rag_tools else _get_or_refresh_cached_content()
```

The Gemini API cannot combine `cached_content` with `tools` in the same request. Since
comprehensive analysis always supplies modality-specific Vertex AI Search tools, `rag_tools`
is never empty, and `cached_content_name` is always `None`. The Gemini context cache is
structurally disabled for every real session going through `handle_comprehensive_analysis`.

---

## Evaluation: Does "Hash the Last-200-Word Query Window; Extend TTL to 90s" Fix the Problem?

This is one of the most frequently generated suggestions for this codebase. The short answer
is **no** — it adjusts two parameters without addressing the structural root cause.

### What the fix changes

**Current code:**
```python
transcript_hash = str(hash(transcript_text[-500:] if len(transcript_text) > 500 else transcript_text))
RAG_CACHE_TTL_SECONDS = 25
```

**Proposed fix:**
```python
words = transcript_text.split()
query_text = " ".join(words[-200:]) if len(words) > 200 else transcript_text
transcript_hash = str(hash(query_text))
RAG_CACHE_TTL_SECONDS = 90
```

This aligns the hash input with the query text already sent to Discovery Engine, and extends
the TTL from 25 to 90 seconds.

### Why it does not resolve cache misses

The core problem is that **the hash input changes on every trigger cycle** because new words are
always appended at the tail of `transcript_text`, and both the current 500-char slice and the
proposed 200-word window capture that tail.

Concretely:

- Trigger fires every 8 words (~3.7s at 130 wpm).
- The 200-word query window shifts by 8 words each cycle: the 8 oldest words drop off the
  leading edge, 8 new words are added at the trailing edge.
- `hash(query_text)` changes with every shift, because the trailing 8 words are different.
- Hit condition 2 still fails on every trigger during active speech.

**Extending the TTL to 90 seconds does not help** because TTL is gated behind the hash check.
`age < 90s AND hash_match` is no more satisfiable than `age < 25s AND hash_match` when
`hash_match` is always false.

### There is a secondary problem: stale passages would degrade guidance quality

Even if the hash check were removed entirely and only the 90-second TTL were used, a cache
stored 89 seconds ago captured RAG passages retrieved against a query built from conversation
that is now ~195 words stale (130 wpm × 1.5 min). The clinical evidence injected into the
realtime Flash prompt would be grounded in a different therapeutic moment. For a tool used
to provide in-the-moment guidance, this degrades quality in exchange for latency savings.

### Summary of the proposed fix's impact

| Dimension | Current | With "fix" | Root cause addressed? |
|---|---|---|---|
| Hash input window | last 500 chars | last 200 words | No — both include the ever-changing tail |
| Hash churn per trigger | Every cycle | Every cycle | Unchanged |
| Cache hit rate (active speech) | ~0% | ~0% | Unchanged |
| TTL | 25s | 90s | Irrelevant — TTL never reached in hash-gated check |
| Passage freshness on a hit | N/A | N/A (hits still don't occur) | N/A |

---

## What Would Actually Resolve the Issue

### Option A: Remove the hash check; rely on TTL alone

```python
# Drop the transcript_hash comparison entirely
if cached and (time.time() - cached["timestamp"]) < RAG_CACHE_TTL_SECONDS:
    return cached["passages"]
```

This produces genuine cache hits during bursts of rapid triggers. The tradeoff is that cached
passages may be 25 seconds stale at most — acceptable for the relatively slow evolution of
therapy topic focus. This is the lowest-effort change with real impact.

### Option B: Hash only the stable prefix of the window

New words land at the tail; the bulk of the 5-minute window (everything more than ~10 seconds
old) is stable across adjacent triggers. Hashing only entries older than a stability threshold
removes churn:

```python
stable_cutoff = time.time() - 10  # entries more than 10s old
stable_entries = [e for e in transcript_segment if _entry_age(e) > 10]
stable_text = format_transcript_segment(stable_entries)
transcript_hash = str(hash(stable_text[-500:]))
```

This preserves topic-sensitivity while allowing the TTL to function as intended.

### Option C: Background prefetch on a fixed timer, decoupled from triggers

Run `prefetch_rag_context` on a separate thread every N seconds regardless of whether a
trigger has fired. Store the result. Realtime handlers consume the pre-warmed result without
any cache-invalidation logic. Latency savings are guaranteed because the prefetch runs ahead
of the next trigger.

### Option D: Accept the miss cost; remove the cache entirely

If the prefetch completes in 200-500ms in parallel with the Gemini Flash call (~800ms-1.5s),
and the total realtime budget is 2-4 seconds, the prefetch does not add to end-to-end latency
anyway since both operations overlap. The cache infrastructure can be removed without
regressing the UX, simplifying the code.

---

## Files Referenced

| File | Relevant Lines |
|---|---|
| `frontend/components/NewTherSession.tsx` | 855-884 (word trigger), 887-915 (time fallback) |
| `frontend/components/NewSession.tsx` | 384-439 (word trigger) |
| `frontend/hooks/useTherapyAnalysis.ts` | 48-142 (`analyzeSegment`) |
| `backend/therapy-analysis-function/main.py` | 494-628 (cache infrastructure + `prefetch_rag_context`) |
| `backend/therapy-analysis-function/main.py` | 853-928 (`handle_segment_analysis`, route split) |
| `backend/therapy-analysis-function/main.py` | 1018-1028 (realtime path calls `prefetch_rag_context`) |
| `backend/therapy-analysis-function/main.py` | 1344-1545 (`handle_comprehensive_analysis`, Gemini context cache disabled) |
