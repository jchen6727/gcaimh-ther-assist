# Multi-Modality RAG Architecture for Ther-Assist

This directory contains the setup scripts and corpus files for the multi-modality RAG (Retrieval Augmented Generation) system that powers Ther-Assist's real-time therapy guidance.

## Architecture Overview

Ther-Assist uses a multi-modality RAG architecture with shared foundational datastores plus per-modality clinical research datastores. The backend dynamically selects which RAG tools to use based on the session's therapeutic approach.

### Shared Datastores (always active)

#### 1. EBT Manuals Store (`ebt-corpus`)
- **Purpose**: Evidence-based protocols, techniques, contraindications
- **Content**:
  - CBT manuals
  - PE for PTSD protocols
  - Social phobia treatment guides
- **Chunking**: 500 tokens with layout-aware parsing
- **Query examples**: "grounding techniques for dissociation", "CBT thought challenging steps"

#### 2. Clinical Transcripts Store (`transcript-patterns`)
- **Purpose**: Pattern recognition, therapeutic moments, real-world examples
- **Content**:
  - Beck CBT sessions (BB3)
  - PTSD/PE sessions
  - Thousand Voices of Trauma conversations
  - Therapeutic pattern library
- **Chunking**: 300 tokens optimized for dialogue (3-turn sequences)
- **Query examples**: "therapist handling client resistance", "preparing client for exposure therapy"

### Per-Modality Datastores (selected based on session type)

#### 3. CBT Research Store (`cbt-corpus`)
- **Purpose**: CBT-specific RCTs, meta-analyses, treatment protocols
- **Selected when**: Session type is CBT, Exposure, or ACT
- **Chunking**: 500 tokens with layout-aware parsing

#### 4. Behavioral Activation Store (`ba-corpus`)
- **Purpose**: BA-specific RCTs, meta-analyses, and treatment studies
- **Content**: 11 clinical research PDFs covering BA efficacy, depression treatment, and activity scheduling
- **Selected when**: Session type is BA (Behavioral Activation)
- **Chunking**: 500 tokens with layout-aware parsing

#### 5. Dialectical Behavior Therapy Store (`dbt-corpus`)
- **Purpose**: DBT-specific RCTs, systematic reviews, and efficacy studies
- **Content**: 6 clinical research PDFs covering DBT for BPD, emotional dysregulation, and skills training
- **Selected when**: Session type is DBT
- **Chunking**: 500 tokens with layout-aware parsing

#### 6. Interpersonal Psychotherapy Store (`ipt-corpus`)
- **Purpose**: IPT-specific RCTs, meta-analyses, and treatment comparisons
- **Content**: 10 clinical research PDFs covering IPT for depression, interpersonal functioning, and comparative efficacy
- **Selected when**: Session type is IPT
- **Chunking**: 500 tokens with layout-aware parsing

### Dynamic RAG Tool Selection

The backend's `get_rag_tools_for_session()` function selects tools based on session type:

| Session Type | Realtime Tools | Comprehensive Tools |
|---|---|---|
| CBT | `ebt-corpus` + `cbt-corpus` | `ebt-corpus` + `cbt-corpus` + `transcript-patterns` |
| BA | `ebt-corpus` + `ba-corpus` | `ebt-corpus` + `ba-corpus` + `transcript-patterns` |
| DBT | `ebt-corpus` + `dbt-corpus` | `ebt-corpus` + `dbt-corpus` + `transcript-patterns` |
| IPT | `ebt-corpus` + `ipt-corpus` | `ebt-corpus` + `ipt-corpus` + `transcript-patterns` |
| Exposure | `ebt-corpus` + `cbt-corpus` | `ebt-corpus` + `cbt-corpus` + `transcript-patterns` |
| ACT | `ebt-corpus` + `cbt-corpus` | `ebt-corpus` + `cbt-corpus` + `transcript-patterns` |

## Setup Instructions

### Prerequisites
- Complete all steps prior to this in the root README.md
- Install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Setting Up EBT Manuals Datastore

```bash
# Run setup script
export GOOGLE_CLOUD_PROJECT="your-gcp-project"
python setup_rag_datastore.py
```

