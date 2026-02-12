#!/usr/bin/env python3
"""
Creates or recreates a Vertex AI Search datastore from an existing GCS bucket.

This script is designed for scenarios where the corpus files already exist in a GCS
bucket. It performs the following steps:
1. Creates a new Vertex AI Search datastore (or gets it if it exists).
2. Scans the specified GCS bucket to generate a metadata.jsonl file with custom
   structData for each document.
3. Imports the documents into the datastore using the metadata file.

This is useful for disaster recovery, CI/CD pipelines, or experimenting with
different datastore configurations against the same source data.
"""

import os
import sys
import time
import json
import argparse
from google.api_core import exceptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage
from . import constants

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
    except exceptions.AlreadyExists:
        print(f"⚠️  Datastore '{datastore_id}' already exists.")
        return client.get_data_store(name=f"{parent}/dataStores/{datastore_id}")
    except Exception as e:
        print(f"❌ Error creating datastore: {e}")
        raise

def create_metadata_jsonl(project_id: str, bucket_name: str, corpus_dir_prefix: str, metadata_file_name: str):
    """
    Creates a metadata.jsonl file in GCS for batch import by scanning a bucket.
    This file includes custom structData for each document.
    """
    print(f"\n📄 Creating metadata file for import from bucket '{bucket_name}'...")
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    corpus_blobs = list(bucket.list_blobs(prefix=corpus_dir_prefix))
    if not corpus_blobs:
        print(f"❌ No corpus files found in GCS bucket '{bucket_name}' under prefix '{corpus_dir_prefix}'.")
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
            data_schema="document"
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
        
        operation.result(timeout=timeout)
        metadata = discoveryengine.ImportDocumentsMetadata(operation.metadata)

        success_count = metadata.success_count
        failure_count = metadata.failure_count

        print("\n✅ Import operation finished!")
        print("  📊 Import Statistics:")
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
    parser = argparse.ArgumentParser(description="Recreate a Vertex AI Search datastore from an existing GCS bucket.")
    parser.add_argument("bucket", help="The name of the GCS bucket containing the corpus files.")
    args = parser.parse_args()
    
    bucket_name = args.bucket

    if not constants.PROJECT_ID:
        sys.exit(1)

    print(f"🚀 Recreating Vertex AI Search datastore from GCS bucket: {bucket_name}")
    print(f"Project ID: {constants.PROJECT_ID}")
    print(f"Datastore ID: {constants.RECREATED_DATASTORE_ID}\n")
    
    try:
        datastore = create_datastore(
            project_id=constants.PROJECT_ID,
            location=constants.RECREATED_LOCATION,
            datastore_id=constants.RECREATED_DATASTORE_ID,
            display_name=constants.RECREATED_DISPLAY_NAME
        )
        
        if create_metadata_jsonl(
            project_id=constants.PROJECT_ID,
            bucket_name=bucket_name,
            corpus_dir_prefix=constants.RECREATED_CORPUS_DIR_PREFIX,
            metadata_file_name=constants.RECREATED_METADATA_FILE_NAME
        ):
            if import_documents_to_datastore(
                location=constants.RECREATED_LOCATION,
                datastore_name=datastore.name,
                bucket_name=bucket_name,
                metadata_file_name=constants.RECREATED_METADATA_FILE_NAME
            ):
                print("\n✨ RAG datastore recreation is complete and ready for use! ✨")
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