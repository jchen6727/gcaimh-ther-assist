#!/usr/bin/env python3
"""
Script to programmatically create a Vertex AI Search datastore with document chunking for RAG,
using the modern Python SDK. This datastore is configured to process EBT therapy
manuals with layout-aware chunking.
"""

import os
import time
import json
from google.api_core import exceptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage

# --- Configuration ---
# Attempt to get Project ID from environment, otherwise fall back to gcloud default
try:
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not PROJECT_ID:
        import subprocess
        PROJECT_ID = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"], text=True
        ).strip()
except Exception:
    print("❌ Could not determine Google Cloud project. Please set GOOGLE_CLOUD_PROJECT environment variable.")
    exit(1)

LOCATION = "us"  # Global location for Discovery Engine
DATASTORE_ID = "ebt-corpus-sdk" # Using a new name to avoid conflicts
DISPLAY_NAME = "EBT Therapy Manuals Corpus (SDK)"
BUCKET_NAME = f"{PROJECT_ID}-ebt-corpus"
CORPUS_DIR = "corpus"


def create_datastore():
    """Create a Vertex AI Search datastore using the Python SDK."""
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection"
    
    client = discoveryengine.DataStoreServiceClient()
    
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

    request = discoveryengine.CreateDataStoreRequest(
        parent=parent,
        data_store=data_store,
        data_store_id=DATASTORE_ID,
    )

    print(f"Creating datastore '{DATASTORE_ID}' with layout-aware chunking...")
    try:
        operation = client.create_data_store(request=request)
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

def import_documents_to_datastore(datastore_name: str, timeout: int = 600):
    """Import documents from GCS to the datastore using the SDK."""
    client = discoveryengine.DocumentServiceClient()
    
    gcs_uri = f"gs://{BUCKET_NAME}/corpus/*"

    request = discoveryengine.ImportDocumentsRequest(
        parent=f"{datastore_name}/branches/0",
        gcs_source=discoveryengine.GcsSource(
            input_uris=[gcs_uri],
            data_schema="content" # `content` schema infers from files
        ),
        reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
    )

    print(f"Importing documents from '{gcs_uri}' to datastore...")
    try:
        operation = client.import_documents(request=request)
        print(f"⏳ Waiting for import operation to complete... (Timeout: {timeout}s)")
        
        response = operation.result(timeout=timeout)
        
        # Process the response
        success_count = response.success_count
        failure_count = response.failure_count

        print("\n✅ Import operation finished!")
        print(f"  📊 Import Statistics:")
        print(f"    - Success Count: {success_count}")
        print(f"    - Failure Count: {failure_count}")

        if failure_count > 0:
            print("\n  ⚠️  Warning: Some documents failed to import.")
            for sample in response.error_samples:
                print(f"    - Error: {sample.message}")
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
    
    try:
        datastore = create_datastore()
        create_gcs_bucket()
        
        if upload_corpus_to_gcs():
            if import_documents_to_datastore(datastore.name):
                print("\n✨ RAG datastore setup is complete and ready for use! ✨")
                print("\n📚 Your EBT corpus has been:")
                print("   ✅ Uploaded to GCS bucket")
                print("   ✅ Imported into Vertex AI Search")
                print("   ✅ Configured with layout-aware chunking")
                
                print(f"\n🔗 Datastore Path: {datastore.name}")
            else:
                print("\n❌❌❌ IMPORT OPERATION FAILED ❌❌❌")
                print("   Please check the logs above for details on failed documents.")
        
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
