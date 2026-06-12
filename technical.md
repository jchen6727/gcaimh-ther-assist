# Backend Rewrite — Technical Rationale and Scope

**Author:** James Chen  
**Date:** 2026-06-11  
**Audience:** Engineers, technical reviewers  
**Branch:** `backend_unit`

---

## 1. Situation

A full static code analysis and multi-session audit of the `gcaimh-ther-assist` backend was completed in early June 2026. The findings document a codebase that is substantially more feature-complete than most early-stage projects, but contains a pattern of issues that make incremental patching a worse return on investment than a scoped, ground-up rewrite of the backend core. #TODO insert here: while this facilitated early mockups and demos, the accumulation of technical debt within the software repository requires rewrite over refactor among several components, most critical being the backend. "This document describes the specific technical findings that justify that decision and the scope and schedule of the focused rewrite.

---

## 2. Technical Findings

### 2.1 Corpus and RAG Infrastructure

The five Vertex AI Search datastores (`ebt-corpus`, `safety-crisis`, `cbt-corpus+ba-corpus`, `dbt-corpus`, `ipt-corpus`) were configured with static ingestion scripts and a fixed set of PDFs. Two separate problems compound each other.

**Content curation problem.** The majority of PDFs loaded into the modality-specific corpora are randomized controlled trial papers and efficacy comparison studies — e.g., "CBT is more effective than IPT for Major Depressive Disorder in adults." This content answers the wrong question. During a live session, the RAG query is looking for *how to execute a technique* — the cognitive restructuring steps, the behavioral activation scheduling protocol, the safety plan template. RCT abstracts contain no procedural content. They will either return zero useful passages or return statistical findings that the model has no clinical use for in a realtime guidance context. The corpus needs to be rebuilt from technique manuals, session guides, and clinical protocols.

**Indexing and metadata problem.** The setup scripts used Vertex AI's layout-aware PDF chunking with default metadata fields. Therapy manuals are structured around techniques, modalities, and session phases — none of which are captured in the default metadata schema. As a result, a query for "grounding exercise for dissociation" will match on keyword overlap across chunks rather than on semantically tagged technique type. This produces retrieval noise and inconsistent citation provenance. The metadata schema needs to be redesigned before re-ingestion, not after.

**Ingestion verification gap.** The existing test suite (`test_datastores` in `test_phase1_e2e.py`) confirms only that a datastore returns *a* response. It does not verify that `grounding_chunks` contain passages from the expected source PDFs. A datastore that was created but not populated, or that contains only partial ingestion, passes this test. There is no runtime check — if RAG returns zero chunks, the LLM generates guidance from its training data alone with no warning surfaced to the system log or the frontend.

**Forward-looking design.** Corpus curation will arrive in sporadic batches — a new manual here, a protocol update there. The current design requires a manual re-run of static ingestion scripts per addition. A redesign should treat ingestion as a first-class API operation: upload a document with typed metadata, trigger chunking, validate retrieval before committing. This is a prerequisite for sustainable corpus management.

---

### 2.2 Code Complexity and Auditability

`therapy-analysis-function/main.py` measures at **1,433–1,660 SLOC** with a **cyclomatic complexity of 174**. For reference, industry heuristics flag CC > 50 for a single file as requiring dedicated specialist review, and CC > 100 as indicating an architecture that has grown past the point of safe iterative modification. At CC=174, the risk of an unintended interaction between a patch and an unexercised code path is not theoretical.

`streaming-transcription-service/main.py` is CC=107 at 636 SLOC.

The git history shows multiple commits touching 1,000+ lines across multiple files and multiple features simultaneously — a pattern associated with AI-generated code that was not incrementally reviewed. This makes ownership attribution and regression analysis difficult. It is not possible to answer the question "did this commit change the behavior of the safety scanner?" without reading the entire diff.

There are function stubs and complete function implementations for features that were never approved (fine-tuning pipeline, multi-session Vertex AI agent, comparative study harness across five LLM providers). These are in the main `main.py` and in `setup_services/` respectively. Their presence in the active codebase means every future code reader and every future tool call must account for them. The multi-session agent reads from a `session_summaries` Firestore collection; the production code writes to `sessions`. If the agent were ever deployed it would silently return empty history.

---

### 2.3 Specific Design Defects

The audit produced a catalog of concrete, named defects. Including:

#TODO removed firebase notes, someone on team is already aware of it.

