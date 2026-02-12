# Ther-Assist Project Structure & Dependencies

## Project Overview
Ther-Assist is an AI-powered real-time therapy guidance system that uses Google Cloud services and Gemini 2.5 Flash to analyze therapy sessions and provide evidence-based treatment recommendations. The architecture consists of a React frontend, multiple Python backend microservices, and infrastructure-as-code deployment configuration.

---

## 📁 ROOT LEVEL FILES

### `README.md`
**Overview**: Main project documentation with complete deployment and setup instructions for local development and cloud deployment.
**Purpose**: Serves as the entry point for understanding the project, prerequisites, initial GCP setup, API enablement, Firebase configuration, and step-by-step deployment guides for both backend services and frontend.
**Dependencies**: References files in `/backend`, `/frontend`, `/setup_services`, and `/terraform` directories.

### `LICENSE`
**Overview**: Apache 2.0 license file.
**Purpose**: Legal licensing document for the project.
**Dependencies**: None.

### `.gitignore`
**Overview**: Git configuration to exclude sensitive and unnecessary files from version control.
**Purpose**: Prevents committing environment files (.env), node_modules, __pycache__, build outputs, Firebase configs, and large media files.
**Dependencies**: None (configuration file).

---

## 🎨 FRONTEND DIRECTORY

### `package.json`
**Overview**: Node.js project manifest defining dependencies and build scripts.
**Purpose**: Lists all npm packages (React, Material-UI, Vite, TypeScript) and defines scripts for dev (`npm run dev`) and build (`npm run build`).
**Dependencies**: `vite.config.ts`, `tsconfig.json`, all components in `/components`.

### `vite.config.ts`
**Overview**: Vite bundler configuration.
**Purpose**: Sets up React plugin, defines dev server settings, and build optimization for the frontend application.
**Dependencies**: Uses `index.tsx` as the entry point.

### `tsconfig.json` & `tsconfig.node.json`
**Overview**: TypeScript compiler configurations.
**Purpose**: `tsconfig.json` defines TypeScript rules for the application; `tsconfig.node.json` for Vite and build tools.
**Dependencies**: Used by all TypeScript files in the frontend.

### `index.html`
**Overview**: Main HTML entry point.
**Purpose**: Root HTML file that contains the `<div id="root">` where React mounts the application.
**Dependencies**: Loads `/index.tsx`.

### `index.tsx`
**Overview**: React application entry point.
**Purpose**: Initializes React, mounts the App component, and wraps it with AuthProvider for authentication context.
**Dependencies**: `App.tsx`, `AuthContext.tsx`, CSS styles.

### `firebase.json`
**Overview**: Firebase hosting configuration.
**Purpose**: Defines Firebase hosting settings, redirect rules, and deployment configuration.
**Dependencies**: Used during Firebase deployment; references public directory.

### `.env.example`
**Overview**: Template for environment variables.
**Purpose**: Shows required environment variables (GCP project, API endpoints, auth configuration) that developers need to configure locally.
**Dependencies**: Referenced by `.env.development` and `.env` production files.

