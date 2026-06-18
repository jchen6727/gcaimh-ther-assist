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

### 2. `cbt-corpus` — CBT Research Papers and Manuals (34 documents)

`cbt_metadata.jsonl` contains 31 research studies plus 3 treatment manuals. Type breakdown:

| `document_type` value | Count |
|---|---|
| `randomized_controlled_trial` | 14 |
| `clinical_study` | 10 |
| `efficacy_study` | 2 |
| `review_paper` | 1 |
| `pilot_study` | 1 |
| `study_protocol` | 1 |
| `treatment_manual` | 3 |

Representative research titles: "Transdiagnostic CBT for Anxiety — RCT," "CBT via Telemedicine vs In-Person — Randomized Trial," "Coach-Guided App-Based CBT — Randomized Trial," "Brief Group CBT — Randomized Trial."

**Assessment**: The 3 treatment manuals are appropriate and provide the procedural content the prompt citation instruction implies. The 31 research studies are **inappropriate for real-time session guidance** — chunks retrieved from those papers will be drawn from participant exclusion criteria, CONSORT flow diagrams, regression tables, follow-up attrition rates, and effect size discussions. None of this answers "patient is resisting the exposure hierarchy right now." Because all 34 documents are mixed into one datastore without type filtering, the model has no way to preferentially retrieve from manuals rather than RCTs. The citation instruction is misleading when RCT methods sections are cited with the same `[1]`-style authority as a manual protocol.

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

| Filename (truncated) | Full title | Type |
|---|---|---|
| A pilot randomized controlled trial of Dialectical.pdf | *(RCT, DBT for BPD)* | RCT |
| A systematic review and meta.pdf | *(Systematic review of DBT efficacy)* | Systematic review |
| Dialectical Behavior Therapy.pdf | "Dialectical Behavior Therapy for Adolescents with Bipolar Disorder: Results from a Pilot Randomized Trial" | RCT |
| Dialectical Behaviour Therapy.pdf | "Dialectical Behaviour Therapy Improves Emotion Dysregulation Mainly in Binge Eating Disorder and Bulimia Nervosa: A Systematic Review and Meta-Analysis" | Meta-analysis |
| Randomized clinical trial of a brief.pdf | *(Brief DBT, RCT)* | RCT |
| Systematic Review Assessing the Efficacy.pdf | *(Systematic review of DBT)* | Systematic review |

**Assessment**: All six documents are research studies. The two filenames that appeared ambiguous — "Dialectical Behavior Therapy.pdf" and "Dialectical Behaviour Therapy.pdf" — are confirmed to be, respectively, a pilot RCT in adolescent bipolar disorder and a meta-analysis on emotion dysregulation in eating disorders. Neither is Linehan's treatment manual or skills training manual. No procedural DBT content is present in this corpus. Zero documents tell a clinician how to conduct a chain analysis, run a diary card review, or teach distress tolerance skills mid-session.

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

## Where RCT and Research Study Content Surfaces During a Session

This is the central clinical risk question: can chunks from RCTs, meta-analyses, and review papers actually reach the therapist's screen? Yes — in **both** the realtime and comprehensive paths. The transcript corpus is a separate and narrower issue.

### Realtime Analysis Path (the live alert stream)

The realtime path (`is_realtime=True`, handled by `handle_realtime_analysis_with_retry()`) does **not** use Vertex AI Search as an inline grounding tool. Instead, it runs a **background prefetch cache** (`prefetch_rag_context()`, `main.py` line 562) that queries the datastores independently and injects the results directly into the prompt text as a `CLINICAL EVIDENCE` block before the LLM call.

The prefetch queries these datastores for every realtime call:

| Session type | Datastores queried at every realtime call |
|---|---|
| CBT (default) | `ebt-corpus` + `safety-crisis` + `cbt-corpus` + `ba-corpus` |
| DBT | `ebt-corpus` + `safety-crisis` + `dbt-corpus` |
| IPT | `ebt-corpus` + `safety-crisis` + `ipt-corpus` |

