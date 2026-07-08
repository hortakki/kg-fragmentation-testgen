"""
06_objective_eval.py — Objective, document-grounded evaluation of generated
Gherkin tests. MODEL-AGNOSTIC: this is the single implementation for ALL
generator models (GPT and Claude alike).

THIN WRAPPER around exp_core.objective_main. This evaluator calls NO LLM — it
scores each test against a document/graph-derived reference — so there is no
per-provider variant to maintain (fix G6; the old 06 vs 06C split existed for
no good reason and had actually diverged, see below).

What changed vs. the original 06_objective_eval.py
--------------------------------------------------
* A1 — Support score is now honestly the supported-term ratio.
  The old formula support = 0.8*supported_ratio + 0.2*(1 - unsupported_ratio)
  was mathematically identical to `supported_ratio`, because there is no
  neutral term class (unsupported_ratio == 1 - supported_ratio). The numbers
  are unchanged; the reported metric now matches the code, and the paper text
  must be corrected to drop the neutral-term description. unsupported_ratio is
  also reported explicitly as its own column.
* A3 — ONE evaluator for both models. The old 06 and 06C differed by a single
  line (06C added nprops['name'] to frag_bits), which silently produced a
  DIFFERENT canonical reference — and therefore different Coverage/Support —
  for the two models. Here frag_bits uniformly includes 'name' for every model.
* A5 — the reference can be FROZEN and human-validated:
      1) build + export the heuristic draft:
         python 06_objective_eval.py --input "runs*/*.csv" --export-reference
      2) manually validate/correct the emitted reference_draft_*.json
         (set reference_status to "human_validated")
      3) evaluate against the frozen reference:
         python 06_objective_eval.py --input "runs*/*.csv" --reference-json reference.json
  Only step (3) yields the paper's actual "Resolved Reference Set". Without
  --reference-json the tool prints a warning and uses the heuristic draft.
* A6 — --max-neighbor-hops defaults to 2, matching generation-time graph depth
  (the old default of 1 systematically penalized graph mode by scoring its
  2-hop content against a 1-hop reference).
* B1 — coverage-match thresholds are CLI-configurable for a sensitivity
  analysis (--match-min-ratio, --match-min-tokens); defaults reproduce the old
  behavior so existing numbers are comparable.
* Metadata — summaries group by model x mode x pipeline, and every run writes a
  *_metadata.json capturing thresholds, weights, hop depth and reference status.

Examples
--------
# quick pass with the on-the-fly heuristic reference (draft; prints a warning):
python 06_objective_eval.py --input "runs*/*.csv" --docs-dir docs

# 1) export the heuristic reference for manual validation, then stop:
python 06_objective_eval.py --input "runs*/*.csv" --docs-dir docs --export-reference

# 3) evaluate against the frozen, human-validated reference (paper-grade):
python 06_objective_eval.py --input "runs*/*.csv" --reference-json reference.json

# coverage-threshold sensitivity analysis (fix B1):
python 06_objective_eval.py --input "runs*/*.csv" --reference-json reference.json \
    --match-min-tokens 3 --match-min-ratio 0.40
"""

from exp_core import objective_main

if __name__ == "__main__":
    objective_main()
