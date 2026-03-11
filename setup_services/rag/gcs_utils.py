from google.api_core.exceptions import AlreadyExists, PermissionDenied, NotFound, InvalidArgument
from google.cloud import discoveryengine_v1 as discoveryengine

# API Endpoints
_ENDPOINTS = {
    "us": "us-discoveryengine.googleapis.com",
    "global": "discoveryengine.googleapis.com",
    "eu": "eu-discoveryengine.googleapis.com",
}

# DEFAULT processing config -- enables layout parsing, passed to
# document_processing_config
_CONFIG = discoveryengine.DocumentProcessingConfig(
    default_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig(
        # enable layout parsing w/ OCR and native PDF text when available
        ocr_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig.OcrParsingConfig(
        use_native_text=True,
        ),
        # layout-based parsing
        layout_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig.LayoutParsingConfig()
        ),
    # chunking configuration is 512 tokens, w/ heading for context
    chunking_config=discoveryengine.DocumentProcessingConfig.ChunkingConfig(
        layout_based_chunking_config=discoveryengine.DocumentProcessingConfig.ChunkingConfig.LayoutBasedChunkingConfig(
            chunk_size=512,
            include_ancestor_headings=True,
        )
    )
    # parsing config overrides...
    # create if custom handling for extensions is needed ...
    # parsing_config_overrides={
    #    "pdf": discoveryengine.DocumentProcessingConfig.ParsingConfig(),
    #    "docx": discoveryengine.DocumentProcessingConfig.ParsingConfig(),
    #    "html": discoveryengine.DocumentProcessingConfig.ParsingConfig(),
)




# note on locations:
# https://docs.cloud.google.com/generative-ai-app-builder/docs/locations
def get_datastore(project_id, location, data_store_id):
    """
    Retrieves an existing DataStore or creates a new one if it doesn't exist.
    If the datastore exists, its configuration will be validated and updated if needed.
    Creation enables layout-aware parsing.
    """
    if location not in ['us', 'global', 'eu']:
        raise ValueError("expecting location in ('us', 'global', 'eu'): see https://docs.cloud.google.com/generative-ai-app-builder/docs/locations")

    client = discoveryengine.DataStoreServiceClient(client_options={"api_endpoint": _ENDPOINTS[location]})
    data_store_name = client.data_store_path(project=project_id, location=location, data_store=data_store_id)

    # Define the desired configuration to ensure consistency

    try:
        # First, try to get the data store.
        data_store = client.get_data_store(name=data_store_name)
        print(f"Data store '{data_store_id}' already exists. Verifying configuration.")

        # Check if the configuration needs updating
        if data_store.document_processing_config != _CONFIG:
            print("Configuration mismatch. Updating data store...")
            data_store.document_processing_config = _CONFIG
            update_mask = {"paths": ["document_processing_config"]}
            request = discoveryengine.UpdateDataStoreRequest(
                data_store=data_store,
                update_mask=update_mask
            )
            operation = client.update_data_store(request=request)
            response = operation.result()
            print("Data store configuration updated.")
            return response
        else:
            print("Configuration is up to date.")
            return data_store

    except NotFound:
        # If not found, then create it.
        print(f"Data store '{data_store_id}' not found. Creating it.")
        parent = f"projects/{project_id}/locations/{location}/collections/default_collection"

    data_store = discoveryengine.DataStore(
        display_name=f"{data_store_id}",
        industry_vertical=discoveryengine.IndustryVertical.GENERIC,
        solution_types=[discoveryengine.SolutionType.SOLUTION_TYPE_SEARCH],
        content_config=discoveryengine.DataStore.ContentConfig.CONTENT_REQUIRED,
        document_processing_config=_CONFIG,
    )

    request = discoveryengine.CreateDataStoreRequest(
        parent=parent,
        data_store=data_store,
        data_store_id=data_store_id
    )

    try:
        operation = client.create_data_store(request=request)
        response = operation.result()
        print(f"Created data store: {response.name}")
        return response
    except PermissionDenied as e:
        print(f"Error during data store creation: {e}")
        print("Please ensure your IAM permissions include 'discovery.dataStore.create'.")
        raise
    except InvalidArgument as e:
        print(f"Invalid argument: {e}")
        raise


def set_parsing_config(project_id, location, data_store_id):
    """
    Update existing data store to enable layout parsing

    if datastore created with gcs_utils.create_datastore(),
    then this function does not need to be called...
    """
    client = discoveryengine.DataStoreServiceClient()

    data_store_name = f"projects/{project_id}/locations/{location}/collections/default_collection/dataStores/{data_store_id}"

    # Get existing data store
    data_store = client.get_data_store(name=data_store_name)

    # Update with parsing config
    data_store.document_processing_config = _CONFIG

    # Update
    update_mask = {"paths": ["document_processing_config"]}
    request = discoveryengine.UpdateDataStoreRequest(
        data_store=data_store,
        update_mask=update_mask
    )

    operation = client.update_data_store(request=request)
    response = operation.result()

    print(f"Updated data store with layout parsing")
    return response