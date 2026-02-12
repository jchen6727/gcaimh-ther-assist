# Ther-Assist: Recent Engineering Updates
## Talking Points for Clinician + Engineering Review

---

## 1. Dual-Model Architecture: Gemini 2.5 Flash + Pro

We upgraded from a single model to a **dual-model architecture** that uses each model where it makes the most clinical sense:

### Gemini 2.5 Flash (Realtime Analysis)
- **Purpose**: Speed-critical, real-time therapeutic guidance during the session
- **Why Flash**: Sub-second latency is essential so the therapist gets alerts (safety, technique, engagement) without lag while the patient is speaking
- **Configuration**: `temperature=0.0` (deterministic, no hallucination), `max_output_tokens=2048`
- **RAG tools loaded**: EBT Manuals + Modality-Specific Research Corpus (e.g., CBT corpus for CBT sessions, BA corpus for BA sessions)
- **Trigger phrase detection**: If the patient says something like "I might fall apart" or "scared but I want to do it", the system switches from a strict prompt (minimal alerts) to a non-strict prompt (richer guidance)

### Gemini 2.5 Pro (Comprehensive, Pathway, Summary)
- **Purpose**: Deep clinical analysis that runs in the background every ~30 words
- **Why Pro**: Higher reasoning capability for multi-dimensional analysis (engagement level, therapeutic alliance, arousal, emotional state, pathway effectiveness) and for generating session summaries with homework recommendations
- **Configuration**: `temperature=0.3`, `max_output_tokens=4096`, extended thinking enabled with variable budgets
- **RAG tools loaded**: EBT Manuals + Modality-Specific Corpus + Clinical Transcript Patterns (real Beck sessions, PTSD sessions, Thousand Voices of Trauma)
- **Used in 3 handlers**:
  - **Comprehensive Analysis** — returns session metrics (engagement, alliance, emotional state, arousal, phase-appropriateness) + pathway guidance (continue/change approach, rationale with citations, alternative approaches, contraindications)
  - **Pathway Guidance** — dedicated pathway analysis with evidence-based recommendations
  - **Session Summary** — end-of-session report with key moments, techniques used, progress indicators, homework assignments referencing treatment manuals, and risk assessment

### Where This Matters Clinically
- The therapist sees **immediate alerts** (Flash) while the session is happening — safety flags, technique suggestions, engagement cues
- The **background analysis** (Pro) powers the metrics dashboard, pathway recommendations, and the full summary — deeper analysis that benefits from more reasoning time
- Both models pull from the same evidence-based RAG datastores, so guidance is always grounded in clinical literature

**Files**: `backend/therapy-analysis-function/constants.py` (model definitions, lines 15-16), `main.py` (Flash at line 525, Pro at lines 779, 953, 1065)

---

## 2. RAG Datastores: Evidence-Based Treatment Corpus on GCP

We built a **multi-datastore RAG architecture** using Google Vertex AI Search (Discovery Engine) on GCP. Each datastore is a searchable corpus of clinical research that the LLM queries during analysis.

### Datastores Created and Active on GCP

| Datastore | Content | Documents |
|---|---|---|
| `ebt-corpus` | Evidence-Based Treatment manuals — PE for PTSD, CBT for Social Phobia, Deliberate Practice in CBT | 4 clinical manuals |
| `cbt-corpus` | CBT randomized controlled trials and clinical studies | 31 RCTs |
| `transcript-patterns` | Real clinical transcripts — Beck CBT sessions, PE sessions, Thousand Voices of Trauma conversations | 30+ session transcripts |

### How They Were Set Up

1. **Setup Script**: `setup_services/rag/setup_rag_datastore.py`
   - Creates the datastore via Discovery Engine REST API
   - Creates a GCS (Google Cloud Storage) bucket
   - Uploads all PDFs to the bucket
   - Imports documents with **layout-aware chunking**: 500 tokens per chunk with ancestor headings preserved for context
   - Waits for the import operation to complete

2. **Chunking Strategy**: Each PDF is parsed with layout awareness — the system understands document structure (headings, sections, tables) and creates 500-token chunks that include the parent heading chain. This means when the LLM retrieves a chunk about "grounding techniques," it also knows it came from the "Dissociation Management" section of the PE manual.

