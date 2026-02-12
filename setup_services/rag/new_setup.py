#!/usr/bin/env python3
"""
Script to programmatically create a Vertex AI Search datastore with document chunking for RAG,
using the modern Python SDK. This script handles the full, end-to-end process including
GCS bucket creation, corpus upload, and datastore import with custom metadata.

This version demonstrates using a metadata.jsonl file to include custom
structData for each document.
"""

import os
import sys
import time
import json
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage
from . import constants
from . import utils

def create_datastore(project_id: str, location: str, datastore_id: str, display_name: str):
    """Create a Vertex AI Search datastore using the Python SDK."""
    parent = f"projects/{project_id}/locations/{location}/collections/default_collection"
    
    client_options = {"api_endpoint": f"{location}-discoveryengine.googleapis.com"}
    client = discoveryengine.DataStoreServiceClient(client_options=client_options)
    
    data_store = discoveryengine.DataStore(
        display_name=display_name,
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

    print(f"Creating datastore '{datastore_id}' with layout-aware chunking...")
    try:
        operation = client.create_data_store(
            parent=parent,
            data_store=data_store,
            data_store_id=datastore_id,
        )
        print("⏳ Waiting for datastore creation to complete...")
        response = operation.result()
        print(f"✅ Datastore '{response.name}' created successfully!")
        return response
    except Exception as e:
        if "AlreadyExists" in str(e):
            print(f"⚠️  Datastore '{datastore_id}' already exists.")
            return client.get_data_store(name=f"{parent}/dataStores/{datastore_id}")
        else:
            print(f"❌ Error creating datastore: {e}")
            raise

def upload_corpus_to_gcs(project_id: str, bucket_name: str, corpus_dir: str):
    """Upload EBT corpus files from the local filesystem to GCS."""
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    if not os.path.exists(corpus_dir):
        print(f"❌ Corpus directory '{corpus_dir}' not found!")
        print(f"   Current directory: {os.getcwd()}")
        return False

    files_uploaded = 0
    files_failed = 0
    for filename in os.listdir(corpus_dir):
        if filename.endswith(('.pdf', '.docx', '.txt')):
            local_path = os.path.join(corpus_dir, filename)
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

def create_metadata_jsonl(project_id: str, bucket_name: str, corpus_dir: str, metadata_file_name: str):
    """
    Creates a metadata.jsonl file in GCS for batch import.
    This file includes custom structData for each document.
    """
    print("\n📄 Creating metadata file for import...")
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    corpus_blobs = list(bucket.list_blobs(prefix=f"{corpus_dir}/"))
    if not corpus_blobs:
        print(f"❌ No corpus files found in GCS bucket '{bucket_name}' under prefix '{corpus_dir}/'.")
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
                    "uri": f"gs://{bucket_name}/{file_path}",
                    "mimeType": mime_type
                }
            }
            metadata_lines.append(json.dumps(metadata))

    if not metadata_lines:
        print("❌ No valid documents found to create metadata for.")
        return False
        
    # Upload metadata file to GCS
    metadata_content = '\n'.join(metadata_lines)
    metadata_blob = bucket.blob(metadata_file_name)
    metadata_blob.upload_from_string(metadata_content)
    print(f"✅ Created metadata file '{metadata_file_name}' with {len(metadata_lines)} documents.")
    return True


def import_documents_to_datastore(location: str, datastore_name: str, bucket_name: str, metadata_file_name: str, timeout: int = 600):
    """
    Import documents from GCS to the datastore using a metadata.jsonl file
    and the 'document' schema.
    """
    client_options = {"api_endpoint": f"{location}-discoveryengine.googleapis.com"}
    client = discoveryengine.DocumentServiceClient(client_options=client_options)
    
    gcs_uri = f"gs://{bucket_name}/{metadata_file_name}"
    error_uri = f"gs://{bucket_name}/import_errors"
    
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
            display_name=constants.EBT_DISPLAY_NAME
        )
        utils.create_gcs_bucket(
            project_id=constants.PROJECT_ID,
            bucket_name=constants.EBT_BUCKET_NAME,
            location=constants.EBT_LOCATION
        )
        
        if upload_corpus_to_gcs(
            project_id=constants.PROJECT_ID,
            bucket_name=constants.EBT_BUCKET_NAME,
            corpus_dir=constants.EBT_CORPUS_DIR
        ):
            if create_metadata_jsonl(
                project_id=constants.PROJECT_ID,
                bucket_name=constants.EBT_BUCKET_NAME,
                corpus_dir=constants.EBT_CORPUS_DIR,
                metadata_file_name=constants.EBT_METADATA_FILE_NAME
            ):
                if import_documents_to_datastore(
                    location=constants.EBT_LOCATION,
                    datastore_name=datastore.name,
                    bucket_name=constants.EBT_BUCKET_NAME,
                    metadata_file_name=constants.EBT_METADATA_FILE_NAME
                ):
                    print("\n✨ RAG datastore setup is complete and ready for use! ✨")
                    print("\n📚 Your EBT corpus has been:")
                    print("   ✅ Uploaded to GCS bucket")
                    print("   ✅ Described in a metadata.jsonl file with custom structData")
                    print("   ✅ Imported into Vertex AI Search")
                    print("   ✅ Configured with layout-aware chunking")
                    
                    print(f"\n🔗 Datastore Path: {datastore.name}")
                else:
                    print("\n❌❌❌ IMPORT OPERATION FAILED ❌❌❌")
            else:
                print("\n❌❌❌ METADATA CREATION FAILED ❌❌❌")
        
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