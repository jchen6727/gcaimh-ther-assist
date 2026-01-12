# Ther-Assist Interaction Sequence

This diagram shows the high-level interaction sequence for the Ther-Assist application, from the offline setup phase to the real-time analysis during a therapy session.

```mermaid
sequenceDiagram
    actor User as Psychotherapist

    participant Frontend_UI as Session UI
    participant Frontend_Audio as Audio/WebSocket Hook
    participant Frontend_Analysis as Analysis Hook
    participant TranscriptionService as Streaming Transcription Service (FastAPI)
    participant AnalysisFunction as Therapy Analysis Function (Cloud Function)
    participant StorageProxy as Storage Access Function (Cloud Function)
    participant SpeechToText as Google Speech-to-Text
    participant Gemini as Google Gemini 1.5 Flash
    participant RAG as Vertex AI Search (RAG)
    participant GCS as Google Cloud Storage (GCS)
    participant FirebaseAuth as Firebase Auth
    participant SetupScripts as RAG Setup Scripts
    participant Corpus as Corpus / Transcripts

    rect rgb(240, 240, 240)
        note over User, Corpus: Setup Phase (Offline)
        User->>SetupScripts: 1. Executes setup scripts
        SetupScripts->>Corpus: 2. Reads local PDF/DOCX files
        Corpus-->>SetupScripts: 3. Provides file content
        SetupScripts->>GCS: 4. Uploads documents to a private bucket
        SetupScripts->>RAG: 5. Indexes documents from GCS for retrieval
    end

    rect rgb(240, 240, 240)
        note over User, Frontend_UI: Real-time Therapy Session
        User->>Frontend_UI: 1. Logs in and starts session
        Frontend_UI->>FirebaseAuth: 1a. Authenticates user
        
        User->>Frontend_Audio: 2. Speaks (provides audio)
        Frontend_Audio->>TranscriptionService: 3. Streams audio data (WebSocket)
        
        TranscriptionService->>SpeechToText: 4. Streams audio for transcription
        SpeechToText-->>TranscriptionService: 5. Returns real-time transcript text
        TranscriptionService-->>Frontend_UI: 6. Streams transcript back (WebSocket)
        
        Frontend_UI->>Frontend_Analysis: 7. Accumulates transcript
        Frontend_Analysis->>AnalysisFunction: 8. Sends transcript context (HTTPS + Auth Token)
        
        AnalysisFunction->>FirebaseAuth: 8a. Verifies user token
        AnalysisFunction->>RAG: 9. Queries for relevant clinical patterns & evidence
        RAG-->>AnalysisFunction: 10. Returns augmented context
        AnalysisFunction->>Gemini: 11. Sends augmented prompt (transcript + RAG results)
        Gemini-->>AnalysisFunction: 12. Returns AI-generated guidance (JSON)
        AnalysisFunction-->>Frontend_UI: 13. Returns guidance to UI
        
        User->>Frontend_UI: 14. Clicks on a citation
        Frontend_UI->>StorageProxy: 15. Requests cited document (e.g., PDF)
        StorageProxy->>GCS: 16. Securely fetches document from private bucket
        GCS-->>StorageProxy: 17. Returns document
        StorageProxy-->>Frontend_UI: 18. Delivers document for display
        Frontend_UI->>User: 19. Displays document
    end
```
