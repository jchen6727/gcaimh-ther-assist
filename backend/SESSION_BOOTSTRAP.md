# Session Bootstrap — Backend Unit Testing & LLM Eval

**Project:** gcaimh — AI-assisted therapy session supervision platform  
**Working directory:** `/Users/jchen/dev/gcaimh`  
**Date of prior session:** 2026-06-06  
**Your first task:** Read `backend/UNIT_TESTING_SPEC.md` in full, then address the `#TODO` items in the priority order defined in Section 3 of this document.

---

## 1. What Was Done in the Prior Session

A static code analysis of all three backend services was completed and a unit testing specification was written to `backend/UNIT_TESTING_SPEC.md`. That document is the authoritative reference for this session. Do not reanalyze the source code unless a specific function is ambiguous — the spec already contains the correct I/O shapes, test cases, and mock patterns.

**No tests were written yet.** No eval harness exists yet. No instrumentation was added to `main.py`. This session starts from zero implementation.

---

## 2. Repository Structure

```
gcaimh/
└── backend/
    ├── UNIT_TESTING_SPEC.md          ← your primary reference (read this first)
    ├── SESSION_BOOTSTRAP.md          ← this file
    │
    ├── streaming-transcription-service/
    │   ├── main.py                   ← FastAPI WebSocket + Google STT v2
    │   └── prompts.py                ← SAFETY_KEYWORDS dict used by scan_safety_keywords()
    │
    ├── therapy-analysis-function/
    │   ├── main.py                   ← Flask Cloud Function; all analysis logic lives here
    │   ├── constants.py              ← prompts, SAFETY_KEYWORDS, SAFETY_CLINICAL_RESPONSES,
    │   │                               TRIGGER_PHRASES, MODEL_NAME, THERAPY_PHASES
    │   └── test_phase1_e2e.py        ← existing integration test (hits real GCP; do not modify)
    │
    └── storage-access-function/
        ├── main.py                   ← Flask Cloud Function; GCS proxy + portal router
        └── portal/
            ├── auth.py               ← Firebase token verification, require_role decorator
            ├── helpers.py            ← document translation functions (pure, high-value tests)
            ├── models.py             ← Pydantic request body models
            ├── router.py             ← URL dispatch table for /portal/* routes
            └── handlers/             ← one file per resource type
                ├── clients.py
                ├── homework.py
                ├── interventions.py
                ├── me.py
                ├── publish.py
                ├── activity.py
                ├── catalog.py
                ├── questionnaires.py
                ├── sessions.py
                └── journal.py
```

---

## 3. #TODO Priority Order

The spec contains `<!-- #TODO ... -->` HTML comments at every point requiring implementation. Address them in this order:

### Tier 1 — Unit Tests (implement before anything else)

These require zero changes to production code and can be done immediately.

| Priority | File to create | Spec section | Key function under test |
|----------|---------------|--------------|------------------------|
| **1** | `tests/service2/test_safety_keywords.py` | §3.3 Priority 1 | `detect_safety_keywords()` in `therapy-analysis-function/main.py` |
| **2** | `tests/service1/test_safety.py` | §3.2 Priority 1 | `scan_safety_keywords()` in `streaming-transcription-service/main.py` |
| **3** | `tests/service2/test_json_extraction.py` | §3.3 Priority 2 | `extract_json_from_text()` in `therapy-analysis-function/main.py` |
| **4** | `tests/service2/test_pure_functions.py` | §3.3 Priority 3–7 | `determine_therapy_phase`, `format_transcript_segment`, `check_for_trigger_phrases`, `summarize_session_history`, `build_diagnostics` |
| **5** | `tests/service2/test_handlers_pure.py` | §3.3 Priority 8–9 | `handle_get_patient_summary`, `_write_publish_draft_from_summary` |
| **6** | `tests/service3/test_doc_translations.py` | §3.4 Priority 1–3, 5 | `response_doc_to_outcome_response`, `session_doc_to_therapy_session*`, `patient_doc_to_bridge_client`, `questionnaire_def_doc_to_*` |
| **7** | `tests/service3/test_auth.py` | §3.4 Priority 4 | `_decode_dev_token()` in `storage-access-function/portal/auth.py` |
| **8** | `tests/service1/test_auth.py` | §3.2 Priority 2 | `is_email_authorized()` in `streaming-transcription-service/main.py` |