#TODO emphasize these issues as symptoms found on preliminary code review and do not encompass other issues within the code base that did not receive as much attention.

#TODO research and add element on prompt engineering itself, where the language of constants.py can cause the LLM to deprioritize, de-emphasize issues, or cause it to exceed real time analysis constraints, (the prompt is not structured for the critical elements to be thought of first)


- *Gemini context cache (comprehensive path):* `_get_or_refresh_cached_content()` is never called. Line 1375: `cached_content_name = None if rag_tools else _get_or_refresh_cached_content()`. Because `rag_tools` is always non-empty (the Gemini API prohibits `tools` and `cached_content` in the same request), `context_cache_hit` is always `False`. The stated ~75% Pro model input token savings are never realized. The cache infrastructure (TTL refresh logic, `_cached_content_resource` global) runs correctly but is never consulted.

- *RAG prefetch cache (realtime path):* Expected cache hit rate in production is approximately 0%. The cache key is `hash(transcript_text[-500:])`. At 130–150 wpm, 500 characters represents approximately 36 seconds of speech. Every analysis call is triggered by a new completed utterance, which always shifts the last 500 characters. The hash changes on every call. The 25-second TTL fails independently as a second constraint: most inter-utterance intervals exceed 25 seconds. The stated "2–4 second" realtime latency assumes cache hits; actual measured latency is 3–11 seconds because `prefetch_rag_context()` blocks synchronously on all four Discovery Engine threads before the prompt is assembled.

**`MODALITY_RAG_MAP` is defined in two unsynchronized locations.** A module-level dict of `Tool` objects in `main.py` drives the comprehensive path. A separate inline `modality_map` dict of plain strings inside `prefetch_rag_context()` drives the realtime path. These are not derived from a shared source. A future modality addition will require updating both; a missed update produces silent inconsistency between the two analysis paths.

**`max_output_tokens=2560` on the comprehensive path is too small.** Gemini 2.5 Pro with `thinking_budget=8192` must produce thinking tokens plus the full structured JSON output (session metrics, pathway indicators, pathway guidance, diarized transcript) within this envelope. The JSON repair logic (`extract_json_from_text`) attempts to close truncated output but is not reliable for large objects. The session summary path uses 4,096 tokens; the comprehensive path should match.

**Safety scanner not applied uniformly.** `detect_safety_keywords` is called in `handle_segment_analysis` but not in `handle_pathway_guidance` or `handle_session_summary`. Safety keyword detection is absent for two of the four analysis handlers.

**Prompt structure attenuates clinical input.** In `COMPREHENSIVE_ANALYSIS_PROMPT`, the transcript — the primary clinical input — sits at the 57th percentile of the prompt. A 1,100-token `<thinking>` block (which Gemini processes as ordinary instructional text, not a special reasoning directive) occupies positions 0–50%. The JSON output schema — format boilerplate — occupies positions 62–91% and sits in the recency position the model attends to most reliably. Calibration rules are most useful immediately before the evidence they are meant to govern; they should precede the transcript, not precede everything else.

#TODO since this falls into the frontend, we can add a snippet on how we did not perform comprehensive review of the frontend, it may be in a better/or worse state.

**`smartMockAnalysis.ts` is bundled into the production build.** If `VITE_ANALYSIS_API` is unconfigured or unavailable, the frontend silently falls back to a client-side keyword matcher that generates realistic-looking safety alerts including `Suicidal Ideation Detected` with no backend validation. There is no visual indicator to the clinician that the system has fallen back to mock mode.

---

### 2.4 Feature Feasibility Constraints

**Sentiment analysis.** The current architecture performs sentiment and emotional state assessment entirely from speech-to-text output — text alone. The empirical clinical literature places nonverbal communication (posture, eye contact, tone, inflection, facial expression, proxemics) at 50–90% of the information a therapist acts on in session. Text-only sentiment analysis can detect lexical distress markers, but cannot distinguish flat affect from calm, or a nervous laugh from genuine affect. The current approach will systematically underperform on the most clinically significant cases — dissociation, flat affect, forced compliance — precisely because those presentations are defined by a mismatch between verbal content and nonverbal expression. A text-only sentiment field in the API response implies a capability the architecture cannot deliver. This is an architectural constraint, not a tuning problem, and it requires a deliberate multi-modal design decision before investment in the feature is appropriate.

