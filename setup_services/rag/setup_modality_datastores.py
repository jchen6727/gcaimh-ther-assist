#!/usr/bin/env python3
"""
Script to create Vertex AI Search datastores for additional therapy modalities:
  - BA (Behavioral Activation)
  - DBT (Dialectical Behavior Therapy)
  - IPT (Interpersonal Psychotherapy)

Each modality gets its own datastore with layout-aware chunking,
following the same pattern as setup_rag_datastore.py (ebt-corpus).

Usage:
    export GOOGLE_CLOUD_PROJECT="your-gcp-project"
    python setup_modality_datastores.py              # Setup all 3
    python setup_modality_datastores.py --modality ba  # Setup only BA
"""

import os
import sys
import time
import json
import argparse
from google.auth import default
from google.auth.transport.requests import Request
import requests

# Configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = "us"

# Modality definitions
MODALITIES = {
    "ba": {
        "datastore_id": "ba-corpus",
        "display_name": "Behavioral Activation Clinical Research",
        "corpus_dir": "corpus_ba",
        "source_label": "BA Research",
        "doc_type": "clinical_research",
        "description": "Behavioral Activation RCTs, meta-analyses, and treatment studies",
    },
    "dbt": {
        "datastore_id": "dbt-corpus",
        "display_name": "Dialectical Behavior Therapy Clinical Research",
        "corpus_dir": "corpus_dbt",
        "source_label": "DBT Research",
        "doc_type": "clinical_research",
        "description": "DBT RCTs, systematic reviews, and efficacy studies",
    },
    "ipt": {
        "datastore_id": "ipt-corpus",
        "display_name": "Interpersonal Psychotherapy Clinical Research",
        "corpus_dir": "corpus_ipt",
        "source_label": "IPT Research",
        "doc_type": "clinical_research",
        "description": "IPT RCTs, meta-analyses, and treatment comparisons",
    },
}


def get_access_token():
    """Get access token for API calls."""
    credentials, _ = default()
    credentials.refresh(Request())
    return credentials.token


def create_datastore(datastore_id, display_name):
    """Create a Vertex AI Search datastore with document chunking enabled."""
    url = (
        f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/locations/{LOCATION}/collections/default_collection"
        f"/dataStores?dataStoreId={datastore_id}"
    )

    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_ID,
    }

    data = {
        "displayName": display_name,
        "industryVertical": "GENERIC",
        "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
        "contentConfig": "CONTENT_REQUIRED",
        "documentProcessingConfig": {
            "chunkingConfig": {
                "layoutBasedChunkingConfig": {
                    "chunkSize": 500,
                    "includeAncestorHeadings": True,
                }
            },
            "defaultParsingConfig": {"layoutParsingConfig": {}},
            "parsingConfigOverrides": {
                "pdf": {"layoutParsingConfig": {}},
                "docx": {"layoutParsingConfig": {}},
            },
        },
    }

    print(f"  Creating datastore '{datastore_id}'...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        print(f"  ✅ Datastore '{datastore_id}' created successfully!")
        return response.json()
    elif response.status_code == 409:
        print(f"  ⚠️  Datastore '{datastore_id}' already exists.")
        return get_datastore(datastore_id)
    else:
        print(f"  ❌ Error creating datastore: {response.status_code}")
        print(f"  Response: {response.text}")
        raise Exception(f"Failed to create datastore: {response.text}")


def get_datastore(datastore_id):
    """Get existing datastore details."""
    url = (
        f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/locations/{LOCATION}/collections/default_collection"
        f"/dataStores/{datastore_id}"
    )
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "X-Goog-User-Project": PROJECT_ID,
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"  ❌ Error getting datastore: {response.status_code}")
        return None


def create_gcs_bucket(datastore_id):
    """Create a GCS bucket for storing corpus documents."""
    from google.cloud import storage

    bucket_name = f"{PROJECT_ID}-{datastore_id}"
    client = storage.Client(project=PROJECT_ID)

    try:
        bucket = client.get_bucket(bucket_name)
        print(f"  ⚠️  Bucket {bucket_name} already exists")
        return bucket_name
    except Exception as e:
        if "404" in str(e):
            try:
                bucket = client.create_bucket(bucket_name, location="US")
                print(f"  ✅ Created GCS bucket: {bucket_name}")
                return bucket_name
            except Exception as create_error:
                if "already own it" in str(create_error):
                    print(f"  ⚠️  Bucket {bucket_name} already exists")
                    return bucket_name
                else:
                    raise create_error
        else:
            raise e


