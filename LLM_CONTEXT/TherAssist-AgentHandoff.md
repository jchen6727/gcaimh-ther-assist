# Ther-Assist — Agent Handoff Brief
## For: Next Code Audit Agent (Blank Slate)
**Prepared by:** Prior audit session (Claude Sonnet 4.6, June 5, 2026)  
**Repository:** `https://github.com/mohsinsub7/gcaimh-ther-assist` (public — clone directly)  
**Full prior report:** `TherAssist-CodeReview-Report.md` (provided separately — read before starting)

---

## 1. What You Are Inheriting

A prior agent completed a full architectural review of this repository and produced a 7-section report (`TherAssist-CodeReview-Report.md`). That report covers:

- Section 1: Executive summary and three pilot-blocking findings
- Section 2: Component-by-component findings (Tier 1–4 files)
- Section 3: Gap analysis (blockers / safety risks / cost-expanders)
- Section 4: Extraneous feature inventory
- Section 5: Coupling map
- Section 6: Open questions (for clinical stakeholder, dev team, project lead)
- Section 7: Prompt engineering and LLM architecture analysis

**Read that report in full before touching any code.** It represents approximately 43,000 tokens of Tier 1 file reading and 15,000 tokens of Tier 4 file reading — re-deriving it from scratch would consume most of your context window before you produce anything new.

---

## 2. Session Budget Guidance

This is important context derived from the prior session and the GitHub issue below.

**Token capacity measured in the prior session:**

| Session type | SLOC at full depth | Cyclomatic complexity budget |
|---|---|---|
| Focused single-service review | ~2,500 | ~350 |
| Benchmark (prior session quality) | ~2,300 | ~280 |
| Two-service comparative review | ~3,500 | ~490 |
| Full codebase triage (head-only) | ~5,000 | ~700 |
| Codebase + full report in one session | ~1,800 | ~250 |

**This codebase's token density:** ~18.7 tokens per SLOC for Tier 1 Python files (high because `main.py` and `constants.py` contain large embedded string literals — the LLM prompt templates). TypeScript files are ~8–10 tokens/SLOC.

**Per-file token cost reference** (from measured file sizes):

| File | SLOC | ~Tokens | Tier | Read depth needed |
|---|---|---|---|---|
| `backend/therapy-analysis-function/main.py` | 1,433 | 22,563 | 1 | Full |
| `backend/therapy-analysis-function/constants.py` | 446 | 7,833 | 1 | Full |
| `backend/streaming-transcription-service/main.py` | 636 | 9,580 | 1 | Full |
| `backend/therapy-analysis-function/test_phase1_e2e.py` | 712 | 9,972 | 1 | Full |
| `setup_services/fine_tuning/setup_fine_tuning.py` | 482 | 8,010 | 3 | Head only |
| `setup_services/agent_builder/setup_multi_session_agent.py` | 608 | 7,335 | 3 | Head only |
| `frontend/hooks/useAudioStreamingWebSocket.ts` | 472 | 5,861 | 4 | Full |
| `frontend/utils/smartMockAnalysis.ts` | 331 | 4,168 | 4 | Full |
| `backend/storage-access-function/portal/handlers/me.py` | 315 | 3,653 | 2 | Partial |
| `setup_services/comparative_study/runner.py` | 258 | 3,301 | 3 | Head only |
| `frontend/hooks/useTherapyAnalysis.ts` | 272 | 3,171 | 4 | Full |
| `frontend/utils/alertDeduplication.ts` | 202 | 2,536 | 4 | Full |

**Known quality degradation pattern from prior session:** The prior agent read Tier 1 files fully and Tier 3/4 files at head-only depth (60–80 lines). This is an intentional triage decision, not a mistake. The findings on Tier 2 and Tier 3 files are directionally correct but less diagnostic than the Tier 1 findings. If your task involves any Tier 2–3 file in depth, re-read it fully.

