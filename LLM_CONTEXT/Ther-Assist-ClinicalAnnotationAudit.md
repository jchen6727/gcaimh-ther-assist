# Ther-Assist — Clinical Requirements Audit: Annotated Code Review

> A pre-refactoring work product: an annotated pass through the backend that produces plain-language descriptions of what each component actually does, delivered to the clinical stakeholder for a requirements alignment review. The goal is to establish ground truth on which features were requested and which were generated speculatively by the LLM, before any refactoring, testing, or CI investment is made on code that may not need to exist.

---

## The Problem This Solves

The Ther-Assist backend was developed with significant AI code generation and limited architectural oversight. As a result:

- Features may have been implemented because an LLM assumed they were needed, not because they were requested (e.g., multi-modality switching, multi-session agent architecture, fine-tuning setup, OpenAI/Anthropic compatibility adapters).
- Performance and complexity in the codebase may be in service of capabilities the clinical team never asked for.
- Refactoring, CI setup, and guardrail redesign costs are all higher if conducted on a codebase that includes dead or extraneous code — you are testing and hardening features that may be removed anyway.

**Doing this audit first means every downstream cost estimate (QA, CI, refactoring, guardrail redesign) is applied only to code that survives the clinical review.** It is the highest-leverage task in the current backlog.

---

## Proposed Workflow

```
Step 1 — Developer annotation pass
  ↓
  Developer reads each backend file and writes plain-language
  inline comments explaining: what this code does, what clinical
  behavior it produces, and what would break if it were removed.
  Comments are written for a non-technical clinical reader.

Step 2 — Clinician review document
  ↓
  Annotated files (or a structured summary extracted from them)
  are delivered to the clinical stakeholder as a readable inventory:
  "Here is what the system currently does. Please mark each item
  as: Needed | Not needed | Unsure."

Step 3 — Triage meeting
  ↓
  30–60 min session with developer + clinician to resolve "Unsure"
  items and confirm the deletion/retention list.

Step 4 — Codebase trim
  ↓
  Confirmed extraneous features are removed or flagged as
  out-of-scope stubs. This reduces the surface area for all
  subsequent QA, CI, refactoring, and guardrail tasks.
```

---

## Scope: Backend Files for Annotation

Files are scoped to backend fragments only — frontend TypeScript excluded, as the UI components are more clearly grounded in visible product decisions. Infrastructure and setup scripts are included where they reveal implicit feature scope.

Flags: 🔬 = high clinical relevance (clinician must opine) | ⚠️ = suspected extraneous (likely candidate for removal)

### Phase 1 — Core Inference & Safety *(highest priority)*

These files define what the AI actually does during a session. The clinical stakeholder needs to confirm that the feature set here matches what was requested.

| File | SLOC | Complexity | Low hrs | High hrs | Low $ | High $ | Notes |
|---|---|---|---|---|---|---|---|
| 🔬 `therapy-analysis-function/main.py` | 1,660 | 174 | 25.3 | 41.1 | $1,670 | $2,713 | Core dispatch: RAG routing, multi-modality, safety scanner, dual-model calls. **Most complex file in codebase.** |
| 🔬 `therapy-analysis-function/constants.py` | 500 | 0 | 2.5 | 4.1 | $165 | $271 | Prompt templates, safety categories, modality map, keyword lists. Data-only but high clinical content. |
| 🔬 `streaming-transcription-service/main.py` | 624 | 107 | 11.6 | 18.8 | $766 | $1,241 | Audio pipeline. Contains known AI artifact (inappropriate phrase loading). Needs clinical review of what phrases/behaviors were specified vs. assumed. |
| 🔬 `transcription-service/prompts.py` | 147 | 0 | 0.7 | 1.2 | $46 | $79 | Transcription prompt definitions. |
| 🔬 `session_context_tool.py` | 138 | 23 | 2.5 | 4.1 | $165 | $271 | Session context management. Relevant to how session state is maintained and passed to the LLM. |
| **Phase 1 Subtotal** | **3,069** | **304** | **42.6** | **69.3** | **$2,812** | **$4,574** | |

