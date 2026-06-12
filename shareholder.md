# Ther-Assist Backend Rewrite — Stakeholder Summary

**Author:** James Chen  
**Date:** 2026-06-11  
**Audience:** Clinical stakeholders, non-technical shareholders  

---

## Overview

This document explains a decision to pause broad development work on the Ther-Assist backend and instead spend four focused weeks rebuilding the backend core from a narrower, more defensible foundation. It describes what is wrong with the current system, why fixing it incrementally is not the right approach, and what the four-week project will deliver.

---

## What the System Is Supposed to Do

Ther-Assist is a real-time AI assistant for therapy sessions. It listens to the audio of a therapy session, transcribes it, and surfaces guidance to the therapist during the session — pointing out potentially significant moments, relevant clinical techniques, and safety concerns. It is also meant to produce structured session summaries after the session ends.

The guidance it provides is supposed to be grounded in evidence-based therapy materials — manuals, protocols, and clinical guides for approaches like Cognitive Behavioral Therapy — rather than generic AI output.

---

## What Is Currently Wrong

### 1. The Knowledge Base Contains the Wrong Kind of Content

The AI draws its clinical guidance from a library of documents that were loaded during initial development. A review of that library found that the majority of documents are **research papers comparing therapeutic approaches** — studies asking questions like "Is CBT more effective than IPT for treating depression in adults?"

These papers are not useful for in-session guidance. They answer academic questions about research populations. They cannot tell the AI *how to perform* a grounding exercise, *what steps* a safety planning conversation should follow, or *what language* to use when a patient discloses self-harm. For that, the system needs clinical protocols, therapy technique manuals, and session guides.

As it stands, when the AI retrieves documents to support its guidance, it is retrieving content that has no practical application to what a therapist needs in the moment. There is also no system in place to verify that the right documents were loaded correctly — the tests only check that *some* content is returned, not that it comes from the expected sources.

### 2. The System Cannot Accurately Read Emotional State from Audio Alone

One of the system's stated capabilities is assessing a patient's emotional state during a session. The current implementation does this by analyzing the words in the transcript.

This is a significant limitation. Clinical research consistently shows that the nonverbal components of a therapeutic interaction — tone of voice, pace and inflection, posture, eye contact, facial expression — account for somewhere between 50 and 90 percent of the information a therapist uses to assess patient state. A patient can say "I'm fine" in a way that communicates the opposite, and no amount of text analysis will detect that.

The current architecture is not designed to capture or analyze these nonverbal signals. As a result, the emotional state assessments it produces reflect only what was said, not how it was said — which is the less clinically significant portion of the signal. Before investing further in this feature, the architecture would need to be reconsidered to incorporate audio features beyond transcription.

### 3. The Codebase Was Generated Without Sufficient Human Review

A detailed technical audit of the codebase found evidence of large blocks of AI-generated code that were added in single commits without incremental review. This is a common pattern in AI-assisted development that creates specific risks:

**Features were built that were never requested.** The codebase contains a complete fine-tuning pipeline (estimated cost if run: $1,500–$2,000 per training run), a multi-model comparison framework testing five different AI providers, a multi-session agent system, and a cross-session memory architecture. None of these appear to have been part of the original product scope. They add complexity, maintenance burden, and cost exposure without delivering clinical value.

**Parts of the system are incomplete in ways that are hard to detect.** For example, the multi-session agent reads patient history from a database table called `session_summaries`, but the production code writes session records to a different table called `sessions`. If the agent were ever deployed, it would silently return empty history with no error. This kind of mismatch — where code looks complete but the pieces don't connect — is harder to catch in a large AI-generated codebase than in code written incrementally by hand.

**The authentication system was left disabled.** The code that verifies a therapist's identity before granting access to session data was commented out during development, with a note saying it would be restored before production. As of this writing, it has not been restored. Any request to the system — from any source — is currently treated as authenticated.

