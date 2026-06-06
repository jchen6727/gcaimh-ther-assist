"""
Adapter base class for comparative study.

Each LLM provider has different API quirks (auth, request shape, response shape,
streaming behavior, token limits). Adapters hide that behind a single uniform
method: `analyze(transcript, system_prompt) → AnalysisResponse`.

The runner doesn't care which model it's calling. Adding a new model means
writing one new adapter class.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class AnalysisResponse:
    """Uniform shape returned by every adapter.

    `text` is the raw model output. `parsed_json` is populated if the response
    looks like JSON (most clinical analyses do). `metadata` carries timing,
    token counts, and provider-specific extras for cost reporting.
    """
    text: str
    parsed_json: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None  # if non-None, the call failed and other fields may be empty


@dataclass
class ModelArm:
    """An arm in the study: one model under one prompt-engineering condition."""
    arm_id: str               # unique slug e.g. "gpt-5-vanilla", "therassist-pipeline"
    display_name: str
    provider: str             # 'openai' | 'anthropic' | 'google' | 'xai' | 'deepseek' | 'therassist'
    model_name: str
    condition: str            # 'vanilla' | 'engineered' | 'pipeline'
    system_prompt: Optional[str] = None
    extra_config: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """Subclasses implement one model provider's analyze() call.

    Adapters are stateful (they may cache an API client). Construct once per
    study run, call analyze() N×M times (cases × arms).
    """

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider key, e.g. 'openai', 'google', 'therassist'."""

    @abstractmethod
    def analyze(self, transcript: str, arm: ModelArm) -> AnalysisResponse:
        """Run one model on one transcript and return the structured response.

        Implementations should:
          - Apply `arm.system_prompt` if non-None
          - Use `arm.model_name` to select the model
          - Time the call (milliseconds)
          - Capture token counts when the provider exposes them
          - Try to parse the response as JSON and populate `parsed_json`
          - On error: return `AnalysisResponse(text='', error=str(e))` — do NOT raise.
            The runner catches errors per-arm so one bad model doesn't kill the run.
        """

    def supports(self, arm: ModelArm) -> bool:
        """Default: this adapter handles arms with matching provider."""
        return arm.provider == self.provider


def parse_json_loose(text: str) -> Optional[Dict[str, Any]]:
    """Try to extract a JSON object from arbitrary model output.

    Handles common patterns:
      - Pure JSON: { ... }
      - Wrapped in ```json ... ```
      - Leading prose then JSON
    Returns None if nothing parses.
    """
    import json
    import re
    if not text:
        return None
    # Strip ```json fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Try the largest brace-delimited substring
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except json.JSONDecodeError:
            pass
    # Last resort: maybe it's already pure JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
