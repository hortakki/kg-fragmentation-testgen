# Result provenance map

This map connects the reported study quantities to the files and implemented
calculations in `hortakki/kg-fragmentation-testgen`. The documented code/data
baseline is commit `53a4ebe47e75a988fd301d6a43707aa888345f41`, checked on
2026-09-19. Section references follow the supplied manuscript inventory;
figure numbers below follow the actual repository exports. Check section
numbering against the manuscript version accompanying a release.

Archive DOI: [10.5281/zenodo.22646533](https://doi.org/10.5281/zenodo.22646533).
Author / maintainer ORCID:
[0009-0003-9766-6684](https://orcid.org/0009-0003-9766-6684).
These identifiers were supplied by the author. The Git baseline above
identifies the files checked for this map; consult the archive record for
the version and files associated with the DOI.

**In Git** means present at that baseline. **Outside Git** identifies a file
excluded from the public package. The large raw evaluation files are held
only on the author's local computer because of upload constraints and have
no public download location. **Console output** identifies a script's printed
results for which no separate historical transcript is archived in the package.
An unsaved transcript cannot be recovered from the fact that the script exists.
Where the original inputs and code survive, a new, separately dated execution
can check the numerical result. **Unresolved provenance** records the limits
of the available historical evidence. Arithmetic derivations are described
explicitly and do not require a separate script for each number.

## Input identifiers

| Short name | Exact file or dataset | Scope |
|---|---|---|
| G6444 | `evaluations/llm_eval_runs_.csv_20260711_060531.csv` | Main Gemini detail file, 6,444 repeat-0 rows across all pipelines; retained on the author's local computer only, without a public download. |
| G3846 | `llm_eval_runs_.csv_20260710_172326.csv` | Original 3,846-row Gemini full-pipeline detail file, retained locally only; its ignore entry uses `evaluations/superseded/`. |
| H1 | `h1_export.csv` | In Git: 3,846 full-pipeline repeat-0 rows, all six Gemini dimensions, keyed by `reqId`, `testId`, `mode`, `model`. |
| H2 | `h2_export.csv` | In Git: the same 3,846 rows with `coverage_score`, `support_score`, `objective_score`. |
| GPT | `evaluations/cross_judge/llm_eval_runs_.csv_20260711_163447.csv` | In Git: 1,889 GPT cross-judge rows. |
| DS | `evaluations/third_judge/llm_eval_runs_.csv_20260716_220053.csv` | In Git: 1,889 DeepSeek rows. |
| OBJ | `evaluations/objective_evaluation_details_runs_.csv_20260709_183209.csv` | Outside Git: 14,174 frozen-reference objective detail rows; summary and metadata in Git. |
| MISS | `analysis/miss_decomposition.csv` | In Git: 6,444 repeat-0 rows of per-test overall/type-specific miss counts. |
| TYPED | `typed_elements.json` | In Git: 203 typed elements over 65 requirements. |
| REF | `evaluations/reference.json` | In Git: 622 canonical objective-reference points. |

Raw evaluation joins use
`reqId + testId + mode + pipeline + model + repeatIndex`.
Here `model` identifies the generator; judge identity must be kept separate.
H1/H2 omit the pipeline/repeat columns because their exported scope is already
restricted to full pipeline and repeat 0. Their four-column keys are unique.
The GPT and DS keys are identical, and all 1,889 have corresponding rows in H1.
The existing script 16 expects the full raw evaluation schema; H1 requires a
documented schema adaptation before being passed to that script.

## Design and requirement set

| Reported quantity | Procedure or implementation | Inputs | Evidence and status |
|---|---|---|---|
| 65 non-contiguous requirement identifiers | Explicit `$DefaultReqs` in `runall.ps1`; keys of TYPED | Requirement documents and typed-element export | In Git; the two lists match exactly. No separate `docs/executed_requirements.txt` is required to recover the list. |
| 1,430 generation cells | `runall.ps1` / `runall.sh` → `03_run_experiment.py`, `03c_run_experiment_claude.py` | 65 requirements, two generators; three full modes with three repeats; two hybrid ablations with one repeat | `runs/` and `runs_haiku/`: 715 CSVs each, with metadata and resolved JSONs; all planned cells present. |
| 14,300 planned test slots and 14,174 saved test rows | Count parsed rows across the 1,430 generation CSVs | Saved generation CSVs | 7,033 GPT + 7,141 Haiku = 14,174. The design asks for 10 tests per cell; it does not establish that all 14,300 were saved. |
| 126 missing slots, 0.881%; 37 underfilled cells | Arithmetic: 14,300 − 14,174; sum cell shortfalls | Generation CSVs and `analysis/missing_cells_report.csv` | Reconstructible from Git. Counts alone do not establish each missing slot's failure cause or retry history. |
| Repeat-0 shortfall: 56 = 47 GPT + 9 Haiku | Arithmetic: 6,500 planned − 6,444 saved | Repeat-0 generation rows | Reconstructible from Git. Full-pipeline repeat-0 shortfall is separately 3,900 − 3,846 = 54. |
| Historical retrieval configuration | Per-cell generation metadata; `exp_core.py` implements retrieval | Neo4j, embedding/index configuration | All 1,430 metadata files record `top_k=15`, `max_hops=2`, `limit=40`, `chunks_per_node=3`, prompt/pipeline `2026-07-03.v3`. Embedding model `text-embedding-3-small`, index `srcChunkEmb`. |

## References and objective evaluation

| Reported quantity | Script or calculation | Inputs | Output and status |
|---|---|---|---|
| 642 → 622 canonical reference points (§3.4) | `09_reference_validate.py`; direct draft/final comparison | `evaluations/reference_draft_20260707_183716.json`, `reference_review.txt` | REF, in Git. Comparison yields 20 removed points and no added points. The review file is also in Git. |
| Typed-element ground truth (§3.4) | `08_export_typed_elements.py`; `19_provenance_audit.py` compares typed versions | Neo4j relation information; `typed_elements_draft.json` | TYPED, in Git: local 65, conflict 18, refine 48, cross_module 68, supersede 4; total 203. |
| Objective scores, frozen reference (§4.7) | `06_objective_eval.py` / `06C_objective_eval_claude.py`, scorer in `exp_core.py` | Generation CSVs + REF | OBJ outside Git; `evaluations/objective_evaluation_summary_runs_.csv_20260709_183209.csv` and matching metadata in Git. H2 supplies the full-pipeline subset's three scores. |
| Earlier draft-reference objective scores | Same evaluator with the draft reference | Generation CSVs + draft reference | Detail CSV outside Git; summary/metadata in `evaluations/objective/`. |
| Objective matching and pass rule | Recorded evaluator parameters | Point/test/evidence tokens | Coverage hit: ratio ≥ 0.25 OR shared tokens ≥ 2. Pass minima: coverage 0.15, support 0.50. Coverage/support weights: 0.55/0.45. |

The objective details are reconstructible without new model calls from the
saved generation records and reference. A reconstructed file must be labelled
with its new execution date; agreement with the historical summaries does not
establish byte identity with the original detail CSV.

## Judge evaluation and reliability

| Reported quantity | Script or calculation | Inputs | Output and status |
|---|---|---|---|
| R1 pilot, 220 evaluated rows (§3.5) | `05G_evaluate_gemini.py`; pilot described in `preregistration.md` | R1 generation cells, judge prompt `2026-07-05.v4` | `evaluations/superseded/llm_eval_runs__R1_.csv_20260705_190136.csv`; summary and metadata in Git. |
| Six reported smoke gates (§3.5) | Historical gate procedure not identified | R1 pilot and any original gate records | Unresolved provenance: separate gate definitions and recorded pass/fail results are not included. |
| R1 repeat-0 re-pass, 100 rows (§3.5) | `05G_evaluate_gemini.py` | R1 repeat-0 cells | `evaluations/superseded/llm_eval_runs_.csv_20260709_185718.csv`; in Git. |
| Main Gemini evaluation, 6,444 rows (§4) | `05G_evaluate_gemini.py` | Repeat-0 generation rows across pipelines | G6444 outside Git; summary and metadata in Git. |
| Full-pipeline Gemini evaluation, 3,846 rows | Same evaluator, full-pipeline scope; `export_h1h2.py` creates compact analysis exports | Main judge and explicit frozen objective detail inputs | G3846 outside Git; H1 and H2 in Git. No `tools/derive_full_pipeline_subset.py` is included. |
| Generator-variance subsample, 1,189 rows (§3.6) | `05G_evaluate_gemini.py`; subsample selection in `07_hypothesis_analysis.py` | Registered ten-requirement subsample, repeats 1–2 | `evaluations/llm_eval_runs_.csv_20260711_084929.csv` (594) and `..._20260711_102827.csv` (595); in Git. |
| Gemini intra-rater comparison, 180 rows (§3.6) | `10_intra_rater_icc.py` | Main Gemini pass and R1/R5/R7 rejudge | `evaluations/icc/llm_eval_runs_.csv_20260711_112052.csv` in Git; ICC/agreements printed to console. |
| GPT cross-judge comparison, 1,889 rows (§3.6 / §4.6) | `05_evaluate.py` | Addendum 2 stratum | GPT detail/summary in `evaluations/cross_judge/`; run metadata retained at the `evaluations/` root. |
| GPT intra-rater comparison, 178 rows | Generic pairing/ICC implementation in `10_intra_rater_icc.py` | GPT main pass and `evaluations/icc_gpt/llm_eval_runs_.csv_20260714_160642.csv` | Both score passes are in Git. A separate historical ICC transcript is not archived; the script can produce a new comparison from the saved inputs. |
| DeepSeek third-family evaluation, 2,127 calls (§3.6 / §4.6) | `05b_evaluate_thirdjudge.py` | Frozen judge prompt and Addendum 3 sampling plan | `evaluations/third_judge/` (1,889), `third_judge_icc/` (178), `third_judge_pilot/` (60); detail, summary and metadata in Git. |
| DeepSeek intra-rater comparison, 178 rows | `10_intra_rater_icc.py` | DS main pass and `evaluations/third_judge_icc/llm_eval_runs_.csv_20260716_221917.csv` | Both passes in Git; comparison is console output. |
| Author-reported study costs (§3.8) | Reported components: USD 60.46 + USD 3.80 + USD 2.70 = USD 66.96, approximately USD 67 | Monetary amounts stated in the supplied manuscript inventory | Reported cost summary. An itemized billing/per-call cost record is not supplied, so independent cent-level verification is unavailable. No billing document or console transcript is reconstructed retrospectively. |
| Main Gemini / variance / Gemini rejudge count, 7,813 (§3.8) | Arithmetic: 6,444 + 594 + 595 + 180 = 7,813 | Main, repeat-1, repeat-2 and Gemini rejudge run totals | Traceable to recorded counts. This count covers the named passes and is separate from the monetary cost evidence. |

DeepSeek metadata records the requested model alias `deepseek-chat`. Addendum 3
describes the served model as DeepSeek V4 Flash. The requested alias and that
historical model attribution should remain distinct; a provider-returned model
identifier or retained run record is the evidence for the served version.

## Statistical analyses

| Result | Script or calculation | Inputs | Output and status |
|---|---|---|---|
| H1 mode-by-dimension descriptives (§4.2) | `07_hypothesis_analysis.py::run_h1` | Judge rows, restricted to full pipeline/repeat 0 | `analysis/h1_mode_by_dimension.csv`; in Git. This function computes descriptives, not the later models. |
| H1 per-dimension models, contrasts, CIs and Holm (§4.2) | `h1_confirmatory.py` | H1 + H2 | `analysis/h1_mixedlm_results.csv`, `analysis/h1_contrasts.csv`, `analysis/h1_metadata.json`; in Git. |
| Cell-median paired H1 analysis (§4.2) | Cell-median Wilcoxon branch of `h1_confirmatory.py` | H1 + H2; cells defined by requirement × generator × mode | `analysis/h1_sensitivity.csv`; in Git. The implemented workflow labels this a sensitivity analysis. |
| TOST at standardized margins 0.1 / 0.2 / 0.3 (§4.2) | `17_sesoi_sensitivity.py` | `analysis/h1_contrasts.csv`: averaged contrasts, raw SE, within-cell pooled SD | `analysis/sesoi_sensitivity.csv`; in Git. Wald/normal TOST, raw margin = standardized margin × pooled SD; maximum of the two one-sided p-values. |
| H2 divergence (§4.7) | `07_hypothesis_analysis.py::run_h2`; divergence = z(objective support) − z(judge grounding) | Paired full-pipeline judge/objective rows | `analysis/h2_divergence_by_mode.csv`, `analysis/divergence_exemplars.csv`; in Git. H1/H2 contain the numerical inputs for this sample, but the existing loader expects raw evaluation files. |
| H3 analysis table (§4.4) | `07_hypothesis_analysis.py::run_h3` | Full-pipeline judge rows and graph moderators | `analysis/h3_analysis_table.csv`; in Git. The function exports data but does not fit the models named in its metadata. |
| Main H3 conflict-moderation regressions (§4.4) | Exact original fitting implementation not identified | `analysis/h3_analysis_table.csv` | Unresolved provenance. The related judge-interaction script below is not a substitute for the original main H3 model. |
| Judge × mode × conflict; six-term Holm family (§4.6) | `row5_judge_dependence_holm.py` | `analysis/h3_analysis_table.csv` + GPT | Console output: coefficients, raw/adjusted p-values and restricted wild-cluster bootstrap p-values. Seed 20260712, 999 Rademacher resamples at requirement level. |
| Within-judge-z, judge × mode Holm family (§4.6) | `row5_judge_dependence_holm.py` | Same paired 1,889-test stratum | Console output; six terms corrected within the family. |
| Generator-subset judge × mode checks | `15_haiku_only_judge_mode.py` | Main Gemini + GPT scores | Console output for Haiku, GPT and pooled subsets, with raw and within-judge-z outcomes. |
| Three-judge robustness analyses (§4.6) | `16_third_judge_analysis.py` | Main Gemini, GPT, DS and H2 | `analysis/third_judge_analysis.json`, in Git: `A_orderings`, `B_agreement`, `C_moderation`, `D_criterion`, `E_haiku_only`. |
| Six-dimension / context / formal composites (Appendix A.3) | Six- and three-dimension means in script 16; formal = 2 × six-dimension mean − context mean | `analysis/third_judge_analysis.json::A_orderings` | Numerical means in Git; the formal composite is an explicit arithmetic derivation. Use unrounded scores for higher precision. |
| Gemini six-dimension graph−vector contrasts +0.114 and +0.046 | Arithmetic on saved `A_orderings` | Haiku: 4.487 − 4.373; GPT: 3.574 − 3.528 | Reproduced from the rounded saved means; no separate contrast output is needed to identify this derivation. |
| Class-level omnibus, 23,076 observations (§4.2) | `H1_analysis_plan.txt` identifies the long-format model `score ~ mode × dimension_class + model`; executed fitting script not identified | H1: 3,846 tests × six dimensions | Unresolved provenance for fitted estimates/output. The long-format row count is derivable; it does not reproduce the model's inferential results. |
| Resolution ablation paired analysis | `wilcoxon_stat_test.py` | MISS, hybrid full vs no_resolution; requirement-level means of integration-miss counts divided by ground-truth element counts, paired within generator | `analysis/resolution_ablation_wilcoxon.csv`; in Git. |
| Attrition sensitivity (§4.3) | `11_sensitivity_attrition.py` | Actual files matching `evaluations/llm_eval_runs_*.csv`, filtered to successful full-pipeline repeat-0 rows | Console output; historical resolved file list and transcript are not archived in the package. A new run requires an explicitly recorded input set. Worst-case imputation uses 1 on the 1–5 scale; overlapping passes must not be counted twice. |

H1 metadata records `score ~ mode * generator`, with a requirement random
intercept and REML estimation, and an OLS requirement-cluster fallback where
needed. The saved primary contrasts use the averaged graph−vector and
hybrid−vector comparisons over the three context dimensions as their six-test
Holm family. The archived plan, implemented analysis and final manuscript's
designation of primary versus sensitivity tests must be read together.

## Coverage and miss decomposition

| Result | Script or calculation | Inputs | Output and status |
|---|---|---|---|
| Per-test typed-element misses, 6,444 rows (§4.3) | `07_hypothesis_analysis.py::run_h4` | Typed reference + judged rows carrying Gherkin/evidence text | MISS, in Git. Normalized element-token overlap threshold 0.5. Counts are saved; element-by-test identities are not. |
| 93.1% local-suite coverage; 27/390 local misses (§4.3 / Table 4) | `row11_generator_paired_test.py`; group full rows by requirement × mode × generator and require all tests to miss the local element | MISS; exactly one local element per requirement | Console output and assertion of 390 suites / 27 misses. Arithmetic: 1 − 27/390 = 0.930769. |
| Generator difference, intervals and paired tests (§5.1) | `row11_generator_paired_test.py` | Local-suite indicators from MISS, 195 paired generator cells | Console output: Clopper–Pearson intervals, requirement-level sign/Wilcoxon tests, 20,000-resample requirement bootstrap (seed 20260719), and McNemar sensitivity. |
| Overall suite non-coverage 27–47% (§4.3 / discussion) | `14_review_response.py`, block A | Full-pipeline repeat-0 Gherkin/evidence texts and TYPED | `analysis/review_response.json::suite_h4`; in Git. Tokens are pooled across the suite before applying the 0.5 element threshold. |
| Type denominators across six conditions | Arithmetic from TYPED | 65 local, 18 conflict, 48 refine, 68 cross_module, 4 supersede | 390 + 108 + 288 + 408 + 24 = 1,218 = 203 × 6. |
| No-resolution decomposition and retrieval saturation | `14_review_response.py`, blocks B/C | Judged texts and TYPED | `analysis/review_response.json`: `no_resolution`, `saturation`, `position`; in Git. |

The precise overall-suite values saved under `suite_h4` are:

| Generator | Retrieval mode | Covered elements / 203 | Coverage | Non-coverage |
|---|---|---:|---:|---:|
| Haiku | graph | 148 | 72.906% | 27.094% |
| Haiku | hybrid | 147 | 72.414% | 27.586% |
| Haiku | vector | 124 | 61.084% | 38.916% |
| GPT-4o-mini | graph | 116 | 57.143% | 42.857% |
| GPT-4o-mini | hybrid | 112 | 55.172% | 44.828% |
| GPT-4o-mini | vector | 107 | 52.709% | 47.291% |

Non-coverage is `100 − coverage`. The rounded endpoints are therefore 27% and
47%. This calculation covers all typed elements in the broader graph
neighbourhood. The 6.9% local result covers the one local element per requirement
and uses the individual-test match rule described above. These measures differ
in both scope and aggregation order; they should not be substituted for one
another. Script 14's introductory “any test” wording is less precise than its
implemented pooled-token rule.

## Human validation and audit trail

| Result or record | Script or procedure | Inputs | Output and status |
|---|---|---|---|
| First-author matcher validation | `12_matcher_validation.py`; export seed 20260712; manual decisions | Sampled integration-miss test–element pairs | `analysis/matcher_validation_sample_human_verdict.csv`: 100 parsed records, 72 TRUE_MISS, 23 PARTIAL, 5 PARAPHRASE. The inventory's earlier “629 rows” does not describe this CSV's record count. |
| Second-annotator reference validation | `13_m2_interannotator.py`, export/kappa modes; seed 20260713 | Draft/final reference comparison and answer key | `m2_annotation/A_reference.csv`: 65 exported, 64 answered; item 65 blank. `_answer_key.json` in Git. Kappa is console output. |
| Second-annotator type classification | Same script and seed | Typed-element sample | `m2_annotation/B_typed.csv`: 40 answered records; in Git. |
| Second-annotator matcher subset | Same script and seed | First-author matcher-validation sample | `m2_annotation/C_m1.csv`: 30 answered records; in Git. |
| Evidence-presence sample, 90 items | `13_evidence_presence_validation.py`; seed 20260714, 30 per mode | Element/evidence pairs from the judge-text inputs | `analysis/evidence_presence_sample.csv` and reviewed versions; in Git. |
| Conflict/supersede sample, 60 items | `14_conflict_supersede_misses.py`; seed 20260715 | Sampled test–element pairs | `analysis/conflict_supersede_sample.csv` and reviewed versions; in Git. |
| Third- and fourth-author post-freeze returns | Independent annotation of the existing 90/60 exports; commit `325614f` | Same sample files and verdict categories | `analysis/evidence_presence_sample_adjudicated_third.csv`, `..._fourth.csv`; `analysis/conflict_supersede_sample_adjudicated_third.csv`, `..._fourth.csv`; in Git, as received. |
| Validation sample provenance audit | `audit_validation_pipeline.py`, `audit_validation_pipeline_v2.py` | Main judge details and original reviewed samples | `analysis/validation_pipeline_audit/`; in Git. Its audit reports 90/90 and 60/60 source matches, with 48 full-pipeline and 12 no-retrieval records in the original 60-item sample. |

The post-freeze return files have an additional physical-line CSV quoting layer.
Normalizing that layer restores 90 and 60 correctly shaped records for each
annotator. The original returns should be retained; normalized copies and any
new agreement calculations should be identified separately. The earlier
`validation_pipeline_audit` outputs should not be presented as agreement
calculations on the later third/fourth-author returns.

## Figures

| Repository figure | Content actually implemented | Plotting source | Input | Output in Git |
|---|---|---|---|---|
| 1 | Experimental design and evaluation overview | `20_make_figures.py` / `20b_make_figures.py` | Design constants in the scripts | `figures/fig1_design.pdf`, `.png` |
| 2 | Per-test miss decomposition and integration share by element type | Same two plotting variants | MISS, restricted to full pipeline | `figures/fig2_miss_decomposition.pdf`, `.png` |
| 3 | Pairwise three-judge ICC and cell-mean Spearman agreement | Same two plotting variants | `analysis/third_judge_analysis.json::B_agreement` | `figures/fig3_judge_agreement.pdf`, `.png` |
| 4 | Judge-dependent mode rankings by generator, using the six-dimension composite | `21_fig4_mode_rankings_by_judge.py` | `analysis/third_judge_analysis.json::A_orderings`, `DIMSET="6dim"` | `figures/fig4_mode_rankings_by_judge.pdf`, `.png` |
| 5 | Mean uncovered elements per test, by type, generator and retrieval mode | `22_fig5_suite_noncoverage_by_element_type.py` / `22b_fig5_suite_noncoverage_by_element_type.py` | MISS, full pipeline; type-specific retrieval + integration miss counts | `figures/fig5_suite_noncoverage_by_element_type.pdf`, `.png`; additional `_a` export also present. |

Figure 4 subtracts each judge's mean across the three retrieval modes. It does
not implement within-judge z standardization or bootstrap confidence intervals.
Figure 5 is a **per-test mean count** despite “suite” in its filename; it is not
the 27–47% suite-union calculation. Select the final layout variant and align
the manuscript captions with the actual plotted quantities.

## Execution history and integrity

| Record | Available evidence | Limitation |
|---|---|---|
| Initial preregistration | Tag `preregistration-freeze-2026-07-08` → `5679865` | Distinguish the tagged plan from later analysis changes. |
| Later H1 plan and Addendum 3 | Both files in Git; late-tracking disclosure `e3630e5` | No pre-execution Git hash was retained for these files, according to the disclosure. |
| Freeze and later annotations | Freeze commit `6b68982`; returned annotations `325614f` | The later annotations are post-freeze evidence. |
| H1 numeric input integrity | `analysis/h1_metadata.json` hashes H1 and H2 | Hashes match CRLF input bytes; LF checkout normalization changes byte hashes. |
| Older descriptive metadata | H1 descriptive and H2 divergence `.metadata.json` files | H1 hashes only one matched judge file; H2 stores `joined` instead of hashes. |
| Full release integrity | Git identifies tracked content at the documented commit | A package-wide SHA-256 manifest and external-data checksums are not included. |
| Archive identifier | Author-supplied DOI [10.5281/zenodo.22646533](https://doi.org/10.5281/zenodo.22646533) | The archive's own file/version inventory defines its coverage; the DOI does not imply that local-only files are public. |
| Author / maintainer identifier | ORCID [0009-0003-9766-6684](https://orcid.org/0009-0003-9766-6684) | Supplied by the author; does not replace any coauthor attribution or a final paper citation. |
| Large raw evaluation exports | Retained on the author's local computer because of upload constraints | No public download is available. Some raw-data reanalyses therefore require the locally held files. |
| Historical console-only calculations | The available script and input paths are mapped above | Unsaved original transcripts are unavailable; new executions can establish new result records where the required inputs/code survive. |