def upload_corpus_to_gcs(bucket_name, corpus_dir):
    """Upload corpus files to GCS bucket."""
    from google.cloud import storage

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(bucket_name)

    if not os.path.exists(corpus_dir):
        print(f"  ❌ Corpus directory '{corpus_dir}' not found!")
        print(f"     Current directory: {os.getcwd()}")
        return False

    files_uploaded = 0
    for filename in sorted(os.listdir(corpus_dir)):
        if filename.endswith((".pdf", ".docx", ".txt")):
            local_path = os.path.join(corpus_dir, filename)
            blob_name = f"corpus/{filename}"
            blob = bucket.blob(blob_name)

            try:
                print(f"  📤 Uploading {filename}...")
                blob.upload_from_filename(local_path)
                files_uploaded += 1
            except Exception as e:
                print(f"  ❌ Failed to upload {filename}: {e}")

    print(f"  📊 Uploaded {files_uploaded} files")
    return files_uploaded > 0


def import_documents_to_datastore(bucket_name, datastore_id, source_label, doc_type):
    """Import documents from GCS to the datastore."""
    from google.cloud import storage

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(bucket_name)

    corpus_files = []
    for blob in bucket.list_blobs(prefix="corpus/"):
        if blob.name.endswith((".pdf", ".docx", ".txt")):
            corpus_files.append(blob.name)

    if not corpus_files:
        print("  ❌ No corpus files found in bucket!")
        return None

    metadata_lines = []
    for file_path in corpus_files:
        filename = file_path.split("/")[-1]
        doc_id = filename.replace(".", "_").replace(" ", "_")

        mime = (
            "application/pdf"
            if file_path.endswith(".pdf")
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        metadata = {
            "id": doc_id,
            "structData": {
                "title": filename,
                "content_uri": f"gs://{bucket_name}/{file_path}",
                "source": source_label,
                "type": doc_type,
            },
            "content": {
                "uri": f"gs://{bucket_name}/{file_path}",
                "mimeType": mime,
            },
        }
        metadata_lines.append(json.dumps(metadata))

    metadata_content = "\n".join(metadata_lines)
    metadata_blob = bucket.blob("import_metadata.jsonl")
    metadata_blob.upload_from_string(metadata_content)
    print(f"  ✅ Created metadata for {len(corpus_files)} documents")

    url = (
        f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/locations/{LOCATION}/collections/default_collection"
        f"/dataStores/{datastore_id}/branches/0/documents:import"
    )

    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_ID,
    }

    data = {
        "gcsSource": {
            "inputUris": [f"gs://{bucket_name}/import_metadata.jsonl"],
            "dataSchema": "document",
        },
        "reconciliationMode": "INCREMENTAL",
    }

    print(f"  Importing {len(corpus_files)} documents...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        operation = response.json()
        print(f"  ✅ Import operation started: {operation['name']}")
        return operation
    else:
        print(f"  ❌ Error importing documents: {response.status_code}")
        print(f"  Response: {response.text}")
        raise Exception(f"Failed to import documents: {response.text}")


def wait_for_operation(operation_name, timeout=600):
    """Wait for a long-running operation to complete."""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "X-Goog-User-Project": PROJECT_ID,
    }

    start_time = time.time()
    while time.time() - start_time < timeout:
        url = f"https://discoveryengine.googleapis.com/v1/{operation_name}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            operation = response.json()
            if operation.get("done"):
                if "error" in operation:
                    error_detail = operation.get("error", {})
                    print(f"  ❌ IMPORT FAILED: {error_detail.get('message', 'Unknown error')}")
                    return False
                else:
                    metadata = operation.get("metadata", {})
                    success = metadata.get("successCount", 0)
                    failure = metadata.get("failureCount", 0)
                    print(f"  ✅ Import complete! Success: {success}, Failed: {failure}")
                    if failure > 0:
                        print(f"  ⚠️  {failure} documents failed — check Cloud Console")
                    return True
        else:
            print(f"  ❌ Error checking operation: {response.status_code}")
            return False

        elapsed = int(time.time() - start_time)
        print(f"  ⏳ Waiting... ({elapsed}s / {timeout}s)")
        time.sleep(10)

    print(f"  ❌ Operation timed out after {timeout}s")
    print(f"     Operation: {operation_name}")
    print(f"     Check Cloud Console for status")
    return False


