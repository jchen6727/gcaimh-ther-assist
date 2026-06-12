# Project Workflow — Backend Rewrite and Integration

> Phase content and rationale deferred to [technical.md](./technical.md).  
> Old-backend I/O specs deferred to [backend/UNIT_TESTING_SPEC.md](./backend/UNIT_TESTING_SPEC.md).

---

```mermaid
---
config:
  layout: dagre
---
flowchart TB
 subgraph TRACK_A["Track A — New Repo · Own Cloud Instance"]
    direction TB
        FORK_A["New repository\nOwn GCP project — full IAM\nNo shared-project privilege limits/latency"]
        A1["Phase 1 · Weeks 1–3\nI/O Endpoints & Contracts\n──────────────────────\nHTTP schemas: analyze_segment, session_summary\nRAG ingestion schemas\nExplicit error envelopes for failure"]
        A2["Phase 2 · Weeks 1–3  ‹overlaps Phase 1›\nCorpus Ingestion API & Metadata Schema\n──────────────────────\nContent type: limited to technique guides\nTyped metadata: modality · technique tags · source\n transparent API allowing for modification\nPre-commit retrieval validation before success response\nIncremental add — no full re-ingest required"]
        A3["Phase 3 · Weeks 2–3\nCI Benchmarking Framework\n──────────────────────\nPure-function unit tests — zero external calls\nscenario eval harness using text, implement into CI. \nRAG provenance check: chunks from expected PDFs\nLatency budget: realtime P95 &lt; 3 s"]
        A4["Phase 4 · Weeks 3–4\nCore RT Analysis Logic Benchmarking \n──────────────────────\nToken cost and Real time response latency cemented for baseline"]
  end
 subgraph TRACK_B["Track B — Old Backend Audit  ‹parallel, read-only until Unit Test›"]
    direction TB
        FORK_B["Isolate existing backend\nRead-only — no production changes\nWork from current branch audit docs"]
        B1["I/O Boundary Documentation\n──────────────────────\nHTTP request/response shapes — all three services\nWebSocket frame inventory  ‹STT service›\nFirestore read/write contracts\nAuth token formats and bypass modes"]
        B2["Unit Test Specification\n──────────────────────\nPure-function targets per service\nPriority order: safety-critical paths first\nShared fixture and mock patterns\nTest isolation constraints  ‹no GCP calls›\nSee: backend/UNIT_TESTING_SPEC.md"]
        B3["Merge Contract\n──────────────────────\nAPI shapes to preserve vs. supersede\nFeature compatibility matrix\nOut-of-scope stubs: confirm keep or delete"]
  end
    START(["Begin"]) --> FORK_A & FORK_B
    FORK_A --> A1
    A1 --> A2
    A2 --> A3
    A3 --> A4
    FORK_B --> B1
    B1 --> B2
    B2 --> B3
    A3 <--> UNIT["Apply CI testing and benchmarking to old repository and project to evaluate current feature implementation"]
    B2 <--> UNIT
    A4 --> MERGE["Merge Point\nNew backend: all Phase 1–5 gates passed\nMerge contract: defined and agreed"]
    B3 --> MERGE
    MERGE --> REIN["Incremental Reintegration\n──────────────────────\nPortal handlers  ‹homework · interventions · questionnaires›\nFrontend wiring to new I/O contracts\nOut-of-scope features  ‹agent · fine-tuning› if confirmed in scope\nFull regression via eval harness before each merge step"]
    REIN --> EFFICACY["Therapeutic Efficacy Analysis · Week 4-> Release\nTherapeutic Conversation Testing\n──────────────────────\nEval harness vs. real or realistic transcripts\nBaseline vs. candidate prompt comparison\nIterate on structure"]

    MERGE@{ shape: rect}
     FORK_A:::trackA
     A1:::trackA
     A2:::trackA
     A3:::trackA
     A4:::trackA
     FORK_B:::trackB
     B1:::trackB
     B2:::trackB
     B3:::trackB
     START:::start
     UNIT:::gate
     MERGE:::gate
     REIN:::rein
     EFFICACY:::rein
    classDef trackA fill:#EBF3FB,stroke:#2E74B5,stroke-width:1.5px,color:#1F3864
    classDef trackB fill:#FEF9EC,stroke:#C9952A,stroke-width:1.5px,color:#3E2A00
    classDef gate fill:#E2EFDA,stroke:#538135,stroke-width:2px,color:#1E3A14,font-weight:bold
    classDef rein fill:#F0EBF9,stroke:#7030A0,stroke-width:1.5px,color:#2E1050
    classDef start fill:#F2F2F2,stroke:#595959,stroke-width:1.5px

---

## Track Summary

| Track | What happens | Constraint |
|---|---|---|
| **A — New Repo** | Phases 1–5 per `technical.md §3` | Each phase gates the next; cannot be parallelised |
| **B — Old Backend Audit** | Read-only I/O extraction and test spec | Feeds the merge contract; does not block Track A |
| **Merge** | New backend passes all eval gates; merge contract agreed | Both tracks must reach their terminal node |
| **Reintegration** | Out-of-scope features re-added incrementally | Each addition re-runs the eval harness |

## Phase Gate Criteria

Gates that must pass before advancing — details in `technical.md §3` and `UNIT_TESTING_SPEC.md`.

| Gate | Criterion |
|---|---|
| Phase 1 → 2 | All I/O schemas reviewed; auth confirmed working end-to-end |
| Phase 2 → 3 | Corpus re-ingested; provenance test confirms chunks from correct source PDFs |
| Phase 3 → 4 | Eval harness runs clean on all 9 scenarios; safety recall = 1.0 |
| Phase 4 → 5 | Cache hit rate measurably positive; all four handlers pass safety scan unit tests |
| Phase 5 → Merge | Therapeutic transcript eval passes all metric targets |
| Merge → Reintegration | Full regression suite green after project merge |
