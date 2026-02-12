# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env python3
"""
Script to programmatically create a Vertex AI Search datastore with document chunking for RAG.
This datastore will be configured to process EBT therapy manuals with layout-aware chunking.
"""

import os
import time
import json
import sys
from google.auth import default
from google.auth.transport.requests import Request
import requests
from . import constants

def get_access_token():
    """Get access token for API calls."""
    credentials, _ = default()
    credentials.refresh(Request())
    return credentials.token

def create_datastore(project_id: str, location: str, datastore_id: str, display_name: str, timeout:int):
    """Create a Vertex AI Search datastore with document chunking enabled."""
    
    url = f"https://{location}-discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores?dataStoreId={datastore_id}"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    # Configure datastore with layout-aware chunking for RAG
    data = {
        "displayName": display_name,
        "industryVertical": "GENERIC",
        "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
        "contentConfig": "CONTENT_REQUIRED",
        "documentProcessingConfig": {
            # Enable document chunking for RAG
            "chunkingConfig": {
                "layoutBasedChunkingConfig": {
                    "chunkSize": 500,  # Token size limit per chunk (100-500)
                    "includeAncestorHeadings": True  # Include headings for context
                }
            },
            "defaultParsingConfig": {"layoutParsingConfig": {}},
            "parsingConfigOverrides": {
                "pdf": {"layoutParsingConfig": {}},
                "docx": {"layoutParsingConfig": {}},
                "html": {"layoutParsingConfig": {}}
            }
        }
    }
    
    print(f"Creating datastore '{datastore_id}' with layout-aware chunking...")
    
    response = requests.post(url, headers=headers, json=data, timeout=timeout)
    
    if response.status_code == 200:
        print(f"✅ Datastore '{datastore_id}' created successfully!")
        return response.json()
    elif response.status_code == 409:
        print(f"⚠️  Datastore '{datastore_id}' already exists.")
        return get_datastore(project_id, location, datastore_id)
    else:
        print(f"❌ Error creating datastore: {response.status_code}")
        print(f"Response: {response.text}")
        raise Exception(f"Failed to create datastore: {response.text}")

def get_datastore(project_id: str, location: str, datastore_id: str):
    """Get existing datastore details."""
    url = f"https://{location}-discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores/{datastore_id}"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "X-Goog-User-Project": project_id
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error getting datastore: {response.status_code}")
        print(f"Response: {response.text}")
        return None

def create_gcs_bucket(project_id: str, bucket_name: str, location: str):
    """Create a GCS bucket for storing the EBT corpus documents."""
    from google.cloud import storage
    
    client = storage.Client(project=project_id)
    
    try:
        bucket = client.get_bucket(bucket_name)
        print(f"⚠️  Bucket {bucket_name} already exists")
        return bucket_name
    except Exception as e:
        if "404" in str(e):
            try:
                bucket = client.create_bucket(bucket_name, location=location)
                print(f"✅ Created GCS bucket: {bucket_name}")
                return bucket_name
            except Exception as create_error:
                if "already own it" in str(create_error):
                    print(f"⚠️  Bucket {bucket_name} already exists")
                    return bucket_name
                else:
                    raise create_error
        else:
            raise e

def upload_corpus_to_gcs(project_id: str, bucket_name: str, corpus_dir: str):
    """Upload EBT corpus files to GCS bucket."""
    from google.cloud import storage
    
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    
    if not os.path.exists(corpus_dir):
        print(f"❌ Corpus directory '{corpus_dir}' not found!")
        return False
    
    files_uploaded = 0
    files_failed = 0
    for filename in os.listdir(corpus_dir):
        if filename.endswith(('.pdf', '.docx', '.txt')):
            local_path = os.path.join(corpus_dir, filename)
            blob_name = f"corpus/{filename}"
            blob = bucket.blob(blob_name)
            
            try:
                print(f"📤 Uploading {filename}...")
                blob.upload_from_filename(local_path)
                files_uploaded += 1
                print(f"  ✅ Successfully uploaded {filename}")
            except Exception as e:
                print(f"  ❌ Failed to upload {filename}: {e}")
                files_failed += 1
    
    print(f"\n📊 Upload Summary:\n  ✅ Successfully uploaded: {files_uploaded} files")
    if files_failed > 0:
        print(f"  ❌ Failed to upload: {files_failed} files")
    return files_uploaded > 0

