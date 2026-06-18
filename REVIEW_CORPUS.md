# RAG Corpus Review

## Context

TherAssist provides real-time analysis during live therapy sessions. The `COMPREHENSIVE_ANALYSIS_PROMPT` in `constants.py` explicitly instructs the model to "Reference evidence-based manual protocols with citations [1], [2]" and "Look for similar patterns in the transcript database." The system routes both a modality-specific research corpus and (in the comprehensive path) a transcript corpus into those citations. This review assesses whether retrieved chunks would actually be useful to a clinician mid-session.

The central problem the user identified is correct: **a chunk from an RCT retrieved mid-session is operationally useless**. "The HAMD-17 score decreased by 6.2 points (95% CI: 4.1–8.3)" tells a therapist nothing about what to say to the patient in the next 30 seconds. What is needed instead is procedural knowledge — how to conduct an exposure hierarchy, how to roll with resistance in MI, what a chain analysis looks like in DBT.

---

## Datastores and Corpus Documents

### 1. `ebt-corpus` — EBT Treatment Manuals (4 documents)

| Document | Type | Clinical Utility |
|---|---|---|
| Prolonged Exposure Therapy for PTSD — Clinical Manual (2022) | Treatment manual | ✓ High — step-by-step PE protocols, imaginal/in-vivo procedures |
| Comprehensive CBT for Social Phobia — Treatment Manual | Treatment manual | ✓ High — session structure, cognitive restructuring scripts |
| Deliberate Practice in CBT (Boswell & Constantino, APA) | Training manual | ✓ Moderate — technique refinement, not session procedures |
| Exposure Therapy Manuals and Guidebooks — Reference Guide | Reference guide (DOCX) | ✗ Low — a bibliography, not procedural content |

**Assessment**: The strongest corpus in the stack. Two genuine treatment manuals provide exactly the procedural content the prompt citation instruction implies. Always included (`MANUAL_RAG_TOOL` is in every call path, realtime and comprehensive).

---

### 2. `cbt-corpus` — CBT Research Papers (31 documents)

Every entry in `cbt_metadata.jsonl` is a research study. Type breakdown:

| `document_type` value | Count |
|---|---|
| `randomized_controlled_trial` | 14 |
| `clinical_study` | 10 |
| `efficacy_study` | 2 |
| `review_paper` | 1 |
| `pilot_study` | 1 |
| `study_protocol` | 1 |
| `training_manual` | 0 |
| `treatment_manual` | 0 |

Representative titles: "Transdiagnostic CBT for Anxiety — RCT," "CBT via Telemedicine vs In-Person — Randomized Trial," "Coach-Guided App-Based CBT — Randomized Trial," "Brief Group CBT — Randomized Trial."

**Assessment**: **Entirely inappropriate for real-time session guidance.** Chunks retrieved from these 31 papers will be drawn from participant exclusion criteria, CONSORT flow diagrams, regression tables, follow-up attrition rates, and discussion of effect sizes. None of this answers "patient is resisting the exposure hierarchy right now." The model's citation instruction is misleading: it will produce `[1]` citations that look authoritative but point to RCT methods sections.

---

### 3. `ba-corpus` — Behavioral Activation Research (11 documents)

All 11 local PDFs are clinical research studies by title:

| Filename (truncated) | Apparent type |
|---|---|
| a phase II randomized controlled.pdf | RCT |
| A Pragmatic Randomized Clinical.pdf | RCT |
| Behavioral activation therapy for.pdf | Clinical study |
| Behavioural Activation for Depression.pdf | Review or study |
| Behavioural activation therapies.pdf | Review |
| behavioural activation.pdf | Overview |
| Brief Behavioral Activation Intervention.pdf | Clinical study |
| Enduring effects of a 5.pdf | Follow-up study |
| Randomized control trial of a culturally.pdf | RCT |
| Randomized Trial of Behavioral Activation.pdf | RCT |
| The Adolescent Behavioral Activation.pdf | Study |