**Use pytest.** Each test file should have a corresponding `conftest.py` with shared fixtures (Firestore doc mocks, Gemini chunk mocks). The mock patterns are in spec §3.5.

**Safety tests are non-negotiable.** Tests 1 and 2 above must cover every keyword in every category of `SAFETY_KEYWORDS` (both services maintain their own copies with slight differences — test both independently). A failure in safety detection is a clinical failure.

---

### Tier 2 — Production Instrumentation (implement after Tier 1 tests pass)

These require changes to `therapy-analysis-function/main.py`. Implement in this order:

#### Step 1: Prompt efficiency fields in `_diagnostics` (§4.2.3)

**Where:** Inside `try_analysis_with_prompt()` and `handle_comprehensive_analysis()` in `main.py`, before the `client.models.generate_content_stream()` call.

**What to add to the diagnostics dict passed to `build_diagnostics()`:**
```python
prompt_efficiency = {
    "prompt_char_count": len(analysis_prompt),
    "transcript_char_count": len(transcript_text),
    "rag_context_char_count": len(_rag_context) if _rag_context else 0,
    "system_prompt_char_count": len(analysis_prompt) - len(transcript_text) - (len(_rag_context) if _rag_context else 0),
    "output_char_count": len(accumulated_text),
    "compression_ratio": round(len(accumulated_text) / max(len(analysis_prompt), 1), 4),
}
```
Add `prompt_efficiency` as a new parameter to `build_diagnostics()` and include it in the returned dict.

#### Step 2: Runtime aggregate counters (§4.2.4)

**Where:** Module level in `therapy-analysis-function/main.py`, just below the RAG tool definitions.

```python
import threading as _threading
_METRICS_LOCK = _threading.Lock()
RUNTIME_METRICS = {
    "total_requests": 0,
    "fallback_used": 0,
    "json_parse_failures": 0,
    "safety_scanner_triggered": 0,
    "empty_responses": 0,
}

def _inc(key: str):
    with _METRICS_LOCK:
        RUNTIME_METRICS[key] = RUNTIME_METRICS.get(key, 0) + 1
```

Increment with `_inc("fallback_used")` etc. at the relevant points in `generate()` inside `handle_realtime_analysis_with_retry()`. Expose in the existing `handle_health_check()` return value under `"runtime_metrics": RUNTIME_METRICS`.

#### Step 3: RAG latency and prefetch metadata in `_diagnostics` (§4.2.1)

**Where:** `prefetch_rag_context()` — return a tuple `(formatted_context, prefetch_meta)` where:
```python
prefetch_meta = {
    "rag_latency_ms": round(prefetch_elapsed),
    "rag_query_words": len(query_text.split()),
    "passages_by_store": {ds_id: len(v) for ds_id, v in results_by_store.items()},
    "prefetch_used": True,
    "prefetch_age_seconds": age if cache_hit else 0,
    "cache_hit": cache_hit,
}
```
Thread this metadata into `build_diagnostics()` under `grounding.prefetch` so it appears in `_diagnostics`.

---

### Tier 3 — Evaluation Harness (implement after Tier 2 instrumentation)

**Where:** Create `backend/therapy-analysis-function/tests/eval/` directory.

#### Files to create

1. **`eval/run_eval.py`** — the skeleton is fully specced in §4.3. Implement it. It calls the local `functions-framework` server, not the real GCP endpoint.

2. **`eval/score_eval.py`** — implement the metric table from §4.3. The `rag_relevance_score()` function skeleton is in §4.2.1. Include the baseline comparison diff output described in §4.4.

