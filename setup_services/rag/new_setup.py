#!/usr/bin/env python3
"""
Script to programmatically create a Vertex AI Search datastore with document chunking for RAG,
using the modern Python SDK. This version demonstrates using a metadata.jsonl file
to include custom structData for each document.

It includes a --skip-gcs-upload flag to recreate the datastore when the GCS bucket
and corpus files already exist.
"""

import os
import sys
import time
import json
from google.api_core import exceptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage
from google.auth import default

# --- Configuration ---
# Attempt to get Project ID from environment, otherwise fall back to gcloud default
try:
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", default()[1])
except Exception:
    print("❌ Could not determine Google Cloud project. Please set GOOGLE_CLOUD_PROJECT environment variable.")
    exit(1)

LOCATION = "us"  # Global location for Discovery Engine
DATASTORE_ID = "ebt-corpus-sdk-metadata" # Using a new name to avoid conflicts
DISPLAY_NAME = "EBT Therapy Manuals Corpus (SDK with Metadata)"
BUCKET_NAME = f"{PROJECT_ID}-ebt-corpus"
CORPUS_DIR = "corpus"
METADATA_FILE_NAME = "import_metadata.jsonl"


def create_datastore():
    """Create a Vertex AI Search datastore using the Python SDK."""
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection"
    
    client_options = {"api_endpoint": f"{LOCATION}-discoveryengine.googleapis.com"}
    client = discoveryengine.DataStoreServiceClient(client_options=client_options)
    
    data_store = discoveryengine.DataStore(
        display_name=DISPLAY_NAME,
        industry_vertical="GENERIC",
        solution_types=["SOLUTION_TYPE_SEARCH"],
        content_config=discoveryengine.DataStore.ContentConfig.CONTENT_REQUIRED,
        document_processing_config=discoveryengine.DocumentProcessingConfig(
            chunking_config=discoveryengine.DocumentProcessingConfig.ChunkingConfig(
                layout_based_chunking_config=discoveryengine.DocumentProcessingConfig.ChunkingConfig.LayoutBasedChunkingConfig(
                    chunk_size=500,
                    include_ancestor_headings=True,
                )
            ),
            default_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig(
                layout_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig.LayoutParsingConfig()
            ),
            parsing_config_overrides={
                "pdf": discoveryengine.DocumentProcessingConfig.ParsingConfig(
                    layout_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig.LayoutParsingConfig()
                ),
                 "docx": discoveryengine.DocumentProcessingConfig.ParsingConfig(
                    layout_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig.LayoutParsingConfig()
                ),
                "html": discoveryengine.DocumentProcessingConfig.ParsingConfig(
                    layout_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig.LayoutParsingConfig()
                )
            }
        ),
    )

    print(f"Creating datastore '{DATASTORE_ID}' with layout-aware chunking...")
    try:
        operation = client.create_data_store(
            parent=parent,
            data_store=data_store,
            data_store_id=DATASTORE_ID,
        )
        print("⏳ Waiting for datastore creation to complete...")
        response = operation.result()
        print(f"✅ Datastore '{response.name}' created successfully!")
        return response
    except exceptions.AlreadyExists:
        print(f"⚠️  Datastore '{DATASTORE_ID}' already exists.")
        return client.get_data_store(name=f"{parent}/dataStores/{DATASTORE_ID}")
    except Exception as e:
        print(f"❌ Error creating datastore: {e}")
        raise

def create_gcs_bucket():
    """Create a GCS bucket for storing the EBT corpus documents."""
    client = storage.Client(project=PROJECT_ID)
    try:
        bucket = client.get_bucket(BUCKET_NAME)
        print(f"⚠️  Bucket '{BUCKET_NAME}' already exists.")
    except exceptions.NotFound:
        print(f"Creating GCS bucket: '{BUCKET_NAME}'...")
        try:
            client.create_bucket(BUCKET_NAME, location="US")
            print(f"✅ Created GCS bucket: '{BUCKET_NAME}'.")
        except exceptions.Conflict:
             print(f"⚠️  Bucket '{BUCKET_NAME}' already exists (creation conflict).")
        except Exception as e:
            print(f"❌ Failed to create bucket: {e}")
            raise
    except Exception as e:
        print(f"❌ An unexpected error occurred with GCS bucket: {e}")
        raise


def upload_corpus_to_gcs():
    """Upload EBT corpus files from the local filesystem to GCS."""
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    if not os.path.exists(CORPUS_DIR):
        print(f"❌ Corpus directory '{CORPUS_DIR}' not found!")
        print(f"   Current directory: {os.getcwd()}")
        return False

    files_uploaded = 0
    files_failed = 0
    for filename in os.listdir(CORPUS_DIR):
        if filename.endswith(('.pdf', '.docx', '.txt')):
            local_path = os.path.join(CORPUS_DIR, filename)
            blob_name = f"corpus/{filename}"
            blob = bucket.blob(blob_name)

            if blob.exists():
                print(f"ℹ️ Skipping {filename}, already exists in GCS.")
                files_uploaded += 1
                continue

            try:
                print(f"📤 Uploading {filename}...")
                blob.upload_from_filename(local_path)
                files_uploaded += 1
                print(f"  ✅ Successfully uploaded {filename}")
            except Exception as e:
                print(f"  ❌ Failed to upload {filename}: {e}")
                files_failed += 1

    print("\n📊 Upload Summary:")
    print(f"  ✅ Files processed (uploaded or skipped): {files_uploaded}")
    if files_failed > 0:
        print(f"  ❌ Failed to upload: {files_failed}")
    return files_uploaded > 0 and files_failed == 0

