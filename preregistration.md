# Pre-registration — Knowledge-graph context reconstruction for LLM Gherkin test generation

**Status:** frozen before main data collection.
**Judge prompt version:** `PROMPT_VERSION = 2026-07-05.v4` (FROZEN — not modified after this commit).
**Commit rule:** this file is committed with a timestamp BEFORE the main Gemini
judging run. Hypotheses are confirmatory; no hypothesis is reworded after the
main run. Endpoint selection was informed by a single-requirement pilot (R1, v4);
see the R1-circularity clause below.

---

## 1. Design (fixed)

- 65 real requirements; 3 retrieval modes (vector, graph, hybrid); 3 repeats of
  the `full` pipeline (repeatIndex 0,1,2); 2 ablations (`no_resolution`,
  `no_retrieval`, repeatIndex 0 only); 2 generator models (gpt-4o-mini,
  claude-haiku-4-5); 10 tests per cell. Total 1430 cells / 14 300 tests.
- Primary judge: **Gemini 2.5 Flash** (neutral third family). Robustness
  cross-judge: **gpt-4o-mini** on a stratified subset. The Claude judge is omitted.
- The same judge configuration scores every row of every model.

## 2. Endpoints (fixed from the v4 R1 pilot distributions)

**Primary endpoints** (these discriminate; the confirmatory claims rest on them):
- `target_specificity` (Gemini)
- `evidence_grounding` (Gemini)
- `coverage` (Gemini)
- plus the objective evaluator's `coverage_score` on the shared, human-validated
  reference.

**Secondary endpoint:** `overall_score` (the deterministic mean of the six
sub-scores).

**Manipulation checks** (ceiling dimensions; NOT endpoints — their role is to
show that condition differences are substantive, not formal):
- `requirement_alignment`, `gherkin_quality`, `executability`.

Pilot evidence (R1, v4, n=220 judged tests) justifying the split:
`coverage` sd≈0.91 (2% fives), `evidence_grounding` sd≈1.41 (45% fives),
`target_specificity` sd≈1.11 (52% fives) — discriminating; whereas
`gherkin_quality` sd≈0.24 (97% fives), `executability` sd≈0.61 (89% fives),
`requirement_alignment` sd≈0.48 (91% fives) — at ceiling.

## 3. Hypotheses (confirmatory, directional)

- **H1 (vector paradox — mode×dimension interaction):** on the FORMAL dimensions
  (`gherkin_quality`, `executability`, `requirement_alignment`) retrieval modes
  do not differ meaningfully (equivalence-style report: effect size + CI); on the
  CONTEXT dimensions (`evidence_grounding`, `coverage`, `target_specificity`)
  **graph > vector** and **hybrid > vector**.
- **H2 (objective–subjective divergence):** the positive gap between term-based
  objective support and subjective grounding ("lexical mimicry": right words,
  wrong context) is **larger in vector mode than in graph mode**.
  Metric: `divergence = z(support_score_obj) − z(evidence_grounding_subj)`,
  standardized over the full main-round sample, **full-pipeline rows only
  (ablation rows excluded from H2)**.
- **H3 (fragmentation as moderator — DECOMPOSED):** the graph−vector advantage
  on the primary endpoints grows with requirement fragmentation. Fragmentation is
  NOT aggregated into a single index; it enters as SEPARATE, fact-based graph
  moderators, each tested independently (mechanism-level evidence):
  `n_conflicts`, `n_affects`, `n_neighbors` (primary), with `has_conflict`
  (binary) as a robustness coding for the rare-conflict moderator, and
  `n_rel_types` as a control. Dropped with documented reasons: `n_specs`
  (binary/weak), `n_supersede` (4/65, too rare), `n_docs_via_chunks`
  (retrieval breadth, not structural fragmentation). Per-moderator model:
  `endpoint ~ C(mode) * <moderator> + C(model) + C(pipeline)`, RE reqId; the
  `mode×moderator` interaction is the confirmatory test.
- **H4 (error decomposition — Opció 1 ground truth):** the majority of
  vector-mode coverage loss is RETRIEVAL failure (the needed element never
  entered the evidence) rather than INTEGRATION failure (present but ignored).
  Ground truth is the FROZEN, HUMAN-VALIDATED `canonical_points_typed` per
  requirement (the shared element set), NOT the cell's own resolved context
  (which would be circular). Presence is tested with the SAME tokenizer as the
  objective coverage matcher (`exp_core.obj_tokenize` + `obj_stemish`), threshold
  adopted from the matcher. Direction pre-registered; the ratio is the reported
  result. Reported by element_type (conflict/gap/cross_module/refine/local).