3. **`eval/scenarios/`** — 9 scenario JSON files per the list in §4.3. Each follows this schema:
```json
{
  "scenario_id": "suicidal_ideation_passive_001",
  "transcript_segment": [
    {"speaker": "Patient", "text": "..."}
  ],
  "session_context": {"session_type": "CBT", "current_approach": "Cognitive Behavioral Therapy"},
  "duration_minutes": 20,
  "expected": {
    "alert_required": true,
    "category": "safety",
    "timing": "now",
    "safety_scan_triggered": true,
    "risk_level": "high"
  }
}
```

   **The 9 required scenarios:**
   - `suicidal_ideation_passive_001.json` — passive SI, no explicit plan
   - `suicidal_ideation_active_001.json` — active SI with stated means
   - `self_harm_disclosure_001.json` — recent cutting disclosure
   - `violence_threat_001.json` — Tarasoff-relevant statement
   - `abuse_disclosure_001.json` — child abuse mandatory reporting
   - `substance_crisis_001.json` — active intoxication/overdose risk
   - `no_alert_smalltalk_001.json` — routine opening conversation, no alert expected
   - `technique_cbt_restructuring_001.json` — CBT thought record moment, technique alert expected
   - `pathway_change_needed_001.json` — patient resisting CBT, pathway_change alert expected

   > **Clinical review required:** Scenarios 1–6 involve safety-critical clinical content. Before using these as regression gates, their expected outputs should be reviewed by a licensed mental health professional. Flag this when presenting the harness for review.

4. **`eval/baselines/`** — empty dir with `.gitkeep`. First baseline is saved after the initial `run_eval.py` run succeeds.

---

## 4. Key Technical Facts to Know

### Two separate `SAFETY_KEYWORDS` dicts exist — they are NOT identical

- `streaming-transcription-service/prompts.py` — used by `scan_safety_keywords()` (STT service)
- `therapy-analysis-function/constants.py` — used by `detect_safety_keywords()` (analysis function)

The STT version is slightly different (e.g., it includes `"jump off"`, `"hang myself"`, `"slit my wrists"` that the analysis version omits). Unit tests for both must import from their own service's module — do not share keyword fixtures between the two test files.

### The `_diagnostics` object is the instrumentation spine

Every LLM response from Service 2 already returns `_diagnostics`. The Tier 2 instrumentation work adds fields to this existing object — it does not introduce a new logging system. The frontend already displays `_diagnostics` in its activity log panel.

### `extract_json_from_text()` has a truncated-JSON repair path (Strategy 3)

This path is triggered when the LLM output is cut off by `max_output_tokens`. The repair logic closes unclosed braces/brackets. This is important context for why the function must be tested under truncation — hitting the token limit on comprehensive analysis is a real production failure mode.

### Both cache systems are broken — see `cache.md` for the fix session

A full investigation (2026-06-06) found that neither caching mechanism delivers value
in production. Details and recommended fixes are in `CACHE_ANALYSIS_REPORT.md`. The
dedicated implementation session is bootstrapped in `cache.md`.

**Gemini context cache (comprehensive path):** Permanently disabled. Line 1375:
`cached_content_name = None if rag_tools else _get_or_refresh_cached_content()`.
Because `rag_tools` is always non-empty, `context_cache_hit` is always `False` and
the intended ~75% Pro model input token savings are never realized.

**RAG prefetch cache (realtime path):** ~0% hit rate. The cache key hashes the last
500 characters of the transcript (≈ 36 seconds of speech at 130–150 wpm). Each
analysis call is triggered by a new completed utterance, which always shifts the
500-char window — the hash changes on every call. The 25-second TTL also fails
independently: typical inter-call intervals (20–90 s per utterance) exceed the TTL.
The stated "2–4 s" realtime latency assumes cache hits; actual latency is 3–11 s
because `prefetch_rag_context()` blocks synchronously on every miss.

**Implication for Tier 2 Step 3:** Still implement RAG latency instrumentation as
specified — it documents the miss rate and makes cache behavior observable. But expect
`cache_hit: false` on every response until the fixes in `cache.md` are applied.

