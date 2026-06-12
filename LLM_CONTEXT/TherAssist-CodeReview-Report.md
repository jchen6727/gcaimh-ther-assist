# Ther-Assist — AI Codebase Review Report

**Repository:** `gcaimh-ther-assist` · github.com/mohsinsub7/gcaimh-ther-assist  
**Review Date:** June 4, 2026  
**Reviewed by:** Claude Sonnet 4.6

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Component-by-Component Findings](#2-component-by-component-findings)
   - 2.1 [Tier 1 — Core Inference](#21-tier-1--core-inference)
   - 2.2 [Tier 2 — Portal and Data Models](#22-tier-2--portal-and-data-models)
   - 2.3 [Tier 3 — Suspected Extraneous / Architecturally Ambiguous](#23-tier-3--suspected-extraneous--architecturally-ambiguous)
   - 2.4 [Tier 4 — TypeScript Frontend](#24-tier-4--typescript-frontend)
3. [Gap Analysis](#3-gap-analysis)
4. [Extraneous Feature Inventory](#4-extraneous-feature-inventory)
5. [Coupling Map](#5-coupling-map)
6. [Open Questions](#6-open-questions)

---

## 1. Executive Summary

Ther-Assist is a clinician-facing AI assistant that listens to therapy sessions and surfaces real-time guidance to the therapist. The codebase is substantially more mature than a typical early-stage academic project — the core inference loop, safety keyword scanner, dual-model architecture, RAG routing, and audio streaming pipeline are all implemented with meaningful clinical thought behind them. The frontend is polished, the backend is well-structured, and the deployment tooling is production-caliber.

However, the task tracker's completion claims must be treated with significant skepticism. Several gaps — some pilot-blocking — remain, and a meaningful portion of the codebase appears to be speculative scope generated beyond what was ever requested. The most important finding is that **the system is not pilot-deployable in its current state** for three specific reasons:

**Authentication is commented out.** The Firebase token verification block in `therapy-analysis-function/main.py` is explicitly disabled with a comment reading "REMOVE FOR PRODUCTION." This means any HTTP request can reach the Gemini API and the Firestore database without a valid token. This is a hard blocker for any deployment involving real patient conversations.

**RAG corpus integrity is unverified.** The local corpus directories contain real clinical PDFs (C-SSRS, SAMHSA guidelines, CBT RCTs, PE manuals, etc.), but it is not confirmed whether these files were successfully ingested into the Vertex AI Search datastores. The test suite checks datastore accessibility but does not verify that retrieved passages actually come from the expected documents. The system will generate guidance either way — grounded in correct clinical content, or hallucinated — and there is no runtime validation to distinguish these cases.

**Multi-modality scope has never been confirmed.** The system implements routing across CBT, DBT, and IPT modalities with five distinct RAG corpora. This is the single largest driver of architectural complexity in the codebase. If the clinical stakeholder only requires one modality for the pilot, a significant fraction of `main.py`'s complexity, all modality-specific corpus setup scripts, and several frontend components can be removed — dramatically reducing the risk surface before launch.

**What is genuinely production-ready:** the audio pipeline (STT v2, auto-reconnect, PCM worklet, Safari fallback), the realtime Flash inference path including the safety keyword scanner and deterministic alert injection, the session summary (Pro model + thinking budget), the frontend alert rendering and deduplication, the client portal backend (homework, interventions, questionnaires, journal), and the deployment tooling.

**What is broken or unreliable:** authentication (disabled), RAG corpus content integrity (unverified), the comprehensive analysis path under token pressure (2,560 token cap is likely too small for Pro model output), the STT phrase boost list (see Section 2.1), and the test suite (only one test file, wired to live GCP, no isolated unit tests).

**What appears to be extraneous scope:** fine-tuning pipeline, multi-session agent architecture, comparative study research harness, OpenAI and Anthropic adapters, the full scheduling system, the integrative analysis page, the client portal patient app, and the `SchedulePage` component — none of which serve the core real-time session guidance use case.

---

## 2. Component-by-Component Findings

---

### 2.1 Tier 1 — Core Inference

---

#### `therapy-analysis-function/main.py`

**What it does:** The central Cloud Run Function that handles all analysis requests. It receives HTTP POST requests with a transcript segment and session context, routes between a realtime path (Gemini 2.5 Flash, no thinking, 1,024 token output) and a comprehensive path (Gemini 2.5 Pro, thinking budget 8,192–16,384, 2,560 token output), injects pre-fetched RAG context into prompts, runs a deterministic safety keyword scanner before every LLM call, and streams JSON results back. It also handles session persistence (`save_session`, `get_sessions`) and patient-safe summary filtering (`get_patient_summary`).

| Dimension | Assessment |
|---|---|
| **Status** | Implemented but with several reliability gaps (see below) |
| **Clinical Relevance** | Clearly needed — this is the entire backend brain |
| **Coupling** | Everything depends on this file: `useTherapyAnalysis.ts`, all RAG tools, `constants.py`, Firestore, Firebase Auth, Gemini API. Highest fan-in in the codebase. |

**Key findings:**

- **Authentication is disabled.** Lines 671–680 comment out the entire Firebase token verification block with an explicit "REMOVE FOR PRODUCTION" note. Any request to this endpoint is currently unauthenticated.

- **All four Gemini harm-category thresholds are set to `OFF`** in both the realtime and comprehensive code paths. This is intentional (clinical content requires discussing self-harm, suicide, abuse) and is consistent across all paths.

- **The 2,560 `max_output_tokens` limit on the comprehensive path is likely too small.** Gemini 2.5 Pro with a thinking budget of 8,192 tokens must produce thinking tokens plus output within this envelope. The session summary path uses 4,096, which is more appropriate. Under token pressure, the system's JSON repair logic attempts to patch truncated output, but this is unreliable.

- **RAG empty corpus handling: there is no validation** that retrieved passages are non-empty or that they come from expected documents. If a datastore returns empty results, the LLM receives an empty `CLINICAL EVIDENCE` section and will generate guidance from its training data alone — with no indication to the therapist or the system log that grounding failed.

- **Background RAG pre-fetch race condition.** The `results_by_store` dict inside `prefetch_rag_context` is populated by background threads without a lock. Multiple threads writing to a shared dict concurrently is a potential race condition in CPython, even though the GIL provides some protection.

- **Context caching is effectively disabled.** The `COMPREHENSIVE_SYSTEM_INSTRUCTION` cache path is skipped whenever `rag_tools` are present — which is always. In practice, context caching never fires.

- **`MODALITY_RAG_MAP` is defined twice.** Once as a module-level dict of `Tool` objects in `main.py`, and again as a local `modality_map` dict of plain strings inside `prefetch_rag_context`. These are not synchronized; a future change to one will not propagate to the other.

- **Deduplication is frontend-only.** The backend generates an alert on every call if the transcript warrants one. The frontend's 3-second hard block and category throttle windows are the only protection against alert flooding.

---

#### `therapy-analysis-function/constants.py`

**What it does:** Defines all clinical behavior: model names, the deterministic safety keyword lists (5 categories, ~100 keywords total), clinical response templates for each safety category, the safety context injection template, `REALTIME_ANALYSIS_PROMPT`, `REALTIME_ANALYSIS_PROMPT_STRICT`, `COMPREHENSIVE_ANALYSIS_PROMPT`, `PATHWAY_GUIDANCE_PROMPT`, and `SESSION_SUMMARY_PROMPT`. Data-only with no logic.

| Dimension | Assessment |
|---|---|
| **Status** | Functional — well-organized, clinically thoughtful content |
| **Clinical Relevance** | Clearly needed — defines all LLM-facing clinical behavior |
| **Coupling** | Consumed entirely by `main.py`. Nothing else imports it directly. |

**Key findings:**

- **`TRIGGER_PHRASES` (4 phrases) is now dead code.** Originally used to select between strict and non-strict prompts. The current code uses the non-strict prompt first regardless of trigger phrase detection; these phrases now affect only a logging message.

- **The `<thinking>` block in `COMPREHENSIVE_ANALYSIS_PROMPT`** is not a Gemini thinking tag — it is literal XML embedded in the prompt text intended to guide the model's reasoning. Unconventional but not incorrect.

- **Risk level definitions are clinically well-calibrated.** The three-tier THERAPEUTIC CONTEXT vs ACTIVE RISK distinction (structured therapeutic work / therapeutic processing of past behaviors / patient reporting recent dangerous actions) is a notable strength. However, these definitions exist only in the prompt — they are not validated in code.

- **`MODALITY_RAG_MAP` in `constants.py`** has a comment referencing "March 2026 meeting" suggesting a simplification from 5 to 3 modalities. This is not enforced in code and is inconsistent with the inline `modality_map` dict in `main.py`'s `prefetch_rag_context`.

- **Safety keyword false positive risk.** The lists include terms like `weapon`, `gun`, `knife`, `shoot` that could appear in non-crisis therapeutic contexts (discussing past trauma, news events, figurative language). A false safety alert mid-session is not harmless — it could disrupt therapeutic flow and erode clinician trust. The keyword lists need clinical review for false positive potential.

---

#### `streaming-transcription-service/main.py`

**What it does:** The FastAPI WebSocket service that receives raw PCM audio from the browser, streams it to Google Cloud Speech-to-Text V2, forwards transcripts to the frontend, and runs the deterministic safety keyword scanner on every final transcript with direct WebSocket alert emission.

| Dimension | Assessment |
|---|---|
| **Status** | Implemented and functional — with one significant clinical design flaw (see STT phrase list below) |
| **Clinical Relevance** | Clearly needed — this is the audio-to-text pipeline |
| **Coupling** | Decoupled from the analysis function. Outputs are consumed by the frontend hook which independently calls the analysis function. |

**Key findings:**

- **The `clinical_phrases` STT adaptation list is a clinical design error.** The list contains ~130 boosted terms spanning therapy modalities, assessments, diagnoses, medications, and clinical vocabulary. The intent — improving STT recognition of therapy-relevant words — is sound. The execution conflates two categories of speech that should be treated differently:

  The first category contains words that genuinely appear in patient-therapist conversation: medication names a patient would say aloud (`Xanax`, `Suboxone`, `Prozac`, `Ativan`), technique names both parties use (`safety plan`, `thought record`, `breathing exercise`, `grounding exercise`), and assessment acronyms a therapist might reference (`PHQ-9`, `C-SSRS`, `GAD-7`). Boosting these is correct clinical engineering.

  The second category contains clinical and academic jargon that appears in supervision notes, training literature, and diagnostic discussions — not in a therapy session with a patient present. Terms such as `alexithymia`, `differential diagnosis`, `psychomotor retardation`, `countertransference`, `interoception`, `polyvagal`, `derealization`, `hypoarousal`, `schema`, and `labile affect` are not vocabulary a therapist would use facing a patient in ordinary evidence-based practice. Boosting these terms biases the recognizer toward mishearing ordinary patient speech as clinical jargon — the opposite of the intended effect.

  The list was not filtered on the axis of *who actually says this word in a session*, which is the only axis relevant to an STT adaptation. It requires clinical review to remove supervision-layer vocabulary and retain session-layer vocabulary.

- **`THERAPY_OBSERVER_SYSTEM_PROMPT` in `prompts.py` is dead code.** This is a complete Gemini Live API observer prompt that was never integrated into the current STT V2 architecture. It is a relic of an earlier design and should be removed to avoid confusion.

- **`profanity_filter` is explicitly `False`.** This is correct: profanity filtering would corrupt clinical transcripts.

- **Auto-reconnect logic is well-implemented.** `MAX_STREAM_DURATION_SECONDS = 270` (under the 5-minute STT v2 hard limit), with proper exponential backoff and auth-error detection that halts retries on credential failures.

- **`mock-` token bypass remains active in Cloud Run.** Any token beginning with `mock-` is accepted as "IAP pre-authenticated" in the Cloud Run deployment path. This must be removed before production.

---

#### `setup_services/agent_builder/session_context_tool.py`

**What it does:** A Cloud Function that retrieves session history from Firestore for a given patient, supporting four actions: `get_history`, `get_risk_trajectory`, `get_treatment_progress`, and `store_session_summary`. Designed to be called by the multi-session context Vertex AI Agent.

| Dimension | Assessment |
|---|---|
| **Status** | Functional as a standalone function — but its caller (the multi-session agent) is never invoked from the main application |
| **Clinical Relevance** | Possibly needed — cross-session history is a legitimate clinical need, but it was never confirmed as a pilot requirement |
| **Coupling** | Isolated: reads from the `session_summaries` Firestore collection, which is different from the `sessions` collection that `main.py` writes to. Would silently return empty data if deployed today. |

---

### 2.2 Tier 2 — Portal and Data Models

---

#### `portal/models.py`

**What it does:** Pydantic models for the client portal: homework (upsert, status update, patch), intervention (upsert), publish draft (patch), activity events, questionnaires (assign, status update, response submission), journal entry, outcome responses, and intervention sessions. This file is the structural inventory of the between-session portal feature set.

| Dimension | Assessment |
|---|---|
| **Status** | Functional models — the corresponding handlers are implemented |
| **Clinical Relevance** | Possibly needed for a full product; likely extraneous for a pilot focused on real-time session guidance |
| **Coupling** | Referenced by all portal handlers. The entire `storage-access-function` depends on these models. |

The entity list reveals a fully realized between-session client management system: homework assignment and tracking, structured intervention library, journaling, standardized outcome questionnaires, and a content publishing workflow where therapists toggle which session content to share with clients. This capability is well beyond what a real-time session guidance pilot would require.

---

#### `portal/handlers/questionnaires.py`, `homework.py`, `interventions.py`, `journal.py`

**What they do:** Four fully implemented portal backend API handlers covering: homework assignment/tracking/rescheduling, structured intervention library assignment/archiving, questionnaire assignment and response collection, and patient journaling. All four use proper Pydantic validation, role-based access control (`require_role`, `require_owns_patient` decorators), Firestore reads/writes, and activity event emission.

| Dimension | Assessment |
|---|---|
| **Status** | Functional — complete implementations with auth, validation, and Firestore persistence |
| **Clinical Relevance** | Likely extraneous for a pilot — these are between-session management features, not real-time guidance |
| **Coupling** | Depend on `portal/auth.py`, `portal/helpers.py`, `portal/models.py`, and Firestore. No coupling to the analysis pipeline. |

---

#### `portal/handlers/me.py`

**What it does:** Patient self-service endpoints covering 14 distinct operations — listing homework, interventions, journal entries, therapy sessions, outcome measures, and outcome responses — all keyed to the authenticated patient's identity derived from the Firebase token, never from URL or body parameters. The privacy boundary is well-implemented.

| Dimension | Assessment |
|---|---|
| **Status** | Functional — the `derive_self_patient_id()` auth boundary pattern is sound |
| **Clinical Relevance** | Possibly needed — the patient-facing portal has legitimate clinical value but is not part of the core real-time guidance loop |
| **Coupling** | Depends on `portal/auth.py`, `portal/helpers.py`, journal helpers. Referenced by `ClientPortalRealProvider.ts`. |

---

### 2.3 Tier 3 — Suspected Extraneous / Architecturally Ambiguous

---

#### `setup_services/fine_tuning/setup_fine_tuning.py`

**What it does:** A script to create a supervised fine-tuning job on Gemini 2.5 Flash using clinical scenarios as training examples. Notes an estimated cost of $1,500–$2,000. Training data is prepared inline as a small set of hardcoded scenario/response pairs — not derived from a real clinical feedback corpus.

| Dimension | Assessment |
|---|---|
| **Status** | Stub — would require significant additional work to be meaningful |
| **Clinical Relevance** | Likely extraneous — fine-tuning was almost certainly never a pilot requirement |
| **Coupling** | Completely isolated — no other code references it |

The system already uses prompting and RAG for clinical grounding. Fine-tuning adds cost and complexity with no clinical benefit until a real feedback loop and training dataset exist.

---

#### `setup_services/agent_builder/setup_multi_session_agent.py`

**What it does:** A script to create a Vertex AI Agent Builder agent for cross-session clinical context. Defines a Firestore schema for `session_summaries` and deploys a Cloud Function as an agent tool. The architecture is complete on paper but never integrated into the main application flow.

| Dimension | Assessment |
|---|---|
| **Status** | Stub — never wired into the main application |
| **Clinical Relevance** | Possibly needed for a full product; not confirmed for the pilot |
| **Coupling** | Reads from `session_summaries` collection; `main.py` writes to `sessions` — would silently read empty data if deployed today |

---

#### `setup_services/comparative_study/` — `runner.py`, `arms.py`, `adapters/`

**What it does:** A full multi-model comparative study harness. `arms.py` defines 11 model arms across 5 providers (TherAssist pipeline, Gemini 2.5 Pro vanilla/engineered, GPT-5 vanilla/engineered, Claude Sonnet 4.6 vanilla/engineered, xAI Grok vanilla/engineered, DeepSeek vanilla/engineered). `runner.py` sweeps all test cases against all arms and produces JSONL output for a comparative paper. `adapters/openai_compat.py` supports OpenAI, xAI, and DeepSeek. `adapters/anthropic.py` supports Claude models.

| Dimension | Assessment |
|---|---|
| **Status** | Functional as a research harness — well-implemented and would actually run with valid API keys |
| **Clinical Relevance** | Likely extraneous for a clinical pilot — this is research infrastructure for a comparative paper |
| **Coupling** | Isolated from the main application. Imports from `setup_services/evaluation/run_evaluation.py` for test cases. |

The comments in `arms.py` reference "reviewers scrutinizing this list for the paper," making clear this is intended as academic research infrastructure, not clinical product scope. It should be moved to a separate research repository or excluded from the clinical deployment.

---

#### `setup_services/rag/` — multiple setup scripts

**What it does:** Seven distinct RAG setup scripts creating and configuring Vertex AI Search datastores with layout-aware PDF chunking: `setup_rag_datastore.py` (ebt-corpus), `setup_modality_datastores.py` (cbt, ba, dbt, ipt corpora), `setup_expansion_datastores.py`, `setup_safety_datastore.py`, `setup_transcript_datastore.py`, and `setup_transcript_datastore_resumable.py`. Local corpus directories contain real clinical PDFs across all modalities and the safety corpus.

| Dimension | Assessment |
|---|---|
| **Status** | Infrastructure created; corpus ingestion status unverified and likely incomplete |
| **Clinical Relevance** | The `ebt-corpus` and `safety-crisis` datastores are clearly needed. The modality-specific corpora are needed only if multi-modality is confirmed. |
| **Coupling** | Consumed by `main.py` via `MODALITY_RAG_MAP`. The `safety-crisis` datastore is always included regardless of modality. |

**Critical note:** The test suite (`test_datastores` function) checks only whether the datastores return any response — not whether the response contains passages from the expected PDFs. A datastore that was created but not populated would pass this test if Gemini generates a response from its training data instead of retrieved content.

---

### 2.4 Tier 4 — TypeScript Frontend

---

#### `frontend/hooks/useAudioStreamingWebSocket.ts`

**What it does:** Captures microphone audio or audio file playback as raw PCM 16kHz 16-bit mono, sends it to the transcription backend via WebSocket, and dispatches transcript and analysis events. Uses `AudioWorklet` with `ScriptProcessorNode` fallback for Safari. Implements heartbeat keepalive, auto-reconnect with exponential backoff (5 max attempts), and pause/resume without tearing down the WebSocket.

| Dimension | Assessment |
|---|---|
| **Status** | Functional — well-implemented, handles edge cases correctly |
| **Clinical Relevance** | Clearly needed — this is the browser audio pipeline |
| **Coupling** | Depends on `VITE_STREAMING_API` env var. No coupling to the analysis hook. |

The reconnect logic correctly uses an `intentionalDisconnectRef` flag to distinguish user-initiated stops from network drops. The `ScriptProcessorNode` fallback is deprecated but still functional and correctly identified as a fallback path.

---

#### `frontend/hooks/useTherapyAnalysis.ts`

**What it does:** On every transcript segment, calls the backend (or mock) for both realtime and comprehensive analysis. Controlled by a single boolean: `USE_MOCK_MODE = !VITE_ANALYSIS_API`. When `VITE_ANALYSIS_API` is configured, it calls the live backend and is not in mock mode. When unconfigured, it routes to `generateSmartRealtimeAnalysis` / `generateSmartComprehensiveAnalysis` in `smartMockAnalysis.ts`.

| Dimension | Assessment |
|---|---|
| **Status** | Functional — mock/live switch is clean and correct |
| **Clinical Relevance** | Clearly needed |
| **Coupling** | Depends on `VITE_ANALYSIS_API`. In live mode, depends on the `therapy-analysis-function` backend. |

The mock/live switch is a single environment variable — there is no code duplication and no flag confusion. The session summary call has a 5-minute timeout, appropriate for Pro + thinking budget.

---

#### `frontend/utils/smartMockAnalysis.ts`

**What it does:** Generates content-aware mock analysis responses based on keyword detection in the transcript. Detects safety keywords, distress, anxiety, engagement, and resistance patterns, and synthesizes plausible mock alerts and session metrics. The mock data is substantially more sophisticated than a simple placeholder.

| Dimension | Assessment |
|---|---|
| **Status** | Functional — useful for development and demos without a live backend |
| **Clinical Relevance** | Not needed in production |
| **Coupling** | Referenced only by `useTherapyAnalysis.ts` via the `USE_MOCK_MODE` branch |

**Safety concern:** This file produces realistic-looking safety alerts, including `Suicidal Ideation Detected`, based on keyword matching without backend validation. In a live clinical deployment, if `VITE_ANALYSIS_API` were misconfigured or lost, the frontend would silently fall back to mock analysis with no visible indication. A clinician who does not know they are seeing mock alerts could fail to act on a real safety situation, or could act on a mock alert that does not reflect actual patient speech. This file should be excluded from production builds.

---

#### `frontend/components/scheduling/schedulingUtils.ts`

**What it does:** Utility functions for a scheduling/calendar system: date formatting, time slot generation, business hours configuration, conflict detection, appointment status utilities, availability period management, and pagination helpers.

| Dimension | Assessment |
|---|---|
| **Status** | Functional — complete scheduling utilities |
| **Clinical Relevance** | Likely extraneous for a pilot |
| **Coupling** | Used by `SchedulePage.tsx` and 5 related scheduling components. All scheduling data uses `mockAppointments.ts` — there is no backend API for scheduling. |

The entire scheduling subsystem is frontend-only with no persistence. It is not connected to the real-time session guidance use case.

---

## 3. Gap Analysis

---

### 3.1 Gaps That Block Pilot Launch

#### Authentication Disabled *(Critical Blocker)*

The Firebase token verification in `therapy-analysis-function/main.py` is commented out. Lines 671–680 contain the entire auth check block, explicitly noted as "REMOVE FOR PRODUCTION." In the current state, any HTTP request to the `therapy_analysis` endpoint can trigger Gemini API calls, read from and write to Firestore, and access session data.

- Uncomment the auth block and remove the local-dev bypass, or implement IAP (Identity-Aware Proxy) at the Cloud Run level as an alternative.
- The `mock-` token bypass in `streaming-transcription-service/main.py` also requires removal for production.

#### RAG Corpus Integrity Unverified *(Critical Blocker)*

Clinical guidance quality depends entirely on whether the Vertex AI Search datastores contain the correct clinical content. The PDFs exist locally, but there is no evidence they were successfully ingested and chunked. The test suite checks only that the datastores return any response — not that retrieved passages come from the expected documents.

- Run the existing `test_datastores` function and inspect `grounding_chunks` in the response to verify source titles match the corpus PDFs. Re-run the ingestion pipeline for any empty or incorrectly populated datastore.
- Add a runtime check: if RAG grounding returns 0 chunks, log a warning and surface it in the diagnostics response.

#### Multi-Modality Scope Unconfirmed *(Strategic Blocker)*

The system implements routing across CBT, DBT, and IPT modalities, which drives a significant fraction of the codebase complexity. If the pilot requires only one modality, this complexity can be deferred, reducing the attack surface and the risk of misconfiguration before launch.

- The clinical stakeholder must confirm which modalities are in scope for the pilot before further engineering investment in multi-modality infrastructure.

---

### 3.2 Gaps That Create Clinical Safety Risk

#### No Runtime Validation That RAG Is Grounded

The system can generate clinically plausible-sounding guidance from Gemini's training data alone if the RAG datastores are empty. There is no warning to the therapist or the system log when this occurs. The guidance will look identical whether or not it is grounded in EBT content.

#### STT Phrase Boost List Contains Supervision-Layer Vocabulary

The clinical phrase boost list in `streaming-transcription-service/main.py` includes academic and supervisory terminology that would not ordinarily appear in a patient-facing therapy session (e.g., `alexithymia`, `differential diagnosis`, `countertransference`, `psychomotor retardation`, `polyvagal`, `interoception`). Boosting these terms biases the STT recognizer toward mishearing ordinary patient speech as clinical jargon — producing incorrect transcripts that could in turn produce incorrect AI guidance. The list requires clinical review to distinguish *session vocabulary* (what therapist and patient actually say aloud) from *supervision vocabulary* (what clinicians write in notes and discuss in training).

#### Safety Keyword False Positive Risk

The `SAFETY_KEYWORDS` lists include terms like `weapon`, `gun`, `knife`, `shoot` that could appear in non-crisis therapeutic contexts (discussing a patient's history, news events, figurative language). A false safety alert during a structured therapeutic conversation is not harmless — it disrupts therapeutic flow and erodes clinician trust in the system. The keyword lists need clinical review for false positive potential.

#### `mock-` Token Bypass in Production-Accessible Transcription Service

In the Cloud Run deployment, any token beginning with `mock-` is accepted as authenticated. An unauthorized user who knows the WebSocket endpoint can access the transcription service. Unauthorized access to an active therapy session audio stream is a HIPAA concern.

#### `smartMockAnalysis.ts` Must Not Reach Production

If `VITE_ANALYSIS_API` is misconfigured or unavailable in a live deployment, the frontend silently falls back to mock analysis that generates realistic-looking safety alerts without backend validation. This creates a failure mode where a clinician receives no real guidance but cannot tell the system has failed.

---

### 3.3 Gaps That Expand Cost If Not Addressed First

#### `MODALITY_RAG_MAP` Defined in Two Places

The modality-to-corpus mapping exists as `MODALITY_RAG_MAP` (module-level dict of `Tool` objects in `main.py`) and as a separate `modality_map` dict (plain string-to-list inside `prefetch_rag_context`). A future change to add or remove a modality will require updating both locations; a missed update causes inconsistent RAG routing between the inline-tool path and the prefetch path.

#### Token Budget Too Small for Comprehensive Path

The comprehensive analysis path caps output at 2,560 tokens. Gemini 2.5 Pro with 8,192 thinking tokens + structured JSON output covering session metrics, pathway indicators, pathway guidance, and a diarized transcript frequently requires more than this. A truncated `diarized_transcript` or `pathway_guidance` produces silently incomplete clinical output. The session summary path uses 4,096 tokens, which is more appropriate and should be the reference for the comprehensive path.

#### No Unit Test Coverage for Safety-Critical Code Paths

The only test file is `test_phase1_e2e.py`, which requires live GCP credentials and makes real Gemini API calls. There are no unit tests for `detect_safety_keywords`, `get_rag_tools_for_session`, `extract_json_from_text`, `determine_therapy_phase`, the deduplication logic in `alertDeduplication.ts`, or the mock/live switch in `useTherapyAnalysis.ts`. Adding these before significant refactoring will prevent regression in safety-critical paths.

---

## 4. Extraneous Feature Inventory

The following features should be brought to the clinical stakeholder and/or project lead for a conscious keep/remove decision before any further engineering investment.

| Component | Verdict | What It Does | Why It's Suspect |
|---|---|---|---|
| `setup_fine_tuning.py` | Likely extraneous | Fine-tuning pipeline for Gemini Flash | Pilot does not require a custom-tuned model; adds cost with no clinical benefit until real feedback data exists |
| `setup_multi_session_agent.py` | Possibly needed | Persistent cross-session agent | Legitimate clinical value (longitudinal risk tracking) but integration is broken (wrong Firestore collection) and was not confirmed as a pilot requirement |
| `comparative_study/` (all files) | Likely extraneous | Academic research harness for a comparative paper | Serves a research paper, not the clinical product. Should be in a separate research repo. |
| `adapters/openai_compat.py` | Likely extraneous | OpenAI/xAI/DeepSeek adapter | Only needed for the comparative study; the product uses Gemini |
| `adapters/anthropic.py` | Likely extraneous | Anthropic Claude adapter | Same as above |
| `scheduling/` (all files) | Likely extraneous | Appointment scheduling calendar | Not connected to any backend; all data is mock; not part of the real-time guidance use case |
| `client/` components (patient portal app) | Possibly needed | Patient-facing between-session portal | Legitimate clinical value; confirm whether in scope for the pilot |
| `IntegrativeAnalysisPage.tsx` | Likely extraneous | Integrative analysis view | No clear connection to the core session guidance flow |
| `THERAPY_OBSERVER_SYSTEM_PROMPT` in `prompts.py` | Remove | Gemini Live API system prompt | Dead code — relic of an abandoned earlier architecture. The current system uses STT V2, not Gemini Live. |
| `session_context_tool.py` Firestore collection | Fix or remove | Cross-session context tool | Reads from `session_summaries`; `main.py` writes to `sessions`. Would silently return empty history. |

---

## 5. Coupling Map

---

### 5.1 Core Inference Path *(High Coupling, Pilot-Critical)*

The critical path through the system on every transcript segment:

```
Browser mic
  → AudioWorklet (pcm-processor.worklet.js)
  → WebSocket
  → streaming-transcription-service/main.py
  → STT V2
  → transcript event
  → frontend (useTherapyAnalysis.ts)
  → HTTP POST
  → therapy-analysis-function/main.py
  → constants.py (prompts + safety keywords)
  → Gemini API (Flash + Pro)
  → RAG datastores (Vertex AI Search)
  → JSON response
  → useTherapyAnalysis.ts → onAnalysis callback
  → AlertDisplay component
```

Key coupling facts:

- `therapy-analysis-function/main.py` has the highest fan-in of any file: imports `constants`, `firebase_admin`, `google.genai`, `google.cloud.discoveryengine`, `flask`, `dotenv`, and `firestore`.
- The transcription service and the analysis function are **decoupled** — they communicate only through the frontend. A transcript event does not automatically trigger analysis; the frontend hook decides when and whether to call the analysis endpoint.
- Alert deduplication is entirely frontend-side (`alertDeduplication.ts`). Removing or changing its behavior requires only a frontend change.

---

### 5.2 Safety System Coupling

The safety system spans three layers:

**Backend deterministic scanner:** `detect_safety_keywords` in `main.py` reads from `constants.SAFETY_KEYWORDS`, runs before every LLM call in `handle_segment_analysis`, injects `SAFETY_CONTEXT_INJECTION` into the prompt if triggered, and forces a deterministic alert if the LLM returns empty JSON despite a keyword match.

**Frontend secondary scanner (mock mode only):** `smartMockAnalysis.ts` contains a duplicate `SAFETY_KEYWORDS` list (slightly different from the backend list). In mock mode, this is the only safety detection. In live mode, it is dead code.

**Frontend alert rendering:** `AlertDisplay.tsx` renders the alert JSON. Safety alerts with `timing='now'` are visually distinct (red, immediate). The deduplication logic in `alertDeduplication.ts` explicitly exempts safety alerts with `timing='now'` from the category throttle window.

Safety bypass paths:
1. If `VITE_ANALYSIS_API` is not configured, the frontend silently uses mock analysis. Mock safety alerts are generated by keyword matching only, bypassing the backend scanner's deterministic injection and clinical response templates.
2. In the transcription service, the safety scan fires on every final transcript and sends an alert directly over the WebSocket — this path is **independent of the analysis function** and bypasses the comprehensive prompt injection.

**Note:** The backend safety scanner is not applied in `handle_pathway_guidance` or `handle_session_summary`.

---

### 5.3 Modality Dispatch Coupling

Modality routing touches the following locations:

- **`main.py`:** `MODALITY_RAG_MAP` (module-level dict of `Tool` objects), `get_rag_tools_for_session()` (selects tools by `session_type`), `prefetch_rag_context()` (inline `modality_map` — separate from `MODALITY_RAG_MAP`), `handle_segment_analysis`, `handle_pathway_guidance`, `handle_session_summary` (all three call `get_rag_tools_for_session`).
- **`constants.py`:** A comment references "March 2026 meeting" as justification for simplifying from 5 to 3 modalities. This is the closest thing to a source-of-truth note but is not enforced in code.
- **Frontend:** `session_context` object passed by the frontend includes `session_type`. The frontend does not validate or constrain this value. The backend falls back to CBT for unrecognized session types.
- **RAG setup scripts:** Seven separate scripts, each hardcoded with a specific datastore ID. There is no central registry tying a modality name to a datastore ID — the mapping exists only in `main.py`'s `MODALITY_RAG_MAP`.

**Effort to remove modality routing if stakeholder confirms single-modality pilot:** Moderate. The routing logic is concentrated in `get_rag_tools_for_session` (~30 lines) and `prefetch_rag_context` (the `modality_map` dict). Removal simplifies both functions to always return the base set (`ebt-corpus` + `safety-crisis`). The modality-specific corpus setup scripts and corpus directories can be archived. The frontend `session_type` selector becomes a no-op or can be removed. Estimated: **2–3 days of focused work with testing.**

---

### 5.4 Frontend Mock/Live Boundary

The mock/live switch in `useTherapyAnalysis.ts` is a single boolean computed at module load time from `VITE_ANALYSIS_API`. Clean in design, but with several implicit dependencies:

- `smartMockAnalysis.ts` is always bundled and compiled into the production build. It is only skipped at runtime by the `USE_MOCK_MODE` check. A build-time exclusion would be more robust.
- The `SchedulePage` component uses `mockAppointments.ts` exclusively — there is no live backend path for scheduling. This is **not gated by `USE_MOCK_MODE`**; it silently uses mock data in all configurations.
- The patient portal frontend uses `ClientPortalRealProvider.ts` in production and `DummyClientPortalProvider.ts` otherwise — a separate switching mechanism from `USE_MOCK_MODE`, controlled by a different env var pattern.

---

## 6. Open Questions

---

### 6.1 For the Clinical Stakeholder

- Which therapy modalities are in scope for the pilot? The system currently implements CBT, DBT, and IPT routing. If the pilot is single-modality, a significant simplification is possible before launch.
- Were questionnaires, homework tracking, structured interventions, and journaling requested as part of the pilot? The portal backend implements all of these. If not requested, they add surface area without clinical benefit.
- Was the patient-facing client portal requested for the pilot? The frontend and backend implement a complete client portal entirely separate from the real-time session guidance use case.
- Were appointment scheduling features requested? The scheduling system is a full calendar prototype that uses only mock data and has no backend.
- Was longitudinal session tracking (cross-session risk trajectory, treatment progress) requested? This corresponds to the multi-session agent architecture.
- Which clinical terms would a therapist *actually say to a patient* in a standard session? This question must drive the review of the STT phrase boost list to distinguish session vocabulary from supervision vocabulary.

---

### 6.2 For the Development Team

- Has the RAG corpus ingestion been verified end-to-end? Can you confirm that a query to `ebt-corpus` returns passages from the PE manual, the CBT Social Phobia manual, or the Deliberate Practice CBT manual? This can be tested using the `test_datastores` function by inspecting `grounding_chunks` for source titles.
- Is the `MODALITY_RAG_MAP` in `main.py` consistent with the `modality_map` dict in `prefetch_rag_context`? These are two separate implementations that can diverge — they need to be the same mapping.
- What was the original intent of `THERAPY_OBSERVER_SYSTEM_PROMPT` in `prompts.py`? The current STT V2 architecture does not use this prompt. Was there a Gemini Live API integration planned or abandoned?
- The Firestore collection for session storage is `sessions` (written by `main.py`) but `session_summaries` (read by `session_context_tool.py`). Is this intentional? If the multi-session agent is intended to work, these must be reconciled.
- What is the intended production auth mechanism — Firebase token verification, IAP, or both? The `therapy-analysis-function` has token verification code that is commented out; the transcription service has an IAP comment but implements Firebase verification.

---

### 6.3 For the Project Lead

- The comparative study infrastructure references an academic paper in its comments. Is this research activity coordinated with the clinical stakeholder and IRB? Comparative study infrastructure in the same repo as the clinical product warrants clarity on scope separation.
- The fine-tuning script hardcodes a GCP project ID (`brk-prj-salvador-dura-bern-sbx`). Is this a sandbox project or is it connected to production data? If the latter, the fine-tuning script should not be in the main repo.
- Are the Firestore security rules in `firestore.rules` reviewed and enforced for the patient data collections? The portal backend implements auth checks in Python, but Firestore rules provide defense in depth.

---

### 6.4 Specific Questions from the Briefing — Answers

#### On Multi-Modality

**How deeply is modality routing coupled into `main.py`?** It is present in 4 functions: `get_rag_tools_for_session`, `prefetch_rag_context`, `handle_pathway_guidance`, and `handle_session_summary`. Removal is moderate effort (2–3 days).

**Does the modality dispatch function end-to-end?** Structurally yes, but content integrity of modality-specific datastores is unverified.

**Is `MODALITY_RAG_MAP` the single source of truth?** No. It is duplicated in `prefetch_rag_context` as an inline dict with different tool references.

#### On the RAG Infrastructure

**What happens when a corpus is empty?** The LLM receives an empty `CLINICAL EVIDENCE` section. It will generate guidance from training data alone. There is no error, no warning, and no indication in the response that grounding failed.

**Are there validation steps to detect a silently empty datastore?** No. The test suite checks that a datastore returns a response, not that the response contains passages from the expected PDFs.

**How many distinct RAG corpus paths exist?** Five: `ebt-corpus` (always), `safety-crisis` (always), `cbt-corpus` + `ba-corpus` (CBT path), `dbt-corpus` (DBT path), `ipt-corpus` (IPT path). For comprehensive analysis, `transcript-patterns` is also added regardless of modality. A standard CBT session uses 4 datastores; DBT/IPT use 3.

#### On the Safety System

**Are all four Gemini harm-category thresholds disabled?** Yes, consistently across all code paths: realtime, comprehensive, pathway guidance, and session summary.

**Is the safety scanner applied before every LLM call?** Yes — in `handle_segment_analysis` before both the realtime and comprehensive paths, and independently in the transcription service on every final transcript. It is *not* applied in `handle_pathway_guidance` or `handle_session_summary`.

**Do the deduplication windows apply correctly?** Deduplication is frontend-only. Safety alerts (`timing='now'`, `category='safety'`) are explicitly exempted from the category throttle. However, the 3-second hard block applies to *all* alerts including safety, which could suppress a second safety alert arriving within 3 seconds of the first.

**Does the safety system behave differently in mock vs live?** Yes, significantly. In mock mode, safety detection uses a simpler keyword list in `smartMockAnalysis.ts`. In live mode, it uses the backend scanner with context injection, deterministic alert injection, and clinical response templates.

#### On the Dual-Model Architecture

**Could Flash and Pro calls be confused?** Unlikely. Model selection is explicit via `constants.MODEL_NAME` (Flash, realtime) and `constants.MODEL_NAME_PRO` (Pro, comprehensive/pathway/summary), checked in `test_phase1_e2e.py`.

**What happens if the Pro thinking budget is exhausted?** The `thinking_budget` parameter is a hint, not a hard limit. The model will continue to the output phase. The real risk is the 2,560 `max_output_tokens` cap on the comprehensive path — if thinking tokens consume much of this, the JSON response may be truncated.

**Is temperature enforced consistently?** Yes: 0.0 for Flash (realtime), 0.1 for Pro comprehensive, 0.2 for Pro pathway guidance, 0.2 for Pro session summary. Set at the config level in each respective handler.

#### On the Audio/Transcription Pipeline

**What other behavior appears to be AI-generated without clinical validation?** The `voice_activity_timeout` values (`speech_start_timeout: 60s`, `speech_end_timeout: 60s`) appear to be default/arbitrary values rather than clinically informed. In a therapy session where a patient falls silent for an extended period (dissociation, processing time, pause before disclosure), the implications of these timeout values have not been clinically validated.

The STT phrase boost list (see Section 2.1) is the primary example of AI-generated content applied without clinical review: terms appropriate for clinical literature were included alongside terms appropriate for session-layer speech, with no filtering criterion applied.

**Is the transcription output wired into the analysis pipeline in a way that would work live?** Yes, in the live configuration. The WebSocket hook receives transcripts and the analysis hook fires HTTP calls on transcript events. The two services communicate through the frontend, which is architecturally sound.

#### On Test Coverage

**What does `test_phase1_e2e.py` actually test?** Six test groups: (1) datastore accessibility — does not verify content, (2) document metadata and citation flow, (3) model version confirmation via constants and test API calls, (4) RAG guardrails — tests that `SAFETY_KEYWORDS` fire correctly in the live system, (5) citation extraction from grounding metadata, (6) frontend-backend integration connectivity. All tests require live GCP credentials.

**Are there other test files?** No. `test_phase1_e2e.py` is the only test file. `setup_services/evaluation/run_evaluation.py` is an evaluation harness (not a test suite) that runs clinical scenario transcripts through the live system and scores responses.

**Are tests isolated from production?** No. All tests make real API calls to the Gemini API, real queries to the Vertex AI Search datastores, and potentially write to Firestore. There is no test environment, no mocking of external services, and no cleanup of test data.

#### On the Frontend

**How much of the UI is wired to mock vs live?** The core session guidance UI (transcript display, alert panel, session metrics) switches cleanly via `USE_MOCK_MODE`. The scheduling system is always mock (no backend). The patient portal switches via a separate provider pattern (`ClientPortalRealProvider` vs `DummyClientPortalProvider`).

**Does `schedulingUtils.ts` serve the core clinical use case?** No. It serves the scheduling subsystem, which is not connected to the real-time session guidance use case and has no backend integration.

---

*End of Report · Ther-Assist AI Codebase Review · June 4, 2026*

---

## 7. Prompt Engineering and LLM Architecture Analysis

This section covers three related topics: the structural quality of the prompts in `constants.py`, the multithreaded RAG pre-fetch architecture, and the latency implications of the dual-model analysis design in `main.py`.

---

### 7.1 Prompt Structure and Attention Positioning

**Background: why prompt position matters.** Large language models apply attention across the full input, but attention weight is not uniform. Empirically, models attend most reliably to content at the very beginning and the very end of a prompt — the primacy and recency positions. Content in the middle of a long prompt is at elevated risk of being underweighted relative to its importance. This effect is well-documented and becomes more pronounced as prompt length increases. The prompts in this system are long — the comprehensive prompt is approximately 2,150 tokens before any variable substitution — which makes the positioning of each section a meaningful design decision.

---

#### `COMPREHENSIVE_ANALYSIS_PROMPT`

The prompt is structured as follows, with token positions based on measured character counts:

| Section | Position in prompt | Est. tokens |
|---|---|---|
| `<thinking>` block (risk definitions, calibration rules, 3-tier distinction) | 0–50% | ~1,100 |
| Role statement + RAG citation instruction | 51–54% | ~70 |
| Session context variables (phase, session type, concern, approach) | 54–56% | ~50 |
| **`{transcript_text}` — the actual clinical input** | **56–58%** | **variable** |
| RAG citation instructions (IMPORTANT block) | 58–62% | ~100 |
| JSON schema (all output fields) | 62–91% | ~600 |
| Speaker diarization instructions | 91–97% | ~140 |
| Final instructions | 97–100% | ~60 |

Several structural concerns arise from this layout:

**The transcript is buried at 57%.** The transcript is the primary clinical input — everything else in the prompt exists to help the model interpret it correctly. Placing it in the middle, between 4,939 characters of preamble and 3,667 characters of schema, means it occupies neither the primacy nor the recency position. The JSON schema — which is format boilerplate — is 38% of the prompt and sits after the transcript, occupying the recency position instead. The model's final attention before generating output is focused on field names and enumeration constraints rather than the patient's words.

**The `<thinking>` block is misnamed and misunderstood.** Gemini's `<thinking>` tags are *output* tokens produced by the model during its internal reasoning pass — they are not a recognized input directive. The XML tags here carry no special meaning to the model; they are processed as ordinary instructional prose. The content inside — risk level definitions, ambiguity calibration examples, the three-tier therapeutic context distinction — is genuinely valuable clinical guidance. But wrapping it in `<thinking>` tags does not make the model reason inside that framework; it simply buries 1,100 tokens of instructions in the first half of a long prompt where they are most at risk of attention decay by the time the transcript arrives. These calibration rules would be better placed immediately before the transcript, where they can directly condition the model's interpretation of what follows.

**Citation numbers are unverifiable.** The prompt instructs the model to embed inline citations (`[1]`, `[2]`, etc.) inside the `rationale` and `immediate_actions` fields of the JSON response. These citation numbers correspond to entries in `grounding_chunks` — the metadata Gemini attaches to a response when inline RAG tools retrieved source documents. The problem is that citation number assignment is internal to the Gemini grounding mechanism; the prompt cannot control which numbers appear. If the RAG datastores return empty results (as is currently unverified), the model will generate citation numbers that reference nothing. The JSON output will contain `[1]`, `[2]` markers with no corresponding `grounding_chunks` in the response, and there is no runtime check that verifies this correspondence. A clinician seeing a cited recommendation has no way of knowing whether the citation is grounded or hallucinated.

---

#### `REALTIME_ANALYSIS_PROMPT` and `REALTIME_ANALYSIS_PROMPT_STRICT`

The realtime prompt's structure is:

| Section | Position | Notes |
|---|---|---|
| Task framing (2 lines) | 0–2% | Only ~90 chars of actual instructions before data |
| `{transcript_text}` | 2–5% | Good — transcript is near the top |
| `{previous_alert_context}` | 5–7% | Good — immediately after transcript |
| Timing priority list (NOW/PAUSE/INFO) | 7–19% | |
| Categories list | 19–34% | |
| SAFETY-SPECIFIC INSTRUCTIONS | 34–51% | |
| DEDUPLICATION GUIDELINES | 51–64% | |
| IMPORTANT: bias-to-alert instruction | 64–70% | |
| JSON format schema | 70–100% | ~30% of prompt is output schema |

The transcript's placement near the top is correct and is the strongest structural feature of this prompt. However, several other issues exist:

**The prompt pushes hard toward always generating an alert, then relies on the frontend to suppress most of them.** The DEDUPLICATION GUIDELINES at 51% state: "Focus on what is NEW in the latest transcript — there is almost always something worth flagging." The IMPORTANT block at 64% states: "Only return empty JSON if the transcript is truly mundane small-talk with zero clinical relevance. In a therapy session, this is rare." These instructions, taken together, tell the model to treat the empty JSON return as an exceptional case. The frontend's 3-second hard block then silently discards most of the resulting alerts before display. The practical consequence is that the system burns Gemini Flash tokens and API quota generating guidance that is mostly deduped away. The better design would be to calibrate the prompt toward selective output, and let the LLM do the deduplication rather than the frontend.

**Eleven emphasis markers in a 971-token prompt.** The realtime prompt contains the following emphasis words: `Do not`, `always`, `always`, `IMPORTANT`, `Only`, `only`, `only`, `NOTE`, `IMPORTANT`, `NOTE`, `Always`. When every instruction is marked as important, none of them are. The final line — "IMPORTANT NOTE: Always refer to the patient as 'patient'" — is a style preference that carries the same emphasis weight as "IMPORTANT: ...crisis resources REQUIRED for all safety alerts." Safety-critical constraints and stylistic conventions are indistinguishable in priority. The guidance on crisis resources — which has direct clinical consequences if omitted — should be structurally separated from stylistic notes.

**`REALTIME_ANALYSIS_PROMPT_STRICT` is barely differentiated.** Both prompts share the same JSON schema, category list, safety instructions, deduplication rules, and final NOTE. The strict variant adds explicit timing threshold lists and a `60%+` confidence threshold, and labels the empty JSON format "use this most of the time." The key problem: both prompts are now used in a non-strict-first, strict-fallback pattern, but the prompts are evaluated in separate API calls. The second call (fallback) starts from a clean context — it is not influenced by the first call's result. The only purpose of the fallback is to produce an alert when the first call returned `{}`. But if the first call returned `{}` because the transcript genuinely had nothing to flag, the fallback call will face the same transcript and is likely to return `{}` again. The second call adds latency (~2s+) for minimal marginal benefit and is not currently cancellable once started.

---

#### `SESSION_SUMMARY_PROMPT`

The session summary prompt is better structured than the comprehensive prompt: the transcript appears at position 5%, giving it primacy. However, the JSON schema occupies 45% of the prompt and trails the transcript. The final instruction — "Only suggest [alternate therapy paths] with genuine clinical rationale — do not suggest alternatives just to fill the field" — appears at approximately 95% of the prompt. By recency standards this instruction is well-positioned, but its distance from the transcript means the model has processed the entire schema definition before reaching it, which can lead to schema-filling behavior despite the warning.

---

#### `SAFETY_CONTEXT_INJECTION`

The safety injection is prepended before both the RAG context block and the prompt template, placing it at position 0 of the assembled prompt — the correct priority position. However, the assembled order creates a gap between the safety flag and the transcript that triggered it:

```
[SAFETY FLAG ⚠️  ~120 tokens]
[RAG PASSAGES  ~variable, typically 100-300 tokens]
[Task framing  ~50 tokens]
[TRANSCRIPT]
```

By the time the model reaches the transcript, it has processed 270–500 tokens of other content since the safety flag. For a 120-token injection that says "keywords `want to die` were detected — YOU MUST generate a safety alert," the model must hold that instruction in attention across the intervening RAG passages before it reaches the utterance that triggered it. This is a known attention-distance risk for critical instructions. Placing the safety flag and the triggering transcript together — ideally immediately adjacent, with RAG passages elsewhere in the prompt — would be more reliable.

---

### 7.2 RAG Retrieval Architecture and the Pre-fetch Cache

The system uses two distinct RAG mechanisms depending on the analysis path:

**Realtime path (Flash):** RAG context is retrieved *before* the API call, in parallel background threads, then injected as plain text into the prompt. This avoids the 8–12 second latency of inline Vertex AI Search tool calls during Gemini inference.

**Comprehensive path (Pro):** RAG is handled as inline Vertex AI Search tools passed in the `config.tools` parameter. Gemini performs retrieval internally during inference. This adds latency but allows Gemini to ground citations in real time and attach `grounding_chunks` metadata to the response.

The pre-fetch cache is designed to amortize the Discovery Engine query cost across multiple analysis calls. The cache has a 25-second TTL and is keyed on `session_type + hash(last 500 chars of transcript)`.

**The cache is effectively inoperative for the realtime path.** Analysis triggers every 10 words — at a typical combined speaking rate of 150 words per minute, that is approximately every 4 seconds. The transcript changes with every trigger because new words are appended. The cache key is derived from the last 500 characters of the transcript, which changes on every trigger. Every realtime analysis call therefore results in a cache miss and makes 4 parallel Discovery Engine queries (for a CBT session: `ebt-corpus`, `safety-crisis`, `cbt-corpus`, `ba-corpus`).

The 25-second TTL was presumably intended to prevent redundant queries within a short window. But because the hash of a growing transcript never repeats, the TTL never becomes the binding constraint — the hash always fails first. The cache as implemented provides latency benefit only in the degenerate case where the patient is completely silent for more than 25 seconds, which by definition produces no new transcript and therefore no analysis trigger.

In practice, each realtime analysis call adds 400–800ms of Discovery Engine latency (best case, warm GCP infrastructure) or up to 10 seconds per thread (the join timeout) when infrastructure is cold or degraded. This is additive to the Flash inference latency.

---

### 7.3 Latency Budget and Concurrent Request Load

#### Realtime path latency

The synchronous steps per realtime analysis call are:

| Step | Estimated time |
|---|---|
| HTTP receive + JSON parse | ~1ms |
| `detect_safety_keywords` (string scan) | ~1ms |
| `format_transcript_segment` | ~1ms |
| `prefetch_rag_context` — cache miss (4 parallel queries) | 400–800ms warm; up to 10,000ms cold |
| Prompt assembly | ~1ms |
| Gemini Flash TTFT (time to first token) | 800–2,000ms typical |
| Flash response stream completion | 500–1,500ms |
| JSON parse + yield | ~5ms |
| **Total (cache miss, warm)** | **~1,700–4,300ms** |
| **Total (cache miss, cold)** | **~3,000–13,000ms** |

The system targets sub-3-second realtime latency. This is achievable on a warm cache hit path (which rarely occurs, as analyzed above) and borderline on a cache-miss path under warm GCP conditions. Under cold infrastructure or Discovery Engine degradation, the realtime path can exceed 10 seconds — making it clinically useless for in-session guidance.

#### Comprehensive path latency

The comprehensive path uses Gemini 2.5 Pro with a thinking budget of 8,192 tokens (escalating to 16,384 on safety keyword detection) and inline RAG tool retrieval. Typical end-to-end latency is 15–25 seconds. This is not problematic on its own — the comprehensive analysis is intended as a background update, not an immediate alert. However, it has implications for concurrent request load.

#### Concurrent Pro calls accumulate without bound

The frontend fires both realtime and comprehensive calls simultaneously on every 10-word trigger. At 150 words per minute, this is 15 triggers per minute — one every 4 seconds. Each trigger starts one Flash call (which completes in ~3–4s) and one Pro call (which takes ~15–25s). The Pro call is not cancelled when a new trigger fires; it runs to completion regardless.

At steady-state conversation pace, 3–5 Pro calls are in flight simultaneously at any given moment. There is no queue, no backpressure, no stale-call cancellation, and no rate limit applied at the application layer. The Gemini API's project-level rate limits are the only constraint. When those limits are reached, calls will begin failing with quota errors — silently, from the clinician's perspective, since failed comprehensive calls are not displayed as errors in the UI.

The frontend's 3-second hard block prevents the *display* of alerts more frequently than once every 3 seconds, but it does not prevent the *firing* of `analyzeSegment()`. The HTTP calls are made unconditionally on each 10-word trigger; deduplication only applies to what is rendered after the response arrives.

#### Practical consequences

For a 50-minute session at a typical speaking pace, the system will make approximately 750 realtime Flash calls and 750 Pro calls. Most of the realtime results will be deduplicated and never displayed. All 750 Pro calls will run to completion in the background regardless of whether their results are used. This is a significant operational cost and API load for a session involving one therapist and one patient.

---

### 7.4 The Dual-Model Strategy: What It Gets Right and What It Risks

The decision to split realtime (Flash, speed-optimized) from comprehensive (Pro, quality-optimized) is architecturally sound. Flash handles the urgent, immediate alert needs — including safety keywords — at 2–4 second latency. Pro handles deeper clinical analysis that can tolerate a 15–25 second delay. The `job_id` pairing mechanism allows the frontend to correlate corresponding realtime and comprehensive responses and update the display coherently.

What the architecture does not address:

**Stale comprehensive results.** A Pro call started at T=0s completes at T=20s. In those 20 seconds, the conversation has advanced by approximately 50 words (3–4 more analysis triggers). The comprehensive analysis at T=20s reflects the transcript state from T=0s, but it arrives and updates the display after the conversation has moved on. There is no mechanism to mark a comprehensive result as stale, to timestamp it relative to the current transcript position, or to suppress it if a newer comprehensive call has already rendered.

**No cancellation of in-flight calls.** If the therapist ends the session, navigates away, or if a critical safety alert fires from the realtime path, there is no mechanism to cancel the 3–5 in-flight Pro calls. They run to completion, consuming API quota and generating results that will never be read.

**The fallback retry doubles Flash latency.** When the first Flash call returns `{}` (no alert), the system immediately fires a second Flash call with the strict prompt. For transcripts that genuinely have nothing to flag, both calls will return `{}`, and the combined latency is 2× the single-call latency (~6–8 seconds) before the frontend receives a confirmed empty response.

---

### 7.5 Summary of Prompt Engineering Recommendations

| Issue | Risk | Recommended Fix |
|---|---|---|
| Transcript at 57% of comprehensive prompt | Clinical input in low-attention zone | Move transcript to near the top; move `<thinking>` calibration rules to immediately before it |
| `<thinking>` tags have no special meaning to Gemini | Calibration rules treated as ordinary text | Rename to `## RISK ASSESSMENT FRAMEWORK` or similar; restructure as a numbered reference section |
| Citation instructions with no enforcement | Model hallucinates `[1],[2]` when RAG is empty | Add runtime check: if `grounding_chunks` is empty, strip citation markers from output before sending to frontend |
| 11 emphasis markers undifferentiate safety-critical from stylistic | Safety instructions not structurally prioritized | Reserve `IMPORTANT:` / `CRITICAL:` for safety-relevant instructions only; use inline prose for style guidance |
| Bias-toward-alert instructions generate alerts that frontend discards | Wasted API calls and tokens | Rebalance toward selective output; let the LLM deduplicate rather than the frontend |
| STRICT and non-strict prompts barely differentiated | Fallback adds latency without benefit | Either meaningfully differentiate them or eliminate the fallback; consider a single well-calibrated prompt |
| Safety injection separated from triggering transcript by 170+ tokens | Attention gap between flag and evidence | Move the safety flag to immediately precede the transcript, after RAG passages |
| RAG prefetch cache invalidated on every call | Cache provides no benefit; 4 queries per realtime call | Fix cache key to not include fast-changing transcript tail; or move RAG to a session-level pre-warm |

