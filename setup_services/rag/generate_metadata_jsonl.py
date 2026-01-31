#!/usr/bin/env python3
"""
Generate metadata JSONL files for Discovery Engine re-import.
Creates structured metadata for each document so that grounding citations
include proper titles, therapy types, and disorder categories.
"""

import json
import os
import subprocess
from google.cloud import storage
from google.auth import default
from google.auth.transport.requests import Request
import requests

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "brk-prj-salvador-dura-bern-sbx")
LOCATION = "us"

# Regional endpoint for Discovery Engine
BASE_URL = f"https://us-discoveryengine.googleapis.com/v1"

def get_access_token():
    credentials, _ = default()
    credentials.refresh(Request())
    return credentials.token

# ============================================================
# EBT CORPUS METADATA (4 manuals)
# ============================================================
EBT_METADATA = [
    {
        "id": "pe-ptsd-manual-2022",
        "title": "Prolonged Exposure Therapy for PTSD - Clinical Manual (2022)",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-ebt-corpus/PE_for_PTSD_2022.pdf",
        "therapy_type": "Prolonged Exposure (PE)",
        "disorder_focus": "PTSD",
        "document_type": "treatment_manual",
        "description": "Comprehensive clinical manual for Prolonged Exposure therapy for PTSD, including in-vivo and imaginal exposure protocols"
    },
    {
        "id": "cbt-social-phobia-manual",
        "title": "Comprehensive CBT for Social Phobia - Treatment Manual",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-ebt-corpus/Comprehensive-CBT-for-Social-Phobia-Manual.pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "Social Anxiety Disorder",
        "document_type": "treatment_manual",
        "description": "Complete treatment manual for CBT approach to social phobia including cognitive restructuring and behavioral experiments"
    },
    {
        "id": "deliberate-practice-cbt",
        "title": "Deliberate Practice in CBT - Boswell & Constantino (APA)",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-ebt-corpus/APA_Boswell_Constantino_Deliberate_Practice_CBT.pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "General",
        "document_type": "training_manual",
        "description": "APA publication on deliberate practice methods for developing CBT clinical competence"
    },
    {
        "id": "exposure-therapy-references",
        "title": "Exposure Therapy Manuals and Guidebooks - Reference Guide",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-ebt-corpus/References_for_Exposure_Therapy_Manuals_and_Guidebooks.docx",
        "therapy_type": "Exposure Therapy",
        "disorder_focus": "Anxiety Disorders, PTSD, OCD",
        "document_type": "reference_guide",
        "description": "Comprehensive reference list of exposure therapy manuals and clinical guidebooks across anxiety disorders"
    }
]

