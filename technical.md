# Backend Rewrite — Technical Rationale and Scope

**Author:** James Chen  
**Date:** 2026-06-11  
**Audience:** Engineers, technical reviewers  
**Branch:** `backend_unit`

---

## 1. Situation

A full static code analysis and multi-session audit of the `gcaimh-ther-assist` backend was completed in early June 2026. The codebase is substantially more feature-complete than most early-stage projects of comparable age, and it served its intended purpose well: it enabled functioning demonstrations and provided a concrete foundation for clinical stakeholder feedback at a phase where iteration speed mattered more than architectural stability. The development model — AI-assisted code generation with aggressive feature delivery — was a reasonable response to those constraints.

However, that model front-loads delivery velocity at the cost of structural coherence. The resulting accumulation of technical debt has reached a threshold where targeted rewrite of the backend core delivers better expected return than continued incremental patching. Specifically: the codebase contains multiple independent defects that each require understanding adjacent code to fix safely, a corpus that is structured incorrectly for its purpose, and feature scope that has never been confirmed against the clinical requirements it is meant to serve. The findings below describe the specific issues and the focused four-week project designed to address them.

---

## 2. Technical Findings

### 2.1 Corpus and RAG Infrastructure

The five Vertex AI Search datastores (`ebt-corpus`, `safety-crisis`, `cbt-corpus+ba-corpus`, `dbt-corpus`, `ipt-corpus`) were configured with static ingestion scripts and a fixed set of PDFs. Two separate problems compound each other.

**Content curation problem.** The majority of PDFs loaded into the modality-specific corpora are randomized controlled trial papers and efficacy comparison studies — e.g., "CBT is more effective than IPT for Major Depressive Disorder in adults." This content answers the wrong question. During a live session, the RAG query is looking for *how to execute a technique* — the cognitive restructuring steps, the behavioral activation scheduling protocol, the safety plan template. RCT abstracts contain no procedural content. They will either return zero useful passages or return statistical findings that the model has no clinical use for in a realtime guidance context. The corpus needs to be rebuilt from technique manuals, session guides, and clinical protocols.

**Indexing and metadata problem.** The setup scripts used Vertex AI's layout-aware PDF chunking with default metadata fields. Therapy manuals are structured around techniques, modalities, and session phases — none of which are captured in the default metadata schema. As a result, a query for "grounding exercise for dissociation" matches on keyword overlap across chunks rather than on semantically tagged technique type. This produces retrieval noise and inconsistent citation provenance. The metadata schema needs to be redesigned before re-ingestion, not after.

**Ingestion verification gap.** The existing test suite (`test_datastores` in `test_phase1_e2e.py`) confirms only that a datastore returns *a* response. It does not verify that `grounding_chunks` contain passages from the expected source PDFs. A datastore that was created but not populated, or that contains only partial ingestion, passes this test. There is no runtime check — if RAG returns zero chunks, the LLM generates guidance from its training data alone with no warning surfaced to the system log or the frontend.

**Forward-looking design.** Corpus curation will arrive in sporadic batches — a new manual here, a protocol update there. The current design requires a manual re-run of static ingestion scripts per addition. A redesign should treat ingestion as a first-class API operation: upload a document with typed metadata, trigger chunking, validate retrieval before committing. This is a prerequisite for sustainable corpus management.

---

### 2.2 Code Complexity and Auditability

`therapy-analysis-function/main.py` measures at **1,433–1,660 SLOC** with a **cyclomatic complexity of 174**. For reference, industry heuristics flag CC > 50 for a single file as requiring dedicated specialist review, and CC > 100 as indicating an architecture that has grown past the point of safe iterative modification. At CC=174, the risk of an unintended interaction between a patch and an unexercised code path is not theoretical.

`streaming-transcription-service/main.py` is CC=107 at 636 SLOC.

The git history shows multiple commits touching 1,000+ lines across multiple files and multiple features simultaneously. This is a predictable consequence of AI-assisted feature development — the generation unit is the feature, not the function. The practical consequence is that ownership attribution and regression analysis are difficult: it is not possible to answer the question "did this commit change the behavior of the safety scanner?" without reading the entire diff.

There are also function stubs and complete implementations for features that were never approved: a fine-tuning pipeline, a multi-session Vertex AI agent, and a comparative study harness covering five LLM providers. These are in `main.py` and in `setup_services/` respectively. Their presence in the active codebase means every future code reader and tool call must account for them. Notably, the multi-session agent reads from a `session_summaries` Firestore collection while the production code writes to `sessions` — if the agent were ever deployed it would silently return empty history.

