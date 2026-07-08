"""
06C_objective_eval_claude.py — DEPRECATED.

The objective evaluation is MODEL-AGNOSTIC: it calls no LLM and scores tests
against a document/graph-derived reference, so there is no Claude-specific
variant. The original separate 06C had, in fact, silently DIVERGED from 06 by
one line (it added nprops['name'] to frag_bits), producing a different
canonical reference and therefore different Coverage/Support for Claude vs. GPT
(fix A3). That class of bug is exactly why a second file must not exist.

This module is kept ONLY so that existing pipelines / runall scripts that call
`python 06C_objective_eval_claude.py ...` keep working. It re-exports the single
implementation from exp_core and prints a deprecation notice. Prefer 06_objective_eval.py.

The correct way to evaluate Claude runs is to point the ONE evaluator at them
(or at both run directories at once):

    python 06_objective_eval.py --input "runs_haiku/*.csv" --reference-json reference.json
    python 06_objective_eval.py --input "runs*/*.csv"      --reference-json reference.json
"""

import sys
from exp_core import objective_main, log

if __name__ == "__main__":
    log.warning(
        "06C_objective_eval_claude.py is DEPRECATED. The objective evaluator is "
        "model-agnostic; use 06_objective_eval.py. Delegating to the same implementation."
    )
    objective_main()