**Both performance optimization systems deliver no benefit.** The system includes two caching mechanisms designed to reduce latency and cost. A detailed investigation found that neither works in practice: one is permanently disabled by an API incompatibility that was never noticed, and the other has a design flaw that causes it to produce zero cache hits under normal conversation conditions. The real-time guidance latency is consequently 3–11 seconds per analysis, rather than the 2–4 seconds the system was designed to achieve.

### 4. The System Is Difficult to Verify or Modify Safely

Because large sections of the codebase were generated and committed in bulk, understanding which pieces depend on which other pieces — and what breaks if something changes — requires significant investigation for each modification. At the current complexity level, even well-intentioned changes carry meaningful risk of introducing errors in parts of the code that weren't the intended target.

---

## What the Four-Week Rewrite Will Deliver

The goal is not to start over entirely, but to rebuild the backend core with clear ownership and verifiable behavior at each step. At the end of four weeks, the project will have:

**A correctly curated knowledge base.** The document library will be rebuilt from clinical technique guides, therapy protocols, and evidence-based practice manuals — content that can actually answer in-session guidance questions. A new ingestion system will make it straightforward to add documents incrementally as new materials become available, without requiring a full technical rebuild each time.

**Verified document retrieval.** A validation step will confirm that when the AI retrieves documents to support a guidance suggestion, those documents are actually from the expected sources. This is a prerequisite for trusting any citation the system provides.

**A measurable safety baseline.** The most important behavioral guarantee for a clinical AI tool is that it never misses a patient safety concern. The rewrite will establish a fixed set of test cases — covering passive and active suicidal ideation, self-harm disclosure, violence risk, and other safety-relevant scenarios — and require the system to pass all of them before any change to the analysis logic is accepted. This creates an auditable safety record.

**Defined and stable API interfaces.** Clear specifications for how the frontend communicates with the backend, what error conditions look like, and how the system behaves when a component (RAG, transcription, LLM) is unavailable. This is the prerequisite for reliable frontend integration and future feature development.

**Authentication enabled.** The identity verification that was disabled during development will be restored and confirmed working.

**Real latency and cost measurements.** With the cache system corrected and instrumentation in place, it will be possible to measure actual per-session cost and latency rather than relying on design estimates that were never validated against real traffic patterns.

---

## Why This Takes Four Weeks

Four weeks is the minimum time to do these things in the right order without creating new problems.

The knowledge base has to be rebuilt before the analysis logic is tuned against it. There is no point in optimizing how the AI uses documents if the documents are wrong. The rebuild — designing the metadata schema, validating document ingestion, confirming retrieval — takes one to two weeks as a self-contained task.

The measurement framework has to be in place before any changes to the analysis logic. Clinical scenario test cases need to be authored, and some of them require clinical review before they can be used as automated regression gates. This is not work that can be skipped or abbreviated.

The interface design has to precede the logic implementation. Decisions made now about what information flows between the backend and the frontend will be difficult and costly to change later.

These phases are sequential, not parallel. Adding more engineers does not compress the timeline — each phase depends on the outputs of the previous one.

---

## What This Project Is Not Doing

This project is not rewriting the entire application. The patient portal (homework, journaling, interventions, questionnaires), the scheduling system, and the frontend are not in scope. The focus is strictly on the backend inference core: the part of the system that receives a therapy transcript and produces clinical guidance.

Features that exist in the current codebase but fall outside this scope will remain in place, untouched, until the core is stable and there is a reliable way to verify that adding them back doesn't break the safety-critical paths.

---

## The Larger Context

The problems identified here are not unusual for an early-stage AI project with limited technical oversight. The underlying clinical concept — a real-time assistant that helps therapists notice what they might otherwise miss — is sound. The path to a trustworthy version of that concept runs through a foundation that can be verified: a correct knowledge base, measurable safety behavior, and code that can be read, tested, and changed with confidence.

Four weeks buys that foundation. Everything built after it will be faster, safer, and more directly aligned with what was actually requested.
