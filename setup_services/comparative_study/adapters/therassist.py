"""
TherAssist adapter — calls our own backend through the full pipeline.

This is the "treatment" arm of the comparative study. Unlike vanilla model arms,
the TherAssist arm runs the COMPLETE pipeline:
  - RAG retrieval (4-9 Discovery Engine datastores depending on session_type)
  - Safety keyword pre-scan (deterministic)
  - 3-tier therapeutic context risk calibration
  - Multi-modality routing (CBT/DBT/IPT)
  - Fine-tuned safety classifier (Gemini 2.0 Flash)
  - LLM call (Gemini 2.5 Pro) with our engineered prompts

Calling our backend directly preserves the full pipeline behavior — which is the
whole point of the comparison.
"""
import os
import time
import json
import logging
from typing import Optional

import requests

from .base import BaseAdapter, ModelArm, AnalysisResponse, parse_json_loose


class TherAssistAdapter(BaseAdapter):
    """Calls our deployed therapy-analysis Cloud Run service.

    Configure via env:
      THERASSIST_ANALYSIS_URL  — full URL to /therapy_analysis endpoint
                                  (default: localhost dev port 8090)
      THERASSIST_AUTH_TOKEN    — Firebase ID token or dev token
                                  (Phase 4 dev tokens work when PORTAL_DEV_AUTH_BYPASS=true)
    """

    DEFAULT_URL = "http://localhost:8090/therapy_analysis"

    def __init__(self, url: Optional[str] = None, auth_token: Optional[str] = None):
        self._url = url or os.environ.get("THERASSIST_ANALYSIS_URL", self.DEFAULT_URL)
        self._token = auth_token or os.environ.get("THERASSIST_AUTH_TOKEN", "")

    @property
    def provider(self) -> str:
        return "therassist"

    def analyze(self, transcript: str, arm: ModelArm) -> AnalysisResponse:
        try:
            # The transcript here is a raw clinical transcript. Our backend expects
            # a session_summary action with `full_transcript` as a list of speaker turns.
            # For the comparative study we use the same "comprehensive analysis" path.
            #
            # Convert simple "Patient: ..." / "Therapist: ..." into our segment shape.
            segments = self._transcript_to_segments(transcript)
            body = {
                "action": "session_summary",
                "full_transcript": segments,
                "session_metrics": {
                    "duration_minutes": arm.extra_config.get("duration_minutes", 50),
                    "session_type": arm.extra_config.get("session_type", "CBT"),
                },
                "session_context": {
                    "session_type": arm.extra_config.get("session_type", "CBT"),
                    "primary_concern": arm.extra_config.get("primary_concern", "Not specified"),
                    "current_approach": arm.extra_config.get("current_approach", "Not specified"),
                },
            }
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            start = time.perf_counter()
            r = requests.post(self._url, json=body, headers=headers, timeout=300)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            r.raise_for_status()
            data = r.json()

            # Backend returns { "summary": { ...parsed_summary... } }
            summary = data.get("summary") if isinstance(data, dict) else None
            text = json.dumps(summary, indent=2) if isinstance(summary, dict) else str(data)

            return AnalysisResponse(
                text=text,
                parsed_json=summary if isinstance(summary, dict) else parse_json_loose(text),
                latency_ms=elapsed_ms,
                metadata={"model": "therassist-pipeline", "condition": "pipeline"},
            )
        except Exception as e:
            logging.exception(f"[TherAssistAdapter] {arm.arm_id} failed")
            return AnalysisResponse(text="", error=str(e), metadata={"model": "therassist-pipeline"})

    @staticmethod
    def _transcript_to_segments(transcript: str) -> list:
        """Convert 'Speaker: text' lines into segment objects our backend expects."""
        segments = []
        for line in transcript.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            speaker = "Unknown"
            text = line
            if ":" in line:
                possible_speaker, rest = line.split(":", 1)
                if possible_speaker.lower() in {"patient", "client", "therapist", "p", "c", "t"}:
                    speaker = "Therapist" if possible_speaker.lower().startswith("t") else "Client"
                    text = rest.strip()
            segments.append({"speaker": speaker, "text": text, "timestamp": ""})
        return segments
