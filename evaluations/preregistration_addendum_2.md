# Preregistration Addendum 2 — Cross-judge sample

**Date:** 2026-07-11
**Status:** Filed before any cross-judge (GPT) evaluation was run. Gemini-judge results existed at this point; the cross-judge sample selection rule is fixed here to prevent post-hoc selection.

## A1. Purpose
The cross-judge round tests whether the Gemini-judge findings — in particular the reversed conflict moderation (H3) and the test-level divergence exemplars (H2) — replicate under an independent judge (GPT-4o-mini), addressing the judge-bias alternative explanation.

## A2. Sample selection rule (fixed before execution)
Repeat-0, full-pipeline rows only; both generator models; judged with the identical frozen prompt chain (PROMPT_VERSION 2026-07-05.v4), judge-side blinding unchanged.

1. **All 16 requirements with recorded conflicts** (n_conflicts > 0 in the graph moderator export): R1, R102d, R103d, R33, R43, R49, R50, R51, R58c, R60c, R63, R70, R71, R72b, R79b, R80. Full coverage of the conflict stratum — the H3 interaction is the primary replication target.
2. **16 conflict-free requirements**, deterministic seeded sample (seed 20260711) from the 49 conflict-free requirements: R22, R25, R26, R31, R31b, R48, R52c, R6, R62, R69, R71b, R72, R81b, R83b, R87b, R93c.
3. Dry-run verified: 1,889 rows (cells 300–320), estimated cost <$1 (GPT-4o-mini).

## A3. Preregistered cross-judge analyses
- Re-estimate the H3 mode×conflict interaction on cross-judge scores (same cluster-robust OLS specification).
- Inter-judge agreement per dimension (ICC / correlation) on the overlapping rows.
- Divergence-exemplar check: do the top Gemini-divergence tests also receive low grounding from the cross-judge?
Outcomes are reported regardless of direction; replication failure would be reported as a judge-dependence finding (consistent with the pilot).
