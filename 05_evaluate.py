"""
05_evaluate.py — Subjective (LLM-judge) evaluation of generated Gherkin tests.

THIN WRAPPER around exp_core.judge_main. All judging logic lives in exp_core,
so GPT-judged and Claude-judged runs use byte-identical logic.

What changed vs. the original 05_evaluate.py
--------------------------------------------
* ONE judge for ALL rows (fix A2). The original design judged GPT outputs with
  GPT and Claude outputs with Claude, confounding the model comparison with
  the judge identity and self-preference bias. Here the judge is a SINGLE
  configuration applied to every row. This wrapper only sets the DEFAULT judge
  (openai/gpt-4o-mini); override it from the CLI so the SAME judge scores every
  generator model:
      --judge-provider {openai,anthropic}  --judge-model <model>
  If the input mixes rows from several generator models, the script warns you.
* Evidence comes ONLY from the persisted `evidenceText` column of the run CSVs
  (fix A7). No live Neo4j rehydration — the judge sees exactly the evidence the
  generator saw, with the same parameters.
* overall_score is computed deterministically in code as the mean of the six
  sub-scores (fix B2); the judge no longer "summarizes" it freely.
* Failed judge calls are recorded with evalStatus=failed and EXCLUDED from all
  aggregates (fix A4) — never averaged in as silent zeros.
* Every output row is stamped with judgeProvider / judgeModel / judgePromptVersion.

Examples
--------
# Judge ALL runs (GPT + Claude) with a single judge, e.g. GPT-4o-mini:
python 05_evaluate.py --input "runs/*.csv"

# Recommended for a clean cross-model comparison: point --input at BOTH dirs
# and use ONE judge for everything:
python 05_evaluate.py --input "runs*/*.csv" --judge-provider openai --judge-model gpt-4o-mini

# Use a third-family judge to avoid either model grading itself (see 05C for the
# Anthropic-default entry point; either way, pick ONE judge for the whole set).
"""

from exp_core import judge_main

if __name__ == "__main__":
    # Default judge = openai/gpt-4o-mini. Override via --judge-provider / --judge-model.
    # IMPORTANT: for a valid cross-model comparison, use the SAME judge for EVERY row.
    judge_main(default_judge_provider="openai", default_judge_model="gpt-4o-mini")