### The `PublishDraft` → portal chain is the highest-risk integration

`session_summary` action → `_write_publish_draft_from_summary()` → Firestore `/patients/{id}/publishDrafts/{id}` → `storage-access-function` portal reads it → served to patient at `/portal/me/sessions`. PHI fields (`risk_assessment`, `key_moments`, `manual_reference`) must be stripped before reaching the patient. This redaction is tested in `test_handlers_pure.py` (§3.3 Priority 8) and `test_doc_translations.py` (§3.4 Priority 2).

### Dev auth bypass pattern

All portal endpoints support `PORTAL_DEV_AUTH_BYPASS=true` in the env, which accepts tokens of the form `dev-therapist-<email>` and `dev-patient-<email>`. This is how local development and testing works without Firebase. The `_decode_dev_token()` function is the pure parser for this format (§3.4 Priority 4).

### Existing e2e test

`backend/therapy-analysis-function/test_phase1_e2e.py` is a 936-line integration test that calls real GCP endpoints. Do not modify it. The new test suite lives in `backend/*/tests/` directories alongside (not replacing) the e2e test.

---

## 5. Test File Directory Layout to Create

```
backend/
├── streaming-transcription-service/
│   └── tests/
│       ├── conftest.py              ← shared fixtures (mock Firebase, mock STT client)
│       ├── test_safety.py           ← scan_safety_keywords() [Tier 1, Priority 2]
│       └── test_auth.py             ← is_email_authorized() [Tier 1, Priority 8]
│
├── therapy-analysis-function/
│   └── tests/
│       ├── conftest.py              ← shared fixtures (mock Gemini client, mock Firestore)
│       ├── test_safety_keywords.py  ← detect_safety_keywords() [Tier 1, Priority 1]
│       ├── test_json_extraction.py  ← extract_json_from_text() [Tier 1, Priority 3]
│       ├── test_pure_functions.py   ← phase/format/trigger/history/diagnostics [Tier 1, Priority 4]
│       ├── test_handlers_pure.py    ← get_patient_summary, _write_publish_draft [Tier 1, Priority 5]
│       └── eval/
│           ├── run_eval.py          ← [Tier 3]
│           ├── score_eval.py        ← [Tier 3]
│           ├── scenarios/           ← 9 JSON files [Tier 3]
│           └── baselines/           ← .gitkeep [Tier 3]
│
└── storage-access-function/
    └── tests/
        ├── conftest.py              ← shared fixtures (mock Firestore, Flask test client)
        ├── test_doc_translations.py ← response_doc_to_*, session_doc_to_*, etc. [Tier 1, Priority 6]
        └── test_auth.py             ← _decode_dev_token() [Tier 1, Priority 7]
```

---

## 6. How to Run Tests (once created)

Each service has its own `requirements.txt`. Install test deps separately per service:

```bash
# Service 2 (most tests live here)
cd backend/therapy-analysis-function
pip install -r requirements.txt pytest pytest-mock

# Run all unit tests (no GCP calls)
pytest tests/ -v --ignore=tests/eval

# Run eval harness (requires local functions-framework server running)
functions-framework --target therapy_analysis --port 8081 &
python tests/eval/run_eval.py --output tests/eval/runs/$(date +%Y%m%d).json
python tests/eval/score_eval.py \
  --baseline tests/eval/baselines/baseline_YYYYMMDD.json \
  --candidate tests/eval/runs/YYYYMMDD.json
```

---

## 7. Absolute Constraints

1. **Safety recall must remain 1.0.** The eval harness must gate on this. No prompt change that reduces safety recall is acceptable regardless of latency or cost savings.
2. **Do not modify `test_phase1_e2e.py`.** It is the existing integration suite and is out of scope.
3. **Do not add mocks inside production code.** All mocking is in `conftest.py` and test files only.
4. **Do not write tests that hit real GCP endpoints.** If a test requires a real network call, it belongs in the e2e suite, not the unit test suite.
5. **Each test file must be independently runnable** with `pytest path/to/test_file.py`.
