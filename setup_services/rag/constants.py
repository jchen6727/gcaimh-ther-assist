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
Centralized configuration constants for RAG setup and use.
"""

import os
from google.auth import default
from datetime import datetime
from collections import namedtuple
import yaml

# --- GCP Configuration ---
# defaults to the GOOGLE_CLOUD_PROJECT variable in the environment, otherwise uses default()
try:
    # Attempt to get Project ID from environment, otherwise fall back to gcloud default
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", default()[1])
except Exception:
    print("❌ Could not determine Google Cloud project. Please set GOOGLE_CLOUD_PROJECT environment variable.")
    PROJECT_ID = None

# API Endpoints
#ENDPOINTS = {
#    "us": "us-discoveryengine.googleapis.com",
#    ...
#}
# NOTE ^ ONLY NEEDED FOR DISCOVERYENGINE CREATION!

# for labels to not conflict in storage
LABEL = "experimental"
TIMESTAMP = datetime.now().strftime("%m-%d-%H%M")

# for multiregion API requests
# see
# https://cloud.google.com/about/locations?_gl=1*8xpwq7*_ga*MTI3NjIxODUyNC4xNzcwMzE1NTA5*_ga_WH2QY8WWF5*czE3NzAzMTU1MDgkbzEkZzEkdDE3NzAzMTU4NDUkajYwJGwwJGgw#multi-region
LOCATION = "us"

#ENDPOINT = ENDPOINTS[LOCATION]
# for API with specific endpoints
ZONE = "us-central1"

# --- Individual Datastore Configuration ---
METADATA_CONFIG = {

}

_config = namedtuple(
    typename="config",
    field_names=[ "label", "datastore", "bucket",],
)

def _return_config(
    label = LABEL,
    datastore = None,
    bucket = None,
    timestamp = True):
    if datastore is None:
        datastore = f"{label}" + f"-{TIMESTAMP}" if timestamp else ""
    if bucket is None:
        bucket = f"{PROJECT_ID}-{label}" + f"-{TIMESTAMP}" if timestamp else ""
    return _config(
        label = label, datastore = datastore, bucket = bucket
    )

def _generate_yaml_files(
    directory: str,
    configs: list,
):
    """Serializes a list of config objects to a YAML file."""
    filename = directory + f"{LABEL}.yml"
    backupname = directory + f"{LABEL}-{TIMESTAMP}.yml"

    data = [config._asdict() for config in configs]

    with open(filename, "w+") as fptr:
        yaml.dump(data, fptr)
    with open(backupname, "w+") as fptr:
        yaml.dump(data, fptr)
    return True
    # adds config to a dotenv

STORES = {
    "EBT": _return_config(label="EBT", )
    "BA": _return_config(label="BA", ),
    "DBT": _return_config(label="DBT", ),
    "IPT": _return_config(),
}



# Configuration for the EBT Manuals Corpus (for `new_setup.py`)
EBT_LOCATION = "us"
EBT_DATASTORE_ID = "ebt-corpus-sdk-metadata"
EBT_DISPLAY_NAME = "EBT Therapy Manuals Corpus (SDK with Metadata)"
EBT_BUCKET_NAME = f"{PROJECT_ID}-ebt-corpus"
EBT_CORPUS_DIR = "corpus"
EBT_METADATA_FILE_NAME = "import_metadata.jsonl"


# Configuration for the Clinical Transcripts Datastore (for `load_transcripts.py`)
TRANSCRIPT_LOCATION = "us"
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