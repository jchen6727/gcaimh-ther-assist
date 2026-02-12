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
Script to programmatically create a Vertex AI Search datastore for clinical transcripts.
This datastore will be configured to process therapy session transcripts with dialogue-aware chunking
to preserve conversational context and therapeutic patterns.
"""

import os
import time
import json
import sys
from google.auth import default
from google.auth.transport.requests import Request
import requests
import PyPDF2
from . import constants

def get_access_token():
    """Get access token for API calls."""
    credentials, _ = default()
    credentials.refresh(Request())
    return credentials.token

def create_datastore(project_id: str, location: str, datastore_id: str, display_name: str):
    """Create a Vertex AI Search datastore with dialogue-aware chunking."""
    
    url = f"https://discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores?dataStoreId={datastore_id}"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
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
    
    print(f"Creating datastore '{datastore_id}' with dialogue-aware chunking...")
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        print(f"✅ Datastore '{datastore_id}' created successfully!")
        return response.json()
    elif response.status_code == 409:
        print(f"⚠️  Datastore '{datastore_id}' already exists.")
        return get_datastore(project_id, location, datastore_id)
    else:
        raise Exception(f"Failed to create datastore: {response.text}")

def get_datastore(project_id: str, location: str, datastore_id: str):
    """Get existing datastore details."""
    url = f"https://discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores/{datastore_id}"
    headers = {"Authorization": f"Bearer {get_access_token()}", "X-Goog-User-Project": project_id}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def create_gcs_bucket(project_id: str, bucket_name: str):
    """Create a GCS bucket for storing the transcript documents."""
    from google.cloud import storage
    client = storage.Client(project=project_id)
    try:
        bucket = client.get_bucket(bucket_name)
        print(f"⚠️  Bucket {bucket_name} already exists")
        return bucket_name
    except Exception as e:
        if "404" in str(e):
            try:
                bucket = client.create_bucket(bucket_name, location="US")
                print(f"✅ Created GCS bucket: {bucket_name}")
                return bucket_name
            except Exception as create_error:
                if "already own it" in str(create_error):
                    print(f"⚠️  Bucket {bucket_name} already exists")
                else:
                    raise create_error
        else:
            raise e

def process_json_conversation(json_path):
    """Process JSON conversation files into searchable dialogue format."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Format as dialogue with 3-turn sequences
    formatted_content = []
    conversation = data.get('messages', data.get('conversation', []))
    
    # Create overlapping 3-turn sequences for better pattern matching
    for i in range(len(conversation) - 2):
        sequence = []
        for j in range(3):
            if i + j < len(conversation):
                msg = conversation[i + j]
                role = msg.get('role', 'Unknown')
                content = msg.get('content', msg.get('text', ''))
                sequence.append(f"{role}: {content}")
        
        if len(sequence) >= 2:  # At least 2 turns
            formatted_content.append("\n".join(sequence))
            formatted_content.append("\n---\n")  # Separator between sequences
    
    # Add metadata about the session
    session_type = "PTSD" if "trauma" in json_path.lower() else "General"
    formatted_content.insert(0, f"Session Type: {session_type}\n")
    formatted_content.insert(1, f"File: {os.path.basename(json_path)}\n\n")
    
    return "\n".join(formatted_content)