**Relevant external data on context-depth tradeoffs:** See GitHub issue `anthropics/claude-code#42796`, which documents a measured 70% reduction in Read:Edit ratio under reduced thinking budget, and the quality collapse pattern it produces. The implication for this session: bounded, single-purpose tasks with fresh context are more reliable than long iterative sessions with accumulated history.

---

## 3. Confirmed Findings — Do Not Re-Derive

The following findings are confirmed by direct code measurement in the prior session. Do not re-derive them from scratch; accept them as ground truth and build on them.

### 3.1 Hard Pilot Blockers

**A. Authentication is disabled.**  
`backend/therapy-analysis-function/main.py` lines 671–680: the entire Firebase token verification block is commented out with the note "REMOVE FOR PRODUCTION." Any HTTP request to the `therapy_analysis` endpoint is currently unauthenticated. This is a hard blocker before any deployment involving real patient conversations.

**B. RAG corpus integrity is unverified.**  
The clinical PDF files exist in `setup_services/rag/corpus*/` directories, but ingestion into the Vertex AI Search datastores has not been confirmed. The test suite (`test_datastores` in `test_phase1_e2e.py`) checks only that datastores return *a* response — it does not verify that retrieved passages come from the expected PDFs. If a datastore is empty, the LLM generates guidance from training data alone with no warning.

**C. Multi-modality scope unconfirmed.**  
The system routes across CBT, DBT, and IPT modalities with five distinct RAG corpora. Whether the clinical stakeholder requested this capability has never been confirmed. If single-modality is sufficient for the pilot, a significant simplification is possible before launch (estimated 2–3 days).

### 3.2 Safety Risks

**D. `mock-` token bypass active in Cloud Run.**  
`backend/streaming-transcription-service/main.py`: any WebSocket connection token beginning with `mock-` is accepted as "IAP pre-authenticated." This path remains accessible in a deployed Cloud Run environment. Remove before production.

**E. `smartMockAnalysis.ts` must not reach production.**  
`frontend/utils/smartMockAnalysis.ts` generates realistic-looking safety alerts (including "Suicidal Ideation Detected") via keyword matching, with no backend validation. If `VITE_ANALYSIS_API` is misconfigured in a live deployment, the frontend silently falls back to this mock. A clinician cannot tell they are seeing mock alerts. This file should be excluded from production builds at the build level, not just via the runtime `USE_MOCK_MODE` flag.

**F. Safety scanner not applied in pathway guidance or session summary.**  
`detect_safety_keywords` is called in `handle_segment_analysis` but not in `handle_pathway_guidance` or `handle_session_summary`. Safety keyword detection is therefore absent for two of the four analysis handlers.

**G. STT phrase list is a clinical design error.**  
`backend/streaming-transcription-service/main.py`, `get_streaming_config()`: the `SpeechAdaptation` phrase boost list contains approximately 130 terms. These fall into two categories that were not distinguished:

- *Session vocabulary* (words therapist or patient would say aloud in a session): medication names (`Xanax`, `Suboxone`, `Prozac`), technique names (`safety plan`, `thought record`, `breathing exercise`), assessment acronyms (`PHQ-9`, `C-SSRS`, `GAD-7`). Boosting these is correct.
- *Supervision vocabulary* (clinical/academic jargon that appears in notes, literature, and training — not in patient-facing speech): `alexithymia`, `differential diagnosis`, `countertransference`, `psychomotor retardation`, `polyvagal`, `interoception`, `derealization`, `hypoarousal`, `labile affect`, `depersonalization`, `alexithymia`, `somatization`. Boosting these biases the recognizer toward mishearing ordinary patient speech as clinical jargon.

The list has not been filtered on the axis of *who says this word aloud in a session*. It requires clinical review.

### 3.3 Architectural / Code Defects