No BA treatment manual (e.g., Lejuez's BATD manual or Martell's BA for Depression) is present.

**Assessment**: Same problem as CBT corpus. Empirically validates BA; tells a clinician nothing about how to construct an activity schedule with a patient who is anhedonic and resistant mid-session.

---

### 4. `dbt-corpus` — DBT Research (6 documents)

| Filename (truncated) | Apparent type |
|---|---|
| A pilot randomized controlled trial of Dialectical.pdf | RCT |
| A systematic review and meta.pdf | Meta-analysis |
| Dialectical Behavior Therapy.pdf | **Possibly Linehan manual** |
| Dialectical Behaviour Therapy.pdf | **Possibly Linehan manual** |
| Randomized clinical trial of a brief.pdf | RCT |
| Systematic Review Assessing the Efficacy.pdf | Systematic review |

**Assessment**: Two documents have titles that may correspond to Linehan's foundational DBT texts, which are treatment manuals with procedural content. If so, these would be the only modality-specific manuals in any of the non-EBT datastores. The remaining four are research studies. Cannot verify content without reading the PDFs; the filenames are ambiguous.

---

### 5. `ipt-corpus` — IPT Research (10 documents)

| Filename (truncated) | Apparent type |
|---|---|
| A meta analysis.pdf | Meta-analysis |
| A Randomized Clinical Trial of.pdf | RCT |
| Adapting group interpersonal psychotherapy.pdf | Adaptation study |
| cognitive behavioral therapy for depression delivered both.pdf | Comparative RCT |
| Depressed Women With Sexual Abuse.pdf | Clinical study |
| Group Interpersonal.pdf | Group therapy study |
| Interpersonal psychotherapy versus.pdf | Comparative study |
| Randomized Controlled Trial of Interpersona.pdf | RCT |
| The efficacy of interpersonal psychotherapy.pdf | Efficacy study |
| Treatment of Depression in.pdf | Clinical study |

No IPT treatment manual (e.g., Weissman & Markowitz) is present. One document (`cognitive behavioral therapy for depression delivered both.pdf`) appears to be a CBT comparative study that landed in the IPT corpus by accident.

**Assessment**: Entirely research studies. One appears misclassified. Zero procedural content.

---

### 6. `safety-crisis` — Safety and Crisis Protocols (9 documents)

| Document | Type |
|---|---|
| 988 Lifeline Suicide Risk Assessment Standards | Clinical protocol |
| 988 Lifeline Suicide Safety Policy | Policy/protocol |
| C-SSRS Baseline Screening | Assessment instrument |
| C-SSRS Full Baseline | Assessment instrument |
| ChildWelfare Mandatory Reporting Statutes | Legal/protocol |
| SAMHSA National Guidelines for Crisis Care | Clinical guideline |
| SAMHSA SAFE-T Suicide Assessment | Assessment protocol |
| SAMHSA TIP50 Suicidal Thoughts and Substance Abuse | Clinical guideline |
| Stanley-Brown Safety Planning Intervention | Treatment protocol |

**Assessment**: **The most appropriate corpus in the stack.** These are all procedural instruments and clinical guidelines — exactly the kind of document a clinician needs during a safety event. Always included via `SAFETY_RAG_TOOL`. This corpus is well-curated.

---

### 7. `transcript-patterns` — Clinical Transcripts (3,012 documents)

Three sub-collections:

**Annotated PDFs (3 documents)**

| Document | Type | Clinical Utility |
|---|---|---|
| Beck CBT Session 2 — Annotated Transcript (Judith Beck) | Annotated transcript | ✓ High |
| Beck CBT Session 10 — Annotated Transcript (Judith Beck) | Annotated transcript | ✓ High |
| PE Supplement Handouts (Oct 2022) | Patient handouts | ✓ Moderate |

The Beck annotated sessions are genuinely useful: they show the Socratic sequence, collaborative empiricism, agenda-setting, and behavioral activation assignment in action, with annotations. These are the closest analog to what the prompt is asking for when it says "if you find a similar moment in clinical transcripts, mention how it was handled."

