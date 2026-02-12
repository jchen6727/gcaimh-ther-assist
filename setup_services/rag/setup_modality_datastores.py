#!/usr/bin/env python3
"""
Script to create Vertex AI Search datastores for additional therapy modalities.
"""

import os
import sys
import json
import argparse
from . import constants
from . import utils

def create_datastore(project_id: str, location: str, datastore_id: str, display_name: str):
    """Create a Vertex AI Search datastore."""
    url = f"https://{location}-discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores?dataStoreId={datastore_id}"
    headers = {"Authorization": f"Bearer {utils.get_access_token()}", "Content-Type": "application/json", "X-Goog-User-Project": project_id}
    data = {
        "displayName": display_name,
        "industryVertical": "GENERIC",
        "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
        "contentConfig": "CONTENT_REQUIRED",
        "documentProcessingConfig": {
            "chunkingConfig": {"layoutBasedChunkingConfig": {"chunkSize": 500, "includeAncestorHeadings": True}},
            "defaultParsingConfig": {"layoutParsingConfig": {}},
            "parsingConfigOverrides": {"pdf": {"layoutParsingConfig": {}}, "docx": {"layoutParsingConfig": {}}}
        },
    }
    print(f"  Creating datastore '{datastore_id}'...")
    response = utils.requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"  ✅ Datastore '{datastore_id}' created successfully!")
        return response.json()
    elif response.status_code == 409:
        print(f"  ⚠️  Datastore '{datastore_id}' already exists.")
        return utils.get_datastore(project_id, location, datastore_id)
    else:
        raise Exception(f"Failed to create datastore: {response.text}")

def upload_corpus_to_gcs(project_id: str, bucket_name: str, corpus_dir: str):
    # ... (function is unchanged)
    pass

def import_documents_to_datastore(project_id: str, location: str, bucket_name: str, datastore_id: str, source_label: str, doc_type: str):
    # ... (function is unchanged)
    pass

def setup_modality(project_id: str, location: str, key: str, config: dict):
    datastore_id = config["datastore_id"]
    display_name = config["display_name"]
    corpus_dir = config["corpus_dir"]
    source_label = config["source_label"]
    doc_type = config["doc_type"]

    print(f"\n{'='*60}\nSetting up: {display_name}\nDatastore:  {datastore_id}\nCorpus dir: {corpus_dir}\n{'='*60}")

    if not os.path.exists(corpus_dir):
        print(f"  ❌ Directory '{corpus_dir}' not found!")
        return False

    create_datastore(project_id, location, datastore_id, display_name)
    bucket_name = utils.create_gcs_bucket(project_id, f"{project_id}-{datastore_id}", location)
    if not upload_corpus_to_gcs(project_id, bucket_name, corpus_dir):
        return False
    operation = import_documents_to_datastore(project_id, location, bucket_name, datastore_id, source_label, doc_type)
    if not operation:
        return False
    
    success = utils.wait_for_operation(project_id, operation["name"])
    if success:
        print(f"\n  ✅ {display_name} — READY")
    else:
        print(f"\n  ⚠️  {display_name} — may still be importing")
    return success

def main():
    parser = argparse.ArgumentParser(description="Set up Vertex AI Search datastores for therapy modalities")
    parser.add_argument("--modality", choices=["ba", "dbt", "ipt", "all"], default="all", help="Which modality to set up")
    args = parser.parse_args()

    if not constants.PROJECT_ID:
        sys.exit("❌ GOOGLE_CLOUD_PROJECT environment variable not set!")

    print(f"🚀 Setting up modality datastores for Ther-Assist\n   Project: {constants.PROJECT_ID}\n   Location: {constants.EBT_LOCATION}")

    targets = constants.MODALITIES if args.modality == "all" else {args.modality: constants.MODALITIES[args.modality]}
    
    results = {key: setup_modality(constants.PROJECT_ID, constants.EBT_LOCATION, key, config) for key, config in targets.items()}

    print(f"\n{'='*60}\nSETUP SUMMARY\n{'='*60}")
    for key, success in results.items():
        status = "✅ READY" if success else "❌ FAILED / PENDING"
        print(f"  {constants.MODALITIES[key]['display_name']}: {status}")

    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
