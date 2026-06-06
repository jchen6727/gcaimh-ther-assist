"""Google Gemini adapter — uses google-genai SDK."""
import os
import time
import logging
from typing import Optional

from .base import BaseAdapter, ModelArm, AnalysisResponse, parse_json_loose


class GeminiAdapter(BaseAdapter):
    """Calls Gemini models via Vertex AI (when GOOGLE_CLOUD_PROJECT is set)
    or the Gemini API directly (when GEMINI_API_KEY is set).

    Supported arms:
      provider='google', model_name in {'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash-001'}
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
    ):
        from google import genai
        self._genai = genai
        self._project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self._location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self._client = None  # lazy init

    @property
    def provider(self) -> str:
        return "google"

    def _get_client(self):
        if self._client is None:
            if self._project_id:
                self._client = self._genai.Client(
                    vertexai=True,
                    project=self._project_id,
                    location=self._location,
                )
            else:
                # Falls back to GEMINI_API_KEY env var
                self._client = self._genai.Client()
        return self._client

    def analyze(self, transcript: str, arm: ModelArm) -> AnalysisResponse:
        from google.genai import types
        client = self._get_client()
        start = time.perf_counter()
        try:
            # Build the prompt: system + user transcript
            contents = []
            if arm.system_prompt:
                # Gemini accepts a system_instruction config field; we use it directly.
                pass
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=transcript)],
            ))
            config = types.GenerateContentConfig(
                temperature=arm.extra_config.get("temperature", 0.0),
                max_output_tokens=arm.extra_config.get("max_output_tokens", 4096),
                system_instruction=arm.system_prompt if arm.system_prompt else None,
            )
            response = client.models.generate_content(
                model=arm.model_name,
                contents=contents,
                config=config,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            text = ""
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                text = response.candidates[0].content.parts[0].text or ""
            usage = getattr(response, "usage_metadata", None)
            in_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            out_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            return AnalysisResponse(
                text=text,
                parsed_json=parse_json_loose(text),
                latency_ms=elapsed_ms,
                input_tokens=in_tokens or 0,
                output_tokens=out_tokens or 0,
                metadata={"model": arm.model_name, "condition": arm.condition},
            )
        except Exception as e:
            logging.exception(f"[GeminiAdapter] {arm.arm_id} failed")
            return AnalysisResponse(text="", error=str(e), metadata={"model": arm.model_name})
