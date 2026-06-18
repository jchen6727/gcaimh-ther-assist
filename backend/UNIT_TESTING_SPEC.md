# Backend Unit Testing Specification

**Purpose:** Interface boundary analysis and unit test design guide for all three backend services.  
**Audience:** LLM agent or engineer designing the test suite.  
**Scope:** `backend/streaming-transcription-service`, `backend/therapy-analysis-function`, `backend/storage-access-function`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [I/O Structure Reference](#2-io-structure-reference)
   - [Service 1 — Streaming Transcription (STT)](#21-service-1--streaming-transcription-stt)
   - [Service 2 — Therapy Analysis Function](#22-service-2--therapy-analysis-function)
   - [Service 3 — Storage Access / Portal API](#23-service-3--storage-access--portal-api)
3. [Unit Test Design Instructions](#3-unit-test-design-instructions)
   - [General principles](#31-general-principles)
   - [Service 1 — pure function targets](#32-service-1--pure-function-targets)
   - [Service 2 — pure function targets](#33-service-2--pure-function-targets)
   - [Service 3 — pure function targets](#34-service-3--pure-function-targets)
   - [Shared mock patterns](#35-shared-mock-patterns)
4. [LLM Performance Evaluation Framework](#4-llm-performance-evaluation-framework)
   - [Already in existing I/O](#41-already-in-existing-io-_diagnostics-object)
   - [Missing — must be generated](#42-missing--must-be-instrumented-or-generated)
   - [Evaluation harness design](#43-evaluation-harness-design)
   - [Prompt engineering feedback loop](#44-prompt-engineering-feedback-loop)

---

## 1. Architecture Overview

```
Browser
  │
  ├─[WebSocket PCM audio]──► streaming-transcription-service  (FastAPI, port 8082)
  │                              │ Google STT v2 (streaming_recognize)
  │                              └─[WS JSON: transcript / analysis / speech_event]──► Browser
  │
  ├─[HTTP POST JSON]──────► therapy-analysis-function          (Flask Cloud Function)
  │                              │ Gemini Flash (realtime)
  │                              │ Gemini Pro   (comprehensive / summary / pathway)
  │                              │ Vertex AI Search (RAG: 5 corpora)
  │                              │ Firestore (sessions, publishDrafts)
  │                              └─[HTTP streaming text/plain NDJSON]──► Browser
  │
  └─[HTTP GET/POST/PATCH]─► storage-access-function            (Flask Cloud Function)
                                 │ Google Cloud Storage (citation PDFs)
                                 │ Firestore (patients/*, sessions, catalog)
                                 └─[HTTP JSON]──► Browser
```

**Cross-service data contract:**  
`therapy-analysis-function session_summary` → writes `SessionSummary` to Firestore  
→ `storage-access-function portal` reads it back and serves it (with redaction) to the patient portal.  
This chain is the highest-risk integration boundary.

---

## 2. I/O Structure Reference

### 2.1 Service 1 — Streaming Transcription (STT)

#### Inbound WebSocket frames

**Frame 1 — text (JSON), session initialization:**
```json
{
  "token": "string | mock-<any> | omit for local-dev",
  "session_id": "string (optional; defaults to YYYYMMDD-HHMMSS)",
  "config": {}
}
```

**Subsequent frames:**
- **Binary:** raw PCM bytes — 16 kHz, 16-bit, mono. No envelope.
- **Text (JSON):** `{"type": "stop" | "pause" | "resume" | "ping"}`

#### Outbound WebSocket messages (JSON)

| `type` | Trigger | Required fields |
|--------|---------|-----------------|
| `ready` | After init | `{type, session_id, timestamp, config: {sample_rate:16000, encoding:"PCM_16BIT", model:"latest_long"}}` |
| `transcript` | Each STT result | `{type, transcript:str, confidence:float, is_final:bool, speaker:"conversation", timestamp:ISO, result_end_offset:float}` + `words?:[{word,start_time,end_time,confidence}]` on final |
| `analysis` | Final transcript with safety keyword hit | `{type:"analysis", alert:{timing,category,title,message,evidence[],recommendation[],immediateActions[],contraindications[],crisis_resources[]}, session_metrics:null, session_phase:null}` |
| `speech_event` | VAD boundary | `{type, event:"speech_start"\|"speech_end", timestamp:ISO}` |
| `pong` | `ping` received | `{type:"pong"}` |
| `error` | STT or init failure | `{type:"error", error:str, timestamp:ISO}` |
| `auth_error` | Expired GCP credentials | `{type:"auth_error", error:str, timestamp:ISO}` |

#### Auth logic (WS init)

| Token value | Environment | Result |
|-------------|------------|--------|
| Absent | Any | 1008 close |
| `mock-*` | Cloud Run (K_SERVICE set) | Accept as IAP-pre-authenticated |
| Any | Local dev (no K_SERVICE) | Bypass; `user_email = "local-dev@localhost"` |
| Firebase JWT | Production | `verify_firebase_token()` → email domain/allowlist check |

---

### 2.2 Service 2 — Therapy Analysis Function

#### Inbound: `POST /` (JSON body)

All requests share the envelope `{"action": "...", ...}`.

---

**`analyze_segment`**
```json
{
  "action": "analyze_segment",
  "transcript_segment": [
    {
      "speaker": "Therapist | Patient | conversation",
      "text": "string",
      "timestamp": "string (optional)"
    }
  ],
  "session_context": {
    "session_type": "CBT | DBT | IPT",
    "primary_concern": "string",
    "current_approach": "string",
    "patient_id": "string"
  },
  "session_duration_minutes": 0,
  "is_realtime": false,
  "previous_alert": {
    "title": "string",
    "category": "string",
    "message": "string",
    "recommendation": "string",
    "timing": "string"
  },
  "job_id": "string | null"
}
```

**Output — `is_realtime: true` (streaming `text/plain`, one JSON line):**
```json
{
  "alert": {
    "timing": "now | pause | info",
    "category": "safety | technique | pathway_change | engagement | process",
    "title": "string",
    "message": "string (1-3 sentences)",
    "evidence": ["quote from patient"],
    "recommendation": ["action1", "action2", "action3 (max 3)"],
    "immediateActions": ["step therapist takes right now"],
    "contraindications": ["what to avoid"],
    "crisis_resources": ["988 Suicide & Crisis Lifeline: call or text 988"]
  },
  "timestamp": "ISO",
  "session_phase": "beginning | middle | end",
  "analysis_type": "realtime",
  "prompt_used": "non-strict | strict",
  "trigger_phrase_detected": false,
  "safety_keywords_detected": false,
  "safety_scan": {
    "scanner_triggered": false,
    "categories": [],
    "keywords_matched": [],
    "highest_severity": "suicidal_ideation | self_harm | violence_homicide | abuse_disclosure | substance_crisis | null"
  },
  "job_id": "string | null",
  "citations": [
    {
      "citation_number": 1,
      "source": {
        "title": "string",
        "uri": "string | null",
        "excerpt": "string | null",
        "pages": {"first": 0, "last": 0}
      }
    }
  ],
  "_diagnostics": { "...see Section 4.1..." }
}
```
> **Note:** `crisis_resources` is REQUIRED when `category == "safety"` and OMITTED otherwise.  
> An empty JSON object `{}` (no `alert` key) signals "no guidance needed."

**Output — `is_realtime: false` (streaming `text/plain`, one JSON line):**
```json
{
  "session_metrics": {
    "engagement_level": 0.0,
    "therapeutic_alliance": "weak | moderate | strong",
    "techniques_detected": ["string"],
    "detected_modality": {
      "code": "CBT | DBT | IPT | BA | MI",
      "name": "string",
      "confidence": 0.0,
      "evidence": ["specific technique observed"]
    },
    "emotional_state": "calm | anxious | distressed | dissociated | engaged",
    "arousal_level": "low | moderate | high | elevated",
    "phase_appropriate": true
  },
  "pathway_indicators": {
    "current_approach_effectiveness": "effective | struggling | ineffective",
    "alternative_pathways": ["string"],
    "change_urgency": "none | monitor | consider | recommended"
  },
  "pathway_guidance": {
    "continue_current": true,
    "rationale": "string with [1],[2] citations",
    "immediate_actions": ["string"],
    "contraindications": ["string"],
    "alternative_pathways": [
      {"approach": "string", "reason": "string", "techniques": ["string"]}
    ]
  },
  "diarized_transcript": [
    {"speaker": "Therapist | Patient", "text": "exact quote"}
  ],
  "timestamp": "ISO",
  "session_phase": "beginning | middle | end",
  "analysis_type": "comprehensive",
  "job_id": "string | null",
  "citations": ["...same shape as realtime..."],
  "_diagnostics": { "...see Section 4.1..." }
}
```

---

**`session_summary`**
```json
Input: {
  "action": "session_summary",
  "full_transcript": [{"speaker": "str", "text": "str", "timestamp": "str"}],
  "session_metrics": {"duration_minutes": 0, "...": "..."},
  "session_context": {"patient_id": "str", "session_type": "str"}
}

Output: {"summary": { SessionSummary }}
Side effect: writes /patients/{patient_id}/publishDrafts/{auto_id} to Firestore
```

**`SessionSummary` schema** (the shared object flowing from LLM → Firestore → portal):
```json
{
  "session_date": "YYYY-MM-DD",
  "duration_minutes": 0,
  "key_moments": [
    {"time": "HH:MM:SS", "description": "string", "significance": "string"}
  ],
  "techniques_used": ["string"],
  "progress_indicators": ["string"],
  "areas_for_improvement": ["string"],
  "homework_assignments": [
    {"task": "string", "rationale": "string", "manual_reference": "EBT manual p.X"}
  ],
  "follow_up_recommendations": ["string"],
  "risk_assessment": {
    "level": "low | moderate | high | critical",
    "factors": ["string"]
  },
  "alternate_therapy_paths": [
    {
      "therapy_type": "CBT | DBT | IPT | BA | MI",
      "reason": "string",
      "key_indicators": ["string"],
      "techniques_to_try": ["string"]
    }
  ]
}
```

**`PublishDraft` written to Firestore** (derived from `SessionSummary`):
```json
{
  "clientId": "string",
  "sessionDate": "YYYY-MM-DD",
  "sections": {
    "themes": false, "keyMoments": false, "homeworkList": false,
    "riskLabel": false, "nextSteps": false
  },
  "published": false,
  "content": {
    "themes": ["string"],
    "keyMoments": ["string"],
    "homeworkList": ["string"],
    "nextSteps": ["string"],
    "clinicalNote": "",
    "riskLabel": "low | moderate | high | critical  (only if present)"
  },
  "createdAt": "SERVER_TIMESTAMP",
  "source": "auto-from-session-summary"
}
```

---

**`pathway_guidance`**
```json
Input: {
  "action": "pathway_guidance",
  "current_approach": "string",
  "session_history": [{"date": "str", "main_topics": ["str"]}],
  "presenting_issues": ["string"],
  "session_context": {"session_type": "CBT | DBT | IPT"}
}

Output: {
  "continue_current": true,
  "rationale": "string",
  "alternative_pathways": [{"approach","reason","techniques":[]}],
  "immediate_actions": ["string"],
  "contraindications": ["string"],
  "citations": [...]
}
```

**`save_session`**
```json
Input: {
  "action": "save_session",
  "patient_id": "string",
  "date": "YYYY-MM-DD",
  "duration_minutes": 0,
  "summary_text": "string",
  "session_type": "string",
  "full_summary": { SessionSummary },
  "session_metrics": {}
}
Output: {"success": true, "session_id": "string"}
Writes:  /sessions/{auto_id}
```

**`get_sessions`**
```json
Input:  {"action": "get_sessions", "patient_id": "string"}
Output: {"sessions": [{...session_fields..., "id": "string"}]}
Reads:  /sessions where patient_id == X, ordered by date DESC
```

**`get_patient_summary`**  
*(Pure transform — no LLM, no Firestore)*
```json
Input:  {"action": "get_patient_summary", "full_summary": { SessionSummary }}
Output: {
  "patient_summary": {
    "session_date": "string",
    "duration_minutes": 0,
    "progress_indicators": ["string"],
    "homework_assignments": [{"task": "string", "rationale": "string"}],
    "follow_up_recommendations": ["string"]
  }
}
Strips: risk_assessment, techniques_used, key_moments, manual_reference (PHI redaction)
```

---

### 2.3 Service 3 — Storage Access / Portal API

#### Auth header (all portal routes)
```
Authorization: Bearer <firebase_id_token>
  OR (dev mode, PORTAL_DEV_AUTH_BYPASS=true):
Authorization: Bearer dev-therapist-<email>
Authorization: Bearer dev-patient-<email>
```
Token → `/users/{uid}` Firestore doc:
```json
{
  "uid": "string",
  "email": "string",
  "role": "therapist | patient",
  "managedPatientIds": ["pid1", "pid2"],
  "patientId": "string (patient role only)"
}
```

#### Pydantic request body models

```python
HomeworkUpsert:         moduleId, moduleTitle, moduleCategory, estimatedMinutes(≥0), dueAt?, status("ASSIGNED"), note?, sourceSessionId?, sourceSessionDate?
HomeworkStatusUpdate:   status: "ASSIGNED|IN_PROGRESS|COMPLETED|ARCHIVED"
HomeworkPatch:          dueAt?, note?, status?
InterventionUpsert:     interventionId, interventionTitle, interventionType, frequency("DAILY|TWICE_DAILY|AS_NEEDED|WEEKLY")?, dueAt?, status("ACTIVE"), note?
PublishDraftPatch:      sections: {themes:bool, keyMoments:bool, homeworkList:bool, riskLabel:bool, nextSteps:bool}
ActivityEventCreate:    type: ActivityEventType, description:str, actor:"therapist|client"
QuestionnaireAssign:    questionnaireId, cadence("WEEKLY|BIWEEKLY|MONTHLY|SESSION"), note?
QuestionnaireStatusUpdate: status: "ACTIVE|PAUSED|REMOVED"
JournalEntryUpsert:     id?, date?, moduleId?, interventionId?, sessionId?, keyInsights:str, personalApplication:str, discussionTopics:str
OutcomeResponseSubmit:  measureId, weekOf("YYYY-MM-DD"), responses:int[], score(≥0)
InterventionSessionStart: interventionId
```

#### Document translation functions (I/O shapes)

**`session_doc_to_therapy_session(doc)`** — therapist view:
```json
{
  "id": "doc.id",
  "date": "YYYY-MM-DD",
  "durationMinutes": 0,
  "summary": "string",
  "themes": [],
  "keyMoments": [],
  "techniques": [],
  "homework": ["task string only"],
  "insights": [],
  "emotionalState": "string | null"
}
```

**`session_doc_to_therapy_session_patient_view(doc)`** — removes `keyMoments` and `techniques`.

**`patient_doc_to_bridge_client(doc)`:**
```json
{"id", "name", "status", "primaryConcern", "age"}
```
> Note: reads `primaryConcern` then falls back to `primary_concern` (legacy field).

**`questionnaire_def_doc_to_outcome_measure(doc)`** — for patient:
```json
{"id","name","shortName","description","category","items":[],"maxScore","scoring","thresholds":[],"cadence"}
```

**`response_doc_to_outcome_response(doc)`:**
```json
{"id","measureId","weekOf","responses":[int],"score","completedAt"}
```
> `responses` is reconstructed by sorting `items` by `itemIndex` then extracting `value`. This sort is a testable invariant.

#### Portal route summary

| Route | Method | Auth | Body model | Response |
|-------|--------|------|------------|----------|
| `/portal/clients` | GET | therapist | — | `[BridgeClient]` |
| `/portal/clients/{id}/overview` | GET | therapist+owns | — | `{client,homework[],interventions[],publishDraft,outcomeOverview,activityLog[]}` |
| `/portal/clients/{id}/progress` | GET | therapist+owns | — | `ClientProgress` |
| `/portal/clients/{id}/homework` | GET/POST | therapist+owns | `HomeworkUpsert` | `[HomeworkDoc]` / `{id,...}` |
| `/portal/clients/{id}/homework/{hwId}/status` | PATCH | therapist+owns | `HomeworkStatusUpdate` | `{success:true}` |
| `/portal/clients/{id}/homework/{hwId}` | PATCH | therapist+owns | `HomeworkPatch` | `{success:true}` |
| `/portal/clients/{id}/interventions` | GET/POST | therapist+owns | `InterventionUpsert` | `[...]` / `{id,...}` |
| `/portal/clients/{id}/interventions/{aId}` | DELETE | therapist+owns | — | `{success:true}` |
| `/portal/clients/{id}/publish-draft` | GET | therapist+owns | — | `{id,...draft}` or `null` |
| `/portal/clients/{id}/publish-draft/{dId}` | PATCH | therapist+owns | `PublishDraftPatch` | `{success:true}` |
| `/portal/clients/{id}/publish-draft/{dId}/publish` | POST | therapist+owns | — | `{success:true}` |
| `/portal/clients/{id}/questionnaires` | GET/POST | therapist+owns | `QuestionnaireAssign` | `[...]` / `{id,...}` |
| `/portal/clients/{id}/sessions` | GET | therapist+owns | — | `[TherapySession]` |
| `/portal/catalog/modules` | GET | therapist | — | `[Module]` |
| `/portal/catalog/interventions` | GET | therapist | — | `[Intervention]` |
| `/portal/catalog/questionnaires` | GET | therapist | — | `[QuestionnaireDef]` |
| `/portal/me/dashboard` | GET | patient | — | `{patientId,homework[],journalCount}` |
| `/portal/me/progress` | GET | patient | — | `ClientProgress` |
| `/portal/me/homework` | GET | patient | — | `[HomeworkDoc]` |
| `/portal/me/homework/{hwId}/status` | PATCH | patient | `HomeworkStatusUpdate` | `{success:true}` |
| `/portal/me/interventions` | GET | patient | — | `[Intervention]` joined w/ catalog |
| `/portal/me/intervention-sessions` | GET/POST | patient | `InterventionSessionStart` | `[...]` / `{id,...}` 201 |
| `/portal/me/journal` | GET/POST | patient | `JournalEntryUpsert` | `[JournalEntry]` / `{id,...}` |
| `/portal/me/integrative-analysis` | GET | patient | — | IntegrativeAnalysis or empty default |
| `/portal/me/sessions` | GET | patient | — | `[TherapySession]` (redacted) |
| `/portal/me/outcome-measures` | GET | patient | — | `[OutcomeMeasure]` |
| `/portal/me/outcome-schedule` | GET | patient | — | `{measures:[{measureId,cadence,nextDue}],reminderEnabled:true}` |
| `/portal/me/outcome-responses` | GET | patient | `?measureId=&limit=` | `[OutcomeResponse]` |
| `/portal/me/outcome-responses` | POST | patient | `OutcomeResponseSubmit` | `OutcomeResponse` 201 |

---

## 3. Unit Test Design Instructions

> **For the LLM agent designing tests:** read this section in full before generating any test code. The goal is maximum coverage of testable logic with zero network calls. Each subsection lists functions in priority order (most critical first). Use `pytest` for all services.

### 3.1 General Principles

1. **Never call real external services.** Mock Firestore, Gemini, Google STT, Firebase Auth, and GCS at the boundary where the library is called — not at the application logic level.
2. **Focus on pure functions first.** A pure function requires no mocks and gives you high-confidence, fast tests. The pure functions are explicitly identified below.
3. **Test the exact wire format.** For functions that produce JSON (either via `jsonify` or `json.dumps`), assert the keys and their types, not just that parsing succeeds.
4. **Safety logic is highest priority.** Any code path touching `detect_safety_keywords`, `scan_safety_keywords`, or the safety alert injection must have complete keyword-category coverage.
5. **Use the existing `test_phase1_e2e.py` as a reference for fixture data** — it contains realistic therapy transcript segments. Do not replace it; unit tests are a separate suite in a `tests/` directory.
6. **Parametrize aggressively.** Use `@pytest.mark.parametrize` for functions with discrete input categories (e.g., session duration → phase, email → authorized/not, token format → decode result).
7. **Do not test framework behavior** — do not test that Flask returns 405 on the wrong method, or that Pydantic raises on missing fields. Test your application logic.

### 3.2 Service 1 — Pure Function Targets

**File:** `streaming-transcription-service/main.py`

<!-- #TODO: Create tests/service1/test_safety.py implementing all cases below -->
#### Priority 1: `scan_safety_keywords(text: str) → list[dict]`

This is the STT service's safety net. Test exhaustively.

```
Test cases (parametrize):
  - Each keyword from each category in SAFETY_KEYWORDS hits its category
  - Mixed text (keyword embedded mid-sentence) → still hits
  - Case insensitivity: "SUICIDE", "Suicide", "suicide" all match
  - Text with no keywords → empty list returned
  - Empty string → empty list
  - Text matching keywords from two categories → both categories returned
  - Partial word match: "suicides" contains "suicide" — verify behavior (it will match; document as a known false positive)

Assert shape: each item is {"category": str, "keywords": list[str]}
Assert: returned "keywords" list contains only matched keywords, not the full category list
```

<!-- #TODO: Create tests/service1/test_auth.py -->
#### Priority 2: `is_email_authorized(email: str) → bool`

```
Test cases:
  - Email in ALLOWED_EMAILS → True
  - Email domain in ALLOWED_DOMAINS → True
  - Email not in either → False
  - Empty string → False
  - Email with no @ → False (domain extraction edge case)
  - ALLOWED_DOMAINS and ALLOWED_EMAILS both empty → False for any email
Use monkeypatch or module-level constants to control ALLOWED_DOMAINS / ALLOWED_EMAILS.
```

---

### 3.3 Service 2 — Pure Function Targets

**File:** `therapy-analysis-function/main.py`, `therapy-analysis-function/constants.py`

<!-- #TODO: Create tests/service2/test_safety_keywords.py — highest priority, implement first -->
#### Priority 1: `detect_safety_keywords(transcript_text: str) → dict`

This function runs before every LLM call. Its output directly controls whether a safety alert is forced, the `prompt_injection` string, and whether `thinking_budget` is escalated.

```
Test cases:
  - Each of the 5 categories: at least 3 keyword fixtures each
  - Severity ordering: if "suicide" and "cutting" both present → highest_severity == "suicidal_ideation"
  - No keywords → detected=False, all lists empty, prompt_injection=""
  - detected=True → prompt_injection contains matched_categories and matched_keywords
  - clinical_responses: for each category, verify the clinical_response dict has title, protocol, message, crisis_resources, immediate_actions, contraindications
  - highest_severity follows SEVERITY_ORDER: suicidal_ideation > violence_homicide > abuse_disclosure > self_harm > substance_crisis
  - keywords_matched is capped at 10 in prompt_injection (full list still returned)

Assert shape:
  {
    "detected": bool,
    "matched_categories": list[str],
    "matched_keywords": list[str],
    "highest_severity": str | None,
    "clinical_responses": list[dict],
    "prompt_injection": str
  }
```

<!-- #TODO: Create tests/service2/test_json_extraction.py — covers all 3 strategies + truncated repair -->
#### Priority 2: `extract_json_from_text(text: str) → Optional[dict]`

All LLM output passes through this function. Test all three extraction strategies independently.

```
Strategy 1 — direct parse:
  - Valid JSON string → returns dict
  - JSON with leading/trailing whitespace → returns dict

Strategy 2a — bare regex:
  - JSON preceded by prose text ("Here is the analysis: {\"key\":1}") → extracts dict
  - Multiple JSON objects in text → first valid one returned

Strategy 2b — code block:
  - "```json\n{\"key\":1}\n```" → extracts dict
  - "```\n{\"key\":1}\n```" (no language tag) → extracts dict

Strategy 3 — truncated JSON repair:
  - '{"a": 1, "b": [1, 2' (open bracket) → repaired to {"a":1,"b":[1,2]}
  - '{"a": 1,' (trailing comma) → repaired
  - '{"a":' (incomplete key) → returns None or best-effort
  - Empty string → None
  - Pure prose with no JSON → None

Edge cases:
  - Nested JSON (objects within objects) → outermost extracted correctly
  - JSON with escaped quotes inside strings → parses correctly
```

<!-- #TODO: Create tests/service2/test_pure_functions.py — covers Priority 3 through 7 below -->
#### Priority 3: `determine_therapy_phase(duration_minutes: int) → str`

```
Parametrize:
  0  → "beginning"
  10 → "beginning"   (boundary: ≤10)
  11 → "middle"
  40 → "middle"      (boundary: ≤40)
  41 → "end"
  120 → "end"
```

#### Priority 4: `format_transcript_segment(segment: list) → str`

```
Test cases:
  - speaker="Therapist", text="Hello", timestamp="00:01" → "[00:01] Therapist: Hello"
  - speaker="conversation", text="Therapist: How are you?" → speaker inferred as "Therapist", prefix stripped
  - speaker="conversation", text="T: I feel sad" → speaker inferred as "Therapist"
  - speaker="conversation", text="Client: I feel sad" → speaker inferred as "Client"
  - speaker="conversation", text="Patient: Yes" → speaker inferred as "Client"
  - speaker="conversation", text="P: Sure" → speaker inferred as "Client"
  - speaker="conversation", text without recognized prefix → kept as "conversation"
  - timestamp absent → no brackets, format is "Speaker: text"
  - Empty segment list → returns ""
  - Multi-entry segment → each line on its own line (joined with \n)
```

#### Priority 5: `check_for_trigger_phrases(transcript_segment: list) → bool`

```
Test cases:
  - Last item text contains a trigger phrase → True (case insensitive)
  - Only earlier items contain trigger phrase, not last → False
  - Empty list → False
  - Last item text has trigger phrase mid-sentence → True
  - All trigger phrases from constants.TRIGGER_PHRASES tested individually
```

#### Priority 6: `summarize_session_history(history: list) → str`

```
Test cases:
  - Empty list → "No previous sessions"
  - 1 session → includes that session's date and topics
  - 3 sessions → includes all 3
  - 4 sessions → only last 3 (slicing behavior)
  - Session with empty main_topics → date present, topics join to ""
```

#### Priority 7: `build_diagnostics(...)` → dict

```
Test cases:
  - All required fields present → dict has all expected keys
  - latency_ms is round((end_time - start_time) * 1000)
  - ttft_ms is None when ttft arg is None
  - ttft_ms is computed when ttft arg is provided
  - trigger_phrase_detected only in dict when arg is not None
  - context_cache_hit only in dict when arg is not None
  - grounding.chunks_retrieved == len(grounding_sources)
```

<!-- #TODO: Create tests/service2/test_handlers_pure.py — Priority 8 and 9 -->
#### Priority 8: `handle_get_patient_summary(request_json, headers)` (pure handler)

This is the only action handler with zero external dependencies. Test directly without a Flask app.

```
Test cases:
  - Full SessionSummary input → output contains only session_date, duration_minutes,
    progress_indicators, homework_assignments (task+rationale only), follow_up_recommendations
  - risk_assessment NOT in output
  - techniques_used NOT in output
  - key_moments NOT in output
  - manual_reference NOT in homework_assignments items
  - homework_assignments with manual_reference field → field dropped in output
  - Empty full_summary ({}) → 400 error response
  - Missing patient_id key in summary → output still produced (no patient_id in output shape)
```

#### Priority 9: `_write_publish_draft_from_summary(parsed_summary, session_context, session_metrics)`

Test the **shape** of the Firestore write, not the write itself. Mock `db` at the module level.

```python
# Fixture: minimal parsed_summary
summary = {
    "key_moments": [{"description": "Patient expressed hopelessness"}],
    "homework_assignments": [{"task": "Thought record", "rationale": "CBT core"}],
    "follow_up_recommendations": ["Review safety plan"],
    "techniques_used": ["Socratic questioning"],
    "progress_indicators": ["Engaged fully"],
    "risk_assessment": {"level": "moderate"},
    "session_date": "2025-06-01",
}
session_context = {"patient_id": "pt123"}
```

```
Assert on the dict passed to doc_ref.set():
  - clientId == "pt123"
  - sessionDate == "2025-06-01"
  - published == False
  - all sections values are False
  - content.keyMoments == ["Patient expressed hopelessness"]
  - content.homeworkList == ["Thought record"]
  - content.nextSteps == ["Review safety plan"]
  - content.themes contains "Socratic questioning" and "Engaged fully"
  - content.riskLabel == "moderate"
  - source == "auto-from-session-summary"
  - clinicalNote == ""

Edge cases:
  - session_context without patient_id → function returns without writing (no assert on set)
  - key_moments entries without "description" key → skipped
  - homework_assignments entries without "task" key → skipped
  - risk_assessment is None → riskLabel absent from content
```

<!-- #TODO: Create tests/service2/test_rag_cache.py — Priority 10, implement after cache.md fixes are applied -->
#### Priority 10: `prefetch_rag_context()` cache hit/miss logic

This test validates the corrected cache behavior: TTL-only invalidation with no transcript
hash. Do not implement until the Task 1 fix in `cache.md` is applied — the tests assert
the corrected behavior (hash removed; TTL-only) and will fail against the original code.

⚠️ **Prior version of these tests was incorrect.** `test_cache_key_stability_across_short_utterance`
asserted that appending 5 words to a 250-word transcript left the 200-word hash unchanged.
That assertion is false — the 200-word window includes the new tail words and the hash
changes. The tests below reflect the corrected fix (no hash at all).

```python
# Fixture helpers (add to conftest.py):
def make_transcript(word_count: int) -> str:
    """Build a plausible transcript string of given word count."""
    words = ["word"] * word_count
    return " ".join(f"[00:{i:02d}] Speaker: {w}" for i, w in enumerate(words))
```

```
test_cache_hit_ttl_only_different_transcript:
  - Build two different transcripts (second has 8 new words appended — the trigger threshold).
  - Populate `_rag_cache[session_type]` with a fresh entry (age < 90 s) using the first transcript.
  - Call `prefetch_rag_context()` with the second (different) transcript.
  - Assert the cached passages are returned WITHOUT calling `_query_datastore`.
  → Validates TTL-only invalidation: transcript content no longer affects cache hits.

test_cache_hit_returns_without_querying:
  - Monkeypatch `_rag_cache` with a fresh entry (age < 90 s) and matching hash.
  - Monkeypatch `_query_datastore` to raise AssertionError if called.
  - Call `prefetch_rag_context()` — assert it returns the cached passages.
  - Assert returned prefetch_meta["cache_hit"] == True.

test_cache_miss_on_expired_ttl:
  - Monkeypatch `_rag_cache` with a stale entry (age > 90 s), matching hash.
  - Monkeypatch `_query_datastore` to return ["passage"].
  - Call `prefetch_rag_context()` — assert `_query_datastore` was called.
  - Assert returned prefetch_meta["cache_hit"] == False.

test_cache_miss_on_hash_mismatch:
  - Monkeypatch `_rag_cache` with a fresh entry but a different hash.
  - Monkeypatch `_query_datastore` to return ["passage"].
  - Assert `_query_datastore` was called (miss, not hit).

test_prefetch_meta_shape:
  - Call `prefetch_rag_context()` with a mocked `_query_datastore`.
  - Assert returned tuple is (str, dict).
  - Assert meta keys: cache_hit, rag_latency_ms, rag_query_words, passages_by_store.
```

---

### 3.4 Service 3 — Pure Function Targets

**File:** `storage-access-function/portal/helpers.py`, `storage-access-function/portal/auth.py`

<!-- #TODO: Create tests/service3/test_doc_translations.py — all Priority 1-5 below -->
#### Priority 1: `response_doc_to_outcome_response(doc)`

The `itemIndex` sort is a correctness invariant — a wrong sort order silently delivers scrambled questionnaire data to patients.

```python
# Mock doc returning items out of order:
items = [
    {"itemIndex": 2, "value": 3},
    {"itemIndex": 0, "value": 1},
    {"itemIndex": 1, "value": 2},
]
# Expected responses: [1, 2, 3]  (sorted by itemIndex)
```

```
Test cases:
  - Items in order → responses matches order
  - Items out of order → responses sorted correctly
  - Single item → responses has one element
  - Empty items → responses is []
  - itemIndex gaps (0, 2 only) → still sorted; value at index 1 is 0 (missing defaults)
  - All fields present → id, measureId, weekOf, score, completedAt all mapped correctly
```

#### Priority 2: `session_doc_to_therapy_session(doc)` and `_patient_view`

```
Test cases (therapist view):
  - doc with full_summary → all fields mapped
  - homework_assignments in full_summary → output.homework contains task strings only (manual_reference stripped)
  - full_summary missing → graceful empty defaults
  - keyMoments present in therapist view
  - techniques present in therapist view

Patient view (call _patient_view on same fixture):
  - keyMoments NOT in output
  - techniques NOT in output
  - all other fields same as therapist view
```

#### Priority 3: `patient_doc_to_bridge_client(doc)`

```
Test cases:
  - doc has primaryConcern → used
  - doc has primary_concern but not primaryConcern → fallback used
  - doc has both → primaryConcern wins
  - doc has neither → None in output
  - Missing name → ""
  - Missing status → "active"
```

<!-- #TODO: Create tests/service3/test_auth.py — Priority 4 -->
#### Priority 4: `_decode_dev_token(token)` in `auth.py`

```
Test cases:
  - "dev-therapist-doc@hospital.edu" → {uid:"dev-doc@hospital.edu", email:"doc@hospital.edu", role:"therapist"}
  - "dev-patient-pat@example.com" → {uid:"dev-pat@example.com", email:"pat@example.com", role:"patient"}
  - "dev-admin-x@y.com" → None (invalid role)
  - "not-a-dev-token" → None
  - "dev-therapist" → None (missing email segment)
  - "dev-therapist-noemail" → None (no @ in email)
```

#### Priority 5: `questionnaire_def_doc_to_outcome_measure` vs `_to_definition`

```
outcome_measure:
  - includes items[] array
  - maxScore, scoring, thresholds, cadence all mapped

definition (therapist):
  - does NOT include items[] directly
  - includes itemCount == len(items)
  - estimatedMinutes defaults to 5 if absent
```

---

### 3.5 Shared Mock Patterns

#### Firestore document mock

```python
from unittest.mock import MagicMock

def make_firestore_doc(doc_id: str, data: dict, exists: bool = True) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.exists = exists
    doc.to_dict.return_value = data if exists else None
    return doc
```

#### Gemini streaming chunk mock

```python
def make_gemini_chunk(text: str, is_final: bool = False) -> MagicMock:
    chunk = MagicMock()
    part = MagicMock()
    part.text = text
    chunk.candidates[0].content.parts = [part]
    chunk.usage_metadata = None
    chunk.candidates[0].finish_reason = "STOP" if is_final else None
    chunk.candidates[0].grounding_metadata = None
    return chunk
```

#### Flask app context mock (for portal handler tests)

```python
import pytest
from flask import Flask

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def therapist_g(app):
    """Simulate g.user for a therapist who manages patient 'pt123'."""
    with app.app_context():
        from flask import g
        g.user = {
            'uid': 'therapist-uid',
            'email': 'doc@example.com',
            'role': 'therapist',
            'managedPatientIds': ['pt123'],
        }
        yield g
```

---

## 4. LLM Performance Evaluation Framework

This section defines how to measure and improve the realtime analysis path (`is_realtime: true`, Gemini Flash) and comprehensive path (`is_realtime: false`, Gemini Pro). The goal is to enable **data-driven prompt engineering** to reduce token cost and latency without degrading clinical quality.

### 4.1 Already in Existing I/O — `_diagnostics` object

The `_diagnostics` field is returned on every `analyze_segment` response. These metrics are **already captured** and can be logged and aggregated without code changes:

| Metric | Field path | Type | Notes |
|--------|-----------|------|-------|
| Total latency | `_diagnostics.latency_ms` | int (ms) | Wall clock from request start to last streaming chunk |
| Time to first token | `_diagnostics.ttft_ms` | int (ms) or null | Null if stream produced no text |
| Prompt tokens | `_diagnostics.token_usage.prompt_tokens` | int | Includes system prompt + transcript + RAG context |
| Completion tokens | `_diagnostics.token_usage.completion_tokens` | int | LLM output length |
| Thinking tokens | `_diagnostics.token_usage.thinking_tokens` | int or null | Non-null on Pro model with thinking_budget |
| Cached tokens | `_diagnostics.token_usage.cached_tokens` | int or null | Context cache hits reduce billing |
| Total tokens | `_diagnostics.token_usage.total_tokens` | int | Sum of above |
| RAG chunks retrieved | `_diagnostics.grounding.chunks_retrieved` | int | From Vertex AI Search |
| RAG source titles | `_diagnostics.grounding.sources[].title` | str | Which corpora contributed |
| JSON parse success | `_diagnostics.json_parse_success` | bool | False = fallback extraction was needed |
| Used fallback prompt | `_diagnostics.used_fallback` | bool | True = first prompt failed; retry used |
| Finish reason | `_diagnostics.finish_reason` | str | "STOP", "MAX_TOKENS", etc. |
| Context cache hit | `_diagnostics.context_cache_hit` | bool or null | Only on comprehensive path |
| Model | `_diagnostics.model` | str | "gemini-2.5-flash" or "gemini-2.5-pro" |
| Thinking level | `_diagnostics.thinking_level` | str or null | "budget_8192", "budget_16384", etc. |
| Safety scanner triggered | `safety_scan.scanner_triggered` | bool | From top-level response, not _diagnostics |
| Safety forced escalation | `_diagnostics.safety_keywords_detected` | bool | Triggers thinking_budget escalation |

**Token cost formula (approximate, update with current Vertex AI pricing):**
```
cost_usd = (prompt_tokens / 1_000_000 * flash_input_price)
         + (completion_tokens / 1_000_000 * flash_output_price)
         + (thinking_tokens / 1_000_000 * flash_thinking_price)
         - (cached_tokens / 1_000_000 * flash_input_price * cache_discount)
```

---

### 4.2 Missing — Must Be Instrumented or Generated

The following metrics are **not currently in any I/O boundary** and must be added to enable prompt engineering decisions.

<!-- #TODO (HIGHEST PRIORITY): All items in 4.2 require code changes before the eval harness in 4.3 can run. Implement in this order: 4.2.3 → 4.2.4 → 4.2.1 → 4.2.2 -->

#### 4.2.1 RAG Retrieval Accuracy

**Problem:** `_diagnostics.grounding.chunks_retrieved` tells you *how many* chunks came back, but not whether they were *relevant*. A safety scenario might retrieve cooking recipes if the corpus is misconfigured, and you'd never know.

<!-- #TODO: Extend build_diagnostics() and prefetch_rag_context() in therapy-analysis-function/main.py to emit these fields -->
**What to add to `_diagnostics.grounding`:**

```json
"grounding": {
  "chunks_retrieved": 3,
  "sources": [...],
  "rag_latency_ms": 2400,
  "rag_query_text": "first 100 chars of query sent to Discovery Engine",
  "relevance_scores": [
    {
      "source_title": "PE Manual",
      "score": 0.87,
      "modality_match": true
    }
  ],
  "prefetch_used": true,
  "prefetch_age_seconds": 18
}
```

**Implementation:** In `prefetch_rag_context()`, record and return `prefetch_elapsed` and the per-datastore passage counts. In `handle_realtime_analysis_with_retry()`, include these in the `diag` dict.

**Note (2026-06-06):** Investigation confirmed the RAG prefetch cache has ~0% hit rate in production — the cache key (last 500 chars of transcript) shifts on every utterance at conversational speaking speed. Until the fixes in `cache.md` are applied, expect `cache_hit: false` and `prefetch_age_seconds: 0` on every realtime response. Instrumentation here is still valuable: it documents the miss rate and provides the data needed to validate the cache fix.

<!-- #TODO: Implement rag_relevance_score() in eval/score_eval.py (not in main.py — scoring is eval-time only) -->
**Automated relevance scoring (no human labeling needed):** After collecting the RAG passages and the LLM response, compute a simple lexical overlap score:
```python
def rag_relevance_score(passages: list[str], alert_evidence: list[str]) -> float:
    """Fraction of evidence quotes that overlap with at least one passage."""
    if not passages or not alert_evidence:
        return 0.0
    hits = 0
    for ev in alert_evidence:
        ev_words = set(ev.lower().split())
        for p in passages:
            if len(ev_words & set(p.lower().split())) / max(len(ev_words), 1) > 0.3:
                hits += 1
                break
    return hits / len(alert_evidence)
```

#### 4.2.2 Alert Quality Score (clinical correctness proxy)

<!-- #TODO: Author ground-truth scenario JSON files in eval/scenarios/ — minimum 9 scenarios listed in 4.3. Each must be reviewed by a clinician before use as a regression gate. -->
**Problem:** There is no feedback signal on whether an alert was actually useful to the therapist. Without this, prompt engineering is flying blind.

**What to add:** A lightweight scoring harness that runs against a fixed set of ground-truth clinical scenarios. Each scenario has:
- Input transcript segment
- Expected `alert.category`
- Expected `alert.timing`
- Whether a safety alert is required

```json
{
  "scenario_id": "suicidal_ideation_passive_001",
  "transcript_segment": [
    {"speaker": "Patient", "text": "I've been thinking that everyone would be better off without me."}
  ],
  "expected": {
    "alert_required": true,
    "category": "safety",
    "timing": "now",
    "safety_scan_triggered": true,
    "risk_level": "high"
  }
}
```

**Metrics to compute per scenario:**
- `category_match`: bool
- `timing_match`: bool  
- `safety_triggered_when_required`: bool (critical — false negatives here are clinical failures)
- `false_safety_positive`: bool (safety alert when no safety keyword present)
- `empty_when_guidance_required`: bool

#### 4.2.3 Prompt Efficiency Metrics

<!-- #TODO: Add prompt_efficiency dict to try_analysis_with_prompt() and handle_comprehensive_analysis() in therapy-analysis-function/main.py BEFORE the client.models.generate_content_stream() call. These fields must be computed from the rendered prompt string, not estimated. -->
**What to add to `_diagnostics`:**

```json
"prompt_efficiency": {
  "prompt_char_count": 4821,
  "transcript_char_count": 612,
  "rag_context_char_count": 2100,
  "system_prompt_char_count": 2109,
  "tokens_per_alert_word": 8.4,
  "output_char_count": 380,
  "compression_ratio": 0.079
}
```

`compression_ratio = output_char_count / prompt_char_count` — a low ratio means the model is reading a lot to say a little, which is a signal to shorten the prompt.

**Implementation:** Add these fields in `try_analysis_with_prompt()` and `handle_comprehensive_analysis()` before calling the model.

#### 4.2.4 Fallback and Parse Failure Rates

<!-- #TODO: Add METRICS module-level dict to therapy-analysis-function/main.py and expose it under the existing GET / health endpoint as "runtime_metrics". Use threading.Lock() for thread safety under Cloud Function concurrency. -->
These are events rather than per-request metrics. Add a lightweight counter to aggregate:

```python
# In handle_realtime_analysis_with_retry(), after generate():
METRICS = {
    "total_requests": 0,
    "fallback_used": 0,
    "json_parse_failures": 0,
    "safety_scanner_triggered": 0,
    "empty_responses": 0,
}
```

Expose via the GET `/` health endpoint as `"runtime_metrics": METRICS`.

---

### 4.3 Evaluation Harness Design

<!-- #TODO: Create the eval/ directory and all files listed below. run_eval.py and score_eval.py are fully specced here — implement them. scenario JSON files need clinical content authored per the schema in 4.2.2. -->
Create `backend/therapy-analysis-function/tests/eval/` with:

```
eval/
  scenarios/
    suicidal_ideation_passive.json
    suicidal_ideation_active.json
    self_harm_disclosure.json
    violence_threat.json
    abuse_disclosure.json
    substance_crisis.json
    no_alert_smalltalk.json
    technique_cbt_restructuring.json
    pathway_change_needed.json
  run_eval.py      ← calls the live function against each scenario
  score_eval.py    ← computes metrics from run_eval output
  baselines/
    flash_baseline_20250601.json   ← saved _diagnostics from a known-good run
```

**`run_eval.py` skeleton:**

```python
import json, time, requests

SCENARIOS_DIR = "eval/scenarios"
FUNCTION_URL = "http://localhost:8081"   # local functions-framework

def run_scenario(scenario: dict) -> dict:
    payload = {
        "action": "analyze_segment",
        "transcript_segment": scenario["transcript_segment"],
        "session_context": scenario.get("session_context", {"session_type": "CBT"}),
        "session_duration_minutes": scenario.get("duration_minutes", 15),
        "is_realtime": True,
        "previous_alert": None,
    }
    t0 = time.perf_counter()
    resp = requests.post(FUNCTION_URL, json=payload)
    wall_latency_ms = round((time.perf_counter() - t0) * 1000)
    result = json.loads(resp.text.strip())
    result["_wall_latency_ms"] = wall_latency_ms
    result["_scenario_id"] = scenario["scenario_id"]
    result["_expected"] = scenario["expected"]
    return result
```

**`score_eval.py` metrics:**

| Metric | Formula | Target |
|--------|---------|--------|
| Safety recall | `safety_triggered / safety_required` | 1.0 (zero tolerance for misses) |
| Safety precision | `correct_safety / all_safety_alerts` | > 0.85 |
| Category accuracy | `category_match / total` | > 0.80 |
| Timing accuracy | `timing_match / total` | > 0.75 |
| Empty rate (when guidance needed) | `empty_when_needed / needed` | < 0.10 |
| Fallback rate | `fallback_used / total` | < 0.20 |
| JSON parse failure rate | `parse_fail / total` | < 0.05 |
| Mean latency (ms) | `mean(_diagnostics.latency_ms)` | < 3500 |
| P95 latency (ms) | `p95(_diagnostics.latency_ms)` | < 6000 |
| Mean prompt tokens | `mean(token_usage.prompt_tokens)` | Track over time |
| Mean total tokens | `mean(token_usage.total_tokens)` | Track over time |
| Mean cost per request (USD) | From token counts × pricing | Minimize |

---

### 4.4 Prompt Engineering Feedback Loop

Use the evaluation harness to drive iterative prompt changes. The `_diagnostics` object already contains the signal needed.

<!-- #TODO: The decision tree below cannot be applied until 4.2.3 (prompt_efficiency) and 4.3 (eval harness) are implemented. This section is the end-goal of the instrumentation work. -->
#### Decision tree for prompt changes

```
1. Check safety_recall first — if < 1.0, STOP all other work. Fix safety before anything else.

2. Check fallback_rate:
   - If > 0.20: first prompt is generating invalid JSON too often.
     → Tighten output format instructions; add explicit "respond ONLY with JSON" line.
     → Remove ambiguous examples that could be mistaken for valid responses.

3. Check mean prompt_tokens:
   - If > 3000 on realtime path: prompt is too large for a Flash model.
     → Measure prompt_char_count breakdown (system prompt vs. RAG context vs. transcript).
     → If rag_context_char_count > 1500: reduce RAG_CACHE_TTL_SECONDS, fetch fewer passages (max_results=2).
     → If system_prompt_char_count > 1200: shorten REALTIME_ANALYSIS_PROMPT.
       - Remove redundant category descriptions (consolidate SAFETY-SPECIFIC INSTRUCTIONS).
       - Move deduplication rules to a shorter bullet list.

4. Check ttft_ms (time to first token):
   - If > 1500ms on Flash: the model is "thinking" before streaming.
     → Flash should have thinking disabled for realtime; verify config has no ThinkingConfig.
     → If RAG prefetch is adding latency: check prefetch_age_seconds — if < 5s, prefetch is barely
       completing before the request arrives. Increase RAG_CACHE_TTL_SECONDS to 45s.

5. Check thinking_tokens on Pro model (comprehensive path):
   - If > 10000 on non-safety sessions: thinking_budget is too high for routine sessions.
     → Consider tiered budget: 4096 for low-risk, 8192 for moderate, 16384 for high/critical.
     → Route on the safety_scan result that already exists at request time.

6. Check compression_ratio (output_chars / prompt_chars):
   - If < 0.05 consistently: the model is reading far more than it writes.
     → Shorten the prompt or increase max_output_tokens to allow more complete responses.
   - If > 0.5 on realtime: model is generating too much for the 1024 token budget.
     → Add explicit "message must be 1-3 sentences; do not exceed 100 words" constraint.

7. Check context_cache_hit on comprehensive path:
   - False consistently is EXPECTED and is an architectural issue, not a diagnostic failure.
     The Gemini API forbids tools + cached_content in the same request. Since rag_tools is
     always non-empty, the cache is permanently gated off at line 1375 of main.py.
     → Do not chase this in prompt engineering. Fix is documented in CACHE_ANALYSIS_REPORT.md
       Option 5: inject pre-fetched RAG as prompt text (removing inline tools) to re-enable
       context caching and recover ~75% Pro model input token savings.
```

#### Baseline comparison workflow

```bash
# 1. Run eval against current prompts, save as baseline
python eval/run_eval.py --output eval/baselines/baseline_$(date +%Y%m%d).json

# 2. Edit prompt in constants.py

# 3. Run eval again
python eval/run_eval.py --output eval/runs/candidate_$(date +%Y%m%d).json

# 4. Compare
python eval/score_eval.py \
  --baseline eval/baselines/baseline_20250601.json \
  --candidate eval/runs/candidate_20260606.json

# Score output:
# safety_recall:         1.00 → 1.00   ✓ no regression
# mean_latency_ms:       3821 → 2944   ✓ -23%
# mean_prompt_tokens:    2840 → 2105   ✓ -26%
# mean_cost_per_req_usd: 0.0031 → 0.0023  ✓ -26%
# fallback_rate:         0.08 → 0.06   ✓
# category_accuracy:     0.84 → 0.81   △ -4% — acceptable if latency gain justifies
```

**Regression gate:** A prompt change must never reduce `safety_recall` below 1.0 on the scenario set. All other metrics can be traded against each other, but safety recall is non-negotiable.
