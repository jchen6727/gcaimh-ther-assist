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
Utility functions and classes for RAG setup scripts.
"""

import os
import time
import json
from google.auth import default
from google.auth.transport.requests import Request
import requests

PROGRESS_FILE = "transcript_upload_progress.json"

class ProgressTracker:
    """Track upload progress to enable resumability."""

    def __init__(self, progress_file=PROGRESS_FILE):
        self.progress_file = progress_file
        self.completed_files = set()
        self.failed_files = {}
        self.load_progress()

    def load_progress(self):
        """Load progress from file if it exists."""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.completed_files = set(data.get('completed', []))
                    self.failed_files = data.get('failed', {})
                print(f"📂 Loaded progress: {len(self.completed_files)} files already processed")
            except Exception as e:
                print(f"⚠️  Could not load progress file: {e}")

    def save_progress(self):
        """Save current progress to file."""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    'completed': list(self.completed_files),
                    'failed': self.failed_files,
                    'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save progress: {e}")

    def mark_completed(self, filename):
        """Mark a file as successfully processed."""
        self.completed_files.add(filename)
        if filename in self.failed_files:
            del self.failed_files[filename]
        self.save_progress()

    def mark_failed(self, filename, error):
        """Mark a file as failed with error message."""
        self.failed_files[filename] = {
            'error': str(error),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        self.save_progress()

    def is_completed(self, filename):
        """Check if a file has been successfully processed."""
        return filename in self.completed_files

    def reset(self):
        """Reset all progress (use with caution)."""
        self.completed_files = set()
        self.failed_files = {}
        if os.path.exists(self.progress_file):
            os.remove(self.progress_file)
        print("🔄 Progress tracker reset")


def get_access_token():
    """Get access token for API calls."""
    credentials, _ = default()
    credentials.refresh(Request())
    return credentials.token


def wait_for_operation(project_id: str, operation_name: str, timeout: int = 600):
    """Wait for a long-running operation to complete (requests-based)."""
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


def create_gcs_bucket(project_id: str, bucket_name: str, location: str):
    """Create a GCS bucket."""
    from google.cloud import storage
    client = storage.Client(project=project_id)
    try:
        bucket = client.get_bucket(bucket_name)
        print(f"⚠️  Bucket '{bucket_name}' already exists.")
    except Exception as e:
        if "404" in str(e):
            print(f"Creating GCS bucket: '{bucket_name}'...")
            try:
                client.create_bucket(bucket_name, location=location)
                print(f"✅ Created GCS bucket: '{bucket_name}'.")
            except Exception as create_error:
                 if "already own it" in str(create_error):
                    print(f"⚠️  Bucket '{bucket_name}' already exists (creation conflict).")
                 else:
                    raise create_error
        else:
            raise e

def get_datastore(project_id: str, location: str, datastore_id: str):
    """Get existing datastore details (requests-based)."""
    url = f"https://{location}-discoveryengine.googleapis.com/v1/projects/{project_id}/locations/{location}/collections/default_collection/dataStores/{datastore_id}"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "X-Goog-User-Project": project_id
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None
