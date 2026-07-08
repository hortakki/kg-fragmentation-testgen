"""
05G_evaluate_gemini.py — Subjective (LLM-judge) evaluation with a NEUTRAL,
third-family judge: Google Gemini.

THIN WRAPPER around exp_core.judge_main — the SAME judging code as 05/05C.
The only difference is the DEFAULT judge provider ("gemini").

Why a Gemini judge
------------------
The two generators are OpenAI (GPT) and Anthropic (Claude). A judge from EITHER
of those families risks self-preference bias (a model rating its own family's
outputs higher). Gemini belongs to neither family, so it is the cleanest choice
for a Q1-grade cross-model comparison: NEITHER generator is graded by its own
family. Use ONE Gemini judge for EVERY row of BOTH generators.

All other guarantees are identical to 05/05C: persisted-evidence only (no
rehydration, fix A7), deterministic composite overall_score (fix B2), failed
rows excluded from aggregates (fix A4), judge identity stamped on every row.

Requirements
------------
    pip install google-genai
    # .env:  GEMINI_API_KEY=...   (GOOGLE_API_KEY also accepted)
    #        GEMINI_MODEL=gemini-2.5-flash   (override per run; see note below)

Model choice note
-----------------
Google's model lineup moves fast. As of mid-2026 `gemini-2.5-flash` is a stable,
widely available default; stronger 3.x / 3.5 Flash models also exist. Pick the
model at run time with --judge-model (or GEMINI_MODEL in .env) — do NOT hardcode
a fast-moving name into the paper without checking it is still current. A single,
fixed model must score the whole set; record it (it is stamped on every row and
in the run metadata).

Examples
--------
# Gemini judge over ALL runs (GPT + Claude), single neutral judge:
python 05G_evaluate_gemini.py --input "runs*/*.csv"

# pin a specific Gemini model for the whole set:
python 05G_evaluate_gemini.py --input "runs*/*.csv" --judge-model gemini-2.5-flash

# robustness cross-check: also judge everything with GPT and with Claude, then
# compare the strategy/model ranking across the three judges:
python 05_evaluate.py                        --input "runs*/*.csv"   # GPT judge
python 05C_evaluate_claude_structured_corr.py --input "runs*/*.csv"  # Claude judge
python 05G_evaluate_gemini.py                 --input "runs*/*.csv"  # Gemini judge
"""

from exp_core import judge_main, GEMINI_MODEL

if __name__ == "__main__":
    # Default judge = gemini/GEMINI_MODEL. Override via --judge-provider / --judge-model.
    # For a valid cross-model comparison, this ONE judge must score EVERY row (both dirs).
    judge_main(default_judge_provider="gemini", default_judge_model=GEMINI_MODEL)
