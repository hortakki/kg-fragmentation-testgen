"""
03c_run_experiment_claude_structured.py — Claude (Anthropic) Gherkin generation.

THIN WRAPPER around exp_core.py. Identical logic to the GPT generator
(03_run_experiment.py); the ONLY differences are provider="anthropic",
the default model, and the default output directory ("runs_haiku").

Because both generators call the same exp_core code path, the GPT and Claude
runs differ only by provider/model — no divergent retrieval, filtering,
resolution or persistence logic (this was the root cause of the old
03 vs 03c drift). See exp_core.py for the full fix documentation (A1-A7, G1-G6).

Caching (important for Claude — it is the more expensive provider):
  * Response-level LLM cache is ON by default (--llm-cache-dir, default cache/llm).
    Key = provider+model+system+user+schema+PROMPT_VERSION+repeat_index, so a
    re-run with the same inputs is free, while an intentional repeat
    (--repeat-index N) always makes a fresh call.
  * Anthropic prompt caching is applied automatically to the (stable) system
    prompt via cache_control=ephemeral inside exp_core.LLMClient — this reduces
    input-token cost across the many calls that share a system prompt.
  * The same caching is available to GPT too (harmless, just cheaper reruns).

To DISABLE the response cache (e.g. to force fresh calls), pass an empty
string: --llm-cache-dir "".

Examples
--------
# main condition, hybrid retrieval, full pipeline (cache on by default)
python 03c_run_experiment_claude_structured.py --target-id R25 --mode hybrid --pipeline full

# balanced design: run Claude on ALL requirements, same as GPT
#   (loop over R1..R65 in your runall script, mode in {graph,vector,hybrid})

# ablation A0 / A1
python 03c_run_experiment_claude_structured.py --target-id R25 --mode hybrid --pipeline no_retrieval
python 03c_run_experiment_claude_structured.py --target-id R25 --mode graph  --pipeline no_resolution

# variance repeat (fresh call, separate cache slot)
python 03c_run_experiment_claude_structured.py --target-id R25 --mode vector --repeat-index 1
"""

from exp_core import generation_main, CLAUDE_MODEL

if __name__ == "__main__":
    # provider=anthropic, default model from env (claude-haiku-4-5-...), out dir "runs_haiku"
    generation_main(provider="anthropic", default_model=CLAUDE_MODEL, default_out_dir="runs_haiku")