## 4. Interpretation rules (fixed)

- **no_resolution vs full:** `no_resolution` sees more RAW evidence
  (`RAW_EVIDENCE_CHAR_CAP`). Therefore if `no_resolution ≥ full`, it is
  interpreted as "distillation adds nothing beyond raw evidence", NOT as a
  retrieval failure.
- **no_retrieval in H4:** with no retrieval, every miss is a retrieval miss by
  definition. These rows are EXCLUDED from the mode comparison (or reported
  separately), never aggregated in.
- **R1 circularity:** endpoint selection used R1 as a pilot; because the judge is
  cached, R1's v4 pilot scores equal its main-run scores, so R1 formally
  participated in endpoint selection (1/65). A sensitivity analysis excluding R1
  is reported; the conclusions do not change if R1 is dropped.

## 5. Variance sub-sample (10 requirements)

- Selection: stratified by `has_conflict` × `has_cross_module` × `n_neighbors`
  tercile (fact-based graph moderators), deterministic seeded pick.
- **Seed:** `20260705`. Neighbor-tercile bounds from the real 65-req
  distribution: t1=2, t2=3. Strata count: 9.
- **Selected reqIds** (from `07_hypothesis_analysis.py --select-subsample`, seed
  20260705): **R1, R5, R7, R29, R31b, R49, R51, R62, R63, R103d**.
- The full 3 repeats are judged only on these 10 requirements (variance
  evidence); all 65 requirements are judged on repeatIndex 0 (main analysis).

## 5b. H3 moderators (fixed, fact-based)

Primary moderators (from the Neo4j graph, real 65-req distribution):
`n_conflicts` (0–2, 16/65 nonzero), `n_affects` (0–7, 45/65), `n_neighbors`
(1–9). Binary robustness: `has_conflict`, `has_cross_module`. Control:
`n_rel_types`. Dropped (documented): `n_specs`, `n_supersede`,
`n_docs_via_chunks`. No aggregated fragmentation index is used.

## 5c. H4 element-type convention (fixed)

When a fragmentation element derives from a neighbor carrying multiple relations,
the type is assigned by descending specificity (documented convention):
conflict (CONFLICTS_WITH) > gap (IDENTIFIES_GAP_IN) > cross_module (AFFECTS) >
supersede (SUPERSEDES/VIOLATES_REQUIREMENT) > refine (REFINES). Target-document
bullet rules are `local`. HAS_COMMENT is excluded (absent from the graph).

## 6. Statistical model (fixed)

- `statsmodels` MixedLM, test-level observations, random intercept `reqId`.
- Base per endpoint: `score ~ C(mode) * C(model) + C(pipeline)`, groups=reqId.
  The mode×model interaction is mandatory (pilot showed a strong GPT×hybrid signal).
- H1: per-dimension models; formal dims → equivalence-style main-effect report;
  context dims → graph−vector and hybrid−vector contrasts.
- H2: divergence as outcome; vector vs graph contrast.
- H3: per moderator, `score ~ C(mode) * <moderator> + C(model) + C(pipeline)`,
  RE reqId, for each of {n_conflicts, n_affects, n_neighbors} + has_conflict
  (binary robustness). No aggregated index.
- Repeats: repeatIndex as a variance component; ICC reported (requirement- and
  repeat-level); Levene test for condition-dependent variance.
- Multiplicity: **Holm correction** across the family of primary endpoints.
- Effect sizes: standardized coefficients + 95% CI everywhere; no bare p-values.
- Ordinal robustness: because endpoints are 1–5 ordinal, primary LMM results are
  accompanied by an ordinal (proportional-odds) or cell-median non-parametric
  sensitivity check; agreement is reported in one sentence.

## 7. What is forbidden (fixed)

- Modifying the judge prompt after this commit.
- Rewording any hypothesis after the main run.
- Accepting a join-cardinality other than 1:1 as a "small discrepancy".
- Aggregating `no_retrieval` rows into H4 without exclusion.
- Introducing any new LLM call in the analysis layer.

---

## Appendix A — selected variance sub-sample (committed)

Seed `20260705`, strata = has_conflict × has_cross_module × n_neighbors-tercile
(t1=2, t2=3), 9 strata over 65 requirements. Deterministic selection:

**R1, R5, R7, R29, R31b, R49, R51, R62, R63, R103d**

Full `variance_subsample.json` (with the complete strata table) is produced by
`python 07_hypothesis_analysis.py --select-subsample --seed 20260705
--graph-csv graph_moderators.csv` and committed alongside this file.