**H. `MODALITY_RAG_MAP` is defined twice, inconsistently.**  
- Module-level in `main.py`: a dict of `types.Tool` objects mapping `"CBT" → [CBT_RAG_TOOL, BA_RAG_TOOL]`, `"DBT" → [DBT_RAG_TOOL]`, `"IPT" → [IPT_RAG_TOOL]`
- Inline in `prefetch_rag_context()`: a separate dict of plain strings `{"CBT": ["cbt-corpus", "ba-corpus"], "DBT": ["dbt-corpus"], "IPT": ["ipt-corpus"]}`

These are not synchronized. A future change to one will not propagate to the other. The inline dict in `prefetch_rag_context` is the source of the pre-fetch RAG queries; the module-level dict is used for inline tool calls in the comprehensive path. They must be reconciled to a single source of truth.

**I. Firestore collection name mismatch.**  
`main.py` writes completed sessions to the `sessions` collection. `setup_services/agent_builder/session_context_tool.py` reads from `session_summaries`. If the multi-session agent is ever deployed, it will silently read from an empty collection.

**J. `THERAPY_OBSERVER_SYSTEM_PROMPT` in `prompts.py` is dead code.**  
`backend/streaming-transcription-service/prompts.py` contains a complete Gemini Live API observer system prompt that is never imported or used. The current architecture uses Google Cloud Speech-to-Text V2, not Gemini Live. This is a relic of an earlier design. It should be removed to avoid confusion about the service's architecture.

**K. `max_output_tokens=2560` on the comprehensive path is likely too small.**  
`handle_comprehensive_analysis` in `main.py` sets `max_output_tokens=2560` for Gemini 2.5 Pro with a `thinking_budget` of 8,192 tokens. Thinking tokens consume part of this envelope, leaving insufficient space for the full JSON output (session metrics + pathway indicators + pathway guidance + diarized transcript). The session summary path uses 4,096, which is more appropriate. The JSON repair logic (`extract_json_from_text`) attempts to close truncated output but is not reliable.

**L. RAG prefetch cache is effectively inoperative.**  
`prefetch_rag_context()` in `main.py` uses a 25-second TTL cache keyed on `session_type + hash(last 500 chars of transcript)`. Analysis triggers every 10 words; the transcript grows with every trigger; the hash changes on every call. The TTL never becomes the binding constraint because the hash always fails first. In practice, every realtime analysis call makes 4 parallel Discovery Engine queries regardless of recency.

### 3.4 Prompt Engineering Defects

**M. Transcript buried at 57% in `COMPREHENSIVE_ANALYSIS_PROMPT`.**  
The transcript is the primary clinical input, but it sits between 4,939 characters of preamble (including a 1,100-token `<thinking>` block) and 3,667 characters of JSON schema. The JSON schema occupies the recency position — the model's final attended content before generating output is field names and enumeration constraints, not the patient's words. The `<thinking>` XML tags carry no special meaning to Gemini as input; they are processed as ordinary instructional text.

**N. Citation instructions with no enforcement.**  
The comprehensive prompt instructs the model to embed `[1]`, `[2]` citations inside the JSON response. These numbers are generated by Gemini's internal RAG grounding mechanism. If the datastores return empty results, the model will hallucinate citation markers with no corresponding `grounding_chunks`. There is no runtime check that citation numbers match actual sources.

**O. Analysis triggers ~15x per minute with no cancellation of in-flight Pro calls.**  
The frontend fires both realtime (Flash) and comprehensive (Pro) calls on every 10-word transcript trigger. At 150 words/minute, this is approximately every 4 seconds. Flash calls complete in ~3–4s. Pro calls take ~15–25s. At steady-state, 3–5 Pro calls are in flight simultaneously. There is no queue, no backpressure, and no cancellation mechanism. The Gemini API's project-level rate limits are the only constraint.

### 3.5 Extraneous Scope

**P. The following components are likely extraneous and should be confirmed with the clinical stakeholder before any further investment:**