**ThousandVoicesOfTrauma Conversations (3,009 documents)**

All 3,009 conversations are Prolonged Exposure / PTSD sessions. The dataset covers varied trauma types (witnessing violence, natural disasters, medical trauma, combat, accidents, loss) and demographic combinations, but **every single entry has `disorder_focus = "PTSD"` and `therapy_type = "Prolonged Exposure (PE)"`.**

This means a CBT session for social anxiety, a DBT session for BPD/self-harm, a BA session for depression, or an IPT session for grief has zero transcript coverage. All 3,009 transcripts are inaccessible as useful pattern references for the majority of sessions the system is intended to support.

---

## Transcript Conversations Metadata — Tag Discoverability During a Session

**Would these tags cause documents to be retrieved during non-PTSD sessions?**

Yes, and here is why.

Vertex AI Search uses **semantic similarity**, not structured field filtering. The `structData` fields (e.g., `exhibited_behaviors`, `session_topic`) are indexed and contribute to retrieval scoring, but the query is derived from the LLM prompt — specifically from `COMPREHENSIVE_ANALYSIS_PROMPT`, which includes the live transcript text.

The `exhibited_behaviors` field in the majority of entries includes terms like:

```
"avoidance, hypervigilance, flashbacks, self-blame, dissociation"
"avoidance, nightmares, hypervigilance"
"hypervigilance, self-blame, avoidance"
```

These terms — especially "avoidance" and "self-blame" — are not PTSD-exclusive. They appear routinely in CBT for depression ("behavioral avoidance"), CBT for anxiety, and BA sessions. A prompt containing a patient expressing avoidance of social situations or self-critical cognition will semantically match PE/PTSD transcripts tagged with those behaviors.

The `session_topic` values ("police brutality," "military combat experience," "natural disaster experience") are specific enough that they would NOT match a typical CBT-depression session, but `exhibited_behaviors` will.

**Practical consequence**: During a comprehensive analysis of a CBT session for depression, the model may cite a PE/PTSD synthetic transcript as a matched "similar moment in clinical transcripts" — which is modality-mismatched and potentially misleading (PE techniques like imaginal exposure are contraindicated approaches in standard CBT for depression).

Additionally, the transcript datastore is **not used in realtime analysis** (`get_rag_tools_for_session(is_realtime=True)` excludes `TRANSCRIPT_RAG_TOOL`, line 478 of `main.py`). It is only used in the comprehensive path. So this cross-modality contamination risk exists only in comprehensive analysis, not the live alert stream.

---

## How `transcript_conversations_metadata.jsonl` Was Created — Static Code Analysis

Source: `generate_metadata_jsonl.py`, function `generate_transcript_conversation_jsonl()` (line 428).

**Step 1 — File enumeration from GCS** (line 437):
```python
conv_blobs = list(bucket.list_blobs(prefix="transcripts/ThousandVoicesOfTrauma/conversations/"))
conv_files = [b.name for b in conv_blobs if b.name.endswith(".json")]
```
All `.json` files under the `conversations/` prefix are discovered dynamically at script execution time. The JSONL reflects whatever files existed in the bucket at that moment.

**Step 2 — ID derivation from filename** (lines 450–451):
```python
filename = conv_path.split("/")[-1]
base_id = filename.replace("_conversation.json", "")
```
The document ID is produced by stripping `_conversation.json` from the filename and then lowercasing and replacing underscores: `"100_P10" → "100-p10"`. This is a pure string operation with no content reading.