**Phase 1 midpoint: 56 hrs / $3,693**

---

### Phase 2 — Portal & Data Models *(clinician confirms what patient/therapist interactions were requested)*

| File | SLOC | Complexity | Low hrs | High hrs | Low $ | High $ | Notes |
|---|---|---|---|---|---|---|---|
| `portal/models.py` | 90 | 0 | 0.5 | 1.0 | $33 | $66 | Data models — reveals what entities the system was built to manage. |
| 🔬 `portal/handlers/questionnaires.py` | 86 | 25 | 2.1 | 3.4 | $139 | $224 | Questionnaire logic. Was a questionnaire feature requested? |
| 🔬 `portal/handlers/homework.py` | 71 | 19 | 1.7 | 2.7 | $112 | $178 | Homework assignment. Was this in scope? |
| 🔬 `portal/handlers/interventions.py` | 42 | 7 | 0.8 | 1.3 | $53 | $86 | Intervention catalog. Was a structured intervention library requested? |
| 🔬 `portal/handlers/journal.py` | 41 | 14 | 1.1 | 1.8 | $73 | $119 | Journal entry handlers. Was journaling requested? |
| `portal/handlers/me.py` | 296 | 80 | 5.6 | 9.0 | $370 | $594 | User/session identity. Likely needed but worth confirming scope. |
| `portal/handlers/clients.py` | 70 | 9 | 0.9 | 1.5 | $59 | $99 | Client management. |
| `portal/handlers/sessions.py` | 13 | 3 | 0.5 | 1.0 | $33 | $66 | Session CRUD. |
| `portal/handlers/catalog.py` | 49 | 8 | 0.7 | 1.2 | $46 | $79 | Content catalog. |
| `portal/handlers/activity.py` | 41 | 10 | 0.7 | 1.2 | $46 | $79 | Activity tracking. |
| `portal/helpers.py` | 152 | 10 | 1.6 | 2.6 | $106 | $172 | Shared utilities. |
| **Phase 2 Subtotal** | **951** | **185** | **16.2** | **26.7** | **$1,069** | **$1,762** | |

**Phase 2 midpoint: 21 hrs / $1,386**

---

### Phase 3 — Suspected Extraneous / Architecturally Ambiguous *(high probability of removal)*

These files show the strongest signs of speculative AI generation — capabilities that go well beyond a clinical pilot and were likely never requested.

| File | SLOC | Complexity | Low hrs | High hrs | Low $ | High $ | Concern |
|---|---|---|---|---|---|---|---|
| ⚠️ `setup_multi_session_agent.py` | 643 | 19 | 5.9 | 9.6 | $389 | $634 | Multi-session agent architecture. Was a persistent cross-session agent ever specified? |
| ⚠️ `setup_fine_tuning.py` | 468 | 9 | 4.1 | 6.7 | $271 | $442 | Fine-tuning pipeline. Fine-tuning Gemini was almost certainly never requested for a pilot. |
| ⚠️ `comparative_study/runner.py` | 286 | 7 | 2.6 | 4.2 | $172 | $277 | Comparative study runner. Research eval tooling — is this in pilot scope? |
| ⚠️ `comparative_study/arms.py` | 73 | 6 | 0.8 | 1.3 | $53 | $86 | Study arms definition. Same concern. |
| ⚠️ `adapters/openai_compat.py` | 81 | 5 | 0.8 | 1.4 | $53 | $92 | OpenAI compatibility layer. The system uses Gemini — why does an OpenAI adapter exist? |
| ⚠️ `adapters/anthropic.py` | 64 | 0 | 0.5 | 1.0 | $33 | $66 | Anthropic adapter. Same question. |
| `adapters/therassist.py` | 79 | 11 | 1.1 | 1.7 | $73 | $112 | Ther-Assist adapter. Probably needed; confirm role. |
| `adapters/gemini.py` | 79 | 0 | 0.5 | 1.0 | $33 | $66 | Gemini adapter. Likely needed. |
| `rag/analyze_corpus.py` | 96 | 19 | 1.5 | 2.5 | $99 | $165 | Corpus analysis utility. |
| `rag/setup_rag_datastore.py` | 283 | 50 | 4.3 | 6.9 | $284 | $455 | RAG datastore setup. Needed, but scope of multi-datastore architecture should be confirmed. |
| **Phase 3 Subtotal** | **2,152** | **126** | **22.1** | **36.3** | **$1,459** | **$2,396** | |

