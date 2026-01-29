gcloud auth login --login-config="gcloud.json" --no-launch-browser

gcloud config set project brk-prj-salvador-dura-bern-sbx
gcloud auth application-default set-quota-project brk-prj-salvador-dura-bern-sbx

zsh gcloud_env.zsh




Notes: GCloud Auth & Discovery Engine API (2026)
1. Authentication: GCloud CLI vs. ADC
gcloud config set billing/quota_project: Affects the CLI tool. Use this if gcloud commands fail with "quota project" errors.
Fix if broken: gcloud config unset billing/quota_project
gcloud auth application-default set-quota-project: Affects Python/Local Code. It writes to a local JSON file used by Client Libraries.
Fix "invalid_grant": Your session expired. Run gcloud auth application-default login first.
2. Dynamic Project ID in Python
Avoid hardcoding os.environ. Use the google-auth library to detect the project context automatically from ADC or the Cloud Metadata service:
python
import google.auth
credentials, PROJECT_ID = google.auth.default()
Use code with caution.

3. Discovery Engine API Best Practices
Regional Endpoints: If your data is in the us multi-region, you must use the us- prefix in the URL.
Correct: https://us-discoveryengine.googleapis.com...
Note: us-central1 is not a valid location for this API; use us.
Timeouts & Cold Starts: Creating a datastore is a "Long-Running Operation" (LRO).
Cold Start Time: Usually 2–10 minutes.
Requests Timeout: Set timeout=300 (5 mins) in requests.post() to avoid 504 Deadline Exceeded.
Client Libraries vs. Requests:
requests.post returns an Operation ID. You must poll this ID to know when the datastore is actually ready.
Best Practice: Use google-cloud-discoveryengine. It handles LRO polling (operation.result()), token refreshing, and gRPC performance automatically.
4. Troubleshooting "Quota Project Not Set"
If you still get this error after setting the quota project:
Check Permissions: Ensure your user has the Service Usage Consumer role on the billing project.
Verify ADC File: Ensure quota_project_id appears in ~/.config/gcloud/application_default_credentials.json.
Environment Variables: Ensure GOOGLE_APPLICATION_CREDENTIALS is not set, as it will override your local ADC settings.
5. Billing & Cost (2026)
Enabling an API is generally free.
Usage-based: You are billed for API calls and storage.
Exceptions: Watch for "Provisioned" resources or "Static Fees" (e.g., active Cloud Monitoring alerts) which may charge even without active data ingestion.