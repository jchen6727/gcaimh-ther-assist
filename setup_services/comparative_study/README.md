# TherAssist Comparative Study Harness

Multi-model evaluation framework for comparing TherAssist's full pipeline against frontier LLM baselines.

## What it does

For every test case in the existing evaluation set, calls each configured model arm and records:
- Raw response text
- Parsed JSON (if any)
- Latency, input/output tokens
- Score against expected outcomes (risk level, safety flag, modality)

Output: JSONL with one record per `(case, arm)` call + a summary JSON aggregating pass rates per arm.

## Default arm set (11 arms)

| Arm | Provider | Condition |
|---|---|---|
| `therassist-pipeline` | our backend | full pipeline (RAG + safety classifier + 3-tier risk + engineered prompts) |
| `gemini-2.5-pro-vanilla` | Google | no system prompt |
| `gemini-2.5-pro-engineered` | Google | clinical system prompt |
| `gpt-5-vanilla` | OpenAI | no system prompt |
| `gpt-5-engineered` | OpenAI | clinical system prompt |
| `claude-sonnet-4-6-vanilla` | Anthropic | no system prompt |
| `claude-sonnet-4-6-engineered` | Anthropic | clinical system prompt |
| `grok-4-vanilla` | xAI | no system prompt |
| `grok-4-engineered` | xAI | clinical system prompt |
| `deepseek-v3-vanilla` | DeepSeek | no system prompt |
| `deepseek-v3-engineered` | DeepSeek | clinical system prompt |

Edit `arms.py` to add/remove models.

## Architecture

```
adapters/
   base.py            BaseAdapter, ModelArm, AnalysisResponse
   gemini.py          Google Gemini via google-genai
   openai_compat.py   OpenAI, xAI, DeepSeek (same SDK shape)
   anthropic.py       Claude via Anthropic SDK
   therassist.py      Our backend (calls /therapy_analysis)
arms.py             ModelArm registry (the 11 default arms)
prompts.py          ENGINEERED_CLINICAL_PROMPT — same prompt used for all engineered baselines
runner.py           The main loop: cases × arms → results JSONL
```

**Adapter contract**: each provider exposes a uniform `analyze(transcript, arm) → AnalysisResponse`. The runner doesn't know or care which provider is being called.

## Setup

```bash
pip install google-genai openai anthropic requests
```

Set environment variables for the providers you want to test:
```bash
export GOOGLE_CLOUD_PROJECT=brk-prj-salvador-dura-bern-sbx   # for Gemini via Vertex
# or: export GEMINI_API_KEY=...                              # for Gemini API
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export XAI_API_KEY=...
export DEEPSEEK_API_KEY=...

# For the TherAssist arm:
export THERASSIST_ANALYSIS_URL=https://therapy-analysis-420536872556.us-central1.run.app/therapy_analysis
export THERASSIST_AUTH_TOKEN=dev-therapist-mohsin.sardar@downstate.edu   # dummy mode
```

If a provider's env var is missing, that arm simply fails with `error="No API key"` — other arms still run.

## Running

Dry run (lists arms + cases, no API calls):
```bash
python -m setup_services.comparative_study.runner --dry-run
```

Run just two arms on safety cases:
```bash
python -m setup_services.comparative_study.runner \
    --arms therassist-pipeline gemini-2.5-pro-engineered \
    --category safety
```

Run everything:
```bash
python -m setup_services.comparative_study.runner
```

Custom output location:
```bash
python -m setup_services.comparative_study.runner \
    --output results/pilot_2026-06-01.jsonl
```

## Output

### Per-call results (JSONL)
```json
{
  "case_name": "explicit_suicidal_ideation",
  "case_category": "safety",
  "arm_id": "therassist-pipeline",
  "arm_provider": "therassist",
  "arm_model": "therassist-pipeline",
  "arm_condition": "pipeline",
  "response": {
    "text": "...",
    "parsed_json": { ...summary fields... },
    "latency_ms": 4823.5,
    "input_tokens": 1230,
    "output_tokens": 891,
    "error": null
  },
  "score": {
    "passed": true,
    "scores": {
      "risk_level_correct": true,
      "safety_flagged": true
    }
  },
  "wall_ms": 4831.2,
  "timestamp_utc": "2026-05-28T16:50:00.000000Z"
}
```

### Summary JSON
Per-arm pass rate, error count, average latency. Sortable.

## Cost estimate

Per full sweep across 13 cases × 11 arms = 143 calls. Typical session transcript ~1500 tokens in + 1000 tokens out per call.

| Provider | $/1M in | $/1M out | Per sweep est. |
|---|---|---|---|
| GPT-5 | ~$5 | ~$15 | ~$0.40 |
| Claude Sonnet 4.6 | ~$3 | ~$15 | ~$0.30 |
| Gemini 2.5 Pro | ~$1.25 | ~$5 | ~$0.10 |
| Grok 4 | ~$3 | ~$15 | ~$0.30 |
| DeepSeek V3 | ~$0.27 | ~$1.10 | ~$0.02 |

Full sweep: **~$1.10 in API costs**. Cheap. Run as many times as needed.

When the study expands to 100+ cases × 11 arms with multiple runs for statistical power, budget ~$20-50.

## Extending

### Add a new model
1. Add `ModelArm` to `arms.py`
2. If new provider, write a new adapter under `adapters/`
3. Register in `adapters/__init__.py`

### Add test cases
Extend `setup_services/evaluation/run_evaluation.py` `SAFETY_CASES` / `MODALITY_CASES` / `DIARIZATION_CASES`. Runner imports from there to keep the comparative study consistent with the existing eval.

### Add new scoring dimensions
Edit `runner.score_response()`. Each score component is a boolean — the overall `passed` flag is true iff all components are true.

## Statistical analysis (after the run)

For the paper, the JSONL output feeds standard statistical tests:

```python
import pandas as pd
import json
df = pd.DataFrame([json.loads(l) for l in open("results/study_xxx.jsonl")])

# Pass rate per arm:
df.groupby("arm_id")["score"].apply(lambda s: sum(r["passed"] for r in s) / len(s))

# Friedman test across arms (per-case repeated measures):
from scipy.stats import friedmanchisquare
pivot = df.assign(pass_int=df["score"].map(lambda s: int(s["passed"]))) \
    .pivot(index="case_name", columns="arm_id", values="pass_int")
friedmanchisquare(*[pivot[c] for c in pivot.columns])

# Pairwise McNemar (TherAssist vs each baseline):
from statsmodels.stats.contingency_tables import mcnemar
for arm in pivot.columns:
    if arm == "therassist-pipeline": continue
    table = pd.crosstab(pivot["therassist-pipeline"], pivot[arm])
    print(arm, mcnemar(table, exact=True))
```

## Status

| Phase | Status |
|---|---|
| Methodology decisions | ✅ committed (see paper §Methods) |
| Adapter framework | ✅ Complete (this code) |
| Test case set (13 baseline + expansion to 80-150) | 13 ready, expansion TODO |
| Run study | Awaiting expanded test cases + API key provisioning |
| Clinical scoring (blind) | Recruit 2-3 clinicians |
| Statistical analysis + write-up | Post-study |

Target journal: **JMIR Mental Health**.
