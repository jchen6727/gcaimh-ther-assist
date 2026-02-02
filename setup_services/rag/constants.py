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

"""
Centralized configuration constants for RAG setup scripts.
"""

import os
from google.auth import default

# --- GCP Configuration ---
try:
    # Attempt to get Project ID from environment, otherwise fall back to gcloud default
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", default()[1])
except Exception:
    print("❌ Could not determine Google Cloud project. Please set GOOGLE_CLOUD_PROJECT environment variable.")
    PROJECT_ID = None

# --- Datastore Configuration ---

# Configuration for the EBT Manuals Corpus (for `new_setup.py`)
EBT_LOCATION = "us"
EBT_DATASTORE_ID = "ebt-corpus-sdk-metadata"
EBT_DISPLAY_NAME = "EBT Therapy Manuals Corpus (SDK with Metadata)"
EBT_BUCKET_NAME = f"{PROJECT_ID}-ebt-corpus"
EBT_CORPUS_DIR = "corpus"
EBT_METADATA_FILE_NAME = "import_metadata.jsonl"


# Configuration for the Clinical Transcripts Datastore (for `load_transcripts.py`)
TRANSCRIPT_LOCATION = "global"
TRANSCRIPT_DATASTORE_ID = "transcript-patterns"
TRANSCRIPT_DISPLAY_NAME = "Clinical Therapy Transcripts"
TRANSCRIPT_BUCKET_NAME = f"{PROJECT_ID}-transcript-patterns"

# Configuration for the Recreated Datastore (for `recreate_datastore_from_gcs.py`)
RECREATED_LOCATION = "us"
RECREATED_DATASTORE_ID = "ebt-corpus-recreated"
RECREATED_DISPLAY_NAME = "EBT Therapy Manuals Corpus (Recreated)"
RECREATED_CORPUS_DIR_PREFIX = "corpus/"
RECREATED_METADATA_FILE_NAME = "import_metadata_recreate.jsonl"

# Modality definitions for `setup_modality_datastores.py`
MODALITIES = {
    "ba": {
        "datastore_id": "ba-corpus",
        "display_name": "Behavioral Activation Clinical Research",
        "corpus_dir": "corpus_ba",
        "source_label": "BA Research",
        "doc_type": "clinical_research",
        "description": "Behavioral Activation RCTs, meta-analyses, and treatment studies",
    },
    "dbt": {
        "datastore_id": "dbt-corpus",
        "display_name": "Dialectical Behavior Therapy Clinical Research",
        "corpus_dir": "corpus_dbt",
        "source_label": "DBT Research",
        "doc_type": "clinical_research",
        "description": "DBT RCTs, systematic reviews, and efficacy studies",
    },
    "ipt": {
        "datastore_id": "ipt-corpus",
        "display_name": "Interpersonal Psychotherapy Clinical Research",
        "corpus_dir": "corpus_ipt",
        "source_label": "IPT Research",
        "doc_type": "clinical_research",
        "description": "IPT RCTs, meta-analyses, and treatment comparisons",
    },
}