# ============================================================
# CBT CORPUS METADATA (31 research papers)
# ============================================================
CBT_METADATA = [
    {
        "id": "transdiagnostic-cbt-anxiety-rct",
        "title": "Transdiagnostic CBT for Anxiety Disorders - Randomized Clinical Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/A Randomized Clinical Trial of Transdiagnostic CBT for Anxiety.pdf",
        "therapy_type": "Transdiagnostic CBT",
        "disorder_focus": "Anxiety Disorders",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "telephone-delivered-cbt-rct",
        "title": "Telephone-Delivered CBT - Randomized Controlled Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/A Randomized Controlled Trial of Telephone-Delivered.pdf",
        "therapy_type": "Telephone CBT",
        "disorder_focus": "General",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "applied-relaxation-gad",
        "title": "Applied Relaxation for Adults with Generalized Anxiety Disorder",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Applied Relaxation for Adults With Generalized.pdf",
        "therapy_type": "Applied Relaxation",
        "disorder_focus": "Generalized Anxiety Disorder (GAD)",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "binge-eating-disorder",
        "title": "CBT for Binge-Eating Disorder",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Binge-eating disorder.pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "Binge-Eating Disorder",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "brief-depression-prevention",
        "title": "Brief CBT Depression Prevention Program",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Brief depression prevention program.pdf",
        "therapy_type": "Brief CBT",
        "disorder_focus": "Depression",
        "document_type": "clinical_study",
        "study_design": "Prevention Trial"
    },
    {
        "id": "cbt-efficacy-study",
        "title": "CBT Efficacy - Clinical Study",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/CBT efficacy clinical study.pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "General",
        "document_type": "efficacy_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "cbt-evidence-overview",
        "title": "CBT Evidence Base - Core Overview Paper",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/CBT evidence overview (core paper).pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "General",
        "document_type": "review_paper",
        "study_design": "Evidence Review"
    },
    {
        "id": "cbt-ptsd-severe-mental-illness",
        "title": "CBT for PTSD in Severe Mental Illness - Randomized Controlled Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/CBT for PTSD in severe mental illness (randomized controlled trial).pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "PTSD, Severe Mental Illness",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "cbt-telemedicine-vs-inperson",
        "title": "CBT via Telemedicine vs In-Person - Randomized Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/CBT via telemedicine vs in-person (randomized trial).pdf",
        "therapy_type": "Telehealth CBT",
        "disorder_focus": "General",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "cbti-insomnia-alcohol",
        "title": "CBT-I Efficacy Trial - Insomnia and Alcohol Outcomes",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/CBT-I efficacy trial (insomnia + alcohol outcomes.pdf",
        "therapy_type": "CBT for Insomnia (CBT-I)",
        "disorder_focus": "Insomnia, Alcohol Use Disorder",
        "document_type": "efficacy_study",
        "study_design": "RCT"
    },
    {
        "id": "cbt-treatment-general",
        "title": "Cognitive Behavioral Therapy for the Treatment of Psychiatric Disorders",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Cognitive Behavioral therapy for the treatment.pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "General Psychiatric Disorders",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "cbt-combined-therapy",
        "title": "Cognitive-Behavioral Therapy Combined with Other Treatments",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Cognitive-Behavioral Therapy and.pdf",
        "therapy_type": "Combined CBT",
        "disorder_focus": "General",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "erp-augmenting-sris",
        "title": "ERP (CBT) Augmenting SRIs - Randomized Controlled Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/ERP (CBT) augmenting SRIs randomized controlled trial.pdf",
        "therapy_type": "Exposure and Response Prevention (ERP)",
        "disorder_focus": "OCD",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "gad-integrated-techniques",
        "title": "Generalized Anxiety Disorder Treatment with Integrated CBT Techniques",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Generalized Anxiety Disorder with Integrated Techniques.pdf",
        "therapy_type": "Integrated CBT",
        "disorder_focus": "Generalized Anxiety Disorder (GAD)",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "integrated-cbt-eating-disorder",
        "title": "Integrated CBT for Eating Disorders",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Integrated CBT for eating disorder.pdf",
        "therapy_type": "Integrated CBT",
        "disorder_focus": "Eating Disorders",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "internet-cbt-social-anxiety-rct",
        "title": "Internet-Based Cognitive Therapy for Social Anxiety - Randomized Controlled Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Internet cognitive therapy CBT for social anxiety randomized controlled trial.pdf",
        "therapy_type": "Internet-Based CBT",
        "disorder_focus": "Social Anxiety Disorder",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "internet-cbt-gad",
        "title": "Internet-Delivered CBT for Generalized Anxiety Disorder",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Internet-delivered CBT for GAD.pdf",
        "therapy_type": "Internet-Based CBT",
        "disorder_focus": "Generalized Anxiety Disorder (GAD)",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "ocd-cbt-erp-augmentation",
        "title": "OCD Treatment - CBT/ERP Augmentation Strategy",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/OCD CBTERP augmentation.pdf",
        "therapy_type": "CBT/ERP Augmentation",
        "disorder_focus": "OCD",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "panic-disorder-collaborative-care",
        "title": "Primary Care Panic Disorder - CBT and Medication Collaborative Care RCT",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Primarycare panic disorder CBT  medication collaborativecare RCT.pdf",
        "therapy_type": "Collaborative Care CBT",
        "disorder_focus": "Panic Disorder",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "social-anxiety-treatment",
        "title": "CBT Treatment for Social Anxiety",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Social anxiety.pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "Social Anxiety Disorder",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "latino-gad-cbt-pilot",
        "title": "CBT for GAD in Spanish-Speaking Latinos - Randomized Pilot Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Spanishspeaking Latinos with GAD randomized pilot CBT trial.pdf",
        "therapy_type": "Culturally Adapted CBT",
        "disorder_focus": "Generalized Anxiety Disorder (GAD)",
        "document_type": "pilot_study",
        "study_design": "Randomized Pilot"
    },
    {
        "id": "cbt-study-protocol",
        "title": "Study Protocol for Cognitive Behavioral Therapy Clinical Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Study Protocol for Cognitive Behavioral Therapy.pdf",
        "therapy_type": "Cognitive Behavioral Therapy (CBT)",
        "disorder_focus": "General",
        "document_type": "study_protocol",
        "study_design": "Protocol"
    },
    {
        "id": "telephone-cbt",
        "title": "Telephone-Administered CBT - Clinical Study",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Telephone-administered CBT.pdf",
        "therapy_type": "Telephone CBT",
        "disorder_focus": "General",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "cbti-acute-insomnia",
        "title": "Treating Acute Insomnia with CBT-I",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/Treating Acute Insomnia.pdf",
        "therapy_type": "CBT for Insomnia (CBT-I)",
        "disorder_focus": "Insomnia",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "vr-social-anxiety",
        "title": "Adaptive Virtual Reality CBT for Social Anxiety",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/adaptive virtual reality for social anxiety.pdf",
        "therapy_type": "VR-Based CBT",
        "disorder_focus": "Social Anxiety Disorder",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "brief-group-cbt-rct",
        "title": "Brief Group CBT - Randomized Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/brief group CBT randomized trial.pdf",
        "therapy_type": "Group CBT",
        "disorder_focus": "General",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "coach-guided-app-cbt",
        "title": "Coach-Guided App-Based CBT - Randomized Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/coach-guided app CBT randomized trial.pdf",
        "therapy_type": "App-Based CBT",
        "disorder_focus": "General",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "cognitive-therapy-ocd",
        "title": "Cognitive Therapy for Obsessive-Compulsive Disorder",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/cognitive therapy for obsessive-compulsive disorder.pdf",
        "therapy_type": "Cognitive Therapy",
        "disorder_focus": "OCD",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "act-social-phobia",
        "title": "Acceptance and Commitment Therapy for Social Phobia",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/commitment therapy for social phobia.pdf",
        "therapy_type": "Acceptance and Commitment Therapy (ACT)",
        "disorder_focus": "Social Anxiety Disorder",
        "document_type": "clinical_study",
        "study_design": "Clinical Trial"
    },
    {
        "id": "group-vs-individual-cbt",
        "title": "Group vs Individual CBT - Randomized Clinical Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/group vs individual CBT randomized clinical trial.pdf",
        "therapy_type": "Group CBT vs Individual CBT",
        "disorder_focus": "General",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    },
    {
        "id": "trial-based-cognitive-therapy",
        "title": "Trial-Based Cognitive Therapy - Randomized Trial",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-cbt-material/trial-based cognitive therapy randomized trial.pdf",
        "therapy_type": "Trial-Based Cognitive Therapy",
        "disorder_focus": "General",
        "document_type": "randomized_controlled_trial",
        "study_design": "RCT"
    }
]

# ============================================================
# TRANSCRIPT METADATA (3 annotated PDFs)
# ============================================================
TRANSCRIPT_PDF_METADATA = [
    {
        "id": "beck-session-2-annotated",
        "title": "Beck CBT Session 2 - Annotated Transcript (Depression, Behavioral Activation)",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-transcript-patterns/transcripts/BB3-Session-2-Annotated-Transcript.pdf",
        "therapy_type": "Beck Cognitive Behavioral Therapy",
        "disorder_focus": "Depression",
        "document_type": "annotated_transcript",
        "session_number": 2,
        "therapist": "Judith Beck"
    },
    {
        "id": "beck-session-10-annotated",
        "title": "Beck CBT Session 10 - Annotated Transcript (Depression, Core Beliefs)",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-transcript-patterns/transcripts/BB3-Session-10-Annotated-Transcript.pdf",
        "therapy_type": "Beck Cognitive Behavioral Therapy",
        "disorder_focus": "Depression",
        "document_type": "annotated_transcript",
        "session_number": 10,
        "therapist": "Judith Beck"
    },
    {
        "id": "pe-supplement-handouts",
        "title": "Prolonged Exposure Therapy - Supplement Handouts (October 2022)",
        "uri": "gs://brk-prj-salvador-dura-bern-sbx-transcript-patterns/transcripts/PE_Supplement_Handouts-Oct-22_0.pdf",
        "therapy_type": "Prolonged Exposure (PE)",
        "disorder_focus": "PTSD",
        "document_type": "clinical_handout",
        "description": "Supplementary patient handouts for Prolonged Exposure therapy sessions"
    }
]


def generate_jsonl(metadata_list, output_path):
    """Generate a JSONL file from metadata list in Discovery Engine document format."""
    lines = []
    for doc in metadata_list:
        # Build structured data from all fields except id, uri
        struct_data = {}
        for key, value in doc.items():
            if key not in ("id", "uri"):
                struct_data[key] = value

        # Determine MIME type
        uri = doc["uri"]
        if uri.endswith(".pdf"):
            mime = "application/pdf"
        elif uri.endswith(".docx"):
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif uri.endswith(".json"):
            mime = "application/json"
        else:
            mime = "text/plain"

        entry = {
            "id": doc["id"],
            "structData": struct_data,
            "content": {
                "mimeType": mime,
                "uri": uri
            }
        }
        lines.append(json.dumps(entry))

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Generated {output_path} with {len(lines)} entries")
    return output_path


def generate_transcript_conversation_jsonl(output_path):
    """
    Generate JSONL for ThousandVoicesOfTrauma conversations by reading
    metadata from GCS for each conversation file.
    """
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket("brk-prj-salvador-dura-bern-sbx-transcript-patterns")

    # List all conversation files
    conv_blobs = list(bucket.list_blobs(prefix="transcripts/ThousandVoicesOfTrauma/conversations/"))
    conv_files = [b.name for b in conv_blobs if b.name.endswith(".json")]

    print(f"Found {len(conv_files)} conversation files")

    lines = []
    metadata_cache = {}
    processed = 0
    errors = 0

    for conv_path in conv_files:
        # Extract the ID pattern: e.g., "100_P10" from "100_P10_conversation.json"
        filename = conv_path.split("/")[-1]
        base_id = filename.replace("_conversation.json", "")

        # Try to get matching metadata
        meta_path = f"transcripts/ThousandVoicesOfTrauma/metadata/{base_id}_metadata.json"

        struct_data = {
            "title": f"Trauma Therapy Session - {base_id}",
            "therapy_type": "Prolonged Exposure (PE)",
            "document_type": "synthetic_transcript",
            "source_dataset": "ThousandVoicesOfTrauma"
        }

        # Read metadata if available
        try:
            if meta_path not in metadata_cache:
                meta_blob = bucket.blob(meta_path)
                if meta_blob.exists():
                    meta_content = meta_blob.download_as_text()
                    metadata_cache[meta_path] = json.loads(meta_content)
                else:
                    metadata_cache[meta_path] = None

            meta = metadata_cache[meta_path]
            if meta:
                client_profile = meta.get("client_profile", {})
                trauma_info = meta.get("trauma_info", {})

                struct_data["title"] = f"PE Session - {trauma_info.get('session_topic', 'Trauma Processing')} ({base_id})"
                struct_data["trauma_type"] = trauma_info.get("type", "Unknown")
                struct_data["session_topic"] = trauma_info.get("session_topic", "Unknown")
                struct_data["client_age_group"] = client_profile.get("age_group", "Unknown")
                struct_data["client_gender"] = client_profile.get("gender", "Unknown")
                struct_data["co_occurring_condition"] = client_profile.get("co_occurring_condition", "None")
                struct_data["disorder_focus"] = "PTSD"

                behaviors = client_profile.get("exhibited_behaviors", [])
                if behaviors:
                    struct_data["exhibited_behaviors"] = ", ".join(behaviors)

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Warning: Could not read metadata for {base_id}: {e}")

        entry = {
            "id": base_id.replace("_", "-").lower(),
            "structData": struct_data,
            "content": {
                "mimeType": "application/json",
                "uri": f"gs://brk-prj-salvador-dura-bern-sbx-transcript-patterns/{conv_path}"
            }
        }
        lines.append(json.dumps(entry))
        processed += 1

        if processed % 500 == 0:
            print(f"  Processed {processed}/{len(conv_files)} conversations...")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Generated {output_path} with {len(lines)} entries ({errors} metadata read errors)")
    return output_path


def purge_datastore(datastore_id):
    """Delete all existing documents from a datastore via purge API."""
    url = f"{BASE_URL}/projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/dataStores/{datastore_id}/branches/0/documents:purge"

    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_ID
    }

    data = {
        "filter": "*",
        "force": True
    }

    print(f"Purging all documents from '{datastore_id}'...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        operation = response.json()
        print(f"  Purge started: {operation.get('name', 'unknown')}")
        return operation
    else:
        print(f"  Error purging: {response.status_code} - {response.text}")
        return None


def upload_jsonl_to_gcs(local_path, bucket_name, gcs_path):
    """Upload a JSONL file to GCS."""
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    print(f"Uploaded {local_path} -> gs://{bucket_name}/{gcs_path}")
    return f"gs://{bucket_name}/{gcs_path}"


def import_with_metadata(datastore_id, gcs_jsonl_uri):
    """Import documents using metadata JSONL with 'document' schema."""
    url = f"{BASE_URL}/projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/dataStores/{datastore_id}/branches/0/documents:import"

    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_ID
    }

    data = {
        "gcsSource": {
            "inputUris": [gcs_jsonl_uri],
            "dataSchema": "document"
        },
        "reconciliationMode": "FULL",
        "autoGenerateIds": False
    }

    print(f"Importing to '{datastore_id}' from {gcs_jsonl_uri}...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        operation = response.json()
        print(f"  Import started: {operation.get('name', 'unknown')}")
        return operation
    else:
        print(f"  Error importing: {response.status_code} - {response.text}")
        return None


def wait_for_operation(operation_name, timeout=600):
    """Wait for a long-running operation to complete."""
    import time

    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "X-Goog-User-Project": PROJECT_ID
    }

    start_time = time.time()
    while time.time() - start_time < timeout:
        url = f"{BASE_URL}/{operation_name}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            operation = response.json()
            metadata = operation.get("metadata", {})
            if operation.get("done"):
                success = metadata.get("successCount", "?")
                failure = metadata.get("failureCount", 0)
                print(f"  Operation complete: {success} success, {failure} failures")
                if "error" in operation:
                    print(f"  Error: {operation['error']}")
                    return False
                return True
            else:
                success = metadata.get("successCount", 0)
                total = metadata.get("totalCount", "?")
                elapsed = int(time.time() - start_time)
                print(f"  Waiting... {success}/{total} processed ({elapsed}s)")
        else:
            print(f"  Error checking status: {response.status_code}")
            return False

        time.sleep(15)

    print(f"  Timed out after {timeout}s")
    return False


