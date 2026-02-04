# Ther-Assist

'Ther-Assist' is a sophisticated real-time guidance tool for psychotherapists. It uses a multimodal, generative AI architecture to provide evidence-based feedback during therapy sessions.

## Project Overview

'Ther-Assist' aims to assist psychotherapists by providing real-time, evidence-based guidance during therapy sessions. The application transcribes the session in real-time and uses a generative AI model to analyze the conversation, offering clinical insights and suggestions. This helps therapists to stay aligned with evidence-based practices and improves the quality of care.

## Architecture

The application is composed of a frontend application and a set of backend microservices.

### Backend Architecture

The backend is built with serverless microservices on Google Cloud Platform:

-   **`streaming-transcription-service`**: A FastAPI WebSocket service on Cloud Run that uses Google Speech-to-Text v2 to provide low-latency, real-time transcription.
-   **`therapy-analysis-function`**: The core AI brain. A Google Cloud Function that takes transcript segments and uses the Gemini model to generate clinical insights, grounded by multiple RAG datastores.
-   **RAG Setup Scripts (`setup_services/rag/`)**: A collection of Python scripts for creating and populating the Vertex AI Search datastores.

### Frontend Architecture

The frontend is a React+Vite application using Material-UI for components. It communicates with the backend via WebSockets and authenticated HTTPS calls.

## Agent Instructions & Development Guidelines

The following are standing instructions for the Gemini agent working on this project. Please adhere to these rules in all your actions to ensure code quality, maintainability, and safety.

### 1. Code Modification Integrity

-   **Principle of No Destruction:** Never delete or replace functional code with placeholder comments (`# ...`).
-   **Read-Modify-Write Cycle:** For any file modification, always read the entire file, perform the specific changes in memory, and write the complete, functional file back.
-   **Targeted Changes:** When asked to refactor or modify code, apply changes only to the relevant sections. Do not summarize or omit code that is intended to remain unchanged.

### 2. Configuration Management

-   **Single Source of Truth:** All project configuration (e.g., GCP settings, datastore IDs, metadata schema) must be stored in the root `config.yml` file.
-   **No Hardcoded Constants:** Do not hardcode configuration values like datastore IDs, locations, or bucket names directly in Python scripts.
-   **Load from Config:** Scripts must load their configuration from the central `config.yml`. The `constants.py` files should act as loaders and validators for this configuration, not as places to define new, independent constants.

### 3. Software Design Principles

-   **Dependency Injection:** Pass configuration and dependencies (like API clients or datastore IDs) as explicit arguments to functions. Avoid using global variables within functions to improve testability and clarity.
-   **Code Consolidation:** Duplicated code should be refactored into shared utility functions. For this project, `setup_services/rag/utils.py` should be used for shared setup script logic.
-   **Single Responsibility:** Scripts should have a clear, single purpose (e.g., `new_setup.py` for full end-to-end setup, `recreate_datastore_from_gcs.py` for rebuilding from existing data).

### 4. Technical Preferences

-   **PDF Processing:** When extracting text from PDF documents, prefer using the `PyMuPDF` library over `PyPDF2` due to its robustness and better text extraction capabilities.