The prefetch uses the last ~200 words of the live transcript as the search query (`query_text = " ".join(words[-200:])`, line 598). It retrieves up to 3 extractive answers and 3 snippets per datastore, formats them as:

```
--- Evidence from cbt-corpus ---
[cbt-corpus:1] <chunk text from RCT methods section>
[cbt-corpus:2] <chunk text from efficacy table>
...
```

and prepends this block to the realtime prompt (`REALTIME_ANALYSIS_PROMPT` or `REALTIME_ANALYSIS_PROMPT_STRICT`) under the label `CLINICAL EVIDENCE (from evidence-based therapy corpus — use these to ground your guidance)`.

The consequence is direct: **during every realtime alert generation in a CBT session, the model receives and is instructed to use chunks drawn from the 31 research studies in `cbt-corpus` and 11 studies in `ba-corpus`.** A passage like "participants in the CBT arm showed significantly greater symptom reduction at 12-week follow-up (Cohen's d = 0.71, p < 0.001)" will be handed to Flash with the instruction to ground its guidance on it. Because the model cannot distinguish between a procedures section and a results section from injected text alone, it may incorporate this content into technique recommendations or cite it as clinical evidence.

The cache TTL is 25 seconds (`RAG_CACHE_TTL_SECONDS = 25`). This means the same prefetched RCT passages are reused across multiple consecutive realtime calls within a 25-second window unless the transcript content changes. RCT content is not a rare edge case — it is a structural feature of every realtime call.

### Comprehensive Analysis Path

The comprehensive path (`is_realtime=False`) passes the modality-specific corpora as **inline Vertex AI Search grounding tools** (`rag_tools` list, line 920). Gemini retrieves from those datastores directly during generation. The `COMPREHENSIVE_ANALYSIS_PROMPT` explicitly instructs: "Reference evidence-based manual protocols with citations [1], [2]" and "Search for similar patterns in clinical transcripts." With 31 CBT research studies mixed into `cbt-corpus` alongside 3 treatment manuals, the model will retrieve from whichever documents are semantically closest to the transcript — which may well be a study on telephone-delivered CBT or an app-based CBT RCT if the session involves discussion of remote engagement.

The comprehensive path additionally includes `transcript-patterns` (not present in realtime), introducing the cross-modality contamination risk described below.

### Summary by Call Type

| What fires | Path | RCT content present? | Mechanism |
|---|---|---|---|
| Live alert (every ~30s) | Realtime | **Yes** — always | Injected as `CLINICAL EVIDENCE` text block via prefetch cache |
| Comprehensive segment analysis | Comprehensive | **Yes** | Inline Vertex AI Search grounding tools |
| Pathway guidance | Uses `is_realtime=True` tools | **Yes** | Same prefetch mechanism as realtime |
| Session summary | Uses `is_realtime=True` tools | **Yes** | Same prefetch mechanism as realtime |
| ThousandVoicesOfTrauma transcripts | Comprehensive only | N/A | Inline grounding tool, excluded from realtime |

---

## Transcript Conversations Metadata — Tag Discoverability During Comprehensive Analysis

**Would these tags cause PE/PTSD transcripts to surface during non-PTSD sessions?**

Yes, in the comprehensive path only (realtime excludes `transcript-patterns`).

Vertex AI Search uses **semantic similarity**, not structured field filtering. The `structData` fields (e.g., `exhibited_behaviors`, `session_topic`) are indexed and contribute to retrieval scoring, but the query is derived from the LLM prompt — specifically from `COMPREHENSIVE_ANALYSIS_PROMPT`, which includes the live transcript text.

The `exhibited_behaviors` field in the majority of entries includes terms like:

```
"avoidance, hypervigilance, flashbacks, self-blame, dissociation"
"avoidance, nightmares, hypervigilance"
"hypervigilance, self-blame, avoidance"
```

These terms — especially "avoidance" and "self-blame" — are not PTSD-exclusive. They appear routinely in CBT for depression ("behavioral avoidance"), CBT for anxiety, and BA sessions. A prompt containing a patient expressing avoidance of social situations or self-critical cognition will semantically match PE/PTSD transcripts tagged with those behaviors.

