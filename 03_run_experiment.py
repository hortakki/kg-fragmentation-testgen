"""
03_run_experiment.py — GPT (OpenAI) Gherkin generation.

This is now a THIN WRAPPER around exp_core.py. All retrieval, evidence
filtering, context resolution, generation, persistence and caching logic
lives in exp_core so that the GPT and Claude runs are byte-identical except
for the provider/model. See exp_core.py for the full documentation of the
methodological fixes (A1-A7, G1-G6).

CLI is backward compatible with the original script and adds:
  --pipeline {full,no_resolution,no_retrieval}  ablation variants (RQ3)
  --repeat-index N                              intentional repeats for variance
  --keep-stale                                  disable the recency filter
  --llm-cache-dir / --data-cache-dir            caching (empty string disables)

Examples
--------
# main condition, hybrid retrieval, full pipeline
python 03_run_experiment.py --target-id R25 --mode hybrid --pipeline full

# ablation A0 (no retrieval, target text only)
python 03_run_experiment.py --target-id R25 --mode hybrid --pipeline no_retrieval

# ablation A1 (retrieval, but no LLM resolution layer)
python 03_run_experiment.py --target-id R25 --mode graph --pipeline no_resolution

# a second repeat for variance estimation (different cache slot)
python 03_run_experiment.py --target-id R25 --mode vector --repeat-index 1
"""

from exp_core import generation_main, OPENAI_MODEL

if __name__ == "__main__":
    # provider=openai, default model from env (gpt-4o-mini), default out dir "runs"
    generation_main(provider="openai", default_model=OPENAI_MODEL, default_out_dir="runs")
