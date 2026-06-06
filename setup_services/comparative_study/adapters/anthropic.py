"""Anthropic Claude adapter."""
import os
import time
import logging
from typing import Optional

from .base import BaseAdapter, ModelArm, AnalysisResponse, parse_json_loose


class AnthropicAdapter(BaseAdapter):
    """Calls Claude models via the Anthropic SDK.

    Supported models (arm.model_name):
      'claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001', etc.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None

    @property
    def provider(self) -> str:
        return "anthropic"

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                ) from e
            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self._client = Anthropic(api_key=self._api_key)
        return self._client

    def analyze(self, transcript: str, arm: ModelArm) -> AnalysisResponse:
        try:
            client = self._get_client()
            kwargs = {
                "model": arm.model_name,
                "max_tokens": arm.extra_config.get("max_tokens", 4096),
                "temperature": arm.extra_config.get("temperature", 0.0),
                "messages": [{"role": "user", "content": transcript}],
            }
            if arm.system_prompt:
                kwargs["system"] = arm.system_prompt

            start = time.perf_counter()
            resp = client.messages.create(**kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            text = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    text += block.text
            usage = getattr(resp, "usage", None)
            in_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            out_tokens = getattr(usage, "output_tokens", 0) if usage else 0
            return AnalysisResponse(
                text=text,
                parsed_json=parse_json_loose(text),
                latency_ms=elapsed_ms,
                input_tokens=in_tokens or 0,
                output_tokens=out_tokens or 0,
                metadata={"model": arm.model_name, "condition": arm.condition},
            )
        except Exception as e:
            logging.exception(f"[AnthropicAdapter] {arm.arm_id} failed")
            return AnalysisResponse(text="", error=str(e), metadata={"model": arm.model_name})
