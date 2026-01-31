# Ther-Assist Local Development Environment Setup Guide

Complete step-by-step guide to set up and run the Ther-Assist application locally on Windows. This guide covers backend services, frontend, authentication, and testing.

---

## 📋 PREREQUISITES

### System Requirements
- **OS**: Windows 10+ with PowerShell 5.1+
- **Free Disk Space**: ~2GB minimum
- **Internet**: Required for initial setup and GCP services

### Required Software
1. **Node.js & npm** (v18+)
   - Download: https://nodejs.org/
   - Verify: Open PowerShell, run `node --version` and `npm --version`

2. **Python** (v3.13+)
   - Download: https://www.python.org/
   - Verify: Open PowerShell, run `python --version`
   - Ensure Python is added to PATH

3. **Git**
   - Download: https://git-scm.com/
   - For Windows commands, use **Git Bash** (included with Git installation)

4. **Google Cloud SDK** (gcloud CLI)
   - Download: https://cloud.google.com/sdk/docs/install-sdk
   - Initialize: Run `gcloud init` after installation

### GCP Project Setup
- You need access to Google Cloud Project: **brk-prj-salvador-dura-bern-sbx**
- Have your GCP credentials file ready (obtained via `gcloud auth application-default-login`)
- Required APIs enabled:
  - ✅ Cloud Functions API
  - ✅ Cloud Run API
  - ✅ Cloud Speech-to-Text API
  - ✅ Cloud Storage API
  - ✅ Vertex AI Search / Discovery Engine API (for RAG)

---

## 🔑 STEP 1: AUTHENTICATION & GOOGLE CLOUD SETUP

### 1.1 Authenticate with Google Cloud

⚠️ **CRITICAL**: You MUST use the SUNY-specific login link. Do NOT use console.cloud.google.com directly.

**Option 1: Manual Authentication (Recommended)**

If `gcloud auth login` opens the wrong page, use this manual approach:

1. Open Microsoft Edge or Firefox (NOT Chrome, as it may default to wrong account)
2. Manually navigate to: https://auth.cloud.google/signin/locations/global/workforcePools/suny-wfif-pool-glb/providers/suny-wfif-pvdr-glb?continueUrl=https%3A//console.cloud.google/
3. Sign in with: **mohsin.sardar@downstate.edu** (NOT mohsinsub7@gmail.com)
4. Verify your Global ID: **2009332485**
5. Complete the authorization

**Option 2: Configure gcloud for SUNY Workforce Pool**

To make `gcloud auth login` use the SUNY link automatically:

```bash
gcloud config set auth/workforce_audience_url https://iam.googleapis.com/locations/global/workforcePools/suny-wfif-pool-glb/providers/suny-wfif-pvdr-glb
```

Then use:
```bash
gcloud auth application-default login --workforce
```

**What this does**: Creates authentication credentials at:
```
C:\Users\mohsi\AppData\Roaming\gcloud\application_default_credentials.json
```

### 1.2 Verify Project Configuration
```bash
gcloud config set project brk-prj-salvador-dura-bern-sbx
gcloud config get-value project
```
Should output: `brk-prj-salvador-dura-bern-sbx`

### 1.3 Set Default Region
```bash
gcloud config set compute/region us-central1
```

---

## 📁 STEP 2: CLONE & ORGANIZE PROJECT

### 2.1 Clone Repository
```bash
cd "c:\Users\mohsi\OneDrive\Documents\Personal Projects\AI Mental Health Model\GMAIC Model"
git clone <repository-url> gcaimh-ther-assist-main
cd gcaimh-ther-assist-main
```
Or if already cloned, navigate to the directory:
```bash
cd "c:\Users\mohsi\OneDrive\Documents\Personal Projects\AI Mental Health Model\GMAIC Model\gcaimh-ther-assist-main"
```

### 2.2 Verify Project Structure
```bash
ls -la
```
Should show: `LICENSE`, `README.md`, `backend/`, `frontend/`, `setup_services/`, `terraform/`

---

## 🐍 STEP 3: SETUP BACKEND SERVICES

You'll be running 3 backend services. Open **3 separate PowerShell/Git Bash terminals** (one for each service).

### 3.1 Service 1: Therapy Analysis Function (Port 8080)

#### Terminal 1 - Navigate to Service
```bash
cd backend/therapy-analysis-function
```

#### Create Virtual Environment
```bash
python -m venv venv
```

#### Activate Virtual Environment
**On Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**On Git Bash:**
```bash
source venv/Scripts/activate
```

**Expected Output**: Your prompt should show `(venv)` at the beginning.

#### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected Output**: Successfully installed functions-framework==3.8.0, Flask, google-genai, firebase-admin, python-dotenv, google-cloud-logging