3. **Transcript Datastore**: `setup_services/rag/setup_transcript_datastore.py` — different chunking strategy (300 tokens, optimized for 3-turn dialogue sequences) to preserve therapeutic conversation flow.

### RAG Tool Definitions in Backend

Each datastore is registered as a Vertex AI Search retrieval tool in `main.py` (lines 227-279):

```
MANUAL_RAG_TOOL  → ebt-corpus   (always active — core protocols)
CBT_RAG_TOOL     → cbt-corpus   (active for CBT, Exposure, ACT sessions)
TRANSCRIPT_RAG_TOOL → transcript-patterns (active for comprehensive analysis only)
```

### Prompts Updated

All prompt templates in `constants.py` were updated to support multi-modality:
- `REALTIME_ANALYSIS_PROMPT` — instructs the LLM: "Analyze this therapy segment for real-time guidance using a **{current_approach}** approach"
- `COMPREHENSIVE_ANALYSIS_PROMPT` — includes full session context (phase, duration, session type, focus topics, current therapeutic approach) and instructs the LLM to search transcript patterns and reference EBT manual protocols with inline citations [1], [2]
- `PATHWAY_GUIDANCE_PROMPT` — references current approach and presenting issues with citation requirements
- `SESSION_SUMMARY_PROMPT` — generates homework assignments with treatment manual references

**Files**: `setup_services/rag/setup_rag_datastore.py`, `setup_services/rag/setup_transcript_datastore.py`, `backend/therapy-analysis-function/main.py` (lines 224-318), `constants.py` (lines 34-296)

---

## 3. New Modality Manuscripts: BA, DBT, IPT (Staged for GCP Upload)

We prepared **three additional therapy modality corpora** for Behavioral Activation, Dialectical Behavior Therapy, and Interpersonal Psychotherapy. These manuscripts have been:

### What's Done
- **27 clinical research PDFs** organized into corpus directories in the repo:
  - `setup_services/rag/corpus_ba/` — 11 PDFs (BA RCTs, meta-analyses, depression treatment, activity scheduling studies)
  - `setup_services/rag/corpus_dbt/` — 6 PDFs (DBT RCTs, BPD treatment, emotional dysregulation, skills training)
  - `setup_services/rag/corpus_ipt/` — 10 PDFs (IPT RCTs, meta-analyses, depression, interpersonal functioning)

- **Setup script created**: `setup_services/rag/setup_modality_datastores.py`
  - Supports `--modality ba|dbt|ipt|all`
  - Same chunking strategy as EBT corpus (500 tokens, layout-aware, ancestor headings)
  - Creates GCS bucket, uploads PDFs, imports into Discovery Engine datastore

- **Backend fully wired**: `main.py` already has the RAG tool definitions (`BA_RAG_TOOL`, `DBT_RAG_TOOL`, `IPT_RAG_TOOL`) and the dynamic selection map:

  ```
  MODALITY_RAG_MAP:
    CBT      → cbt-corpus
    BA       → ba-corpus
    DBT      → dbt-corpus
    IPT      → ipt-corpus
    Exposure → cbt-corpus (PE protocols in ebt-corpus)
    ACT      → cbt-corpus
  ```

- **Dynamic selection function**: `get_rag_tools_for_session()` automatically selects the right RAG tools based on the session's therapeutic approach. A BA session will query BA-specific research, a DBT session will query DBT research, etc.

### What's Pending
- The PDFs are **on Google Drive and in the Git repo** but **not yet uploaded to GCP**
- Running `python setup_modality_datastores.py` will create the 3 new datastores and upload all documents
- Once uploaded, the backend will automatically use them — no further code changes needed

**Files**: `setup_services/rag/corpus_ba/`, `corpus_dbt/`, `corpus_ipt/`, `setup_services/rag/setup_modality_datastores.py`, `backend/therapy-analysis-function/main.py` (lines 255-318)

---

## 4. Frontend-to-Backend Mapping: Removing Hardcoded Values