def main():
    print("=" * 60)
    print("GENERATING METADATA JSONL FILES FOR PILOT")
    print("=" * 60)

    output_dir = os.path.dirname(os.path.abspath(__file__))

    # Step 1: Generate JSONL files
    print("\n--- Step 1: Generate metadata JSONL files ---")

    ebt_jsonl = generate_jsonl(EBT_METADATA, os.path.join(output_dir, "ebt_metadata.jsonl"))
    cbt_jsonl = generate_jsonl(CBT_METADATA, os.path.join(output_dir, "cbt_metadata.jsonl"))
    transcript_pdf_jsonl = generate_jsonl(TRANSCRIPT_PDF_METADATA, os.path.join(output_dir, "transcript_pdf_metadata.jsonl"))

    print("\nGenerating ThousandVoicesOfTrauma conversation metadata (this reads from GCS)...")
    conv_jsonl = generate_transcript_conversation_jsonl(os.path.join(output_dir, "transcript_conversations_metadata.jsonl"))

    # Step 2: Upload JSONL files to GCS
    print("\n--- Step 2: Upload JSONL files to GCS ---")

    ebt_gcs = upload_jsonl_to_gcs(ebt_jsonl, "brk-prj-salvador-dura-bern-sbx-ebt-corpus", "metadata/ebt_metadata.jsonl")
    cbt_gcs = upload_jsonl_to_gcs(cbt_jsonl, "brk-prj-salvador-dura-bern-sbx-cbt-material", "metadata/cbt_metadata.jsonl")
    tp_pdf_gcs = upload_jsonl_to_gcs(transcript_pdf_jsonl, "brk-prj-salvador-dura-bern-sbx-transcript-patterns", "metadata/transcript_pdf_metadata.jsonl")
    tp_conv_gcs = upload_jsonl_to_gcs(conv_jsonl, "brk-prj-salvador-dura-bern-sbx-transcript-patterns", "metadata/transcript_conversations_metadata.jsonl")

    # Step 3: Purge existing documents (they have no metadata)
    print("\n--- Step 3: Purge existing documents (no metadata) ---")

    purge_ops = []
    for ds_id in ["ebt-corpus", "cbt-corpus", "transcript-patterns"]:
        op = purge_datastore(ds_id)
        if op:
            purge_ops.append((ds_id, op))

    # Wait for purges to complete
    for ds_id, op in purge_ops:
        op_name = op.get("name", "")
        if op_name:
            print(f"\nWaiting for purge of '{ds_id}'...")
            wait_for_operation(op_name, timeout=300)

    # Step 4: Re-import with metadata
    print("\n--- Step 4: Re-import with structured metadata ---")

    import_ops = []

    # EBT corpus
    op = import_with_metadata("ebt-corpus", ebt_gcs)
    if op:
        import_ops.append(("ebt-corpus", op))

    # CBT corpus
    op = import_with_metadata("cbt-corpus", cbt_gcs)
    if op:
        import_ops.append(("cbt-corpus", op))

    # Transcript patterns - two imports (PDFs + conversations)
    op = import_with_metadata("transcript-patterns", tp_pdf_gcs)
    if op:
        import_ops.append(("transcript-patterns (PDFs)", op))

    # Wait for PDF import before starting conversations import
    for ds_name, op in import_ops:
        op_name = op.get("name", "")
        if op_name:
            print(f"\nWaiting for import of '{ds_name}'...")
            wait_for_operation(op_name, timeout=600)

    # Now import conversations (large batch)
    print("\nStarting ThousandVoicesOfTrauma conversations import (3010 files)...")
    op = import_with_metadata("transcript-patterns", tp_conv_gcs)
    if op:
        op_name = op.get("name", "")
        if op_name:
            print("Waiting for conversations import...")
            wait_for_operation(op_name, timeout=1800)  # 30 min timeout for 3010 files

    print("\n" + "=" * 60)
    print("METADATA IMPORT COMPLETE")
    print("=" * 60)
    print("\nDatastore summary:")
    print("  ebt-corpus:          4 manuals with full metadata")
    print("  cbt-corpus:          31 research papers with full metadata")
    print("  transcript-patterns: 3 annotated PDFs + 3010 conversations with metadata")
    print("\nCitations will now include proper titles, therapy types, and disorder categories.")


if __name__ == "__main__":
    main()