---

### 2.3 Specific Design Defects

The following defects were identified during a preliminary code review of the core backend services. This review was not exhaustive — several files, particularly in the portal layer and the frontend, were read at summary depth only (head-only passes on files exceeding 200 lines). The issues below are representative symptoms of a codebase that accumulated faster than it was audited, not a complete inventory. A full review would likely surface additional issues in areas that received less attention.

**Both caching systems deliver zero benefit in production.**

- *Gemini context cache (comprehensive path):* `_get_or_refresh_cached_content()` is never called. Line 1375 reads: `cached_content_name = None if rag_tools else _get_or_refresh_cached_content()`. Because `rag_tools` is always non-empty (the Gemini API prohibits `tools` and `cached_content` in the same request), `context_cache_hit` is always `False`. The stated ~75% Pro model input token savings are never realized. The cache infrastructure — TTL refresh logic, the `_cached_content_resource` global — runs correctly but is never consulted.

- *RAG prefetch cache (realtime path):* Expected cache hit rate in production is approximately 0%. The cache key is `hash(transcript_text[-500:])`. At 130–150 wpm, 500 characters represents approximately 36 seconds of speech. Every analysis call is triggered by a new completed utterance, which always shifts the last 500 characters — the hash changes on every call. The 25-second TTL fails independently as a second constraint: most inter-utterance intervals exceed 25 seconds. The stated "2–4 second" realtime latency assumes cache hits; actual measured latency is 3–11 seconds because `prefetch_rag_context()` blocks synchronously on all four Discovery Engine threads before the prompt is assembled.

**`MODALITY_RAG_MAP` is defined in two unsynchronized locations.** A module-level dict of `Tool` objects in `main.py` drives the comprehensive path. A separate inline `modality_map` dict of plain strings inside `prefetch_rag_context()` drives the realtime path. These are not derived from a shared source. A future modality addition requires updating both; a missed update produces silent inconsistency between the two analysis paths.

**`max_output_tokens=2560` on the comprehensive path is too small.** Gemini 2.5 Pro with `thinking_budget=8192` must produce thinking tokens plus the full structured JSON output (session metrics, pathway indicators, pathway guidance, diarized transcript) within this envelope. The JSON repair logic (`extract_json_from_text`) attempts to close truncated output but is not reliable for large objects. The session summary path uses 4,096 tokens and serves as the correct reference.

**Safety scanner not applied uniformly.** `detect_safety_keywords` is called in `handle_segment_analysis` but not in `handle_pathway_guidance` or `handle_session_summary`. Safety keyword detection is absent for two of the four analysis handlers.

---

### 2.3.1 Prompt Structure and Real-Time Latency Constraints

The prompt templates in `constants.py` contain structural decisions that work against the model's attention and against the timing requirements of a real-time system. These are design issues, not content issues — the clinical knowledge embedded in the prompts is generally sound. The problem is the order and emphasis in which that knowledge is presented to the model.

**Attention positioning in `COMPREHENSIVE_ANALYSIS_PROMPT`.** Large language models apply attention non-uniformly across a long input. Empirically, content at the beginning (primacy) and end (recency) of a prompt is attended to most reliably; content in the middle is at elevated risk of being underweighted. The prompt's structure works against this:

| Section | Position | Est. tokens |
|---|---|---|
| `<thinking>` block — risk definitions and calibration rules | 0–50% | ~1,100 |
| Role statement, session context | 51–56% | ~120 |
| **Transcript — the primary clinical input** | **56–58%** | variable |
| RAG citation instructions | 58–62% | ~100 |
| JSON output schema — format boilerplate | 62–91% | ~600 |
| Speaker diarization and final instructions | 91–100% | ~200 |

The transcript — everything the analysis is meant to reason about — sits at the 57th percentile of a ~2,150 token prompt, occupying neither the primacy nor recency position. The JSON output schema, which is format boilerplate, occupies the recency position: the model's final attention before generating output is on field names and enumeration constraints rather than patient speech.

The `<thinking>` XML tags at the top of the prompt carry no special meaning to Gemini as input. They are processed as ordinary instructional prose, not as a reasoning directive. The 1,100-token calibration block they wrap is valuable clinical guidance — risk definitions, the three-tier therapeutic context distinction — but its placement at positions 0–50% means those calibration rules are furthest from the transcript they are meant to govern. A model that has processed 2,000 tokens of other content between the calibration rules and the transcript it is calibrating against is not in the same attentional state as a model that reads the rules immediately before the evidence.

