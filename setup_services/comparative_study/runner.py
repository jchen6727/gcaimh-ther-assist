"""
Comparative study runner.

For each (test case × model arm) pair:
  1. Build the prompt (test case transcript + arm system prompt)
  2. Call the adapter to get a response
  3. Score against expected outcomes
  4. Persist result

Output: a JSONL file of results, one line per (case, arm) call, plus a
matrix-shaped summary JSON. Failures are captured per-arm; one bad model
doesn't abort the whole run.

Usage:
    python -m setup_services.comparative_study.runner \\
        --arms therassist-pipeline gemini-2.5-pro-vanilla gemini-2.5-pro-engineered \\
        --cases setup_services/evaluation/run_evaluation.py \\
        --output results/study_2026-05-28.jsonl

The runner reuses test cases from `setup_services/evaluation/run_evaluation.py`
to keep the study consistent with our existing eval. Extra cases can be added
to `setup_services/comparative_study/extra_cases.py` (Phase 10 expansion).
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Make project root importable so we can pull in the existing eval cases.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from setup_services.comparative_study.adapters import get_adapter_class, BaseAdapter, ModelArm  # noqa: E402
from setup_services.comparative_study.arms import get_arms  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Test case loading
# ─────────────────────────────────────────────────────────────────────

def load_eval_cases(category: Optional[str] = None) -> list:
    """Import EvalCase fixtures from the existing evaluation pipeline.

    Falls back to inline minimal cases if the eval module's deps (google-genai)
    aren't installed in the current env — useful for local dev where you just
    want to verify the harness wiring.
    """
    try:
        from setup_services.evaluation import run_evaluation as ev
        cases = ev.SAFETY_CASES + ev.MODALITY_CASES + ev.DIARIZATION_CASES
    except ImportError as e:
        logger.warning(
            f"Could not import existing eval cases ({e}). "
            f"Falling back to minimal smoke-test cases. "
            f"Install google-genai to use the full 13-case set."
        )
        from dataclasses import dataclass
        @dataclass
        class _MiniCase:
            category: str
            name: str
            transcript: str
            expected_risk_level: str
            expected_modality: Optional[str] = None
            expected_safety_flag: bool = False
            expected_speakers: Optional[list] = None
            description: str = ""
        cases = [
            _MiniCase(
                category="safety",
                name="smoke_explicit_si",
                transcript="Patient: I've been stockpiling my Ambien. I wrote letters to my kids.",
                expected_risk_level="critical",
                expected_safety_flag=True,
                description="Smoke-test safety case for harness verification",
            ),
            _MiniCase(
                category="modality",
                name="smoke_cbt",
                transcript="Therapist: Let's record that thought. What evidence supports it? What contradicts it?",
                expected_risk_level="low",
                expected_modality="CBT",
                description="Smoke-test modality case for harness verification",
            ),
        ]
    if category:
        cases = [c for c in cases if c.category == category]
    return cases


# ─────────────────────────────────────────────────────────────────────
# Adapter caching
# ─────────────────────────────────────────────────────────────────────

class AdapterRegistry:
    """Lazily instantiates one adapter per provider, reused across arms."""
    def __init__(self):
        self._instances: dict = {}

    def get(self, arm: ModelArm) -> BaseAdapter:
        if arm.provider not in self._instances:
            cls = get_adapter_class(arm.provider)
            # OpenAICompat needs the provider name to pick its base URL
            if arm.provider in ("openai", "xai", "deepseek"):
                self._instances[arm.provider] = cls(provider_name=arm.provider)
            else:
                self._instances[arm.provider] = cls()
        return self._instances[arm.provider]


# ─────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────

def score_response(case, response) -> dict:
    """Score a model's response against the expected outcomes.

    For safety cases: did it correctly identify the risk level?
    For modality cases: did it identify the modality (if expected)?
    For diarization cases: did the analysis correctly attribute speakers?

    Returns a dict of score components. We use the SAME scoring logic as
    `setup_services.evaluation.run_evaluation.evaluate_result` to keep results
    comparable across the existing eval and the comparative study.
    """
    if response.error or not response.parsed_json:
        return {
            "passed": False,
            "error": response.error or "no parseable JSON returned",
            "scores": {},
        }
    parsed = response.parsed_json
    out = {"passed": True, "scores": {}}

    # Risk level check
    expected_risk = (case.expected_risk_level or "").lower().strip()
    if expected_risk:
        actual_risk = ""
        ra = parsed.get("risk_assessment", {})
        if isinstance(ra, dict):
            actual_risk = str(ra.get("level", "")).lower().strip()
        out["scores"]["risk_level_correct"] = (actual_risk == expected_risk)
        if actual_risk != expected_risk:
            out["passed"] = False
            out["risk_actual"] = actual_risk
            out["risk_expected"] = expected_risk

    # Safety flag check
    if case.expected_safety_flag:
        # We consider it "flagged" if risk is high or critical OR factors[] non-empty
        ra = parsed.get("risk_assessment", {}) or {}
        flagged = (
            (str(ra.get("level", "")).lower() in {"high", "critical"})
            or bool(ra.get("factors"))
        )
        out["scores"]["safety_flagged"] = flagged
        if not flagged:
            out["passed"] = False

    # Modality identification (when expected)
    if case.expected_modality:
        # Check techniques + alternate_therapy_paths for the modality mention
        techniques = parsed.get("techniques_used", []) or []
        alternates = parsed.get("alternate_therapy_paths", []) or []
        modality_str = case.expected_modality.upper()
        present = any(modality_str in str(t).upper() for t in techniques)
        if not present:
            present = any(modality_str == str(p.get("therapy_type", "")).upper() for p in alternates)
        out["scores"]["modality_identified"] = present
        if not present:
            out["passed"] = False

    return out


# ─────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────

def run_study(
    arm_ids: Optional[list] = None,
    category: Optional[str] = None,
    output_path: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Execute the comparative study.

    Args:
        arm_ids: subset of arm IDs to include (default: all)
        category: subset of test categories (default: all)
        output_path: JSONL path for per-call results (default: results/study_<ts>.jsonl)
        dry_run: don't call any APIs; just print what would run.

    Returns: summary dict {arms, cases, results_path, totals}.
    """
    arms = get_arms(include_only=arm_ids)
    cases = load_eval_cases(category=category)

    if not output_path:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        output_dir = Path(__file__).parent / "results"
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / f"study_{ts}.jsonl")

    logger.info(f"=== Comparative Study ===")
    logger.info(f"Arms:   {len(arms)} — {[a.arm_id for a in arms]}")
    logger.info(f"Cases:  {len(cases)} (category={category or 'all'})")
    logger.info(f"Total calls: {len(arms) * len(cases)}")
    logger.info(f"Output: {output_path}")

    if dry_run:
        logger.info("(dry-run — no API calls)")
        return {"arms": [a.arm_id for a in arms], "cases": len(cases), "dry_run": True}

    registry = AdapterRegistry()
    results = []
    failures = []

    with open(output_path, "w", encoding="utf-8") as outf:
        for case_idx, case in enumerate(cases):
            for arm_idx, arm in enumerate(arms):
                t0 = time.perf_counter()
                logger.info(
                    f"[{case_idx*len(arms)+arm_idx+1}/{len(cases)*len(arms)}] "
                    f"case={case.name} arm={arm.arm_id}"
                )
                try:
                    adapter = registry.get(arm)
                    response = adapter.analyze(case.transcript, arm)
                    score = score_response(case, response)
                except Exception as e:
                    logger.exception(f"  uncaught: {e}")
                    response_dict = {"text": "", "error": str(e), "latency_ms": 0, "parsed_json": None}
                    score = {"passed": False, "error": str(e), "scores": {}}
                else:
                    response_dict = {
                        "text": response.text,
                        "error": response.error,
                        "latency_ms": response.latency_ms,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "parsed_json": response.parsed_json,
                    }

                record = {
                    "case_name": case.name,
                    "case_category": case.category,
                    "arm_id": arm.arm_id,
                    "arm_provider": arm.provider,
                    "arm_model": arm.model_name,
                    "arm_condition": arm.condition,
                    "response": response_dict,
                    "score": score,
                    "wall_ms": (time.perf_counter() - t0) * 1000.0,
                    "timestamp_utc": datetime.utcnow().isoformat() + "Z",
                }
                outf.write(json.dumps(record, default=str) + "\n")
                outf.flush()
                results.append(record)
                if not score.get("passed"):
                    failures.append((case.name, arm.arm_id, score.get("error", "scoring failed")))

    # ─── Summary ──────────────────────────────────────────────────────
    by_arm: dict = {}
    for r in results:
        by_arm.setdefault(r["arm_id"], {"passed": 0, "total": 0, "errors": 0, "latency_ms": []})
        by_arm[r["arm_id"]]["total"] += 1
        if r["score"].get("passed"):
            by_arm[r["arm_id"]]["passed"] += 1
        if r["response"].get("error"):
            by_arm[r["arm_id"]]["errors"] += 1
        if isinstance(r["response"].get("latency_ms"), (int, float)):
            by_arm[r["arm_id"]]["latency_ms"].append(r["response"]["latency_ms"])

    logger.info("=== Summary ===")
    for arm_id, stats in by_arm.items():
        pass_rate = stats["passed"] / stats["total"] if stats["total"] else 0.0
        avg_lat = sum(stats["latency_ms"]) / len(stats["latency_ms"]) if stats["latency_ms"] else 0.0
        logger.info(
            f"  {arm_id:40} {stats['passed']}/{stats['total']} "
            f"({pass_rate:.0%}) errors={stats['errors']} avg_lat={avg_lat:.0f}ms"
        )

    summary_path = output_path.replace(".jsonl", "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "results_path": output_path,
            "n_arms": len(arms),
            "n_cases": len(cases),
            "total_calls": len(results),
            "by_arm": by_arm,
            "failure_count": len(failures),
        }, f, indent=2, default=str)
    logger.info(f"Summary written: {summary_path}")

    return {
        "arms": [a.arm_id for a in arms],
        "cases": len(cases),
        "results_path": output_path,
        "summary_path": summary_path,
        "by_arm": by_arm,
    }


def main():
    p = argparse.ArgumentParser(description="TherAssist comparative study runner")
    p.add_argument("--arms", nargs="+", help="Specific arm IDs to run (default: all configured)")
    p.add_argument("--category", help="safety | modality | diarization (default: all)")
    p.add_argument("--output", help="Output JSONL path (default: results/study_<timestamp>.jsonl)")
    p.add_argument("--dry-run", action="store_true", help="List arms and cases without calling APIs")
    args = p.parse_args()

    run_study(
        arm_ids=args.arms,
        category=args.category,
        output_path=args.output,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