We audited every frontend component to ensure **no static or hardcoded values** are displayed where real backend data should appear. The frontend developer (Tarek) built the UI with placeholder values; we mapped those to actual backend responses.

### Changes Made

**`frontend/components/App.tsx`**:
- Added `patientId` prop pass-through to `NewTherSession` — was never connected before
- Session summary now looks up the actual patient name from the patient list instead of hardcoded "John Doe"

**`frontend/components/NewTherSession.tsx`**:
- **Session Context**: Previously hardcoded as `{session_type: 'CBT', primary_concern: 'Anxiety and Social Situations', current_approach: 'Cognitive Behavioral Therapy'}`. Now **dynamically derived** from the patient's `focusTopics` — parses the topics, detects the modality (CBT, EMDR, Exposure, BA, ACT, DBT), and sets the session type and approach accordingly
- **Patient Name**: Changed fallback from "John Doe" to "New Session"
- **Phase Indicator**: Was static "Phase-appropriate" label. Now shows "Phase-appropriate" (green) or "Assessing..." (amber) based on real `sessionMetrics.phase_appropriate` from the backend

**`frontend/components/GuidanceTab.tsx`**:
- Engagement percentage display restructured — label and percentage on separate row from progress bar to prevent overlap at 100% zoom

**`frontend/components/TherapistNotesPanel.tsx`**:
- Default state changed from expanded to collapsed to reclaim vertical space

### How the Data Flows
1. Patient selected in sidebar → `patientId` passed to `NewTherSession`
2. Patient's `focusTopics` parsed → `sessionContext` derived (session_type, primary_concern, current_approach)
3. `sessionContext` sent with every API request → backend selects correct RAG tools and formats prompts with the right therapeutic approach
4. Backend returns metrics → frontend displays real values (engagement level, alliance, emotional state, etc.)

**Files**: `frontend/components/App.tsx`, `NewTherSession.tsx`, `GuidanceTab.tsx`, `TherapistNotesPanel.tsx`

---

## 5. LLM Response Metadata: Citations and Grounding Chunks

When the LLM responds, it doesn't just give text — it returns **grounding metadata** that traces every claim back to the clinical literature.

### How It Works

1. **RAG Query**: The LLM sends a retrieval query to the Vertex AI Search datastores
2. **Chunk Retrieval**: The datastore returns relevant chunks (500-token passages) from clinical PDFs
3. **Grounded Response**: The LLM generates its response using those chunks as context
4. **Grounding Metadata Returned**: The API response includes `grounding_metadata.grounding_chunks`, each containing:
   - **Source title**: Which PDF/document the chunk came from (e.g., "PE_for_PTSD_2022.pdf")
   - **URI**: The GCS path to the original document
   - **Excerpt**: The exact text chunk the LLM used
   - **Page span**: First and last page numbers the chunk was extracted from
   - **Citation number**: Maps to inline `[1]`, `[2]` references in the LLM's response text

### What the Clinician Sees

- The LLM's guidance text includes inline citations like `[1]`, `[2]`
- The citation panel shows which clinical document each number refers to, with page numbers
- Example: "Consider graded exposure following the PE protocol [1], while monitoring for avoidance behaviors [2]" — where [1] = PE for PTSD Manual, p.45 and [2] = CBT Social Phobia Manual, p.112

### Technical Details

- **Extraction code**: `main.py` lines 540-560 — iterates over `grounding_chunks` from the Gemini API response
- **Citation structure**: Each citation includes `citation_number`, `source.title`, `source.uri`, `source.excerpt`, `source.pages.first/last`
- **Attached to every response type**: Realtime alerts, comprehensive analysis, pathway guidance, and session summaries all include citations

**Files**: `backend/therapy-analysis-function/main.py` (lines 540-560 extraction, lines 657/842/994/1102 attachment)

---

## 6. LLM Activity Log: Live Diagnostics Panel

We added an **LLM Activity Log** panel so engineers and clinicians can see exactly what the AI is doing in real time during a session.

### What It Shows

