# Preregistration Addendum 1

**Date:** 2026-07-09
**Status:** Filed after the original preregistration commit, before any paid LLM-judge evaluation was run. No judge scores existed at the time of this addendum.

## A1. Completion of manual reference validation

The original preregistration specified a human-validated canonical-point reference for the objective (docs-based) evaluation. This validation is now complete:

- Source: heuristic draft export `reference_draft_20260707_183716.json` (65 requirements, 642 canonical points, status `heuristic_draft`).
- Procedure: every canonical point was reviewed line-by-line via an export–edit–rebuild workflow (`09_reference_validate.py`). Items carrying no requirement content (e.g., standalone author names leaked from ticket comments) were removed. No points were reworded to favor any model or pipeline; edits were deletions of noise only.
- Result: 642 → **622 canonical points** (−20 noise items removed). All 65 requirements set to `reference_status = human_validated`. Frozen as `evaluations/reference.json`.
- The objective evaluation was re-run against the frozen validated reference before any LLM-judge scoring. The heuristic draft is retained unchanged for audit purposes.

## A2. Attrition rule for malformed generator outputs

- During objective evaluation, a validity check excludes tests with empty or structurally malformed Gherkin (unparseable output from the generator models).
- Observed attrition: **126 of 14,300 tests (0.88%)**. All 1,430 experimental cells remain populated; attrition occurs at the individual-test level only.
- Breakdown (model / pipeline): claude vector −9; gpt graph −11; gpt hybrid full −8; gpt hybrid no_resolution −2; gpt vector −26 (repeat 0); remainder in repeats 1–2. The asymmetry between generator models will be reported as a secondary format-compliance outcome.
- These excluded tests are likewise not submitted to the LLM judge (they carry no judgeable content).
- **Planned sensitivity analysis:** primary hypothesis tests (H1–H2) will be re-run with excluded tests imputed as worst-case zero scores; conclusions will be reported under both treatments.

## A3. What is unchanged

- Generation data (1,430 cells / 14,300 tests, v3) — frozen, untouched.
- Judge chain `PROMPT_VERSION=2026-07-05.v4` — frozen, untouched.
- All hypotheses (H1, H2, decomposed H3, H4 Option 1), the subsample (seed 20260705: R1, R5, R7, R29, R31b, R49, R51, R62, R63, R103d), moderators, and analysis plan — unchanged from the original preregistration.
