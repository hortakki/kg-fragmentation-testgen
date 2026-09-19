# Knowledge graph context reconstruction for LLM Gherkin test generation

This replication package contains the requirement documents, saved generation
records, evaluation data and statistical analyses for a study of test generation
from fragmented requirements. It compares GPT-4o-mini and Claude Haiku across
vector, graph and hybrid retrieval, with two additional hybrid ablation arms.

The design contains **65 requirements, 1,430 generation cells and 14,300 planned
test slots**. The saved generation files contain **14,174 test rows**. The main
repeat-0 evaluation contains 6,444 rows, including 3,846 full-pipeline rows.
All 1,430 generation cells are present; 37 cells contain fewer than the requested
10 tests. Cell completeness and test-row completeness are distinct quantities.

Start with [RESULTS_MAP.md](RESULTS_MAP.md) to locate a result and its inputs.
The full-pipeline H1 analysis can be rerun from the compact exports already in
Git. Large raw evaluation files are retained exclusively on the author's
local computer because of upload constraints and are not publicly downloadable.

## Documented snapshot

| Record | Identifier |
|---|---|
| Repository | <https://github.com/hortakki/kg-fragmentation-testgen> |
| Code and data baseline for this documentation | `53a4ebe47e75a988fd301d6a43707aa888345f41` |
| Documentation checked | 2026-09-19 |
| Initial release tag | `v1.0.0`, commit `6bd922c1427dab5d9ac0e04d99534489ba7e9419` |
| Initial preregistration tag | `preregistration-freeze-2026-07-08`, commit `5679865d70bf67590fe97b68bf7fe4405e971de2` |
| Archival-freeze commit | `6b68982`, 2026-07-19 |
| Returned post-freeze annotations | `325614f`, 2026-07-29 |
| Archive DOI | [10.5281/zenodo.22646533](https://doi.org/10.5281/zenodo.22646533) |
| Author / maintainer ORCID | [0009-0003-9766-6684](https://orcid.org/0009-0003-9766-6684) |

The initial release tag predates the later H1 analysis, third-judge evaluation
and annotation returns. Use the documented later commit when following this
guide. Commit dates and retained file metadata describe the available history;
they do not independently establish when every analysis was executed.
The DOI identifies the archive record supplied by the author. Consult that
record for its archived version and file inventory; the code/data baseline
used by this guide is the commit stated above. The large local-only files
described below are not supplied through the public archive.

## Repository layout

| Path | Contents |
|---|---|
| `docs/` | Requirement-source documents, including JIRA records, e-mails and toolchain configurations. |
| `runs/`, `runs_haiku/` | 715 generation CSVs per generator, each with a resolved-context JSON and run metadata. |
| `evaluations/` | Available judge CSVs, summaries, metadata, and draft/final objective references. |
| `evaluations/cross_judge/` | GPT-4o-mini cross-judge scores for 1,889 tests. |
| `evaluations/icc/`, `evaluations/icc_gpt/` | Gemini and GPT rejudge data: 180 and 178 rows respectively. |
| `evaluations/third_judge/` | DeepSeek scores for the same 1,889-test comparison stratum. |
| `evaluations/third_judge_icc/`, `evaluations/third_judge_pilot/` | DeepSeek rejudge data, 178 rows, and the 60-row format pilot. |
| `evaluations/objective/`, `evaluations/superseded/` | Earlier objective summaries/metadata and superseded judge passes. |
| `analysis/` | Descriptive tables, model results, sensitivity analyses and validation records. Metadata coverage varies by output. |
| `h1_export.csv` | 3,846 full-pipeline, repeat-0 rows with identifiers and all six Gemini scores. |
| `h2_export.csv` | The corresponding 3,846 rows with objective coverage, support and composite scores. |
| `typed_elements.json` | 203 typed elements over 65 requirements for the H4 analysis. |
| `reference_review.txt` | The reference-review record used by the reference-validation workflow. |
| `m2_annotation/` | Returned second-annotator files and the comparison answer key. |
| `figures/` | PDF and PNG figure exports. Plotting scripts are at the repository root. |
| Root Python scripts and `runall.ps1` / `runall.sh` | Generation, evaluation, analysis, validation and plotting entry points. |

The plans are `preregistration.md`, `preregistration_addendum_1.md`, the addenda
under `evaluations/`, `prereg_addendum_3_third_judge.md` and
`H1_analysis_plan.txt`.

## Requirement identifiers and generation settings

The 65 identifiers are non-contiguous. The complete list in
`runall.ps1::$DefaultReqs` matches the keys of `typed_elements.json`:

```text
R1 R100b R102d R103d R2 R21 R22 R23 R24 R25 R26 R29
R3 R30 R31 R31b R32 R33 R34 R37 R38 R39 R4 R41 R43
R44 R45 R47 R48 R49 R5 R50 R51 R51c R52c R58c R6 R60c
R61 R61c R62 R63 R64 R65 R69 R7 R70 R71 R71b R72 R72b
R74 R79b R80 R81b R81c R82b R83b R84b R87b R91c R91d
R92c R93c R97b
```

The PowerShell runner uses that list by default. Its generation plan can be
previewed without launching the generation commands:

```powershell
.\runall.ps1 -Stage gen -DryRun $true
```

The Bash runner defaults to `R1..R65`. Override `REQS` with the actual list
before a Bash run. Do not use the numeric range for this dataset.

The 1,430 saved generation metadata files record `top_k=15`, `max_hops=2`,
`limit=40`, `chunks_per_node=3`, and prompt/pipeline version
`2026-07-03.v3`. The evidence limit of 40 is not the vector top-k value.
The frozen main judge prompt is `2026-07-05.v4`. Consult the per-run metadata
when reconstructing a historical configuration; current code defaults alone
do not identify the original generation configuration.

## Environment

`analysis/h1_metadata.json` records the following environment for the saved H1
analysis:

| Component | Recorded version |
|---|---|
| Python | 3.14.0 |
| NumPy | 2.4.4 |
| pandas | 3.0.2 |
| SciPy | 1.18.0 |
| statsmodels | 0.14.6 |

A full dependency lockfile is not included in the documented snapshot.
These recorded versions cover the H1 environment; they do not specify every
generation, provider-client, plotting or database dependency.

For a fresh offline analysis environment, the main packages are NumPy, pandas,
SciPy, statsmodels and Matplotlib. The following installs current available
versions, so record the installed versions with any new results:

```bash
python -m venv .venv
```

Activate the environment using the command for your shell, then run:

```bash
python -m pip install numpy pandas scipy statsmodels matplotlib
```

Full retrieval and generation additionally require the provider clients,
credentials and a Neo4j database populated with the original graph and vector
index. A complete graph export/import package and database setup guide are
not included in the documented snapshot. Saved-score reanalysis does not
require Neo4j or new model calls.

## Offline analysis entry points

Run these commands from the repository root. Use a separate checkout for
reanalysis: several historical scripts write to fixed locations under
`analysis/` or `figures/`. New runs should be identified by their execution
date and environment, while preserving the committed outputs.

### H1 models and sensitivity analysis

```bash
python h1_confirmatory.py --h1 h1_export.csv --h2 h2_export.csv --out reanalysis/h1
```

Expected outputs are `h1_mixedlm_results.csv`, `h1_contrasts.csv`,
`h1_sensitivity.csv` and `h1_metadata.json` under the selected output directory.
The script checks input-key uniqueness and fits the per-dimension models,
with the documented fallback and Holm family. Its cell-median Wilcoxon
analysis is labelled as a sensitivity analysis in the source code.

### Equivalence analysis

```bash
python 17_sesoi_sensitivity.py
```

This reads the committed `analysis/h1_contrasts.csv` and writes
`analysis/sesoi_sensitivity.csv`, using standardized margins 0.1, 0.2 and 0.3.
It does not automatically read the new `reanalysis/h1` directory. To analyse
newly fitted contrasts, use a separate checkout and place those contrasts at
the input path expected by script 17.

### Local-suite comparison and judge dependence

```bash
python row11_generator_paired_test.py analysis/miss_decomposition.csv
python row5_judge_dependence_holm.py analysis/h3_analysis_table.csv evaluations/cross_judge/llm_eval_runs_.csv_20260711_163447.csv
```

Both scripts print results to the console. Script `row11` checks 390 suites
and 27 local misses, then reports intervals and paired comparisons.
Script `row5` reports the judge-dependence families, Holm corrections and
restricted wild-cluster bootstrap results. Preserve console output with the
date and input paths if recording a new execution.

### GPT and DeepSeek intra-rater reliability

```bash
python 10_intra_rater_icc.py --main evaluations/cross_judge/llm_eval_runs_.csv_20260711_163447.csv --rejudge evaluations/icc_gpt/llm_eval_runs_.csv_20260714_160642.csv
python 10_intra_rater_icc.py --main evaluations/third_judge/llm_eval_runs_.csv_20260716_220053.csv --rejudge evaluations/third_judge_icc/llm_eval_runs_.csv_20260716_221917.csv
```

The generic pairing and ICC calculation in script 10 also supports these
judges despite its Gemini-specific introductory comment. Each command uses
one judge's main pass and its separate rejudge pass.

### Figures

```bash
python 20b_make_figures.py
python 21_fig4_mode_rankings_by_judge.py
python 22b_fig5_suite_noncoverage_by_element_type.py
```

These scripts use the committed analysis tables/JSON and write PDF/PNG files
under `figures/`. Scripts `20`/`20b` and `22`/`22b` are layout variants.
See the figure-specific definitions in [RESULTS_MAP.md](RESULTS_MAP.md),
especially the distinction between per-test and suite-level measures.

## Evaluation files retained outside Git

The large raw evaluation files are retained exclusively on the author's
local computer because of upload constraints. They are not available for
public download from GitHub or the archive. The two main repeat-0 judge CSVs
are approximately **70 MB each**, as reported by the author. Their local
retention is distinct from the availability of the compact public exports.

| File or record | Rows | Availability in the documented snapshot |
|---|---:|---|
| `evaluations/llm_eval_runs_.csv_20260711_060531.csv` | 6,444 | Main judge detail file retained locally only; summary and metadata are in Git. |
| `llm_eval_runs_.csv_20260710_172326.csv` | 3,846 | Original full-pipeline judge detail file retained locally only; summary and metadata are in Git. Its exclusion rule names the `evaluations/superseded/` location. |
| `evaluations/objective_evaluation_details_runs_.csv_20260709_183209.csv` | 14,174 | Large frozen-reference detail file outside the public package; summary and metadata are in Git. |
| `evaluations/objective/objective_evaluation_details_runs.csv_20260708_172151.csv` | 14,174 | Large draft-reference detail file outside the public package; summary and metadata are in Git. |
| `logs/`, `cache/`, `.cache/`, `nincs_cache/` | — | Local logs and caches are excluded. An ignore rule does not establish that a particular historical console transcript was saved. |
| `.env` and local virtual environments | — | Local configuration and credentials are excluded. |

No public download or future deposit of these local-only files is promised by
this guide. Consequently, a fresh public checkout does not support every
raw-data reanalysis, including analyses requiring all 6,444 rows of detailed
judge output. This is a stated access limitation of the public package.

The compact `h1_export.csv` and `h2_export.csv` already provide all six Gemini
scores and the three objective scores for the 3,846-row full-pipeline sample.
They omit the bulk text and detailed judge reasoning in the original exports.
Filtering the 6,444-row file to `pipeline == "full"` should yield 3,846 rows;
verify keys and scores before treating that derivation as a substitute for
the separately dated historical file.

The objective evaluator can regenerate scores from the saved generation CSVs
and frozen reference without new model calls. Its recorded rule is an overlap
ratio of at least 0.25 **or** at least two shared tokens; pass thresholds are
coverage 0.15 and support 0.50, with coverage/support weights 0.55/0.45.
The normal evaluator imports the pipeline dependencies even for this local
operation.

## Coverage definitions

The objective reference contains **622 canonical points**. The H4 reference
contains **203 typed elements**: 65 local, 18 conflict, 48 refine,
68 cross-module and 4 supersede elements. These are different references and
use different matching rules.

The **27–47% overall suite non-coverage** is recorded in
`analysis/review_response.json`, key `suite_h4`, produced by
`14_review_response.py`. That implementation unions the normalized tokens of
all tests within each requirement–generator–mode suite, then applies the
0.5 element-overlap threshold. Across the six conditions, the precise
non-coverage range is 27.094–47.291%.

The **27/390 = 6.923% local-suite non-coverage**, complementary to 93.077%
coverage, is calculated from `analysis/miss_decomposition.csv` by
`row11_generator_paired_test.py`. A local element is missed when every
individual test in its suite misses it. Pooling tokens before matching and
taking the union of individual-test matches are different operations; the
two reported quantities should retain their respective definitions.

## Reported costs and historical console output

The manuscript-reported cost components are USD 60.46, USD 3.80 and USD 2.70,
which sum to USD 66.96, or approximately USD 67. These are author-reported
study costs. No itemized billing or per-call cost ledger has been supplied
with the package, so the monetary amounts cannot be independently verified
to the cent from the public files. Their reported precision does not establish
that a reconstructible cost audit exists.

The 7,813-evaluation count for the main Gemini, variance and Gemini rejudge
passes is separately derived as 6,444 + 594 + 595 + 180. Run counts alone do
not establish charges: token usage and the applicable billing conditions
would also be needed for a new cost calculation.

For calculations displayed only in a console without a saved transcript, the
original console record is unavailable. This is a historical retention
limitation. Where the script and inputs survive, a new execution can verify
the numerical result and produce a separately dated output. Such an output
records the new execution and does not supply the missing historical log.
The offline statistical entry points above do not require new model calls.

## Provenance and remaining limitations

* `H1_analysis_plan.txt`, Addendum 3 and several later scripts were tracked
  late. Commit `e3630e5` discloses that the root-level ignore rule had excluded
  them and that no pre-execution Git hash exists for those files. Their retained
  headers must be read together with that disclosure.
* The root-level default-deny ignore rule remains in place with explicit
  exceptions. Newly added root documents may require explicit tracking.
* The older H1 descriptive metadata records only the first matching judge
  file's hash. Older H2 divergence metadata contains `joined` instead of input
  hashes. `analysis/h1_metadata.json` separately hashes both compact H1 inputs.
  Those input hashes match their CRLF bytes; Git LF normalization changes the
  raw-byte hash.
* The historical definitions and pass/fail records for the six reported smoke
  gates are not included in the documented snapshot. The R1 pilot evaluation
  files do not themselves supply that gate report.
* `11_sensitivity_attrition.py` uses a broad judge-file wildcard and prints to
  the console. A historical resolved input list and separate saved transcript
  are not archived in the documented package. A new execution should record
  its actual input files and avoid counting overlapping judge passes twice.
* Separate implementations/outputs for the original main H3 regression and
  the 23,076-observation class-level omnibus remain unidentified. Available
  related models are mapped explicitly in `RESULTS_MAP.md`.
* The four returned `*_adjudicated_third.csv` / `*_adjudicated_fourth.csv`
  annotation files retain an extra layer of CSV quoting on physical lines.
  Removing that layer restores 90 evidence-presence and 60 conflict/supersede
  records per annotator. Preserve the as-received files and use documented
  normalized copies for machine analysis. In `m2_annotation/A_reference.csv`,
  item 65 has no verdict: 64 of 65 exported items were answered.
* A package-wide SHA-256 manifest, complete environment lock and complete
  graph-reconstruction package are not included in this snapshot.

## Citation and licensing

Identify the package using the archive DOI and the exact repository commit or
archived version used. The author-supplied ORCID is
[0009-0003-9766-6684](https://orcid.org/0009-0003-9766-6684). The archive DOI
identifies the research package; a final journal-publication citation is a
separate bibliographic record.

> hortakki/kg-fragmentation-testgen. Replication package for knowledge graph
> context reconstruction in LLM Gherkin test generation. Commit
> 53a4ebe47e75a988fd301d6a43707aa888345f41.
> Archive DOI: https://doi.org/10.5281/zenodo.22646533.
> Repository: https://github.com/hortakki/kg-fragmentation-testgen.

Use the archive record's own version metadata when citing an archived
snapshot; the DOI is not evidence that the archive contains this Git commit
or the local-only large files.

The accompanying [LICENSE.md](LICENSE.md) specifies MIT for code and
CC BY 4.0 for the project-owned data, figures and documentation, subject to
any separately identified third-party rights.