#### Create `.env` File
Create a new file: `backend/therapy-analysis-function/.env`
```
GOOGLE_CLOUD_PROJECT=brk-prj-salvador-dura-bern-sbx
AUTH_ALLOWED_DOMAINS=downstate.edu
AUTH_ALLOWED_EMAILS=mohsin.sardar@downstate.edu
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\mohsi\AppData\Roaming\gcloud\application_default_credentials.json
```

#### Start the Service
```bash
functions-framework --target=therapy_analysis --debug --port=8080
```

**Expected Output**:
```
WARNING:root:No port specified, defaulting to 8080
WARNING:root:Functions Framework initialized.
WARNING:werkzeug._internal._address_info:WARNING:werkzeug._internal._address_info:  * Address reachable at http://127.0.0.1:8080
Serving Flask app 'therapy_analysis'
```

**Keep this terminal running.**

---

### 3.2 Service 2: Storage Access Function (Port 8081)

#### Terminal 2 - Navigate to Service
```bash
cd backend/storage-access-function
```

#### Create Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # On PowerShell
# or: source venv/Scripts/activate  # On Git Bash
```

#### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Create `.env` File
Create: `backend/storage-access-function/.env`
```
GOOGLE_CLOUD_PROJECT=brk-prj-salvador-dura-bern-sbx
AUTH_ALLOWED_DOMAINS=downstate.edu
AUTH_ALLOWED_EMAILS=mohsin.sardar@downstate.edu
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\mohsi\AppData\Roaming\gcloud\application_default_credentials.json
```

#### Start the Service
```bash
functions-framework --target=storage_access --debug --port=8081
```

**Expected Output**: Similar to therapy-analysis, but on port 8081.

**Keep this terminal running.**

---

### 3.3 Service 3: Streaming Transcription Service (Port 8082)

#### Terminal 3 - Navigate to Service
```bash
cd backend/streaming-transcription-service
```

#### Create Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # On PowerShell
# or: source venv/Scripts/activate  # On Git Bash
```

#### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Create `.env` File
Create: `backend/streaming-transcription-service/.env`
```
GOOGLE_CLOUD_PROJECT=brk-prj-salvador-dura-bern-sbx
AUTH_ALLOWED_DOMAINS=downstate.edu
AUTH_ALLOWED_EMAILS=mohsin.sardar@downstate.edu
PORT=8082
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\mohsi\AppData\Roaming\gcloud\application_default_credentials.json
```

#### Start the Service
```bash
uvicorn main:app --host 0.0.0.0 --port 8082 --reload
```

**Expected Output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8082
```

**Keep this terminal running.**

---

## ✅ STEP 4: VERIFY BACKEND SERVICES

Open a **4th Terminal** and test each service:

### Test Therapy Analysis Service
```bash
curl -X POST http://localhost:8080/therapy_analysis -H "Content-Type: application/json" -d '{}'
```
**Expected Response**: HTTP 200 (even if returns error about missing transcript, connection is working)

### Test Storage Access Service
```bash
curl -X GET http://localhost:8081/storage_access
```
**Expected Response**: HTTP response (may be 400 or 200 depending on parameters)

### Test Streaming Transcription Service
```bash
curl http://localhost:8082/health
```
**Expected Response**: Service responding on port 8082

---

## 🎨 STEP 5: SETUP FRONTEND

### 5.1 Navigate to Frontend
Open a **5th Terminal**:
```bash
cd frontend
```

### 5.2 Create Development Environment File
Create file: `frontend/.env.development`
```
VITE_GCP_PROJECT_ID=brk-prj-salvador-dura-bern-sbx
VITE_ANALYSIS_API=http://localhost:8080/therapy_analysis
VITE_STORAGE_ACCESS_URL=http://localhost:8081/storage_access
VITE_STREAMING_API=ws://localhost:8082
```

### 5.3 Install Dependencies
```bash
npm install
```

**Expected Output**: npm packages installed, takes 2-3 minutes

### 5.4 Start Development Server
```bash
npm run dev
```

**Expected Output**:
```
VITE v5.4.0  ready in XXX ms