| Component | Location | Reason |
|---|---|---|
| Fine-tuning pipeline | `setup_services/fine_tuning/` | Never a pilot requirement; hardcodes a GCP project ID |
| Multi-session agent | `setup_services/agent_builder/setup_multi_session_agent.py` | Not integrated; wrong Firestore collection |
| Comparative study harness | `setup_services/comparative_study/` | Research infrastructure for a paper; not clinical scope |
| OpenAI/xAI/DeepSeek adapter | `adapters/openai_compat.py` | Only used by the comparative study |
| Anthropic Claude adapter | `adapters/anthropic.py` | Same |
| Scheduling system | `frontend/components/scheduling/` | All mock data; no backend; not connected to session guidance |
| Patient portal app | `frontend/components/client/` | Between-session features; confirm pilot scope |
| `IntegrativeAnalysisPage.tsx` | `frontend/components/client/` | No clear connection to core session guidance |

---

## 4. Open Questions That Block Further Work

These questions were identified in the prior session and remain unresolved. The next agent cannot resolve them — they require human decisions. Surface them early if the task touches any of the related code.

**For the clinical stakeholder:**
1. Which therapy modalities are in scope for the pilot (CBT only, or CBT + DBT + IPT)?
2. Were questionnaires, homework tracking, interventions, and journaling explicitly requested?
3. Was the patient-facing client portal requested for the pilot?
4. Was appointment scheduling requested?
5. Which clinical terms would a therapist *actually say to a patient* in a standard session? (Required to fix the STT phrase list.)

**For the development team:**
6. Has RAG corpus ingestion been verified end-to-end? Can a query to `ebt-corpus` be confirmed to return passages from the PE manual or CBT Social Phobia manual?
7. Is `MODALITY_RAG_MAP` intentionally defined in two places, or is the inline dict in `prefetch_rag_context` an oversight?
8. Was the Gemini Live API integration (THERAPY_OBSERVER_SYSTEM_PROMPT) intentionally abandoned, or is it planned for a future phase?
9. Is the `sessions` vs `session_summaries` Firestore collection mismatch intentional?
10. What is the intended production auth mechanism — Firebase token verification, IAP, or both?

**For the project lead:**
11. Is the comparative study research activity (`setup_services/comparative_study/`) coordinated with IRB?
12. Is `brk-prj-salvador-dura-bern-sbx` (hardcoded in `setup_fine_tuning.py`) a sandbox or connected to production data?

---

## 5. Recommended Task Scope for This Session

Based on the prior analysis and the token budget constraints documented in Section 2, the following are ranked by clinical risk and readiness-to-fix. Pick a scope that fits within your session's context budget.

### Option A — Fix the three hard blockers (highest priority, ~1,800 SLOC)

Scope: `main.py` (therapy-analysis-function) + `main.py` (streaming-transcription-service) only.

1. Uncomment the Firebase auth block (lines 671–680, `therapy-analysis-function/main.py`). Remove the local-dev bypass comment.
2. Remove the `mock-` token acceptance in `streaming-transcription-service/main.py`.
3. Add a runtime grounding check: if `grounding_chunks` is empty in a comprehensive response, log a `WARNING` and include a `"rag_grounded": false` flag in the response JSON so the frontend can surface it.
4. Increase `max_output_tokens` from 2,560 to 4,096 in `handle_comprehensive_analysis`.

These four changes are surgical, low-risk, and directly address the blockers that prevent any pilot deployment.

**Token cost:** `main.py` at ~22,500 tokens + streaming `main.py` at ~9,600 tokens + this document (~5,000 tokens) + output = ~45,000 tokens. Comfortable within budget.

---

### Option B — Fix the MODALITY_RAG_MAP duplication (~1,800 SLOC)

Scope: `main.py` (therapy-analysis-function) only.

Consolidate the two modality maps into a single source of truth. Recommended approach:

1. Define a `MODALITY_DATASTORE_IDS: dict[str, list[str]]` constant in `constants.py` mapping modality codes to datastore ID strings.
2. Build `MODALITY_RAG_MAP` from it at module init time using the existing `Tool` constructors.
3. Replace the inline `modality_map` dict in `prefetch_rag_context()` with a reference to the same constant.
4. Update `get_rag_tools_for_session()` to derive tool names for logging from the same constant rather than `if tool is CBT_RAG_TOOL` identity checks.

