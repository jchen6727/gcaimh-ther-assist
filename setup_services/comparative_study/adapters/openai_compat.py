"""
OpenAI-compatible adapter family.

OpenAI's chat-completions API has become the de facto standard. OpenAI itself,
xAI Grok, DeepSeek, and many others expose the same shape — they only differ by
base URL, API key env var, and model name. We write one adapter that handles
all four, parameterized by provider config.

Anthropic Claude has its own SDK shape, so it gets a separate adapter (anthropic.py).
"""
import os
import time
import logging
from typing import Optional
from urllib.parse import urlparse

from .base import BaseAdapter, ModelArm, AnalysisResponse, parse_json_loose


class OpenAICompatAdapter(BaseAdapter):
    """Calls any chat-completions-compatible API.

    Configure once with provider name + base URL + API key env var. The same
    adapter instance handles OpenAI, xAI Grok, DeepSeek, Mistral, Together, etc.

    Example arms:
      ModelArm(arm_id='gpt-5-vanilla', provider='openai',  model_name='gpt-5', ...)
      ModelArm(arm_id='grok-4-vanilla', provider='xai',     model_name='grok-4', ...)
      ModelArm(arm_id='deepseek-v3-vanilla', provider='deepseek', model_name='deepseek-chat', ...)
    """

    PROVIDER_CONFIGS = {
        "openai":   {"base_url": "https://api.openai.com/v1",            "api_key_env": "OPENAI_API_KEY"},
        "xai":      {"base_url": "https://api.x.ai/v1",                  "api_key_env": "XAI_API_KEY"},
        "deepseek": {"base_url": "https://api.deepseek.com/v1",          "api_key_env": "DEEPSEEK_API_KEY"},
    }

    def __init__(self, provider_name: str, base_url: Optional[str] = None, api_key: Optional[str] = None):
        if provider_name not in self.PROVIDER_CONFIGS and (not base_url or not api_key):
            raise ValueError(
                f"Unknown provider '{provider_name}'. Either use a built-in "
                f"({list(self.PROVIDER_CONFIGS)}) or pass base_url + api_key explicitly."
            )
        cfg = self.PROVIDER_CONFIGS.get(provider_name, {})
        self._provider_name = provider_name
        self._base_url = base_url or cfg.get("base_url")
        self._api_key = api_key or os.environ.get(cfg.get("api_key_env", ""), "")
        self._client = None  # lazy init

    @property
    def provider(self) -> str:
        return self._provider_name

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                ) from e
            if not self._api_key:
                raise RuntimeError(
                    f"No API key for provider {self._provider_name}. "
                    f"Set env var {self.PROVIDER_CONFIGS.get(self._provider_name, {}).get('api_key_env', '?')}"
                )
            self._client = OpenAI(base_url=self._base_url, api_key=self._api_key)
        return self._client

    def analyze(self, transcript: str, arm: ModelArm) -> AnalysisResponse:
        try:
            client = self._get_client()
            messages = []
            if arm.system_prompt:
                messages.append({"role": "system", "content": arm.system_prompt})
            messages.append({"role": "user", "content": transcript})

            start = time.perf_counter()
            resp = client.chat.completions.create(
                model=arm.model_name,
                messages=messages,
                temperature=arm.extra_config.get("temperature", 0.0),
                max_tokens=arm.extra_config.get("max_tokens", 4096),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            text = (resp.choices[0].message.content or "") if resp.choices else ""
            usage = getattr(resp, "usage", None)
            in_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            out_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            return AnalysisResponse(
                text=text,
                parsed_json=parse_json_loose(text),
                latency_ms=elapsed_ms,
                input_tokens=in_tokens or 0,
                output_tokens=out_tokens or 0,
                metadata={"model": arm.model_name, "condition": arm.condition},
            )
        except Exception as e:
            logging.exception(f"[OpenAICompat-{self._provider_name}] {arm.arm_id} failed")
            return AnalysisResponse(text="", error=str(e), metadata={"model": arm.model_name})
