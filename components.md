# Ther-Assist Interaction Sequence

This document outlines the component interactions for the Ther-Assist application, including references to the code responsible for each step.

```mermaid
sequenceDiagram

    actor Patient as Patient
    actor Therapist as Therapist
    participant Frontend_UI as Session UI
    participant FirebaseAuth as Firebase Auth
    participant Frontend_Audio as Audio/WebSocket Hook
    participant Frontend_Analysis as Analysis Hook
    participant TranscriptionService as Streaming Transcription Service
    participant AnalysisFunction as Therapy Analysis Function
    participant StorageProxy as Storage Access Function
    participant SpeechToText as Google Speech-to-Text
    participant Gemini as Google Gemini 2.5 Flash
    participant RAG as Vertex AI Search
    participant GCS as Google Cloud Storage
    participant SetupScripts as RAG Setup Scripts
    participant Corpus as Local Corpus Files
    actor Dev as Developer
    
    rect rgb(250, 240, 240)
        note over Patient, Therapist: Therapy Session
    
    rect rgb(240, 240, 240)
        note over Dev, Rag: Setup Phase (Offline)
        Dev->>SetupScripts: 1. Executes RAG setup script
        SetupScripts->>Corpus: 2. Reads local documents
        Corpus-->>SetupScripts: 3. Returns file content
        SetupScripts->>GCS: 4. Uploads documents to Cloud Storage
        SetupScripts->>RAG: 5. Indexes documents in Vertex AI Search
    end

    rect rgb(240, 240, 240)
        note over User, Frontend_UI: Real-time Therapy Session
        User->>Frontend_UI: 6. Logs in and starts session
        Frontend_UI->>FirebaseAuth: 7. Authenticates user with Firebase
        
        Patient->>Frontend_Audio: 8. Speaks (provides audio)
        Frontend_Audio->>TranscriptionService: 9. Streams audio via WebSocket
        
        TranscriptionService->>SpeechToText: 10. Forwards audio to Speech-to-Text API
        SpeechToText-->>TranscriptionService: 11. Returns real-time transcript
        TranscriptionService-->>Frontend_UI: 12. Streams transcript to UI
        
        Frontend_UI->>Frontend_Analysis: 13. Sends transcript for analysis
        Frontend_Analysis->>AnalysisFunction: 14. Sends transcript context via HTTPS
        
        AnalysisFunction->>FirebaseAuth: 15. Verifies user auth token
        AnalysisFunction->>RAG: 16. Queries RAG datastores
        RAG-->>AnalysisFunction: 17. Returns relevant documents
        AnalysisFunction->>Gemini: 18. Sends augmented prompt to Gemini
        Gemini-->>AnalysisFunction: 19. Returns AI-generated guidance
        AnalysisFunction-->>Frontend_UI: 20. Returns analysis to UI
        
        User->>Frontend_UI: 21. Clicks on a citation
        Frontend_UI->>StorageProxy: 22. Requests cited document
        StorageProxy->>GCS: 23. Fetches document from Cloud Storage
        GCS-->>StorageProxy: 24. Returns document
        StorageProxy-->>Frontend_UI: 25. Delivers document for display
    end
```

### Interaction Details

Here is an elaboration on each step in the sequence diagram:

1.  **Executes RAG setup script**: A developer runs the Python script to build the knowledge base for the RAG system.
    *   **File**: `setup_services/rag/setup_rag_datastore.py`
    *   **Action**: A developer executes the script from the command line (e.g., `python setup_rag_datastore.py`).

2.  **Reads local documents**: The script accesses the local filesystem to read the corpus of clinical manuals and transcripts.
    *   **File**: `setup_services/rag/setup_rag_datastore.py`
    *   **Action**: The script iterates through files in the `setup_services/rag/corpus/` directory.

3.  **Returns file content**: The operating system provides the file content back to the Python script.

4.  **Uploads documents to Cloud Storage**: The script uses the Google Cloud client library to upload the corpus files to a private GCS bucket.
    *   **File**: `setup_services/rag/setup_rag_datastore.py`
    *   **Action**: The code uses `storage.Client()` and methods like `bucket.blob(destination_blob_name).upload_from_filename(source_file_name)`.

5.  **Indexes documents in Vertex AI Search**: The script calls the Vertex AI Search API to index the documents previously uploaded to GCS, making them searchable.
    *   **File**: `setup_services/rag/setup_rag_datastore.py`
    *   **Action**: Uses the `discoveryengine_v1.DocumentServiceClient` to import documents into the datastore.

6.  **Logs in and starts session**: The psychotherapist authenticates through the UI.
    *   **Files**: `frontend/components/LoginPage.tsx`, `frontend/contexts/AuthContext.tsx`
    *   **Action**: The UI calls a login function which uses the Firebase SDK for authentication.