### `.env.development`
**Overview**: Local development environment variables.
**Purpose**: Contains local API endpoints (typically http://localhost:PORT) and GCP project configuration for development.
**Dependencies**: Used by Vite in development mode via `import.meta.env`.

### `vite-env.d.ts`
**Overview**: TypeScript type definitions for Vite environment variables.
**Purpose**: Provides type safety for accessing environment variables (VITE_* prefixed) in TypeScript code.
**Dependencies**: Used by all components that access environment variables.

### `nginx.conf`
**Overview**: Nginx web server configuration.
**Purpose**: Configures nginx to serve the React app, handle routing with SPA fallback, and set CORS headers.
**Dependencies**: Used in Docker deployment for production.

### `firebase-config.ts`
**Overview**: Firebase SDK initialization.
**Purpose**: Initializes Firebase app and authentication services (currently disabled for local development).
**Dependencies**: `firebase` npm package; used by `AuthContext.tsx`.

---

## 🔌 FRONTEND - CONTEXTS

### `contexts/AuthContext.tsx`
**Overview**: React Context for authentication state management.
**Purpose**: Manages user authentication state, login/logout functions, and authorization checks. Currently using mock authentication for local development.
**Dependencies**: Used by all pages/components; imports `firebase-config.ts`.

---

## 🪝 FRONTEND - HOOKS

### `hooks/useAudioRecorderWebSocket.ts`
**Overview**: Custom React hook for audio recording via WebSocket.
**Purpose**: Manages WebSocket connection to streaming transcription service, records audio, and handles streaming transcription responses.
**Dependencies**: Connects to `VITE_STREAMING_API` backend service.

### `hooks/useAudioStreamingWebSocket.ts`
**Overview**: Custom React hook for WebSocket audio streaming.
**Purpose**: Handles real-time audio streaming to the backend for transcription with proper event handling and error recovery.
**Dependencies**: Connects to streaming transcription service at port 8082.

### `hooks/useTherapyAnalysis.ts`
**Overview**: Custom React hook for therapy analysis requests.
**Purpose**: Makes HTTP requests to the therapy analysis backend function to get Gemini-based recommendations, evidence, and guidance.
**Dependencies**: Calls `VITE_ANALYSIS_API` Cloud Function; returns formatted recommendations.

---

## 🎭 FRONTEND - COMPONENTS

### `components/App.tsx`
**Overview**: Main application component with routing logic.
**Purpose**: Manages overall navigation state, routing between landing page, patient views, session creation, and therapy analysis screens. Checks if user is authenticated.
**Dependencies**: Uses `AuthContext` for authentication; imports all page components; manages navigation state.

### `components/LandingPage.tsx`
**Overview**: Application landing/home page.
**Purpose**: Displays welcome screen with three main action buttons: View Patients, Schedule, and New Session.
**Dependencies**: Imports and displays other major components; depends on routing logic.

### `components/LoginPage.tsx`
**Overview**: User login interface.
**Purpose**: Handles user authentication, displays login form (currently mocked for development).
**Dependencies**: Uses `AuthContext` for login functions; redirects to landing page on successful auth.

### `components/Patients.tsx`
**Overview**: Lists all patients.
**Purpose**: Displays a list of patient records with options to view details or start a new session.
**Dependencies**: Uses mock patient data from `utils/mockPatients.ts`.

### `components/Patient.tsx`
**Overview**: Individual patient detail view.
**Purpose**: Shows detailed patient information, session history, and allows starting new therapy sessions with that patient.
**Dependencies**: Receives patient ID from navigation; uses `mockPatients` data.

### `components/NewSession.tsx`
**Overview**: Session creation form.
**Purpose**: Allows therapist to create and start a new therapy session, collects initial assessment data.
**Dependencies**: Prepares session context data for analysis; routes to session view.

### `components/NewTherSession.tsx`
**Overview**: Active therapy session screen.
**Purpose**: Main interface during active therapy - displays transcript, recommendations, and real-time analysis. Handles WebSocket connections for transcription and analysis.
**Dependencies**: Uses `useAudioRecorderWebSocket`, `useTherapyAnalysis` hooks; displays `TranscriptDisplay`, `SessionMetrics`, alert panels.

### `components/TranscriptDisplay.tsx`
**Overview**: Real-time transcript viewer.
**Purpose**: Displays speaker-labeled conversation transcript in real-time as audio is transcribed, formats speaker names and timestamps.
**Dependencies**: Receives transcript data from `NewTherSession` component.

### `components/SessionMetrics.tsx`
**Overview**: Session progress and metrics dashboard.
**Purpose**: Displays therapeutic metrics like therapeutic alliance, patient engagement, emotional state, and current treatment pathway.
**Dependencies**: Receives session context data; uses `SessionLineChart` for visualization.

### `components/SessionLineChart.tsx`
**Overview**: Chart component for session metrics.
**Purpose**: Visualizes session metrics over time using Recharts library.
**Dependencies**: Uses recharts npm package; displays data from `SessionMetrics`.

### `components/SessionPhaseIndicator.tsx`
**Overview**: Shows current therapy phase.
**Purpose**: Visual indicator of current therapy phase (e.g., Beginning, Exposure, Consolidation) with description.
**Dependencies**: Receives phase data from session context.

### `components/PathwayIndicator.tsx`
**Overview**: Treatment pathway visualization.
**Purpose**: Shows the therapeutic pathway (e.g., Cognitive Behavioral Therapy) and guidance status.
**Dependencies**: Receives pathway data from session context.

### `components/TherSummary.tsx`
**Overview**: Session summary view.
**Purpose**: Displays comprehensive summary of therapy session after completion including alerts, recommendations, and key moments.
**Dependencies**: Uses `SessionSummaryModal`, receives summary data from session.

### `components/SessionSummaryModal.tsx`
**Overview**: Detailed session summary modal.
**Purpose**: Detailed view of session summary with all recommendations, evidence citations, and therapeutic decisions made.
**Dependencies**: Displays modal with summary data.

### `components/AlertDisplay.tsx`
**Overview**: Real-time alert notification system.
**Purpose**: Displays critical alerts (red), suggestions (yellow), and info alerts (green) with priority sorting and visual feedback.
**Dependencies**: Receives alert data from therapy analysis; uses `alertDeduplication.ts` utility.

### `components/ActionDetailsPanel.tsx`
**Overview**: Panel showing recommended therapeutic actions.
**Purpose**: Displays detailed recommendations with rationale, evidence citations, and clinical guidance.
**Dependencies**: Receives action data from Gemini analysis via backend.

### `components/EvidenceTab.tsx`
**Overview**: Tab showing evidence-based references.
**Purpose**: Displays citations to EBT manuals and research backing the recommendations.
**Dependencies**: Receives evidence data from RAG-enhanced Gemini responses.

### `components/GuidanceTab.tsx`
**Overview**: Specific clinical guidance tab.
**Purpose**: Provides therapist-focused guidance on implementing recommendations during the session.
**Dependencies**: Receives guidance from backend analysis.

### `components/AlternativesTab.tsx`
**Overview**: Alternative treatment approaches tab.
**Purpose**: Shows alternative pathways or techniques if current approach isn't working.
**Dependencies**: Receives alternatives from Gemini analysis.

### `components/PathwayTab.tsx`
**Overview**: Treatment pathway details tab.
**Purpose**: Shows current treatment pathway details and transitions between phases.
**Dependencies**: Displays pathway metadata and recommendations.

### `components/CitationDetailsPanel.tsx`
**Overview**: Detailed citation information.
**Purpose**: Shows detailed information about cited sources (manual pages, research, etc.).
**Dependencies**: Receives citation data; displays modal with details.

### `components/CitationModal.tsx`
**Overview**: Modal for displaying full citations.
**Purpose**: Shows complete citation information including document source, page numbers, and relevant excerpts.
**Dependencies**: Displays as modal overlay.

### `components/RationaleModal.tsx`
**Overview**: Explains rationale for recommendations.
**Purpose**: Displays detailed clinical reasoning for why a specific recommendation is being made.
**Dependencies**: Receives rationale from backend; shows as modal.

### `components/HistoryManager.tsx`
**Overview**: Generic history management component.
**Purpose**: Generic component for managing versioned history of any data type with expand/collapse functionality.
**Dependencies**: Generic React component; used for tracking changes over time.

---

## 📐 FRONTEND - STYLES

### `styles/global.css`
**Overview**: Global CSS styles.
**Purpose**: Defines global styles, theme colors, responsive breakpoints, and utility classes used across the application.
**Dependencies**: Imported by `index.tsx`.

### `styles/theme.ts`
**Overview**: Material-UI theme configuration.
**Purpose**: Defines color palette, typography, component overrides, and Material-UI theme settings.
**Dependencies**: Used by Material-UI components throughout frontend.

---

## 📦 FRONTEND - UTILITIES

### `utils/mockPatients.ts`
**Overview**: Mock patient data for development.
**Purpose**: Provides sample patient records for testing without a backend database.
**Dependencies**: Used by `Patients.tsx` and `Patient.tsx` components.

### `utils/mockTranscript.ts`
**Overview**: Mock therapy session transcript data.
**Purpose**: Provides sample transcript data for testing transcript display and analysis components.
**Dependencies**: Used for testing `TranscriptDisplay` and analysis features.

### `utils/alertDeduplication.ts`
**Overview**: Alert de-duplication logic.
**Purpose**: Prevents duplicate alerts from being displayed, keeps track of previously shown alerts to avoid alert fatigue.
**Dependencies**: Used by `AlertDisplay.tsx`.

### `utils/colorUtils.ts`
**Overview**: Color utility functions.
**Purpose**: Provides functions for color manipulation, theme color selection based on alert severity, and color conversions.
**Dependencies**: Used by alert and visualization components.

### `utils/textRendering.tsx`
**Overview**: Text rendering utilities.
**Purpose**: Provides functions for rendering formatted text, markdown parsing, and special text formatting.
**Dependencies**: Used by components displaying rich text content.

### `utils/timeUtils.ts`
**Overview**: Time and date utility functions.
**Purpose**: Helper functions for formatting timestamps, calculating durations, and time manipulations.
**Dependencies**: Uses `date-fns` npm package; used throughout components for time formatting.

### `utils/storageUtils.ts`
**Overview**: Browser storage utilities.
**Purpose**: Wrapper functions for localStorage to persist session data, preferences, and user state.
**Dependencies**: Uses browser localStorage API.

---

## 🔙 BACKEND - MAIN DIRECTORY

### `backend/therapy-analysis-function/main.py`
**Overview**: Core Gemini-powered therapy analysis Cloud Function.
**Purpose**: Analyzes therapy session transcripts using Gemini 2.5 Flash with RAG integration, generates real-time alerts, recommendations, and session summaries. Implements three main analysis modes: segment analysis, pathway guidance, and session summaries.
**Dependencies**: Connects to Gemini API (`google-genai`), uses RAG datastores for EBT manuals, requires Firebase Admin for auth (currently disabled), uses `constants.py` for prompts.

### `backend/therapy-analysis-function/constants.py`
**Overview**: Configuration and prompt templates.
**Purpose**: Contains therapy phases, analysis prompts, alert templates, and RAG configuration for the therapy analysis function.
**Dependencies**: Imported by `main.py`; defines templates used in analysis.

### `backend/therapy-analysis-function/requirements.txt`
**Overview**: Python dependencies.
**Purpose**: Lists Python packages: functions-framework, Flask, google-genai, firebase-admin, python-dotenv, google-cloud-logging.
**Dependencies**: Used by `pip install` for setting up the service.

### `backend/therapy-analysis-function/.env`
**Overview**: Environment variables for therapy analysis function.
**Purpose**: Contains GCP project ID, allowed domains/emails for authorization.
**Dependencies**: Loaded by `main.py` using python-dotenv.

### `backend/therapy-analysis-function/deploy.sh`
**Overview**: Deployment script.
**Purpose**: Bash script to deploy the therapy analysis function to Google Cloud Functions.
**Dependencies**: Uses `gcloud` CLI commands; uploads function to GCP.

---

### `backend/storage-access-function/main.py`
**Overview**: Cloud Function for accessing stored therapy session data.
**Purpose**: Provides HTTP endpoint to retrieve stored session summaries, transcripts, and historical data from Google Cloud Storage.
**Dependencies**: Uses `firebase-admin` for auth, `google-cloud-storage` for accessing GCS.

### `backend/storage-access-function/requirements.txt`
**Overview**: Python dependencies.
**Purpose**: Lists packages: functions-framework, Flask, firebase-admin, google-cloud-storage, python-dotenv.
**Dependencies**: Used for pip install.

### `backend/storage-access-function/.env`
**Overview**: Environment variables.
**Purpose**: GCP project ID and authorization configuration.
**Dependencies**: Loaded by `main.py`.

### `backend/storage-access-function/deploy.sh`
**Overview**: Deployment script for storage access function.
**Purpose**: Deploys the storage access function to Google Cloud Functions.
**Dependencies**: Uses gcloud CLI.

---

### `backend/streaming-transcription-service/main.py`
**Overview**: FastAPI WebSocket service for real-time audio transcription.
**Purpose**: WebSocket server that receives audio streams from frontend, sends to Google Cloud Speech-to-Text API, and returns transcription with speaker diarization (therapist vs patient distinction).
**Dependencies**: Uses FastAPI, uvicorn, google-cloud-speech library, firebase-admin for auth.

### `backend/streaming-transcription-service/requirements.txt`
**Overview**: Python dependencies.
**Purpose**: Lists packages: fastapi, uvicorn[standard], websockets, google-cloud-speech, google-auth, firebase-admin, python-dotenv.
**Dependencies**: Used for pip install.

### `backend/streaming-transcription-service/.env`
**Overview**: Environment variables.
**Purpose**: GCP project ID, port (8082), authorization config.
**Dependencies**: Loaded by `main.py`.

### `backend/streaming-transcription-service/Dockerfile`
**Overview**: Docker container definition.
**Purpose**: Builds Docker image for the streaming transcription service using Python 3.12, installs dependencies, exposes port 8080.
**Dependencies**: Used by Terraform and Cloud Run for containerized deployment.

### `backend/streaming-transcription-service/deploy.sh`
**Overview**: Deployment script.
**Purpose**: Builds Docker image and deploys to Google Cloud Run.
**Dependencies**: Uses `gcloud` and `docker` commands.

---

## 🧠 SETUP SERVICES - RAG DIRECTORY

### `setup_services/rag/setup_rag_datastore.py`
**Overview**: Creates EBT corpus datastore in Vertex AI Search.
**Purpose**: Uploads therapy manuals (CBT, PE, DBT, etc.) to Google Cloud Storage, creates Vertex AI Search datastore with layout-aware chunking (500 tokens) for evidence-based treatment protocols.
**Dependencies**: Requires `google-auth`, `requests`, authentication via `gcloud auth application-default-login`, GCS bucket, Discovery Engine API enabled.

### `setup_services/rag/setup_transcript_datastore.py`
**Overview**: Creates transcript patterns datastore in Vertex AI Search.
**Purpose**: Uploads clinical therapy transcripts and conversation JSON files, creates datastore with 300-token chunking optimized for dialogue patterns and therapeutic examples.
**Dependencies**: Same as above; requires PDF and JSON files in corpus.

### `setup_services/rag/setup_transcript_datastore_resumable.py`
**Overview**: Resumable version of transcript datastore setup.
**Purpose**: Same as `setup_transcript_datastore.py` but with resumable upload capability for large operations that might timeout.
**Dependencies**: Same dependencies, handles timeouts gracefully.

### `setup_services/rag/analyze_corpus.py`
**Overview**: Analyzes corpus files to determine optimal RAG configuration.
**Purpose**: Examines PDF/DOCX files in corpus directory, recommends optimal chunking strategy and document parsing configuration for Vertex AI Search.
**Dependencies**: Uses `PyPDF2` for PDF analysis, can be run independently.

### `setup_services/rag/requirements.txt`
**Overview**: Python dependencies for RAG setup.
**Purpose**: Lists packages: google-genai, google-auth, google-cloud-storage, requests, PyPDF2, python-dotenv.
**Dependencies**: Used for pip install in RAG setup directory.

### `setup_services/rag/README.md`
**Overview**: RAG setup documentation.
**Purpose**: Detailed instructions for setting up dual RAG datastores, corpus organization, and troubleshooting.
**Dependencies**: Referenced by main README.md.

---

### `setup_services/generate_example_audio/generate_audio.py`
**Overview**: Audio generation utility for testing.
**Purpose**: Generates sample audio files using Gemini API for testing transcription and analysis features without needing real recorded sessions.
**Dependencies**: Uses `google-genai` library.

---

## 🏗️ TERRAFORM - INFRASTRUCTURE AS CODE

### `terraform/main.tf`
**Overview**: Main Terraform configuration for GCP resources.
**Purpose**: Defines all infrastructure: Cloud Functions for therapy-analysis and storage-access, Cloud Run service for streaming transcription, frontend Cloud Run service, service accounts, IAM bindings, Docker image builds, and environment file generation.
**Dependencies**: Uses `variables.tf` for inputs, creates resources that depend on each other (functions before services), generates `.env` files.

### `terraform/variables.tf`
**Overview**: Terraform input variables.
**Purpose**: Defines configurable variables: project_id, region, auth_allowed_domains, auth_allowed_emails with validation and descriptions.
**Dependencies**: Used by `main.tf` and templates.

### `terraform/outputs.tf`
**Overview**: Terraform output values.
**Purpose**: Outputs deployed service URLs (therapy analysis, storage access, streaming, frontend) and WebSocket endpoint for testing and reference.
**Dependencies**: References resources defined in `main.tf`.

### `terraform/terraform.tfvars.example`
**Overview**: Example Terraform variables file.
**Purpose**: Template showing how to configure `terraform.tfvars` with project-specific values.
**Dependencies**: Should be copied to `terraform.tfvars` and customized.

### `terraform/README.md`
**Overview**: Terraform deployment guide.
**Purpose**: Complete instructions for using Terraform to automate deployment, troubleshooting, and infrastructure management.
**Dependencies**: Referenced by main README.md.

### `terraform/templates/frontend.env.tpl`
**Overview**: Frontend environment file template.
**Purpose**: Template for generating `.env` file with API endpoints and configuration, rendered by Terraform.
**Dependencies**: Used by `local_file` resource in `main.tf`.

### `terraform/templates/frontend.env.development.tpl`
**Overview**: Frontend development environment template.
**Purpose**: Template for `.env.development` with localhost endpoints for local testing.
**Dependencies**: Used by `local_file` resource.

### `terraform/templates/backend.env.tpl`
**Overview**: Backend services environment template.
**Purpose**: Template for backend `.env` files with GCP project ID and auth configuration.
**Dependencies**: Used for both therapy-analysis and storage-access functions.

### `terraform/templates/backend-streaming.env.tpl`
**Overview**: Streaming service environment template.
**Purpose**: Template for streaming transcription service `.env` with port configuration.
**Dependencies**: Used for streaming-transcription-service.

---

## 📊 ASSETS DIRECTORY

### `assets/architecture.png`
**Overview**: System architecture diagram.
**Purpose**: Visual representation of system components and data flow between frontend, backend services, and GCP services.
**Dependencies**: Referenced in main README.md.

---

## 🔄 DEPENDENCY GRAPH

### Frontend → Backend
- `NewTherSession.tsx` → `useTherapyAnalysis.ts` → `VITE_ANALYSIS_API` (therapy-analysis-function)
- `NewTherSession.tsx` → `useAudioRecorderWebSocket.ts` → WebSocket (streaming-transcription-service)
- `Patient.tsx` → Could call storage-access-function for historical data

### Backend Internal Dependencies
- `therapy-analysis-function/main.py` requires:
  - `constants.py` (templates and config)
  - `.env` (environment variables)
  - RAG datastores (ebt-corpus, transcript-patterns)
  - Firebase Admin SDK (for auth - currently disabled)
  - Google GenAI SDK (Gemini API)

### Infrastructure Dependencies
- `main.tf` depends on:
  - `variables.tf` (inputs)
  - `templates/*` (environment file templates)
  - Backend source code (zipped and uploaded to GCS)
  - Frontend source code (built into Docker image)
  
### Cross-Cutting Dependencies
- All services use `.env` files generated by Terraform or manually created
- All services require Google Cloud authentication (`GOOGLE_APPLICATION_CREDENTIALS`)
- Frontend components depend on `AuthContext.tsx` for authentication state
- Components depend on utility functions in `utils/` directory

---

## 🚀 DEPLOYMENT FLOW

1. **Setup Phase** (One-time)
   - Run RAG setup scripts to create datastores
   - Configure Firebase authentication
   - Create `.env` files or use Terraform

2. **Local Development**
   - Start each backend service in separate terminals
   - Run frontend with `npm run dev`
   - Services communicate via localhost:PORT

3. **Cloud Deployment (Terraform)**
   - `terraform init` → Initializes backend and providers
   - `terraform plan` → Shows resource changes
   - `terraform apply` → Creates all GCP resources
   - Generates production `.env` files automatically
   - Deploys Cloud Functions and Cloud Run services

4. **Runtime**
   - Frontend makes requests to backend APIs
   - Backend analyzes with Gemini + RAG
   - Results streamed back to frontend in real-time

---

## 📝 KEY FILE RELATIONSHIPS

```
README.md (entry point)
├── References all setup instructions
├── Links to terraform/README.md for deployment
├── Links to setup_services/rag/README.md for RAG setup
└── Points to individual service setup for local dev

frontend/ (React Application)
├── index.tsx → App.tsx (routing)
├── App.tsx → All page components
├── Components communicate via props and React Context
├── Uses environment variables from .env files
└── Calls backend APIs via hooks (useTherapyAnalysis, useAudioRecorderWebSocket)

backend/therapy-analysis-function/
├── main.py (entry point)
├── constants.py (configuration)
├── Requires RAG datastores (set up by setup_rag_datastore.py)
└── Returns JSON to frontend

terraform/
├── main.tf (infrastructure)
├── variables.tf (inputs)
├── templates/ (generates .env files)
└── Orchestrates deployment and creates all resources
```

---

## 🔐 Security & Authentication Flow

1. **Frontend**: User logs in via LoginPage.tsx (currently mocked)
2. **Firebase Auth**: AuthContext manages authentication (currently disabled for local dev)
3. **Backend**: Receives requests with Firebase ID token in Authorization header
4. **Token Verification**: Backend validates token against Firebase (currently disabled for local dev)
5. **Authorization**: Backend checks email against allowlist from environment variables

---

## 🌐 API Communication

### Frontend → Backend APIs

**Therapy Analysis** (HTTP POST)
- Endpoint: `VITE_ANALYSIS_API`
- Body: `{action, transcript_segment, session_context, session_duration_minutes, is_realtime}`
- Response: Recommendations, alerts, evidence citations

**Streaming Transcription** (WebSocket)
- Endpoint: `VITE_STREAMING_API/ws/transcribe`
- Protocol: WebSocket with binary audio frames
- Response: Real-time transcription updates

**Storage Access** (HTTP GET)
- Endpoint: `VITE_STORAGE_ACCESS_URL`
- Purpose: Retrieve stored session summaries and historical data

---

## 📚 Technology Stack Summary

**Frontend**: React 18, TypeScript, Vite, Material-UI, Recharts, Firebase SDK
**Backend**: Python 3.12/3.13, FastAPI, Flask, google-genai, google-cloud-speech, functions-framework
**Infrastructure**: Google Cloud Platform (Cloud Functions, Cloud Run, Cloud Storage, Vertex AI Search), Terraform
**Authentication**: Firebase Authentication (configurable, currently mocked for dev)
**AI/ML**: Google Gemini 2.5 Flash, Vertex AI Search (RAG)
**DevOps**: Docker, Terraform, gcloud CLI

---

## ✅ File Checklist for Complete Setup

- [x] Backend services have requirements.txt
- [x] .env templates in terraform/templates/
- [x] Frontend has package.json and vite.config.ts
- [x] Authentication context configured
- [x] RAG setup scripts available
- [x] Deployment scripts for all services
- [x] Terraform IaC complete
- [x] Documentation in README files