def setup_modality(key, config):
    """Set up a single modality datastore end-to-end."""
    datastore_id = config["datastore_id"]
    display_name = config["display_name"]
    corpus_dir = config["corpus_dir"]
    source_label = config["source_label"]
    doc_type = config["doc_type"]

    print(f"\n{'='*60}")
    print(f"Setting up: {display_name}")
    print(f"Datastore:  {datastore_id}")
    print(f"Corpus dir: {corpus_dir}")
    print(f"{'='*60}")

    # Count files
    if os.path.exists(corpus_dir):
        pdf_count = len([f for f in os.listdir(corpus_dir) if f.endswith(".pdf")])
        print(f"  Found {pdf_count} PDF files")
    else:
        print(f"  ❌ Directory '{corpus_dir}' not found!")
        return False

    # Step 1: Create datastore
    create_datastore(datastore_id, display_name)

    # Step 2: Create GCS bucket
    bucket_name = create_gcs_bucket(datastore_id)

    # Step 3: Upload files
    if not upload_corpus_to_gcs(bucket_name, corpus_dir):
        print(f"  ❌ Upload failed for {key}")
        return False

    # Step 4: Import documents
    operation = import_documents_to_datastore(
        bucket_name, datastore_id, source_label, doc_type
    )

    if not operation:
        return False

    # Step 5: Wait for completion
    success = wait_for_operation(operation["name"])

    if success:
        print(f"\n  ✅ {display_name} — READY")
        print(f"     Datastore path: projects/{PROJECT_ID}/locations/{LOCATION}"
              f"/collections/default_collection/dataStores/{datastore_id}")
    else:
        print(f"\n  ⚠️  {display_name} — may still be importing in background")
        print(f"     Check: https://console.cloud.google.com/ai/search/datastores")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Set up Vertex AI Search datastores for therapy modalities"
    )
    parser.add_argument(
        "--modality",
        choices=["ba", "dbt", "ipt", "all"],
        default="all",
        help="Which modality to set up (default: all)",
    )
    args = parser.parse_args()

    if not PROJECT_ID:
        print("❌ GOOGLE_CLOUD_PROJECT environment variable not set!")
        print("   export GOOGLE_CLOUD_PROJECT='your-project-id'")
        sys.exit(1)

    print(f"🚀 Setting up modality datastores for Ther-Assist")
    print(f"   Project: {PROJECT_ID}")
    print(f"   Location: {LOCATION}")

    if args.modality == "all":
        targets = MODALITIES
    else:
        targets = {args.modality: MODALITIES[args.modality]}

    results = {}
    for key, config in targets.items():
        try:
            results[key] = setup_modality(key, config)
        except Exception as e:
            print(f"\n  ❌ {key} setup failed: {e}")
            results[key] = False

    # Summary
    print(f"\n{'='*60}")
    print("SETUP SUMMARY")
    print(f"{'='*60}")
    for key, success in results.items():
        status = "✅ READY" if success else "❌ FAILED / PENDING"
        print(f"  {MODALITIES[key]['display_name']}: {status}")

    print(f"\n📋 Next steps:")
    print(f"   1. Verify datastores in Cloud Console:")
    print(f"      https://console.cloud.google.com/ai/search/datastores")
    print(f"   2. Backend main.py already has the RAG tool definitions")
    print(f"   3. Test with a session using BA/DBT/IPT modality")

    all_ok = all(results.values())
    if all_ok:
        print(f"\n✅✅✅ All modality datastores are ready! ✅✅✅")
    else:
        print(f"\n⚠️  Some datastores may still be importing — check Cloud Console")

    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        import google.auth
        from google.cloud import storage
    except ImportError:
        print("Installing required dependencies...")
        os.system("pip install google-auth google-auth-httplib2 google-cloud-storage requests")
        print("Dependencies installed. Please run the script again.")
        sys.exit(0)

    sys.exit(main())