**Step 3 — Metadata lookup from a parallel GCS path** (lines 453–486):
```python
meta_path = f"transcripts/ThousandVoicesOfTrauma/metadata/{base_id}_metadata.json"
meta_blob = bucket.blob(meta_path)
if meta_blob.exists():
    meta = json.loads(meta_blob.download_as_text())
    struct_data["trauma_type"]             = trauma_info.get("type")
    struct_data["session_topic"]           = trauma_info.get("session_topic")
    struct_data["client_age_group"]        = client_profile.get("age_group")
    struct_data["client_gender"]           = client_profile.get("gender")
    struct_data["co_occurring_condition"]  = client_profile.get("co_occurring_condition")
    struct_data["exhibited_behaviors"]     = ", ".join(client_profile.get("exhibited_behaviors", []))
```
The fields (`trauma_type`, `exhibited_behaviors`, etc.) come directly from the ThousandVoicesOfTrauma dataset's own companion metadata JSONs stored in GCS, not from any content analysis or LLM extraction. They are dataset-provided labels.

**Step 4 — Fallback stub** (lines 455–459): If the GCS metadata blob does not exist for a given conversation file, the entry is created with only four fields:
```python
{
    "title": f"Trauma Therapy Session - {base_id}",
    "therapy_type": "Prolonged Exposure (PE)",
    "document_type": "synthetic_transcript",
    "source_dataset": "ThousandVoicesOfTrauma"
}
```
This is what happened for the anomalous entry `"102-p7-conversation(1).json"`: the filename contained a literal `(1)` parenthetical, so `base_id` became `102_P7_conversation(1)` after `.replace("_conversation.json", "")` failed to strip the suffix. The metadata path lookup `metadata/102_P7_conversation(1)_metadata.json` presumably returned 404, producing a stub entry with an ID that retains the parenthetical: `"102-p7-conversation(1).json"`.

The JSONL was **not generated from reading the conversation content** — all fields are from the dataset's sidecar metadata or from filename string manipulation.

---

## Summary Assessment

| Corpus | Documents | Type Quality | Real-time Utility | Verdict |
|---|---|---|---|---|
| `ebt-corpus` | 4 | 2 manuals, 1 training, 1 reference list | ✓ | **Keep. Core of the stack.** |
| `cbt-corpus` | 31 | All RCTs/studies | ✗ | **Replace or remove.** Needs CBT session manuals. |
| `ba-corpus` | 11 | All RCTs/studies | ✗ | **Replace or remove.** Needs Lejuez/Martell BA manual. |
| `dbt-corpus` | 6 | 2 possibly manuals, 4 studies | Partial | **Audit.** If two Linehan texts are present, keep those; remove studies. |
| `ipt-corpus` | 10 | All RCTs/studies, 1 misclassified | ✗ | **Replace or remove.** Needs Weissman/Markowitz IPT manual. |
| `safety-crisis` | 9 | All clinical protocols/instruments | ✓ | **Keep. Best-curated corpus.** |
| `transcript-patterns` (Beck PDFs) | 2 | Annotated session transcripts | ✓ | **Keep.** |
| `transcript-patterns` (ThousandVoicesOfTrauma) | 3,009 | Synthetic PE/PTSD only | ✗ for non-PE sessions | **Expand or isolate.** PTSD-only coverage contaminates non-PTSD comprehensive analyses. Restrict to `MODALITY_RAG_MAP["PE"]` or supplement with CBT/DBT/IPT/BA transcripts. |

### The Core Fix

The modality-specific corpora (`cbt-corpus`, `ba-corpus`, `ipt-corpus`, and partially `dbt-corpus`) need their RCTs replaced with or supplemented by actual treatment manuals. What is needed per modality:

- **CBT**: Beck's Cognitive Therapy of Depression, Clark & Wells CBT for Social Phobia, Barlow Unified Protocol
- **BA**: Lejuez BATD manual, Martell/Addis/Jacobson BA for Depression manual
- **DBT**: Linehan's Skills Training Manual (already possibly present), DBT individual therapy manual
- **IPT**: Weissman/Markowitz/Klerman Comprehensive Guide to Interpersonal Psychotherapy

Without treatment manuals, the `rationale` and `immediate_actions` fields in `COMPREHENSIVE_ANALYSIS_PROMPT`'s output will cite RCTs — giving the clinician confidence-inflated references that actually contain experimental methods, not clinical technique.
