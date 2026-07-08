"""
05C_evaluate_claude_structured_corr.py — Subjective (LLM-judge) evaluation,
Claude-default entry point.

THIN WRAPPER around exp_core.judge_main — the SAME judging code as 05_evaluate.py.
The only difference is the DEFAULT judge (anthropic / claude-haiku-4-5-...).

IMPORTANT — read before using for a cross-model comparison
----------------------------------------------------------
A separate Claude-default entry point exists only for convenience (e.g. when you
deliberately want a Claude judge). It does NOT mean "judge Claude outputs with
Claude and GPT outputs with GPT" — that was exactly the confound in the original
design (fix A2): the model comparison got entangled with judge identity and
self-preference bias.

For a VALID cross-model comparison you MUST use ONE judge for EVERY row of EVERY
generator model. Concretely, pick a single judge and run it once over both run
directories, e.g.:

    # one judge (GPT) over GPT + Claude runs  — recommended
    python 05_evaluate.py  --input "runs*/*.csv" --judge-provider openai    --judge-model gpt-4o-mini

    # or one judge (Claude) over GPT + Claude runs
    python 05C_evaluate_claude_structured_corr.py --input "runs*/*.csv"

Do NOT run 05 over GPT runs and 05C over Claude runs and then compare the two —
that reintroduces the confound. If the input mixes generator models, exp_core
warns you; if you truly want a Claude judge for everything, this entry point is
fine as long as it scores every row.

All other properties are identical to 05_evaluate.py: persisted-evidence only
(no rehydration, fix A7), deterministic composite overall_score (fix B2), failed
rows excluded from aggregates (fix A4), judge identity stamped on every row.

Examples
--------
# Claude judge over ALL runs (GPT + Claude), single judge:
python 05C_evaluate_claude_structured_corr.py --input "runs*/*.csv"

# override the specific Claude model:
python 05C_evaluate_claude_structured_corr.py --input "runs*/*.csv" --judge-model claude-haiku-4-5-20251001
"""

from exp_core import judge_main, CLAUDE_MODEL

if __name__ == "__main__":
    # Default judge = anthropic/CLAUDE_MODEL. Override via --judge-provider / --judge-model.
    # For a valid cross-model comparison, this judge must score EVERY row (both dirs).
    judge_main(default_judge_provider="anthropic", default_judge_model=CLAUDE_MODEL)
