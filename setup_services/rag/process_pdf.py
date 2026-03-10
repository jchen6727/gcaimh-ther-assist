from google.cloud import storage, discoveryengine_v1 as discoveryengine
from google.cloud.exceptions import NotFound, Conflict, Forbidden
from google import genai
import time

def get_gcs_bucket(client: storage.Client = None, project_id: str = None, bucket_id: str = None, location: str = "us-central1"):
    """get bucket_nam a GCS bucket for storing the EBT corpus documents."""
    client = client or storage.Client(project=project_id)
    try:
        bucket = client.get_bucket(bucket_id)
        print(f"bucket {bucket_id} already exists")
        return bucket
    except NotFound: # google cloud exception for bucket DNE
        try:
            bucket = client.create_bucket(
                bucket_id,
                location = location
            )
            print(f"bucket {bucket_id} created in {location}")
            return bucket
        except Conflict:
            print(f"bucket {bucket_id} already exists")
            try:
                bucket = client.get_bucket(bucket_id)
                return bucket
            except NotFound:
                raise Exception(
                    f"bucket {bucket_id} cannot be accessed, please check permissions"
                )
    except Exception as e:
        print(f"encountered unexpected error with bucket {bucket_id}: {e}")
        raise e


class PDF_Processor:
    """
    Production-ready pipeline using Discovery Engine's layout parsing + Gemini enhancement
    """

    def __init__(self, project_id, blob_id, bucket_id, data_store_id, location):
        self.project_id = project_id
        self.blob_id = blob_id
        self.bucket_id = bucket_id
        self.location = location
        self.data_store_id = data_store_id
        self.genai_client = genai.Client(vertexai=True, project=project_id)
        self.doc_client = discoveryengine.DocumentServiceClient()


    def process_file(self, local_path):
        """
        Complete pipeline -- should be abstract class --
        """
        # 1. Upload to GCS
        gcs_uri = self._upload_to_gcs(local_path)

        # 2. Ensure data store has layout parsing
        self._configure_layout_parsing()

        # 3. Import PDF (Discovery Engine chunks it)
        self._import_file(gcs_uri)

        # 4. Wait for processing
        print("Waiting for Discovery Engine to process...")
        time.sleep(60)

        # 5. Retrieve and enhance chunks
        self._enhance_chunks_with_gemini()

        print("Pipeline complete!")

    def _upload_to_gcs(self, local_path, storage_client=None):
        """Upload file to GCS"""
        # Ensure gcs bucket for upload.
        if not local_path.endswith('.pdf'):
            raise ValueError(f"Unsupported file format: {local_path} for PDF_Processor. Expecting a PDF (.pdf) at local_path.")
        bucket = get_gcs_bucket(project_id = self.project_id, bucket_id = self.bucket_id)
        blob = bucket.blob(self.blob_id)
        try:
            blob.upload_from_filename(local_path)
        except Exception as e:
            print(f"Failed to upload file to GCS: {e}")
            return False
        return True

    def _configure_layout_parsing(self):
        """Ensure layout parsing is enabled"""
        # Use ensure_layout_parsing_enabled() from above
        pass

    def _import_file(self, gcs_uri):
        """Import with Discovery Engine"""
        # Use import_pdf_with_layout_parsing() from above
        pass

    def _enhance_chunks_with_gemini(self):
        """Add semantic metadata with Gemini"""
        chunks = self._list_chunks()

        for chunk in chunks:
            # Get layout-based metadata (already there)
            layout_metadata = chunk.get('structData', {})

            # Generate semantic metadata with Gemini
            content = layout_metadata.get('content', '')
            gemini_metadata = self._generate_metadata(content)

            # Merge and update
            enhanced = {**layout_metadata, **gemini_metadata}
            self._update_chunk(chunk['id'], enhanced)