➜  Local:   http://localhost:5173/
➜  press h + enter to show help
```

---

## 🔐 STEP 6: AUTHENTICATION SETUP FOR LOCAL DEVELOPMENT

### Current Status
For **local development**, authentication is **DISABLED** using mock authentication:
- No Firebase credentials required
- Any username/password works
- You'll be logged in as a mock user: **local-dev-user**

### 6.1 Access the Application
1. Open browser: http://localhost:5173
2. You should see the **Login Page**
3. Enter any username and password (e.g., username: `test`, password: `test`)
4. Click **Login**
5. You should be redirected to the **Landing Page**

### Files Modified for Mock Auth
- `frontend/firebase-config.ts` → Firebase initialization disabled
- `frontend/contexts/AuthContext.tsx` → Uses mock user instead of Firebase
- `backend/therapy-analysis-function/main.py` → Authentication checks disabled

### ⚠️ IMPORTANT FOR PRODUCTION
Before deploying to production, you **MUST**:
1. Create Firebase project and get credentials
2. Update `firebase-config.ts` with real Firebase config
3. Restore authentication logic in `AuthContext.tsx`
4. Re-enable authentication checks in backend services

---

## 🧠 STEP 7: SETUP RAG (OPTIONAL - For Full Gemini+Evidence Features)

**Status**: RAG setup requires GCP permissions approval. Skip this if not needed for initial testing.

### 7.1 Request Discovery Engine API Access

⚠️ **IMPORTANT**: Use the SUNY-specific login link, NOT console.cloud.google.com

1. Go to GCP Console: https://auth.cloud.google/signin/locations/global/workforcePools/suny-wfif-pool-glb/providers/suny-wfif-pvdr-glb?continueUrl=https%3A//console.cloud.google/
2. Sign in with mohsin.sardar@downstate.edu
3. Navigate to **APIs & Services** → **Library**
3. Search for **"Vertex AI Search for Retail"** or **"Enterprise Search"**
4. Click **Enable**
5. If you see a permissions error, request access from your GCP org admin

### 7.2 Prepare Corpus Files
```bash
cd setup_services/rag
ls corpus/  # Verify EBT manuals are present
ls transcripts/  # Verify therapy transcripts are present
```

### 7.3 Create EBT Corpus Datastore
```bash
python setup_rag_datastore.py
```

**Expected Output**: Datastore `ebt-corpus` created in us-central1

### 7.4 Create Transcript Datastore
```bash
python setup_transcript_datastore.py
```

**Expected Output**: Datastore `transcript-patterns` created in us-central1

### 7.5 Verify in Backend
Backend will automatically use these datastores when making Gemini requests.

---

## 🚀 STEP 8: LAUNCH COMPLETE APPLICATION

### Summary of Running Services

You should have 5 terminals open:

| Terminal | Service | Port | Command |
|----------|---------|------|---------|
| 1 | Therapy Analysis | 8080 | `functions-framework --target=therapy_analysis --port=8080` |
| 2 | Storage Access | 8081 | `functions-framework --target=storage_access --port=8081` |
| 3 | Streaming Transcription | 8082 | `uvicorn main:app --host 0.0.0.0 --port 8082` |
| 4 | Test Terminal | - | For testing API calls |
| 5 | Frontend Dev Server | 5173 | `npm run dev` |

### Access the Application
1. **Frontend**: http://localhost:5173
2. **Therapy Analysis API**: http://localhost:8080
3. **Storage Access API**: http://localhost:8081
4. **Streaming Transcription**: ws://localhost:8082

---

## 🧪 STEP 9: TEST THE APPLICATION

### 9.1 Login Test
1. Open http://localhost:5173
2. Enter credentials: username=`test`, password=`test`
3. Should redirect to Landing Page

### 9.2 Backend Connectivity Test
```bash
# Test therapy analysis
$headers = @{"Content-Type" = "application/json"}
$body = @{
    action = "segment_analysis"
    transcript_segment = "Patient: I've been having panic attacks"
    session_context = @{therapy_type = "CBT"}
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8080/therapy_analysis" `
    -Method POST -Headers $headers -Body $body
```

**Expected Response**: JSON with Gemini analysis or error (both indicate service is working)

### 9.3 View Patient Records
1. Click "View Patients" on Landing Page
2. Should display list of mock patients

### 9.4 Start New Session
1. Click "New Session"
2. Should show session creation form
3. Verify you can progress through form

---

## 🐛 TROUBLESHOOTING

### Issue: "ModuleNotFoundError: No module named 'google'"
**Solution**: Virtual environment not activated
```bash
.\venv\Scripts\Activate.ps1  # PowerShell
source venv/Scripts/activate  # Git Bash
```

### Issue: "Address already in use" on port 8080/8081/8082
**Solution**: Another service is already running on that port
```bash
# Find and kill process using port 8080
Get-Process | Where-Object {$_.Name -eq "python"} | Stop-Process -Force
# Or manually close the other terminal
```

### Issue: "GOOGLE_APPLICATION_CREDENTIALS" not found
**Solution**: Run authentication again
```bash
gcloud auth application-default-login
```

### Issue: Frontend shows blank page or 404
**Solution**: 
1. Clear browser cache (Ctrl+Shift+Delete)
2. Check console for errors (F12 → Console tab)
3. Verify Vite dev server is running on port 5173

### Issue: Backend responds but returns "no valid JSON found"
**Solution**: This is normal if RAG datastores not set up. Core Gemini is still working.

### Issue: "Discovery Engine API not enabled"
**Solution**: Request API access from GCP org admin, or skip RAG setup for now

### Issue: Python 3.13 compatibility errors
**Solution**: Ensure functions-framework 3.8.0+
```bash
pip show functions-framework
pip install --upgrade functions-framework==3.9.0
```

### Issue: "npm: command not found" on Git Bash
**Solution**: Node.js not in PATH. Reinstall Node.js and restart terminal.

---

## 📊 DEVELOPMENT WORKFLOW

### Daily Startup Sequence
1. **Terminal 1**: `cd backend/therapy-analysis-function && .\venv\Scripts\Activate.ps1 && functions-framework --target=therapy_analysis --port=8080`
2. **Terminal 2**: `cd backend/storage-access-function && .\venv\Scripts\Activate.ps1 && functions-framework --target=storage_access --port=8081`
3. **Terminal 3**: `cd backend/streaming-transcription-service && .\venv\Scripts\Activate.ps1 && uvicorn main:app --host 0.0.0.0 --port 8082 --reload`
4. **Terminal 5**: `cd frontend && npm run dev`
5. Open browser to http://localhost:5173

### Making Code Changes
- **Frontend changes**: Auto-reload in browser (Vite HMR)
- **Backend changes**: Restart the specific backend service
- **Backend Python files**: Use `--reload` flag in services (already set)

### Viewing Logs
- **Frontend errors**: Browser console (F12)
- **Backend errors**: Terminal output (watch the service terminal)
- **GCP errors**: GCP Cloud Logging console

---

## 🔄 ENVIRONMENT VARIABLES REFERENCE

### Frontend (.env.development)
```
VITE_GCP_PROJECT_ID=brk-prj-salvador-dura-bern-sbx
VITE_ANALYSIS_API=http://localhost:8080/therapy_analysis
VITE_STORAGE_ACCESS_URL=http://localhost:8081/storage_access
VITE_STREAMING_API=ws://localhost:8082
```

### Backend Services (.env)
```
GOOGLE_CLOUD_PROJECT=brk-prj-salvador-dura-bern-sbx
AUTH_ALLOWED_DOMAINS=downstate.edu
AUTH_ALLOWED_EMAILS=mohsin.sardar@downstate.edu
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\mohsi\AppData\Roaming\gcloud\application_default_credentials.json
```

### Streaming Service Additional (.env)
```
PORT=8082
```

---

## ✅ FINAL CHECKLIST

Before starting development, verify:
- [ ] Node.js installed: `node --version`
- [ ] Python 3.13+ installed: `python --version`
- [ ] Git installed: `git --version`
- [ ] gcloud CLI installed: `gcloud --version`
- [ ] Authenticated to GCP: `gcloud auth application-default-login`
- [ ] GCP project set: `gcloud config get-value project`
- [ ] All 3 backend services running
- [ ] Frontend dev server running
- [ ] Can access http://localhost:5173
- [ ] Can login with mock credentials
- [ ] Backend APIs respond to test requests

---

## 📞 QUICK REFERENCE

| Task | Command | Location |
|------|---------|----------|
| Activate venv (PowerShell) | `.\venv\Scripts\Activate.ps1` | Backend dir |
| Start therapy analysis | `functions-framework --target=therapy_analysis --port=8080` | therapy-analysis-function |
| Start storage access | `functions-framework --target=storage_access --port=8081` | storage-access-function |
| Start streaming | `uvicorn main:app --host 0.0.0.0 --port 8082` | streaming-transcription-service |
| Start frontend | `npm run dev` | frontend |
| Authenticate with GCP | `gcloud auth application-default-login` | Any |
| Set GCP project | `gcloud config set project brk-prj-salvador-dura-bern-sbx` | Any |
| View frontend | http://localhost:5173 | Browser |
| Test backend | `curl http://localhost:8080/therapy_analysis` | PowerShell/Bash |

---

## 📚 NEXT STEPS

After successful local setup:
1. Explore the application UI and understand the workflow
2. Try creating a new therapy session
3. Review the [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) to understand code organization
4. Read backend service documentation in `backend/*/README.md`
5. Set up RAG datastores once permissions approved
6. Review Gemini prompts in `backend/therapy-analysis-function/constants.py`
7. Configure real Firebase for production deployment
8. Use Terraform for cloud deployment when ready

---

**Last Updated**: January 14, 2026  
**For Issues**: Check TROUBLESHOOTING section or review console output