def process_pdf_transcript(pdf_path):
    """Extract text from PDF transcripts."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = []
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text.append(page.extract_text())
            
            full_text = "\n".join(text)
            
            # Add metadata
            session_type = "Beck CBT" if "BB3" in pdf_path else "PE/PTSD" if "PE" in pdf_path else "General"
            metadata = f"Session Type: {session_type}\nFile: {os.path.basename(pdf_path)}\n\n"
            
            return metadata + full_text
    except Exception as e:
        print(f"⚠️  Error processing PDF {pdf_path}: {e}")
        return None

def upload_transcripts_to_gcs(project_id: str, bucket_name: str, transcripts_dir: str):
    """Upload transcript files to GCS bucket."""
    from google.cloud import storage
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    
    if not os.path.exists(transcripts_dir):
        print(f"❌ Transcripts directory '{transcripts_dir}' not found!")
        return False
    
    files_uploaded = 0
    
    # Process PDF transcripts
    for root, dirs, files in os.walk(transcripts_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            
            # Process PDFs (Beck sessions, PE sessions)
            if filename.endswith('.pdf'):
                print(f"Processing PDF: {filename}...")
                content = process_pdf_transcript(file_path)
                
                if content:
                    # Upload processed content as text
                    blob_name = f"transcripts/{filename}.txt"
                    blob = bucket.blob(blob_name)
                    blob.upload_from_string(content)
                    files_uploaded += 1
                    print(f"  ✅ Uploaded processed PDF: {filename}")
            
            # Process JSON conversations
            elif filename.endswith('.json'):
                print(f"Processing JSON conversation: {filename}...")
                content = process_json_conversation(file_path)
                
                # Upload processed content as text
                blob_name = f"transcripts/{filename}.txt"
                blob = bucket.blob(blob_name)
                blob.upload_from_string(content)
                files_uploaded += 1
                print(f"  ✅ Uploaded processed JSON: {filename}")
    
    print(f"\n✅ Uploaded {files_uploaded} processed transcript files to GCS bucket")
    return True

def create_pattern_library(project_id: str, bucket_name: str):
    """Create a pattern library document with key therapeutic moments."""
    from google.cloud import storage
    
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    
    # Define key patterns from the transcripts
    patterns = {
        "resistance_patterns": [
            {
                "pattern": "Client: I don't want to impose on anyone",
                "technique": "Socratic questioning",
                "response": "Therapist: What makes you think they'll see it as an imposition?",
                "source": "Beck Session 2"
            },
            {
                "pattern": "Client: I'm not sure I'm ready for this",
                "technique": "Validation with gradual approach",
                "response": "Therapist: It's completely understandable to feel hesitant. Let's talk about what makes you feel not ready.",
                "source": "PE Session 1"
            }
        ],
        "engagement_techniques": [
            {
                "pattern": "Checking task likelihood",
                "example": "Therapist: On a scale of 0-100%, how likely are you to complete this task?",
                "purpose": "Assess commitment and adjust expectations",
                "source": "Beck Session 2"
            },
            {
                "pattern": "Collaborative tone",
                "example": "Therapist: Would that be alright with you?",
                "purpose": "Build therapeutic alliance",
                "source": "Beck Session 2"
            }
        ],
        "emotional_moments": [
            {
                "pattern": "Client: My heart is racing and my palms are sweating",
                "indicators": "Physiological anxiety symptoms",
                "intervention": "Grounding techniques, normalization of symptoms",
                "source": "PTSD Session"
            },
            {
                "pattern": "Client: I feel overwhelmed",
                "technique": "Break tasks into smaller steps",
                "example": "Therapist: Let's just focus on cleaning the sink for 10 minutes",
                "source": "Beck Session 2"
            }
        ],
        "quality_markers": {
            "positive": [
                "Concrete planning with specific times and actions",
                "Positive reinforcement: 'That's terrific'",
                "Making tasks optional to reduce pressure",
                "Checking in on task completion likelihood"
            ],
            "warning_signs": [
                "Pushing too fast when client expresses hesitation",
                "Not providing psychoeducation about the process",
                "Ignoring signs of overwhelm or dissociation",
                "Not validating client emotions before proceeding"
            ]
        }
    }
    
    # Convert to searchable text format
    pattern_content = "THERAPEUTIC PATTERN LIBRARY\n\n"
    pattern_content += "This document contains key therapeutic patterns extracted from clinical transcripts.\n\n"
    
    for category, items in patterns.items():
        pattern_content += f"\n## {category.replace('_', ' ').title()}\n\n"
        
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    for key, value in item.items():
                        pattern_content += f"{key}: {value}\n"
                    pattern_content += "\n"
                else:
                    pattern_content += f"- {item}\n"
        elif isinstance(items, dict):
            for subcategory, subitems in items.items():
                pattern_content += f"\n### {subcategory.replace('_', ' ').title()}\n"
                for item in subitems:
                    pattern_content += f"- {item}\n"
                pattern_content += "\n"
    
    # Upload pattern library
    blob_name = "patterns/therapeutic_pattern_library.txt"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(pattern_content)
    
    print("✅ Created and uploaded therapeutic pattern library")
    return True

def import_documents_to_datastore(project_id: str, location: str, datastore_id: str, bucket_name: str):
    """Import documents from GCS to the datastore."""
    
    url = f"https://discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores/{datastore_id}/branches/0/documents:import"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    # Configure import from GCS
    data = {
        "gcsSource": {
            "inputUris": [
                f"gs://{bucket_name}/transcripts/**",
                f"gs://{bucket_name}/patterns/**"
            ],
            "dataSchema": "document"
        },
        "reconciliationMode": "INCREMENTAL"
    }
    
    print(f"Importing documents from GCS to datastore...")
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to import documents: {response.text}")

def wait_for_operation(project_id: str, operation_name: str, timeout=600):
    """Wait for a long-running operation to complete."""
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "X-Goog-User-Project": project_id
    }
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        url = f"https://discoveryengine.googleapis.com/v1/{operation_name}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            operation = response.json()
            if operation.get("done"):
                if "error" in operation:
                    print(f"❌ Operation failed: {operation['error']}")
                    return False
                else:
                    print(f"✅ Operation completed successfully!")
                    return True
        else:
            print(f"❌ Error checking operation status: {response.status_code}")
            return False
        
        print("⏳ Waiting for operation to complete...")
        time.sleep(10)
    
    print(f"❌ Operation timed out after {timeout} seconds")
    return False

def main():
    if not constants.PROJECT_ID:
        sys.exit(1)

    print(f"🚀 Setting up Vertex AI Search datastore for Clinical Transcripts")
    print(f"Project ID: {constants.PROJECT_ID}")
    print(f"Datastore ID: {constants.TRANSCRIPT_DATASTORE_ID}\n")
    
    try:
        create_datastore(
            project_id=constants.PROJECT_ID,
            location=constants.TRANSCRIPT_LOCATION,
            datastore_id=constants.TRANSCRIPT_DATASTORE_ID,
            display_name=constants.TRANSCRIPT_DISPLAY_NAME
        )
        
        bucket_name = create_gcs_bucket(constants.PROJECT_ID, constants.TRANSCRIPT_BUCKET_NAME)
        
        if upload_transcripts_to_gcs(constants.PROJECT_ID, bucket_name, "transcripts"):
            create_pattern_library(constants.PROJECT_ID, bucket_name)
            
            operation = import_documents_to_datastore(
                project_id=constants.PROJECT_ID,
                location=constants.TRANSCRIPT_LOCATION,
                datastore_id=constants.TRANSCRIPT_DATASTORE_ID,
                bucket_name=bucket_name
            )
            
            if operation and wait_for_operation(constants.PROJECT_ID, operation['name']):
                print("\n✅ Transcript RAG datastore setup complete!")
            else:
                print("\n⚠️  Import operation failed or timed out")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        import PyPDF2
        from google.cloud import storage
    except ImportError:
        print("Installing dependencies...")
        os.system("pip install google-auth google-auth-httplib2 PyPDF2 requests google-cloud-storage")
        sys.exit(0)
    
    main()