Each log entry displays:
- **Timestamp**: When the analysis was triggered (HH:MM:SS)
- **Model**: Which model handled it — "Flash" (cyan badge) for realtime, "Pro" (purple badge) for comprehensive
- **Analysis Type**: "realtime" or "comprehensive"
- **Phase**: Started (play icon), Complete (checkmark), Error (X mark)
- **Summary Line**: One-line description of what happened

### Expandable Details (click to expand any entry)

- **Prompt Template**: Which prompt was used (strict vs non-strict for realtime)
- **Configuration**: Temperature, max output tokens, thinking budget
- **RAG Tools**: Which datastores were queried (e.g., `["ebt-corpus", "cbt-corpus"]`)
- **Latency**: Total response time in milliseconds
- **TTFT**: Time to first token (streaming latency)
- **Token Usage**: Input tokens, output tokens, total, thinking tokens, cached tokens
- **Grounding**: Number of chunks retrieved, source documents referenced
- **JSON Parse**: Whether the response was valid JSON (success/failure)
- **Fallback Flag**: Whether the system had to retry with a different prompt
- **Trigger Phrase**: Whether a trigger phrase was detected in the transcript
- **Result Summary**: Quick metrics snapshot (e.g., "engagement=0.72, alliance=moderate")

### Additional Features
- **Download Log**: Export the full activity log as JSON for post-session analysis
- **Auto-Scroll**: Lock/unlock auto-scroll to follow new entries or browse history
- **Clear**: Reset the log for a fresh session

### Why This Matters
- **For engineers**: Full observability into model behavior, latency, token usage, RAG retrieval, and prompt selection
- **For clinicians**: Transparency into what the AI is doing and what evidence it's using — builds trust in the system

**Files**: `frontend/components/ActivityLog.tsx` (full component), `backend/therapy-analysis-function/main.py` (diagnostics builder at lines 124-176)

---

## 7. Transcript Upload Feature

We added the ability to **upload test transcript scripts** so we can run different clinical scenarios through the system without needing a live session.

### How It Works
1. Click the **"Upload Script"** button (green, with upload icon) in the session controls
2. Select a `.json` file containing a transcript
3. The system validates the format and starts automatic playback

### Transcript Format
```json
[
  {"speaker": "THERAPIST", "text": "How are you feeling today?"},
  {"speaker": "PATIENT", "text": "I've been really anxious about the presentation..."},
  {"speaker": "THERAPIST", "text": "Tell me more about what makes you anxious."}
]
```

### Playback Behavior
- Entries are delivered every 2 seconds (simulating real conversation pace)
- Each entry triggers the full analysis pipeline (realtime + comprehensive)
- Playback can be paused and resumed
- When the transcript ends, the system automatically generates a session summary

### Why This Matters
- Test specific clinical scenarios (panic, dissociation, resistance, breakthrough moments)
- Validate RAG retrieval quality with known transcript content
- Demo the system to clinicians with realistic therapy conversations
- Compare system responses across different therapeutic approaches

**Files**: `frontend/components/NewTherSession.tsx` (upload handler at lines 999-1049, playback at lines 930-992, UI at lines 1678-1706)

---

## 8. Backend Connection Indicator

We added a **real-time connection status indicator** in the frontend that tells the therapist whether they're connected to the AI model.

### How It Works
- On page load, the frontend pings the backend at the configured API endpoint
- Checks if the backend is reachable with a 5-second timeout

### Status States

| Status | Icon | Color | Meaning |
|---|---|---|---|
| **Checking** | Cloud Queue | Yellow | Initial ping in progress |
| **Connected** | Cloud | Green | Backend is live and responding — GCP models are available |
| **Mock Mode** | Cloud Off | Amber | No backend URL configured — running with simulated data |
| **Error** | Cloud Off | Red | Backend unreachable — network issue or server down |

### Why This Matters
- **During demo/pilot**: Instant visual confirmation that the system is connected to GCP and the Gemini models
- **During development**: Clear indicator of whether you're running against real models or mock data
- **Troubleshooting**: If the clinician isn't seeing AI guidance, the first thing to check is this indicator

**Files**: `frontend/components/BackendStatusIndicator.tsx` (connection check at lines 25-43, status rendering at lines 48-83)