7.  **Authenticates user with Firebase**: The frontend communicates with Firebase to verify the user's credentials.
    *   **File**: `frontend/firebase-config.ts`
    *   **Action**: The app uses `getAuth()` and associated Firebase functions to manage user state.

8.  **Speaks (provides audio)**: The patient's (and therapist's) voice is captured by the device's microphone.
    *   **File**: `frontend/hooks/useAudioRecorderWebSocket.ts`
    *   **Action**: This hook calls `navigator.mediaDevices.getUserMedia()` to access the microphone and uses an audio encoder to process the stream.

9.  **Streams audio via WebSocket**: The frontend hook sends the encoded audio chunks to the backend transcription service.
    *   **File**: `frontend/hooks/useAudioRecorderWebSocket.ts`
    *   **Action**: A `WebSocket` connection is established, and audio data is sent using `socket.send()`.

10. **Forwards audio to Speech-to-Text API**: The backend service receives the audio from the WebSocket and streams it to the Google Speech-to-Text API.
    *   **File**: `backend/streaming-transcription-service/main.py`
    *   **Action**: The Python service uses the `google.cloud.speech_v2.SpeechClient` and its `streaming_recognize` method.

11. **Returns real-time transcript**: The Speech-to-Text API sends back transcript fragments as they are recognized.
    *   **File**: `backend/streaming-transcription-service/main.py`
    *   **Action**: The service receives responses from the Google API stream.

12. **Streams transcript to UI**: The backend service sends the finalized transcript segments back to the frontend over the WebSocket.
    *   **File**: `backend/streaming-transcription-service/main.py`
    *   **Action**: The service sends messages back to the client using the WebSocket connection (`websocket.send_text()`).

13. **Sends transcript for analysis**: The frontend UI, likely via a component like `TranscriptDisplay.tsx`, triggers an analysis when enough new transcript text has been accumulated.
    *   **File**: `frontend/hooks/useTherapyAnalysis.ts`
    *   **Action**: The hook batches the transcript text and prepares it for sending.

14. **Sends transcript context via HTTPS**: The analysis hook sends the accumulated transcript to the core analysis cloud function.
    *   **File**: `frontend/hooks/useTherapyAnalysis.ts`
    *   **Action**: An authenticated `fetch` or `axios` POST request is made to the `therapy-analysis-function` endpoint.

15. **Verifies user auth token**: The cloud function first validates the Firebase auth token included in the request headers to secure the endpoint.
    *   **File**: `backend/therapy-analysis-function/main.py`
    *   **Action**: The function uses `firebase_admin.auth.verify_id_token()` to check the user's identity.

16. **Queries RAG datastores**: The function queries the pre-indexed clinical manuals and transcript patterns in Vertex AI Search.
    *   **File**: `backend/therapy-analysis-function/main.py`
    *   **Action**: Uses the `discoveryengine_v1.SearchServiceClient` to search the datastores.

17. **Returns relevant documents**: Vertex AI Search returns the most relevant document chunks based on the query.

18. **Sends augmented prompt to Gemini**: The function combines the original transcript with the retrieved RAG documents into a detailed prompt for the Gemini model.
    *   **File**: `backend/therapy-analysis-function/main.py`
    *   **Action**: Uses the `vertexai.generative_models.GenerativeModel` client and its `generate_content()` method.

19. **Returns AI-generated guidance**: The Gemini model returns a structured JSON object containing clinical insights, alerts, and suggestions.

20. **Returns analysis to UI**: The cloud function sends the Gemini model's JSON response back to the frontend.
    *   **File**: `frontend/hooks/useTherapyAnalysis.ts`
    *   **Action**: The hook receives the JSON response from the `fetch` call and updates the application's state.

21. **Clicks on a citation**: The therapist clicks a link in the UI to view the source of a piece of evidence.
    *   **Files**: `frontend/components/EvidenceTab.tsx`, `frontend/components/CitationModal.tsx`
    *   **Action**: An `onClick` handler triggers a function to fetch the document.

22. **Requests cited document**: The frontend calls the secure proxy function to get the document.
    *   **File**: `frontend/utils/storageUtils.ts`
    *   **Action**: A helper function makes an authenticated `fetch` call to the `storage-access-function` endpoint.

23. **Fetches document from Cloud Storage**: The proxy function uses the GCS client library to access the private document.
    *   **File**: `backend/storage-access-function/main.py`
    *   **Action**: The function generates a signed URL or directly streams the file from the GCS bucket.

24. **Returns document**: GCS provides the file data to the cloud function.

25. **Delivers document for display**: The proxy function returns the document data or a signed URL to the frontend, which is then displayed in a modal or new tab.
    *   **File**: `frontend/components/CitationModal.tsx`
    *   **Action**: The component renders the PDF, for example, using a library like `react-pdf`.