def create_metadata_jsonl():
    """
    Creates a metadata.jsonl file in GCS for batch import.
    This file includes custom structData for each document.
    """
    print("\n📄 Creating metadata file for import...")
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    corpus_blobs = list(bucket.list_blobs(prefix=f"{CORPUS_DIR}/"))
    if not corpus_blobs:
        print(f"❌ No corpus files found in GCS bucket '{BUCKET_NAME}' under prefix '{CORPUS_DIR}/'.")
        return False

    metadata_lines = []
    for blob in corpus_blobs:
        if not blob.name.endswith('/'): # Ignore "folders"
            file_path = blob.name
            filename = os.path.basename(file_path)
            doc_id = filename.replace('.', '_').replace(' ', '_')
            
            # Determine MIME type from extension
            if file_path.endswith('.pdf'):
                mime_type = "application/pdf"
            elif file_path.endswith('.docx'):
                mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else:
                mime_type = "text/plain"

            metadata = {
                "id": doc_id,
                "structData": {
                    "title": filename,
                    "source": "EBT Manual",
                    "type": "therapy_manual"
                },
                "content": {
                    "uri": f"gs://{BUCKET_NAME}/{file_path}",
                    "mimeType": mime_type
                }
            }
            metadata_lines.append(json.dumps(metadata))

    if not metadata_lines:
        print("❌ No valid documents found to create metadata for.")
        return False
        
    # Upload metadata file to GCS
    metadata_content = '\n'.join(metadata_lines)
    metadata_blob = bucket.blob(METADATA_FILE_NAME)
    metadata_blob.upload_from_string(metadata_content)
    print(f"✅ Created metadata file '{METADATA_FILE_NAME}' with {len(metadata_lines)} documents.")
    return True


def import_documents_to_datastore(datastore_name: str, timeout: int = 600):
    """
    Import documents from GCS to the datastore using a metadata.jsonl file
    and the 'document' schema.
    """
    client_options = {"api_endpoint": f"{LOCATION}-discoveryengine.googleapis.com"}
    client = discoveryengine.DocumentServiceClient(client_options=client_options)
    
    gcs_uri = f"gs://{BUCKET_NAME}/{METADATA_FILE_NAME}"
    error_uri = f"gs://{BUCKET_NAME}/import_errors"
    
    request = discoveryengine.ImportDocumentsRequest(
        parent=f"{datastore_name}/branches/0",
        gcs_source=discoveryengine.GcsSource(
            input_uris=[gcs_uri],
            data_schema="document"  # Use 'document' schema for JSONL metadata
        ),
        reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        error_config=discoveryengine.ImportErrorConfig(
            gcs_prefix=error_uri,
        )
    )

    print(f"\n📤 Importing documents using metadata file '{gcs_uri}'...")
    try:
        operation = client.import_documents(request=request)
        print(f"⏳ Waiting for import operation to complete... (Timeout: {timeout}s)")
        
        operation.result(timeout=timeout) # Wait for completion
        metadata = discoveryengine.ImportDocumentsMetadata(operation.metadata)

        success_count = metadata.success_count
        failure_count = metadata.failure_count

        print("\n✅ Import operation finished!")
        print(f"  📊 Import Statistics:")
        print(f"    - Success Count: {success_count}")
        print(f"    - Failure Count: {failure_count}")

        if failure_count > 0:
            print(f"\n  ⚠️  Warning: {failure_count} documents failed to import.")
            print(f"     Check the error file in GCS at '{error_uri}' for details.")
            return False
        
        print("\n✅✅✅ All documents imported successfully! ✅✅✅")
        return True

    except Exception as e:
        print(f"❌ Error during document import: {e}")
        raise

def main():
    """Main function to set up the RAG datastore."""
    print(f"🚀 Setting up Vertex AI Search datastore for Ther-Assist")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Datastore ID: {DATASTORE_ID}\n")

    # Check for --skip-gcs-upload flag
    skip_gcs_upload = "--skip-gcs-upload" in sys.argv
    
    try:
        datastore = create_datastore()
        
        if not skip_gcs_upload:
            print("\n☁️  Running full setup including GCS bucket creation and corpus upload.")
            create_gcs_bucket()
            if not upload_corpus_to_gcs():
                print("\n❌ GCS upload failed. Aborting.")
                return # Exit if upload fails
        else:
            print("\n⏭️  --skip-gcs-upload flag detected. Skipping GCS bucket creation and corpus upload.")
            print("   Assuming bucket and corpus files already exist.")

        # Proceed with metadata creation and import
        if create_metadata_jsonl():
            if import_documents_to_datastore(datastore.name):
                print("\n✨ RAG datastore setup is complete and ready for use! ✨")
                print("\n📚 Your EBT corpus has been:")
                if not skip_gcs_upload:
                    print("   ✅ Uploaded to GCS bucket")
                print("   ✅ Described in a metadata.jsonl file with custom structData")
                print("   ✅ Imported into Vertex AI Search")
                print("   ✅ Configured with layout-aware chunking")
                
                print(f"\n🔗 Datastore Path: {datastore.name}")
            else:
                print("\n❌❌❌ IMPORT OPERATION FAILED ❌❌❌")
                print("   Please check the logs above for details on failed documents.")
        else:
            print("\n❌❌❌ METADATA CREATION FAILED ❌❌❌")
            print("   Could not create the import_metadata.jsonl file. Aborting.")
        
    except Exception as e:
        print(f"\n❌ An unrecoverable error occurred during setup: {str(e)}")

if __name__ == "__main__":
    # Check for required libraries
    try:
        import google.cloud.discoveryengine_v1
        import google.cloud.storage
    except ImportError:
        print("🚨 Missing required Python libraries.")
        print("   Please install them by running:")
        print("   pip install google-cloud-discoveryengine google-cloud-storage")
        exit(1)
        
    main()
