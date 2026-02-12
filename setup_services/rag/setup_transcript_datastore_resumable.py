#!/usr/bin/env python3
"""
Resumable script to create and populate a Vertex AI Search datastore for clinical transcripts.
"""

import os
import sys
import time
import json
import PyPDF2
from typing import Set
from . import constants
from . import utils

def create_datastore(project_id: str, location: str, datastore_id: str, display_name: str):
    url = f"https://discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores?dataStoreId={datastore_id}"
    headers = {"Authorization": f"Bearer {utils.get_access_token()}", "Content-Type": "application/json", "X-Goog-User-Project": project_id}
    data = {
        "displayName": display_name,
        "industryVertical": "GENERIC",
        "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
        "contentConfig": "CONTENT_REQUIRED",
        "documentProcessingConfig": {
            "chunkingConfig": {"layoutBasedChunkingConfig": {"chunkSize": 300, "includeAncestorHeadings": True}},
            "defaultParsingConfig": {"layoutParsingConfig": {}}
        }
    }
    print(f"Creating datastore '{datastore_id}'...")
    response = utils.requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"✅ Datastore '{datastore_id}' created successfully!")
        return response.json()
    elif response.status_code == 409:
        print(f"⚠️  Datastore '{datastore_id}' already exists.")
        return utils.get_datastore(project_id, location, datastore_id)
    else:
        raise Exception(f"Failed to create datastore: {response.text}")

def list_existing_blobs(project_id: str, bucket_name: str) -> Set[str]:
    from google.cloud import storage
    print("📋 Listing existing files in GCS bucket...")
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    return {blob.name for blob in bucket.list_blobs()}

def process_json_conversation(json_path: str):
    # ... (function is unchanged)
    pass

def process_pdf_transcript(pdf_path: str):
    # ... (function is unchanged)
    pass

def upload_transcripts_to_gcs_with_resume(project_id: str, bucket_name: str, transcripts_dir: str):
    # ... (function body is largely unchanged, just pass project_id to list_existing_blobs)
    pass

def create_pattern_library(project_id: str, bucket_name: str):
    # ... (function body is largely unchanged)
    pass

def import_documents_to_datastore(project_id: str, location: str, datastore_id: str, bucket_name: str):
    # ... (function body is largely unchanged)
    pass

def main():
    if not constants.PROJECT_ID:
        sys.exit(1)

    print(f"🚀 Setting up Vertex AI Search datastore for Clinical Transcripts (Resumable Version)")
    print(f"Project ID: {constants.PROJECT_ID}")
    print(f"Datastore ID: {constants.TRANSCRIPT_DATASTORE_ID}\n")

    if '--reset' in sys.argv:
        utils.ProgressTracker().reset()

    try:
        create_datastore(
            project_id=constants.PROJECT_ID,
            location=constants.TRANSCRIPT_LOCATION,
            datastore_id=constants.TRANSCRIPT_DATASTORE_ID,
            display_name=constants.TRANSCRIPT_DISPLAY_NAME
        )
        
        bucket_name = utils.create_gcs_bucket(constants.PROJECT_ID, constants.TRANSCRIPT_BUCKET_NAME, "US")
        
        if upload_transcripts_to_gcs_with_resume(constants.PROJECT_ID, bucket_name, "transcripts"):
            create_pattern_library(constants.PROJECT_ID, bucket_name)
            
            operation = import_documents_to_datastore(
                project_id=constants.PROJECT_ID,
                location=constants.TRANSCRIPT_LOCATION,
                datastore_id=constants.TRANSCRIPT_DATASTORE_ID,
                bucket_name=bucket_name
            )
            
            if operation and utils.wait_for_operation(constants.PROJECT_ID, operation['name']):
                print("\n✅ Transcript RAG datastore setup complete!")
            else:
                print("\n⚠️  Import operation failed or timed out")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