**Token cost:** `main.py` (~22,500) + `constants.py` (~7,800) + this document (~5,000) + output = ~40,000 tokens.

---

### Option C — Fix the RAG cache invalidation (~1,800 SLOC)

Scope: `main.py` (therapy-analysis-function) only.

The cache key `hash(transcript[-500:])` invalidates on every trigger because the transcript is always growing. Fix options (choose one based on stakeholder input on acceptable staleness):

- **Option C1 — Time-only key:** Remove the transcript hash from the cache key entirely. Cache by `session_type` with the 25s TTL only. The RAG context will be refreshed every 25 seconds regardless of transcript changes. Acceptable if the RAG corpus is static clinical documents (which it is).
- **Option C2 — Session-level pre-warm:** Move `prefetch_rag_context` out of the per-request path. Call it once at session start and refresh on a background timer. This requires the frontend to pass a persistent `session_id` to the analysis endpoint.
- ~~**Option C3 — Increase window size:** Change hash input to `transcript[-5000:]`.~~ **This approach is incorrect and must not be implemented.** Any window computed over the tail of a growing string changes on every trigger because new speech always appends at the tail. A larger window does not change this. Option C1 (time-only key) is the correct fix. See `AUTOPSY_CACHE_FIX.md` for the full analysis.

**Token cost:** `main.py` (~22,500) + this document (~5,000) + output = ~32,000 tokens.

---

### Option D — Fix the comprehensive prompt structure (~800 SLOC)

Scope: `constants.py` only. No Python logic changes — text editing only.

Structural changes recommended by the prior analysis (Section 7.1 of the report):

1. **Move the transcript to near the top.** Restructure `COMPREHENSIVE_ANALYSIS_PROMPT` so `{transcript_text}` appears within the first 20% of the template, not at 57%.
2. **Rename and relocate the `<thinking>` block.** Replace `<thinking>...</thinking>` wrapper with `## CLINICAL RISK ASSESSMENT FRAMEWORK` as a named reference section. Move it to immediately before the transcript, not at the top of the file, so calibration rules are in the model's recent attention when it reads the transcript.
3. **Reserve emphasis markers for safety-critical instructions.** The word `IMPORTANT` appears 11 times in the realtime prompt. Downgrade stylistic notes (e.g., "Always refer to the patient as 'patient'") to plain prose. Reserve `CRITICAL:` for the crisis resources requirement.
4. **Add a grounding guard instruction.** Immediately after the `{transcript_text}` placeholder, add: "If the clinical evidence section above is empty, do not fabricate citation numbers. Omit all `[N]` citation markers from the JSON response."

**Token cost:** `constants.py` (~7,800) + this document (~5,000) + output = ~18,000 tokens. Lightest option — leaves maximum budget for iteration.

---

### Option E — Full Tier 1 re-review after human edits (future session)

This option is appropriate after the clinical stakeholder has answered the questions in Section 4 and the development team has confirmed the RAG corpus status. At that point, a new session should:

1. Load this handoff document (~5,000 tokens)
2. Load the updated report reflecting stakeholder decisions (~16,000 tokens if unchanged, less if scoped down)
3. Read only the files that changed (~variable)
4. Produce a revised gap analysis and updated recommendations

**Do not attempt to re-read the entire codebase** in that session. Use the per-file token costs in Section 2 to plan which files are worth re-reading versus accepting the prior findings.

---

## 6. Files Not Reviewed in the Prior Session

The prior agent did not read the following files, which exist in the repository:

- `backend/storage-access-function/main.py` — the Cloud Run entry point for the portal backend (not the analysis function)
- `backend/storage-access-function/portal/router.py` — URL routing for portal endpoints
- `backend/storage-access-function/portal/auth.py` — the `require_role` and `require_owns_patient` decorators
- `backend/storage-access-function/portal/helpers.py` — shared utilities including `emit_activity`
- `frontend/components/NewTherSession.tsx` — alternate session component (the other entry point)
- `frontend/components/App.tsx` — root routing
- All `terraform/` infrastructure-as-code files
- All `docs/` generated documentation scripts
- `firestore.rules` — Firestore security rules (mentioned as a concern in the open questions)