The `session_topic` values ("police brutality," "military combat experience," "natural disaster experience") are specific enough that they would NOT match a typical CBT-depression session, but `exhibited_behaviors` will.

**Practical consequence**: During a comprehensive analysis of a CBT-depression session, the model may cite a synthetic PE/PTSD transcript as a matched "similar moment in clinical transcripts." PE techniques — imaginal exposure, in-vivo hierarchy, prolonged imaginal reliving — are not only unhelpful for a CBT-depression patient, some are contraindicated. This cross-modality citation risk is bounded to the comprehensive path and does not affect the realtime alert stream.

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

| Corpus | Documents | Type Quality | Surfaces in realtime? | Surfaces in comprehensive? | Verdict |
|---|---|---|---|---|---|
| `ebt-corpus` | 4 | 2 manuals, 1 training, 1 reference list | Yes — prefetch cache | Yes — inline tool | **Keep. Core of the stack.** |
| `cbt-corpus` | 34 | 3 manuals + 31 RCTs/studies mixed | Yes — prefetch cache | Yes — inline tool | **Separate manuals from studies.** Mixed datastore means RCT chunks compete with manual chunks in every query. |
| `ba-corpus` | 11 | All RCTs/studies | Yes — prefetch cache | Yes — inline tool | **Add BA manuals or remove.** All study content with no procedural material. |
| `dbt-corpus` | 6 | All RCTs/meta-analyses (confirmed) | Yes — prefetch cache | Yes — inline tool | **Replace entirely.** No Linehan manual. Zero procedural content. |
| `ipt-corpus` | 10 | All RCTs/studies, 1 misclassified | Yes — prefetch cache | Yes — inline tool | **Add IPT manual or remove.** Needs Weissman/Markowitz. |
| `safety-crisis` | 9 | All clinical protocols/instruments | Yes — prefetch cache | Yes — inline tool | **Keep. Best-curated corpus.** |
| `transcript-patterns` (Beck PDFs) | 2 | Annotated session transcripts | No — excluded from realtime | Yes — inline tool | **Keep.** |
| `transcript-patterns` (ThousandVoicesOfTrauma) | 3,009 | Synthetic PE/PTSD only | No — excluded from realtime | Yes — inline tool | **Isolate to PE sessions.** Cross-modality contamination risk in comprehensive analysis. |

### The Core Fix

The most urgent problem is not the transcript corpus — it is that **RCT and meta-analysis chunks are injected into every realtime alert prompt** via the prefetch cache. A clinician managing a live patient receives guidance partially grounded in regression tables and efficacy follow-up data from `cbt-corpus`, `ba-corpus`, `dbt-corpus`, and `ipt-corpus` on every call.

Two structural changes are needed:

**1. Add treatment manuals to modality corpora.** What is needed per modality:

- **CBT**: Beck's Cognitive Therapy of Depression, Clark & Wells CBT for Social Phobia, Barlow Unified Protocol (3 manuals in `cbt-corpus` are a start; the 31 studies should be separated into a research-only datastore not included in realtime)
- **BA**: Lejuez BATD manual, Martell/Addis/Jacobson BA for Depression manual
- **DBT**: Linehan's Skills Training Manual, DBT individual therapy manual — confirmed absent from `dbt-corpus`
- **IPT**: Weissman/Markowitz/Klerman Comprehensive Guide to Interpersonal Psychotherapy

**2. Split research studies out of the realtime path.** RCT and meta-analysis documents have legitimate value for comprehensive analysis (informing the session summary's `alternate_therapy_paths` and `rationale` fields with efficacy evidence). They do not belong in the prefetch cache that drives realtime alerts. The cleanest fix is a separate `*-research` datastore for each modality that is excluded from `MODALITY_RAG_MAP` (and therefore from `prefetch_rag_context`) while remaining available for the comprehensive path.

Without these changes, the `rationale` and `immediate_actions` fields in both `REALTIME_ANALYSIS_PROMPT` and `COMPREHENSIVE_ANALYSIS_PROMPT` output will cite RCTs with the same authority as treatment manual protocols — giving the clinician confidence-inflated references that describe experimental populations, not clinical technique.
