"""Adapter registry — maps provider key to concrete adapter class."""
from .base import BaseAdapter, ModelArm, AnalysisResponse, parse_json_loose

# Lazy registry: import errors (missing SDKs) shouldn't break collecting available adapters.
ADAPTER_CLASSES = {}


def register_adapter(provider: str, cls):
    ADAPTER_CLASSES[provider] = cls


def get_adapter_class(provider: str):
    """Look up an adapter class by provider key, importing on demand."""
    if provider in ADAPTER_CLASSES:
        return ADAPTER_CLASSES[provider]
    if provider == "google":
        from .gemini import GeminiAdapter
        register_adapter("google", GeminiAdapter)
        return GeminiAdapter
    if provider in ("openai", "xai", "deepseek"):
        from .openai_compat import OpenAICompatAdapter
        register_adapter(provider, OpenAICompatAdapter)
        return OpenAICompatAdapter
    if provider == "anthropic":
        from .anthropic import AnthropicAdapter
        register_adapter("anthropic", AnthropicAdapter)
        return AnthropicAdapter
    if provider == "therassist":
        from .therassist import TherAssistAdapter
        register_adapter("therassist", TherAssistAdapter)
        return TherAssistAdapter
    raise ValueError(f"Unknown provider '{provider}'")


__all__ = [
    "BaseAdapter",
    "ModelArm",
    "AnalysisResponse",
    "parse_json_loose",
    "get_adapter_class",
    "ADAPTER_CLASSES",
]