If your task requires reviewing the portal auth system, the Firestore security posture, or the infrastructure configuration, these files are the relevant starting point and have not been analyzed.

---

## 7. Repository Structure Reference

```
gcaimh-ther-assist/
├── backend/
│   ├── therapy-analysis-function/     ← TIER 1 — core inference
│   │   ├── main.py                    (CC=174, 1,433 SLOC, ~22,500 tokens)
│   │   ├── constants.py               (prompts + safety keywords, ~7,800 tokens)
│   │   └── test_phase1_e2e.py         (only test file, live GCP, ~10,000 tokens)
│   ├── streaming-transcription-service/  ← TIER 1 — audio pipeline
│   │   ├── main.py                    (CC=107, 636 SLOC, ~9,600 tokens)
│   │   └── prompts.py                 (dead code — Gemini Live prompt, ~2,000 tokens)
│   └── storage-access-function/       ← TIER 2 — client portal backend
│       └── portal/
│           ├── models.py              (Pydantic models, ~1,150 tokens)
│           ├── router.py              (NOT READ)
│           ├── auth.py                (NOT READ)
│           ├── helpers.py             (NOT READ)
│           └── handlers/
│               ├── me.py              (CC=80, patient self-service, ~3,650 tokens)
│               ├── questionnaires.py  (~1,060 tokens)
│               ├── homework.py        (~860 tokens)
│               ├── interventions.py   (~530 tokens)
│               └── journal.py         (~465 tokens)
├── frontend/
│   ├── hooks/
│   │   ├── useAudioStreamingWebSocket.ts   (TIER 4, ~5,860 tokens)
│   │   └── useTherapyAnalysis.ts           (TIER 4, ~3,170 tokens)
│   ├── utils/
│   │   ├── smartMockAnalysis.ts            (MUST NOT reach production, ~4,170 tokens)
│   │   └── alertDeduplication.ts           (frontend-only dedup, ~2,540 tokens)
│   └── components/
│       ├── NewSession.tsx             (10-word trigger logic lives here)
│       ├── NewTherSession.tsx         (NOT READ — alternate session entry point)
│       ├── scheduling/
│       │   └── schedulingUtils.ts     (extraneous, all mock, ~1,840 tokens)
│       └── client/                    (patient portal frontend — confirm pilot scope)
├── setup_services/
│   ├── agent_builder/
│   │   ├── session_context_tool.py    (wrong Firestore collection, ~1,520 tokens)
│   │   └── setup_multi_session_agent.py  (extraneous, ~7,340 tokens)
│   ├── comparative_study/             (TIER 3 — research harness, extraneous)
│   ├── fine_tuning/
│   │   └── setup_fine_tuning.py       (extraneous, hardcoded project ID, ~8,010 tokens)
│   ├── rag/                           (corpus setup scripts — ingestion unverified)
│   │   ├── corpus/                    (3 PDFs: PE manual, CBT Social Phobia, Deliberate Practice)
│   │   ├── corpus_ba/                 (7 BA RCTs)
│   │   ├── corpus_dbt/                (6 DBT RCTs)
│   │   ├── corpus_ipt/                (7 IPT RCTs)
│   │   └── corpus_safety/             (C-SSRS, SAMHSA, 988 Lifeline standards)
│   └── evaluation/
│       └── run_evaluation.py          (clinical scenario evaluation harness)
├── terraform/                         (NOT READ — infrastructure as code)
├── firestore.rules                    (NOT READ — Firestore security rules)
└── deploy-all.sh / DEPLOY_GUIDE.md   (deployment tooling — considered production-capable)
```

---

*End of handoff brief. Read `TherAssist-CodeReview-Report.md` before beginning work.*