**Phase 3 midpoint: 29 hrs / $1,914**

---

## Total Annotation Pass Estimate

| Phase | SLOC | Complexity | Low hrs | High hrs | Low $ | High $ |
|---|---|---|---|---|---|---|
| Phase 1 — Core Inference & Safety | 3,069 | 304 | 42.6 | 69.3 | $2,812 | $4,574 |
| Phase 2 — Portal & Data Models | 951 | 185 | 16.2 | 26.7 | $1,069 | $1,762 |
| Phase 3 — Suspected Extraneous | 2,152 | 126 | 22.1 | 36.3 | $1,459 | $2,396 |
| **Total** | **6,172** | **615** | **80.9** | **132.3** | **$5,339** | **$8,732** |

**Midpoint: 107 hrs / $7,036**

*Blended rate: $66/hr from COCOMO baseline. Hours include annotation writing time only — not the clinician's review time, which is unbilled developer effort.*

---

## What This Unlocks Downstream

The annotation pass is not a standalone deliverable — it is a multiplier on everything else. Its value should be measured against what it prevents:

| Risk it mitigates | Avoided cost if caught early |
|---|---|
| Building CI tests for extraneous features (e.g., fine-tuning, multi-session agent) | ~20–40 hrs of CI pipeline work avoided |
| Refactoring code that gets deleted anyway | ~10–20 hrs of refactoring avoided |
| Guardrail redesign that includes unused modalities | ~4–10 hrs of design discussion avoided |
| RAG re-ingestion of corpora for unused modalities | ~4–8 hrs of re-ingestion avoided |

**Conservative avoided-cost estimate if even 20% of the codebase is confirmed extraneous: $3,000–$8,000.** The annotation pass pays for itself if it surfaces even one major feature area for removal.

---

## Recommended Sequencing

```
1. Phase 3 annotation FIRST (⚠️ files) — 22–36 hrs
   Fastest ROI: these are the most likely candidates for deletion.
   If confirmed extraneous, they drop out of all subsequent scopes.

2. Phase 1 annotation — 43–69 hrs
   Most complex, most clinically consequential.
   main.py alone will take 25–41 hrs and should be assigned to
   the developer with the most context on the inference pipeline.

3. Phase 2 annotation — 16–27 hrs
   Portal handlers are shorter and lower complexity; good for a
   junior team member or second developer.

4. Triage meeting with clinician — 2–4 hrs
   Structured walkthrough of the inventory document.
   Output: confirmed keep/remove/out-of-scope-for-pilot list.

5. Codebase trim — scope TBD based on triage output
   Removal of confirmed extraneous code before any QA/CI/
   refactoring work begins.
```

---

## Note on Multi-Modality Specifically

Multi-modality switching (`session_type` dispatch, `MODALITY_RAG_MAP`, per-modality RAG corpus routing) is implemented across `main.py`, `constants.py`, and the RAG infrastructure. It is one of the most architecturally significant features in the system and one of the most likely candidates to have been generated speculatively.

If the clinical stakeholder confirms it was never requested, removing it would:
- Simplify `main.py` substantially (the modality dispatch logic is a major contributor to its c=174 complexity score)
- Eliminate the DBT, BA, ACT, and IPT corpus re-ingestion tasks entirely (~12–20 hrs of the §1d RAG work)
- Simplify the guardrail redesign (fewer session types to reason about)
- Reduce the CI pipeline surface area meaningfully

This single question — *"Was multi-modality ever requested?"* — is worth resolving in the first 30 minutes of the clinician triage meeting.