**Emphasis saturation in `REALTIME_ANALYSIS_PROMPT`.** The 971-token realtime prompt contains eleven emphasis markers: `Do not`, `always`, `always`, `IMPORTANT`, `Only`, `only`, `only`, `NOTE`, `IMPORTANT`, `NOTE`, `Always`. When every instruction is marked as important, the markup loses signal value. Safety-critical constraints and stylistic conventions carry identical visual weight. The instruction that crisis resources are required for all safety alerts — which has direct clinical consequences if omitted — is structurally indistinguishable from the instruction to refer to the patient as "patient" rather than "client."

**Bias-to-alert instruction creates downstream deduplication load.** The realtime prompt contains the instruction: "In a therapy session, [returning empty JSON] is rare." The intent is to prevent the model from under-alerting. The effect is that the model generates an alert on almost every call regardless of clinical relevance, and the frontend's 3-second hard block and category throttle windows silently discard most of them. At 130–150 wpm with a 10-word trigger interval, this generates approximately 750 Flash API calls per 50-minute session, the majority of which produce output that is never shown. Calibrating the prompt toward selective output — and letting the LLM do the deduplication — is more efficient and produces lower false-positive pressure on the clinician's attention.

**Real-time concurrency accumulates without bound.** The frontend fires both realtime (Flash) and comprehensive (Pro) calls on every 10-word trigger. At typical speaking pace this is one trigger every 4 seconds. Flash calls complete in approximately 3–4 seconds. Pro calls take 15–25 seconds. There is no cancellation of in-flight Pro calls when a new trigger fires — at steady-state conversation pace, 3–5 Pro calls are simultaneously in flight. There is no queue, no backpressure, and no stale-result suppression. A Pro result that arrives 20 seconds after its trigger reflects a transcript state from 50+ words ago, but the system has no mechanism to mark it as stale or to prefer a newer result if one has since arrived. The Gemini API's project-level rate limits are the only constraint; when those are reached, calls begin failing silently.

**Safety context injection gap.** When `detect_safety_keywords` fires, a `SAFETY_CONTEXT_INJECTION` block is prepended to the prompt. The assembled order is: safety flag (120 tokens) → RAG passages (100–300 tokens) → task framing (50 tokens) → transcript. The safety flag and the transcript that triggered it are separated by 270–500 tokens of other content. For an injection that instructs the model to generate a safety alert, the model must hold that instruction in attention across the intervening RAG passages before it reaches the utterance that triggered it. Placing the flag immediately adjacent to the transcript, with RAG passages elsewhere, would reduce this attention gap.

---

### 2.4 Frontend Review Scope Note

The preliminary code review concentrated on the backend services. Frontend TypeScript files were read at partial depth. `smartMockAnalysis.ts` and the audio streaming hook were fully reviewed; the remaining frontend components received head-only passes. The note below reflects what was confirmed during that limited review. The frontend may have additional issues — or may be in better shape than the backend — in areas that were not examined.

**`smartMockAnalysis.ts` is bundled into the production build.** If `VITE_ANALYSIS_API` is unconfigured or unavailable in a deployed environment, the frontend silently falls back to a client-side keyword matcher that generates realistic-looking safety alerts — including `Suicidal Ideation Detected` — with no backend validation. There is no visual indicator to the clinician that the system has fallen back to mock mode.

---

### 2.5 Feature Feasibility Constraints

**Sentiment analysis.** The current architecture assesses emotional state entirely from speech-to-text output — text alone. The empirical clinical literature places nonverbal communication (posture, eye contact, tone, inflection, facial expression, proxemics) at 50–90% of the information a therapist acts on in session. Text-only sentiment analysis can detect lexical distress markers but cannot distinguish flat affect from calm, or a nervous laugh from genuine affect. The approach systematically underperforms on the most clinically significant presentations — dissociation, flat affect, forced compliance — precisely because those presentations are defined by a mismatch between verbal content and nonverbal expression. A text-only sentiment field in the API response implies a capability the architecture cannot deliver. This is an architectural constraint, not a tuning problem, and requires a deliberate multi-modal design decision before further investment in the feature is appropriate.

**Multi-modality.** The system implements three-modality routing (CBT, DBT, IPT) with five RAG corpora. This is the largest single driver of `main.py`'s CC=174 complexity score. Whether this capability was ever requested by the clinical stakeholder is an open question. If the pilot scope is CBT-only, approximately 30–40 lines of dispatch logic, three corpus setup scripts, and three corpus directories can be removed, meaningfully reducing complexity before any other refactoring begins.

---

## 3. Rewrite Scope and Workflow