This will:
- Create the `ebt-corpus` datastore
- Upload manuals to GCS
- Import documents with 500-token chunking
- Configure layout-aware parsing for PDFs

Check your [AI Application Datastore]((https://console.cloud.google.com/ai/search/datastores)) if it times out, sometimes it correctly uploads documents but does not correctly alert the user

### Setting Up Modality Datastores (BA, DBT, IPT)

```bash
export GOOGLE_CLOUD_PROJECT="your-gcp-project"

# Setup all 3 modality datastores
python setup_modality_datastores.py

# Or setup a single modality
python setup_modality_datastores.py --modality ba
python setup_modality_datastores.py --modality dbt
python setup_modality_datastores.py --modality ipt
```

This will for each modality:
- Create the modality-specific datastore (`ba-corpus`, `dbt-corpus`, or `ipt-corpus`)
- Create a GCS bucket and upload research PDFs
- Import documents with 500-token layout-aware chunking
- Wait for the import operation to complete

### Setting Up Transcript Patterns Datastore

```bash
python setup_transcript_datastore.py
```

This will:
- Create the `transcript-patterns` datastore
- Process PDFs and JSON conversations
- Create 3-turn dialogue sequences
- Generate therapeutic pattern library
- Upload to GCS with 300-token chunking

**IMPORTANT NOTES:**
- **Timeout Issues**: Import operations can take 10+ minutes and may timeout. If this happens:
  1. Check the operation status in [Google Cloud Console](https://console.cloud.google.com/ai/search/datastores)
  2. The operation may still be running in the background
  3. Use the resumable version: `python setup_transcript_datastore_resumable.py`
- **File Limit**: If you get a 400 error about exceeding maximum files, go to the [Google Cloud Datastore page](https://console.cloud.google.com/ai/search/datastores) and manually upload your entire bucket as unstructured content
- **Wrong Datastore Error**: If you see references to `ebt-corpus` instead of `transcript-patterns`, make sure you're running the correct script

## Corpus Organization

```
setup_services/rag/
├── corpus/                    # EBT Manuals
│   ├── APA_Boswell_Constantino_Deliberate_Practice_CBT.pdf
│   ├── Comprehensive-CBT-for-Social-Phobia-Manual.pdf
│   ├── PE_for_PTSD_2022.pdf
│   └── References_for_Exposure_Therapy_Manuals_and_Guidebooks.docx
│
├── corpus_ba/                 # Behavioral Activation Research (11 PDFs)
│   ├── BA RCTs, meta-analyses, depression treatment studies
│   └── Activity scheduling and behavioral change research
│
├── corpus_dbt/                # Dialectical Behavior Therapy Research (6 PDFs)
│   ├── DBT RCTs, BPD treatment studies
│   └── Emotional dysregulation and skills training research
│
├── corpus_ipt/                # Interpersonal Psychotherapy Research (10 PDFs)
│   ├── IPT RCTs, meta-analyses
│   └── Depression and interpersonal functioning studies
│
└── transcripts/               # Clinical Transcripts
    ├── BB3-Session-2-Annotated-Transcript.pdf      # Beck CBT
    ├── BB3-Session-10-Annotated-Transcript.pdf     # Beck CBT
    ├── PE_Supplement_Handouts-Oct-22_0.pdf         # PTSD/PE
    └── ThousandVoicesOfTrauma/
        └── conversations/     # JSON therapy conversations
            ├── 100_P5_conversation.json
            ├── 100_P6_conversation.json
            └── ... (30+ sessions)
```

## How It Works in Real-Time

When analyzing a therapy session segment:

1. **Pattern Matching**: The system searches transcript patterns for similar therapeutic moments
2. **Protocol Lookup**: EBT manuals provide evidence-based guidance
3. **Synthesis**: The LLM combines both sources to provide:
   - Theoretical guidance from manuals
   - Practical examples from real sessions
   - Specific recommendations

Example output:
> "This resistance pattern is similar to Beck Session 2, where the client said 'I don't want to impose.' Dr. Beck used Socratic questioning [Transcript Citation]. The CBT manual recommends challenging cognitive distortions through evidence gathering [Manual Citation, p.45]."

## Therapeutic Pattern Library

The system includes a curated pattern library with:

### Resistance Patterns
- "I don't want to impose" → Socratic questioning
- "I'm not ready" → Validation with gradual approach

### Engagement Techniques
- Checking task likelihood (0-100% scale)
- Collaborative tone ("Would that be alright?")
- Breaking overwhelming tasks into small steps

### Quality Markers
**Positive:**
- Concrete planning with specific times
- Positive reinforcement
- Making tasks optional

**Warning Signs:**
- Pushing too fast when client hesitates
- Missing psychoeducation opportunities
- Ignoring signs of overwhelm

## Maintenance

### Adding New EBT Manuals
1. Place PDF/DOCX files in `setup_services/rag/corpus/`
2. Re-run `setup_rag_datastore.py`

### Adding New Modality Research
1. Place PDFs in the appropriate corpus directory:
   - BA research: `setup_services/rag/corpus_ba/`
   - DBT research: `setup_services/rag/corpus_dbt/`
   - IPT research: `setup_services/rag/corpus_ipt/`
2. Re-run `setup_modality_datastores.py --modality <ba|dbt|ipt>`

### Adding a New Modality
1. Create a new corpus directory: `setup_services/rag/corpus_<modality>/`
2. Add the modality config to `MODALITIES` dict in `setup_modality_datastores.py`
3. Add the RAG tool definition in `backend/therapy-analysis-function/main.py`
4. Add the mapping in `MODALITY_RAG_MAP` in `main.py`
5. Run `setup_modality_datastores.py --modality <new_modality>`

### Adding New Transcripts
1. Place PDFs in `setup_services/rag/transcripts/`
2. Place JSON conversations in `setup_services/rag/transcripts/ThousandVoicesOfTrauma/conversations/`
3. Re-run `setup_transcript_datastore.py`

### Updating Pattern Library
Edit the `create_pattern_library()` function in `setup_transcript_datastore.py` to add new patterns.

## Troubleshooting

### Authentication Issues
```bash
gcloud auth application-default login
gcloud config set project your-gcp-project-id
```

### Import Timeout
The import operation can take 5-10 minutes. Check status in:
- [Google Cloud Console](https://console.cloud.google.com/ai/search/datastores)

**If you got a timeout error:**
1. Your operation may still be running in the background
2. Check the Google Cloud Console to see if documents are being imported
3. Wait for the operation to complete before running the script again
4. Use the resumable version to avoid re-uploading files: `python setup_transcript_datastore_resumable.py`

### Operation Status Check
To check if your import operation is still running:

1. **Google Cloud Console** (recommended):
   - Go to [Vertex AI Search](https://console.cloud.google.com/ai/search/datastores)
   - Look for your `transcript-patterns` datastore
   - Check the "Documents" tab to see if import is in progress
   - Look for import status indicators

2. **Check your operation ID**:
   - If you have the operation ID from the script output (like `projects/1001561436755/locations/global/collections/default_collection/dataStores/ebt-corpus/branches/0/operations/import-documents-1777447049591343122`)
   - You can check its status in the Google Cloud Console under Operations

### Missing Dependencies
```bash
pip install -r requirements.txt
```

## Testing

TODO: This doesn't exist yet 

After setup, test the dual-RAG system:

1. Start the backend:
```bash
cd test_scripts
./start_all_services.sh
```

2. Check logs for dual-RAG citations:
- Citations from manuals: `[1], [2]` 
- References to transcript patterns: "Similar to Beck Session 2"

## Architecture Benefits

The multi-modality RAG approach provides:

1. **Evidence-Based Foundation**: Manuals ensure adherence to proven protocols
2. **Modality-Specific Guidance**: Each therapy type gets research tailored to its approach (BA, DBT, IPT, CBT)
3. **Dynamic Selection**: Backend automatically selects the right RAG tools based on session type
4. **Real-World Context**: Transcripts show how theory applies in practice
5. **Pattern Recognition**: Quickly identify and respond to common therapeutic moments
6. **Quality Benchmarking**: Compare current session to exemplar sessions
7. **Scalable Design**: New modalities can be added with a new corpus directory + config entry

This creates a clinically sophisticated AI assistant that provides both theoretical grounding and practical wisdom, tailored to the specific therapeutic modality being used.