**Multi-modality.** The system implements three-modality routing (CBT, DBT, IPT) with five RAG corpora. This is the largest single driver of `main.py`'s CC=174 score. Whether this capability was ever requested by the clinical stakeholder is an open question. If the pilot scope is CBT-only, approximately 30–40 lines of dispatch logic, three corpus setup scripts, and three corpus directories can be removed, meaningfully reducing complexity before any other refactoring begins.

---

## 3. Rewrite Scope and Workflow

The rewrite is scoped to the backend core and does not attempt to take ownership of the full existing codebase. The workflow proceeds in dependency order:

### Phase 1 — I/O Endpoints and Contracts (Weeks 1–2)

Define and stabilize the API surface before any logic is written. This includes:

- Clean HTTP request/response schemas for the analysis endpoint (`analyze_segment`, `session_summary`)
- Explicit error envelope with distinguishable failure modes (auth failure, RAG failure, LLM failure, parse failure)
- WebSocket frame specification for the transcription service
- Authentication enabled and verified from day one — not deferred

The I/O surface is the integration contract with the frontend. Getting this right before implementing logic prevents a class of rework where logic must be refactored to accommodate a changed interface.

### Phase 2 — Corpus Ingestion API and Metadata Schema (Weeks 1–3, overlaps Phase 1)

Design and implement a corpus ingestion endpoint that:

- Accepts a document upload with required typed metadata (modality, content type, technique tags, source)
- Validates that the document chunks are retrievable after ingestion before returning success
- Supports incremental additions without a full re-ingest
- Rejects documents that don't match the expected content type (technique guide vs. efficacy study)

Re-ingest the corpora against the new schema after it is validated.

### Phase 3 — CI Benchmarking Framework (Weeks 2–3)

Before prompt engineering or analysis logic is written, establish the measurement infrastructure:

- Unit tests for all pure functions (safety scanner, JSON extraction, phase detection) with zero external dependencies
- Eval harness: 9 fixed clinical scenarios with expected outputs, runnable against a local server instance
- Metrics: safety recall (target: 1.0, zero tolerance), RAG retrieval provenance (do grounding chunks come from the correct corpus documents?), latency budget (realtime path target: sub-3s at P95), cache hit rate (target: >50% after cache key fix)

No analysis logic change is accepted without running this harness before and after. Safety recall is a non-negotiable gate.

### Phase 4 — Core Analysis Logic (Weeks 3–4)

With the I/O contracts, corpus, and measurement framework in place, implement the analysis logic:

- Fix the RAG cache key (hash the last-200-word query window, not the last-500 characters of raw transcript text; extend TTL to 90 seconds)
- Fix or re-enable the Gemini context cache on the comprehensive path
- Apply safety scanner uniformly across all analysis handlers
- Restructure prompts with transcript in primacy position
- Raise `max_output_tokens` on the comprehensive path
- Implement runtime RAG provenance validation

The order here is deliberate: cache fixes and prompt restructuring are only meaningful if the corpus they operate against is correct. Building on a bad corpus produces optimized garbage.

### Phase 5 — Therapeutic Conversation Testing (Week 4)

Run the eval harness against real or realistic therapeutic transcript segments. Compare baseline and candidate prompt configurations using the established metrics. Identify cases where the analysis is systematically wrong and iterate on the prompt structure.

---

## 4. Month Duration Justification

Four weeks is the minimum credible duration given the serial dependencies in the workflow:

**The corpus must precede the analysis logic.** There is no value in tuning prompt structure or cache behavior against a corpus that retrieves RCT abstracts when it should retrieve technique protocols. The corpus redesign — schema, ingestion API, validation, re-ingest — is a self-contained workstream that cannot be parallelized with the logic that depends on it.

**The measurement framework must precede any prompt changes.** Without a repeatable eval harness, prompt changes are guesses. Building the harness takes time proportional to the number of clinical scenarios that must be covered (minimum 9, covering safety, technique, and pathway change cases). Clinical scenario content must be reviewed before use as a regression gate.

**The I/O contracts must precede the logic.** Schema design decisions made under time pressure tend to accumulate technical debt immediately. One week on interfaces before any logic is cheaper than two weeks of refactoring after the fact.

**Existing defects require verification, not just patching.** The cache bugs, the authentication gap, and the prompt structure problems are each individually fixable in hours. But each fix needs to be confirmed against the eval harness. A cache key fix that does not change hit rate from 0% to measurably positive is not done.

**No parallel acceleration path exists for this scope.** These four phases have strict input/output dependencies. Adding engineers to Phase 3 before Phase 2 produces rework, not acceleration.

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