The rewrite is scoped to the backend core and does not attempt to take ownership of the full existing codebase. The workflow proceeds in dependency order:

### Phase 1 — I/O Endpoints and Contracts (Weeks 1–2)

Define and stabilize the API surface before any logic is written. This includes:

- Clean HTTP request/response schemas for the analysis endpoint (`analyze_segment`, `session_summary`)
- Explicit error envelope with distinguishable failure modes (auth failure, RAG failure, LLM failure, parse failure)
- WebSocket frame specification for the transcription service
- Authentication enabled and verified from day one — not deferred

The I/O surface is the integration contract with the frontend. Locking it before implementing logic prevents a class of rework where logic must be refactored to accommodate a changed interface.

### Phase 2 — Corpus Ingestion API and Metadata Schema (Weeks 1–3, overlaps Phase 1)

Design and implement a corpus ingestion endpoint that:

- Accepts a document upload with required typed metadata (modality, content type, technique tags, source)
- Validates that document chunks are retrievable after ingestion before returning success
- Supports incremental additions without a full re-ingest
- Rejects documents that don't match the expected content type (technique guide vs. efficacy study)

Re-ingest the corpora against the new schema after it is validated.

### Phase 3 — CI Benchmarking Framework (Weeks 2–3)

Before any prompt engineering or analysis logic changes, establish the measurement infrastructure:

- Unit tests for all pure functions (safety scanner, JSON extraction, phase detection) with zero external dependencies
- Eval harness: 9 fixed clinical scenarios with expected outputs, runnable against a local server instance
- Metrics: safety recall (target: 1.0, zero tolerance), RAG retrieval provenance (do grounding chunks come from the correct corpus documents?), latency budget (realtime path target: sub-3s at P95), cache hit rate (target: >50% after cache key fix)

No analysis logic change is accepted without running this harness before and after. Safety recall is a non-negotiable gate.

### Phase 4 — Core Analysis Logic (Weeks 3–4)

With I/O contracts, corpus, and measurement framework in place, implement the analysis logic:

- Fix the RAG cache key (hash the last-200-word query window, not the last-500 characters of raw transcript text; extend TTL to 90 seconds)
- Re-enable the Gemini context cache on the comprehensive path by switching from inline RAG tools to pre-fetched text injection
- Apply safety scanner uniformly across all analysis handlers
- Restructure prompts with transcript in primacy position; move calibration rules to immediately precede the transcript
- Raise `max_output_tokens` on the comprehensive path to match the session summary path (4,096)
- Implement runtime RAG provenance validation

The order is deliberate: cache fixes and prompt restructuring are only meaningful against a corpus that retrieves the correct content. Building on a bad corpus produces optimized garbage.

### Phase 5 — Therapeutic Conversation Testing (Week 4)

Run the eval harness against real or realistic therapeutic transcript segments. Compare baseline and candidate prompt configurations using the established metrics. Identify cases where the analysis is systematically wrong and iterate on prompt structure.

---

## 4. Month Duration Justification

Four weeks is the minimum credible duration given the serial dependencies in the workflow:

**The corpus must precede the analysis logic.** There is no value in tuning prompt structure or cache behavior against a corpus that retrieves RCT abstracts when it should retrieve technique protocols. The corpus redesign — metadata schema, ingestion API, validation, re-ingest — is a self-contained workstream that cannot be parallelized with the logic that depends on it.

**The measurement framework must precede any prompt changes.** Without a repeatable eval harness, prompt changes are guesses. Building the harness takes time proportional to the number of clinical scenarios covered (minimum 9, covering safety, technique, and pathway change cases). Clinical scenario content requires review before use as an automated regression gate.

**The I/O contracts must precede the logic.** Schema design decisions made under time pressure accumulate technical debt immediately. One week on interface design is cheaper than two weeks of refactoring after the fact.

**Existing defects require verification, not just patching.** The cache bugs and the prompt structure problems are each individually fixable in hours. But each fix needs to be confirmed against the eval harness. A cache key fix that does not produce a measurably positive hit rate is not done.

**No parallel acceleration path exists for this scope.** These phases have strict input/output dependencies. Adding engineers to Phase 3 before Phase 2 produces rework, not acceleration.

---

## 5. What Is Explicitly Out of Scope

- Frontend modifications
- Portal handlers (homework, interventions, questionnaires, journal)
- Multi-session agent architecture
- Fine-tuning pipeline
- Comparative study harness
- Scheduling system
- Patient portal frontend

Reintegration of features from the existing codebase will follow after the core is stable and the eval harness is in place to prevent regression.
