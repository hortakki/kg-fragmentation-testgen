# Preregistration Addendum 3 — Third judge (DeepSeek), frozen before execution

Date: 2026-07-16. Status: FROZEN before any scoring of the analysis stratum by the third judge.
Motivation: pre-submission review items M2/M4b — with two judges the sign-reversal finding cannot
identify an outlier judge, and the GPT cross-judge carries a documented self-preference confound.
A third judge from a distinct model family resolves this regardless of outcome direction.

## Instrument
- Judge model: DeepSeek V4 Flash, via the official DeepSeek API (requested as the `deepseek-chat`
  alias; the provider dashboard confirms the served model id `deepseek-v4-flash`, and the model
  string returned in run logs is recorded as the authoritative identifier), no third-party
  quantized host. The corresponding open-weights checkpoint (Hugging Face) is cited for archival.
- Prompt: the frozen, blinded judge prompt PROMPT_VERSION 2026-07-05.v4, UNCHANGED. Temperature 0.
- Instrument note (provider capability): the DeepSeek API does not support `json_schema`
  structured output; requests use `json_object` instead, applied by a wrapper script
  (`05b_evaluate_thirdjudge.py`) that changes nothing else and does not modify the frozen
  `exp_core`. Schema conformance remains enforced by the frozen prompt and the pipeline's
  existing response validation (`evalStatus`).
- Format pilot (disclosed): on 2026-07-16, before this addendum was frozen, a format-compliance
  pilot ran on requirement R5 (60 rows; R5 is OUTSIDE the analysis stratum). All 60 rows returned
  `evalStatus=ok`. The pipeline's default console summary displayed R5 cell means, so the pilot
  was not fully output-blind; no stratum row was scored, and no analysis decision below was
  conditioned on any stratum outcome.

## Sample
The identical paired stratum defined in Addendum 2 (2026-07-11): 32 requirements
(16 with registered conflicts, 16 conflict-free), repeat-0, full pipeline, both generators —
the same ~1,889 test rows scored by the Gemini primary judge and the GPT-4o-mini cross-judge.
No sampling; the full stratum is scored. Attrition handling follows Addendum 1.

Requirement list (verbatim from the Addendum 2 stratum):
R1, R102d, R103d, R22, R25, R26, R31, R31b, R33, R43, R48, R49, R50, R51, R52c, R58c, R6,
R60c, R62, R63, R69, R70, R71, R71b, R72, R72b, R79b, R80, R81b, R83b, R87b, R93c.

## Pre-specified analyses (all reported as-is, whatever the direction)
A. Cell-mean mode ordering per judge on the stratum: averaged over all six dimensions and,
   separately, over the three context dimensions; within each generator.
B. Pairwise judge agreement: per-dimension ICC(2,1)-style agreement and cell-level Spearman,
   DeepSeek–Gemini and DeepSeek–GPT, using the same procedures as the existing cross-judge
   comparison.
C. Mode×conflict moderation on the third judge's scores (coverage, evidence_grounding,
   target_specificity): requirement-cluster-robust OLS with the study's standard convention
   (G−1 df, small-sample correction), parallel to the H3 and cross-judge analyses.
D. Criterion validity of the third judge against the objective human-validated reference,
   using the same procedure as the existing per-judge validity analysis.
E. Judge×mode two-way tests on the Haiku-generated subset (self-preference-free for all
   API-judge pairs involving the GPT judge; for DeepSeek, no generator overlap exists at all),
   parallel to §4.6.
Reporting rule: the third judge's alignment (with Gemini / with the GPT cross-judge / with
neither) is reported descriptively as an added robustness analysis; no confirmatory claim is
attached, and no result is omitted or reframed based on direction.

## Reliability arm (same session or immediately after)
Intra-rater re-judging of the standard 180-row ICC subsample (R1, R49, R62; judge-repeat 1),
mirroring the Gemini and GPT ICC procedure, so all three judges carry an internal-reliability
estimate.

## Execution discipline
Disk-cached calls with interruption-resume; outputs written ONLY under `evaluations/third_judge/`
(never the `evaluations/` root, per the 2026-07-16 glob-quarantine incident). This addendum is
git-committed BEFORE the stratum run; the commit hash is recorded in the manuscript's deviations
table (Appendix A).