def import_documents_to_datastore(project_id: str, location: str, datastore_id: str, bucket_name: str, metadata_file_name: str):
    """Import documents from GCS to the datastore."""
    from google.cloud import storage
    
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    
    corpus_files = [blob.name for blob in bucket.list_blobs(prefix="corpus/") if not blob.name.endswith('/')]
    
    if not corpus_files:
        print("❌ No corpus files found in bucket!")
        return None
    
    metadata_lines = []
    for file_path in corpus_files:
        filename = os.path.basename(file_path)
        doc_id = filename.replace('.', '_').replace(' ', '_')
        
        metadata = {
            "id": doc_id,
            "structData": {"title": filename, "source": "EBT Manual", "type": "therapy_manual"},
            "content": {
                "uri": f"gs://{bucket_name}/{file_path}",
                "mimeType": "application/pdf" if file_path.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            }
        }
        metadata_lines.append(json.dumps(metadata))
    
    metadata_content = '\n'.join(metadata_lines)
    metadata_blob = bucket.blob(metadata_file_name)
    metadata_blob.upload_from_string(metadata_content)
    print(f"✅ Created metadata file with {len(corpus_files)} documents")
    
    url = f"https://{location}-discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores/{datastore_id}/branches/0/documents:import"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    data = {
        "gcsSource": {
            "inputUris": [f"gs://{bucket_name}/{metadata_file_name}"],
            "dataSchema": "document"
        },
        "reconciliationMode": "INCREMENTAL"
    }
    
    print(f"Importing {len(corpus_files)} documents from GCS to datastore...")
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error importing documents: {response.status_code}\nResponse: {response.text}")
        raise Exception(f"Failed to import documents: {response.text}")

def wait_for_operation(project_id: str, operation_name: str, timeout: int = 600):
    """Wait for a long-running operation to complete."""
    headers = {"Authorization": f"Bearer {get_access_token()}", "X-Goog-User-Project": project_id}
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        url = f"https://discoveryengine.googleapis.com/v1/{operation_name}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            operation = response.json()
            if operation.get("done"):
                if "error" in operation:
                    print(f"\n❌❌❌ IMPORT OPERATION FAILED ❌❌❌\n{operation['error']}")
                    return False
                else:
                    print("\n✅ Operation completed successfully!")
                    return True
        else:
            print(f"❌ Error checking operation status: {response.status_code}\nResponse: {response.text}")
            return False
        
        print(f"⏳ Waiting for operation... ({int(time.time() - start_time)}/{timeout}s)")
        time.sleep(10)
    
    print(f"❌ Operation timed out after {timeout} seconds.")
    return False

def main():
    """Main function to set up the RAG datastore."""
    if not constants.PROJECT_ID:
        sys.exit(1)

    print(f"🚀 Setting up Vertex AI Search datastore for Ther-Assist")
    print(f"Project ID: {constants.PROJECT_ID}")
    print(f"Datastore ID: {constants.EBT_DATASTORE_ID}\n")
    
    try:
        datastore = create_datastore(
            project_id=constants.PROJECT_ID,
            location=constants.EBT_LOCATION,
            datastore_id=constants.EBT_DATASTORE_ID,
            display_name=constants.EBT_DISPLAY_NAME,
            timeout=600
        )
        
        bucket_name = create_gcs_bucket(
            project_id=constants.PROJECT_ID,
            bucket_name=constants.EBT_BUCKET_NAME,
            location=constants.EBT_LOCATION
        )
        
        if upload_corpus_to_gcs(constants.PROJECT_ID, bucket_name, constants.EBT_CORPUS_DIR):
            operation = import_documents_to_datastore(
                project_id=constants.PROJECT_ID,
                location=constants.EBT_LOCATION,
                datastore_id=constants.EBT_DATASTORE_ID,
                bucket_name=bucket_name,
                metadata_file_name=constants.EBT_METADATA_FILE_NAME
            )
            
            if operation and wait_for_operation(constants.PROJECT_ID, operation['name']):
                print("\n✅✅✅ RAG DATASTORE SETUP COMPLETE! ✅✅✅")
            else:
                print("\n❌❌❌ IMPORT OPERATION FAILED OR TIMED OUT ❌❌❌")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        from google.cloud import storage
    except ImportError:
        print("Installing dependencies...")
        os.system("pip install google-cloud-storage requests")
        sys.exit(0)
    
    main()
