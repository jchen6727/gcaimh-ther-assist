"""
Default arm definitions for the comparative study.

This is the registry of model × condition combinations the runner sweeps over.
Reviewers will scrutinize this list — comment on every choice in the paper.
"""
from .adapters import ModelArm
from .prompts import ENGINEERED_CLINICAL_PROMPT


# 11 arms — 5 frontier models × 2 conditions + TherAssist pipeline
DEFAULT_ARMS = [
    # ── TherAssist (treatment arm) ────────────────────────────────────
    ModelArm(
        arm_id="therassist-pipeline",
        display_name="TherAssist Pipeline",
        provider="therassist",
        model_name="therassist-pipeline",  # the URL identifies the backend
        condition="pipeline",
    ),

    # ── Google Gemini ─────────────────────────────────────────────────
    ModelArm(
        arm_id="gemini-2.5-pro-vanilla",
        display_name="Gemini 2.5 Pro (vanilla)",
        provider="google", model_name="gemini-2.5-pro", condition="vanilla",
    ),
    ModelArm(
        arm_id="gemini-2.5-pro-engineered",
        display_name="Gemini 2.5 Pro (clinical prompt)",
        provider="google", model_name="gemini-2.5-pro", condition="engineered",
        system_prompt=ENGINEERED_CLINICAL_PROMPT,
    ),

    # ── OpenAI GPT-5 ──────────────────────────────────────────────────
    ModelArm(
        arm_id="gpt-5-vanilla",
        display_name="GPT-5 (vanilla)",
        provider="openai", model_name="gpt-5", condition="vanilla",
    ),
    ModelArm(
        arm_id="gpt-5-engineered",
        display_name="GPT-5 (clinical prompt)",
        provider="openai", model_name="gpt-5", condition="engineered",
        system_prompt=ENGINEERED_CLINICAL_PROMPT,
    ),

    # ── Anthropic Claude ──────────────────────────────────────────────
    ModelArm(
        arm_id="claude-sonnet-4-6-vanilla",
        display_name="Claude Sonnet 4.6 (vanilla)",
        provider="anthropic", model_name="claude-sonnet-4-6", condition="vanilla",
    ),
    ModelArm(
        arm_id="claude-sonnet-4-6-engineered",
        display_name="Claude Sonnet 4.6 (clinical prompt)",
        provider="anthropic", model_name="claude-sonnet-4-6", condition="engineered",
        system_prompt=ENGINEERED_CLINICAL_PROMPT,
    ),

    # ── xAI Grok ──────────────────────────────────────────────────────
    ModelArm(
        arm_id="grok-4-vanilla",
        display_name="Grok 4 (vanilla)",
        provider="xai", model_name="grok-4", condition="vanilla",
    ),
    ModelArm(
        arm_id="grok-4-engineered",
        display_name="Grok 4 (clinical prompt)",
        provider="xai", model_name="grok-4", condition="engineered",
        system_prompt=ENGINEERED_CLINICAL_PROMPT,
    ),

    # ── DeepSeek ──────────────────────────────────────────────────────
    ModelArm(
        arm_id="deepseek-v3-vanilla",
        display_name="DeepSeek V3 (vanilla)",
        provider="deepseek", model_name="deepseek-chat", condition="vanilla",
    ),
    ModelArm(
        arm_id="deepseek-v3-engineered",
        display_name="DeepSeek V3 (clinical prompt)",
        provider="deepseek", model_name="deepseek-chat", condition="engineered",
        system_prompt=ENGINEERED_CLINICAL_PROMPT,
    ),
]


def get_arms(include_only: list = None, exclude: list = None) -> list:
    """Filter the default arm list. Useful for running subsets during dev."""
    arms = DEFAULT_ARMS
    if include_only:
        arms = [a for a in arms if a.arm_id in include_only]
    if exclude:
        arms = [a for a in arms if a.arm_id not in exclude]
    return arms
