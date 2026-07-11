#!/usr/bin/env python3
"""
07_hypothesis_analysis.py — Hypothesis & analysis layer for the "vector paradox"
study. ANALYSIS ONLY: makes ZERO LLM calls, never touches the judge prompt, and
reads exclusively from already-persisted artefacts (run CSVs, judge CSVs,
objective per-test CSVs, frozen reference JSON).

Subcommands
-----------
  --compute-fragmentation   -> fragmentation_metrics.csv   (per reqId; also
                               feeds the H3 moderator and the subsample strata)
  --select-subsample --seed S
                            -> variance_subsample.json      (10 reqIds + strata)
  --join-check              -> validate 1:1 join between judge & objective rows
                               (run FIRST after the main run; hard-fails on any
                               cardinality other than 1:1)
  --h1 / --h2 / --h3 / --h4 -> result tables (CSV) + text model summaries

Every output is accompanied by <output>_metadata.json (input file hashes, seed,
software versions). All computations are deterministic and cache-independent.

Design constraints (from spec):
  * The judge prompt (PROMPT_VERSION 2026-07-05.v4) is FROZEN — untouched here.
  * The objective matcher is REUSED, not reimplemented (H4 presence test uses the
    same normalization/tokenization as the coverage matcher). We import it from
    exp_core so a single logic runs in both places.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

# Reuse the objective matcher's normalization so H4's presence test is identical
# to the coverage matcher (spec section 5: "ne írj új matchert").
try:
    import exp_core as E
except Exception as exc:  # pragma: no cover
    print(f"WARNING: could not import exp_core ({exc}); H4 presence test unavailable.",
          file=sys.stderr)
    E = None

JOIN_KEYS = ("reqId", "testId", "mode", "pipeline", "model", "repeatIndex")

PRIMARY_ENDPOINTS = ("target_specificity", "evidence_grounding", "coverage")
MANIPULATION_CHECKS = ("requirement_alignment", "gherkin_quality", "executability")
FORMAL_DIMS = ("gherkin_quality", "executability", "requirement_alignment")
CONTEXT_DIMS = ("evidence_grounding", "coverage", "target_specificity")
# Element types are derived from the persisted resolved* columns at H4 time
# (exception/conflict/gap/operative); cross_module is a per-requirement graph
# flag (AFFECTS>0), not a per-element text label.


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _load_csv(pattern: str) -> list[dict[str, str]]:
    files = sorted(glob.glob(pattern.strip('"').strip("'")))
    rows: list[dict[str, str]] = []
    for fp in files:
        base = os.path.basename(fp).lower()
        if not fp.endswith(".csv") or "summary" in base or "metadata" in base:
            continue
        with open(fp, encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    return rows


def _write_metadata(out_path: Path, inputs: dict[str, str], **extra: Any) -> None:
    meta = {
        "output": str(out_path),
        "input_hashes": inputs,
        "python": platform.python_version(),
        "prompt_version": getattr(E, "PROMPT_VERSION", "unknown") if E else "unknown",
        **extra,
    }
    out_path.with_suffix(out_path.suffix + ".metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(row: dict[str, str]) -> tuple:
    return tuple(str(row.get(k, "")) for k in JOIN_KEYS)


def _zscores(values: list[float]) -> dict[int, float]:
    """Index-keyed z-scores over the provided list (population sd)."""
    n = len(values)
    if n == 0:
        return {}
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n if n > 1 else 0.0
    sd = var ** 0.5
    if sd == 0:
        return {i: 0.0 for i in range(n)}
    return {i: (v - mean) / sd for i, v in enumerate(values)}


# --------------------------------------------------------------------------- #
# 3. Fragmentation MODERATORS (per reqId) — decomposed, fact-based (spec C)
# --------------------------------------------------------------------------- #
# No aggregated "fragmentation index". Per the chosen (most defensible) design,
# fragmentation enters H3 as SEPARATE, raw graph-derived moderators, each with a
# clear mechanism. Source: the Neo4j export CSV with columns
#   reqId, n_neighbors, n_rel_types, n_specs, n_docs_via_chunks,
#   n_conflicts, n_affects, n_supersede
# Primary moderators (well-spread, conceptually clean, from the real 65-req
# distribution): n_conflicts, n_affects, n_neighbors. n_rel_types is kept as a
# control only (collinear with n_neighbors). n_specs / n_supersede / 
# n_docs_via_chunks are dropped with documented, data-based justification
# (binary/too-rare/retrieval-breadth-not-structural). has_conflict and
# has_cross_module are binary robustness codings + subsample strata axes.
PRIMARY_MODERATORS = ("n_conflicts", "n_affects", "n_neighbors")
CONTROL_MODERATORS = ("n_rel_types",)
DROPPED_MODERATORS = ("n_specs", "n_supersede", "n_docs_via_chunks")


def load_graph_moderators(graph_csv: str) -> dict[str, dict[str, Any]]:
    """Load per-reqId graph moderators from the Neo4j export, add binary codings.
    Pure fact loading — no synthetic index, no weighting, no normalization here
    (z-scoring, if any, happens at analysis time inside the statistical model)."""
    rows = _load_csv(graph_csv)
    if not rows:
        raise SystemExit(f"No graph moderator rows in {graph_csv}")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        req = r["reqId"]
        rec = {c: int(r[c]) for c in
               ("n_neighbors", "n_rel_types", "n_specs", "n_docs_via_chunks",
                "n_conflicts", "n_affects", "n_supersede") if c in r}
        rec["has_conflict"] = int(rec.get("n_conflicts", 0) > 0)
        rec["has_cross_module"] = int(rec.get("n_affects", 0) > 0)
        out[req] = rec
    return out


def export_moderator_table(graph_csv: str, out_dir: Path) -> Path:
    """Emit the cleaned per-reqId moderator table (primary + control + binaries),
    documenting which raw columns are used vs dropped and why."""
    mods = load_graph_moderators(graph_csv)
    keep = list(PRIMARY_MODERATORS) + list(CONTROL_MODERATORS) + ["has_conflict", "has_cross_module"]
    out = out_dir / "moderators.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["reqId"] + keep)
        w.writeheader()
        for req in sorted(mods):
            w.writerow({"reqId": req, **{k: mods[req].get(k) for k in keep}})
    _write_metadata(out, {"graph_csv": _sha256(graph_csv)},
                    primary_moderators=PRIMARY_MODERATORS,
                    control_moderators=CONTROL_MODERATORS,
                    dropped_moderators=DROPPED_MODERATORS,
                    drop_reasons={
                        "n_specs": "binary 0/1, weak discrimination (26/65 nonzero)",
                        "n_supersede": "too rare (4/65) for stable estimation",
                        "n_docs_via_chunks": "retrieval breadth, not structural fragmentation",
                    })
    print(f"Wrote {out} ({len(mods)} requirements; primary={PRIMARY_MODERATORS})")
    return out


# --------------------------------------------------------------------------- #
# 3b. Stratified subsample selection — spec section 3 + 1
# --------------------------------------------------------------------------- #
def select_subsample(graph_csv: str, seed: int, out_dir: Path, n: int = 10) -> Path:
    """Deterministic, seeded, stratified pick of n requirements for the variance
    sub-sample. Strata (fact-based, from the graph moderators):
    has_conflict x has_cross_module x n_neighbors-tercile. Seed recorded for the
    pre-registration."""
    import random
    mods = load_graph_moderators(graph_csv)
    neigh_sorted = sorted(m["n_neighbors"] for m in mods.values())
    t1 = neigh_sorted[len(neigh_sorted) // 3]
    t2 = neigh_sorted[2 * len(neigh_sorted) // 3]

    def tercile(v: int) -> int:
        return 0 if v <= t1 else (1 if v <= t2 else 2)

    strata: dict[tuple, list[str]] = defaultdict(list)
    for req, m in mods.items():
        s = (m["has_conflict"], m["has_cross_module"], tercile(m["n_neighbors"]))
        strata[s].append(req)

    rng = random.Random(seed)
    ordered_strata = sorted(strata.items())
    for _, ids in ordered_strata:
        ids.sort(); rng.shuffle(ids)
    picked: list[str] = []
    idx = 0
    total_available = sum(len(v) for _, v in ordered_strata)
    while len(picked) < min(n, total_available):
        progressed = False
        for _, ids in ordered_strata:
            if idx < len(ids):
                picked.append(ids[idx]); progressed = True
                if len(picked) >= n:
                    break
        idx += 1
        if not progressed:
            break

    result = {
        "seed": seed,
        "n_selected": len(picked),
        "selected_reqids": sorted(picked),
        "neighbor_tercile_bounds": {"t1": t1, "t2": t2},
        "strata_axes": "has_conflict x has_cross_module x n_neighbors_tercile",
        "strata_table": {f"{k}": v for k, v in sorted(strata.items())},
    }
    out = out_dir / "variance_subsample.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_metadata(out, {"graph_csv": _sha256(graph_csv)}, seed=seed)
    print(f"Wrote {out}: {sorted(picked)}")
    return out


# --------------------------------------------------------------------------- #
# 4. Join check — spec sections 4 & 7 (run FIRST after the main run)
# --------------------------------------------------------------------------- #
def join_check(judge_glob: str, objective_glob: str) -> dict[str, Any]:
    judge = _load_csv(judge_glob)
    obj = _load_csv(objective_glob)
    judge_ok = [r for r in judge if r.get("evalStatus") == "ok"]

    jkeys = Counter(_key(r) for r in judge_ok)
    okeys = Counter(_key(r) for r in obj)

    dup_j = {k: c for k, c in jkeys.items() if c > 1}
    dup_o = {k: c for k, c in okeys.items() if c > 1}
    only_j = set(jkeys) - set(okeys)
    only_o = set(okeys) - set(jkeys)

    # Design: judge rows are a SUBSET of objective rows (repeats 1-2 run on a
    # preregistered 10-req subsample). Invariant: no dups, no orphan judgements.
    ok = not dup_j and not dup_o and not only_j

    report = {
        "judge_rows_ok": len(judge_ok),
        "objective_rows": len(obj),
        "judge_duplicate_keys": len(dup_j),
        "objective_duplicate_keys": len(dup_o),
        "judge_only_keys": len(only_j),
        "objective_only_keys": len(only_o),
        "note": "objective_only_keys = rows never scheduled for judging (subsample design)",
        "is_1to1": ok,
    }
    print(json.dumps(report, indent=2))
    if not ok:
        # Hard fail: a silent row mix-up would corrupt H2/H4 (spec: "hard fail").
        print("\nJOIN CHECK FAILED — cardinality is not 1:1. "
              "If testId is not unique within a cell, add the within-cell ordinal "
              "index to the key before proceeding. Do NOT accept this as a 'small "
              "discrepancy'.", file=sys.stderr)
        raise SystemExit(2)
    print("\nJOIN CHECK PASSED — 1:1 mapping between judge and objective rows.")
    return report


# --------------------------------------------------------------------------- #
# Join judge + objective into one keyed table (used by H2/H4)
# --------------------------------------------------------------------------- #
def _joined_rows(judge_glob: str, objective_glob: str) -> list[dict[str, Any]]:
    judge = {_key(r): r for r in _load_csv(judge_glob) if r.get("evalStatus") == "ok"}
    obj = {_key(r): r for r in _load_csv(objective_glob)}
    keys = set(judge) & set(obj)
    joined = []
    for k in keys:
        j, o = judge[k], obj[k]
        row = {jk: j.get(jk) for jk in JOIN_KEYS}
        row["evidence_grounding"] = j.get("evidence_grounding")
        row["coverage_subj"] = j.get("coverage")
        row["target_specificity"] = j.get("target_specificity")
        row["support_score"] = o.get("support_score")
        row["coverage_score_obj"] = o.get("coverage_score")
        row["gherkin"] = j.get("gherkin", "")
        row["reasoning"] = j.get("reasoning", "")
        row["evidenceText"] = j.get("evidenceText", "")
        joined.append(row)
    return joined


# --------------------------------------------------------------------------- #
# H1 — mode x dimension interaction (formal flat, context ordered) — spec 6
# --------------------------------------------------------------------------- #
def run_h1(judge_glob: str, out_dir: Path, filter_repeat: Optional[int] = 0) -> Path:
    rows = [r for r in _load_csv(judge_glob) if r.get("evalStatus") == "ok"]
    if filter_repeat is not None:
        rows = [r for r in rows if str(r.get("repeatIndex")) == str(filter_repeat)]

    # Per (dimension, mode) mean + sd across full-pipeline rows only (H1 is about
    # retrieval modes; ablations excluded here).
    full = [r for r in rows if r.get("pipeline") == "full"]
    out_rows = []
    for dim in FORMAL_DIMS + CONTEXT_DIMS:
        by_mode = defaultdict(list)
        for r in full:
            v = r.get(dim)
            if v not in (None, ""):
                by_mode[r.get("mode")].append(int(v))
        for mode in ("vector", "graph", "hybrid"):
            vals = by_mode.get(mode, [])
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            sd = (sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5 if len(vals) > 1 else 0.0
            out_rows.append({
                "dimension": dim,
                "dimension_class": "formal" if dim in FORMAL_DIMS else "context",
                "mode": mode, "n": len(vals),
                "mean": round(mean, 4), "sd": round(sd, 4),
            })
        # graph - vector and hybrid - vector contrasts (context dims are the test)
        vec = by_mode.get("vector", [])
        for other in ("graph", "hybrid"):
            oth = by_mode.get(other, [])
            if vec and oth:
                d = (sum(oth) / len(oth)) - (sum(vec) / len(vec))
                out_rows.append({
                    "dimension": dim,
                    "dimension_class": "formal" if dim in FORMAL_DIMS else "context",
                    "mode": f"{other}_minus_vector", "n": len(oth) + len(vec),
                    "mean": round(d, 4), "sd": "",
                })
    out = out_dir / "h1_mode_by_dimension.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader(); w.writerows(out_rows)
    _write_metadata(out, {"judge": _sha256(sorted(glob.glob(judge_glob.strip('\"')))[0]) if glob.glob(judge_glob.strip('"')) else "NA"},
                    hypothesis="H1", note="context-dim contrasts are the confirmatory test; formal dims expected flat")
    print(f"Wrote {out}")
    return out


# --------------------------------------------------------------------------- #
# H2 — objective/subjective divergence (lexical mimicry signature) — spec 4
# --------------------------------------------------------------------------- #
def run_h2(judge_glob: str, objective_glob: str, out_dir: Path,
           filter_repeat: Optional[int] = 0) -> Path:
    joined = _joined_rows(judge_glob, objective_glob)
    if filter_repeat is not None:
        joined = [r for r in joined if str(r.get("repeatIndex")) == str(filter_repeat)]
         # H2 is a MODE comparison: ablation rows (esp. no_retrieval, grounding≈1)
         # would inflate hybrid's divergence and shift the z-standardization.
         # Pre-registered: full-pipeline rows only.
        joined = [r for r in joined if str(r.get("pipeline")) == "full"]
    # keep rows with both instruments present
    usable = [r for r in joined
              if r.get("support_score") not in (None, "")
              and r.get("evidence_grounding") not in (None, "")]
    if not usable:
        raise SystemExit("H2: no rows with both objective support_score and subjective grounding.")

    supp = [float(r["support_score"]) for r in usable]
    grnd = [float(r["evidence_grounding"]) for r in usable]
    zs = _zscores(supp)
    zg = _zscores(grnd)
    for i, r in enumerate(usable):
        # divergence = z(objective term support) - z(subjective grounding)
        # HIGH positive => "good words, poor context" = mimicry signature
        r["divergence"] = round(zs[i] - zg[i], 4)

    # per-mode divergence distribution
    by_mode = defaultdict(list)
    for r in usable:
        by_mode[r["mode"]].append(r["divergence"])
    summary = []
    for mode in ("vector", "graph", "hybrid"):
        vals = by_mode.get(mode, [])
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        sd = (sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5 if len(vals) > 1 else 0.0
        summary.append({"mode": mode, "n": len(vals),
                        "divergence_mean": round(mean, 4), "divergence_sd": round(sd, 4)})

    out = out_dir / "h2_divergence_by_mode.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader(); w.writerows(summary)

    # 10 largest-divergence exemplars for the qualitative box
    exemplars = sorted(usable, key=lambda r: r["divergence"], reverse=True)[:10]
    ex_out = out_dir / "divergence_exemplars.csv"
    with ex_out.open("w", encoding="utf-8", newline="") as f:
        cols = list(JOIN_KEYS) + ["divergence", "support_score", "evidence_grounding",
                                  "gherkin", "reasoning"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(exemplars)
    _write_metadata(out, {"judge": "joined", "objective": "joined"},
                    hypothesis="H2",
                    note="divergence = z(support_obj) - z(grounding_subj); "
                         "full pipeline rows only (ablations excluded); "
                         "higher in vector = mimicry")
    print(f"Wrote {out} and {ex_out}")
    return out


# --------------------------------------------------------------------------- #
# H3 — fragmentation as moderator (data table for the MixedLM) — spec 3/6
# --------------------------------------------------------------------------- #
def run_h3(judge_glob: str, graph_csv: str, out_dir: Path,
           filter_repeat: Optional[int] = 0) -> Path:
    """H3 (decomposed): emit an analysis-ready long table carrying the RAW graph
    moderators per test — no aggregated index. Each primary moderator is tested
    separately in the MixedLM (see metadata). has_conflict is included so the
    rare-conflict moderator can also be run as a binary robustness check."""
    rows = [r for r in _load_csv(judge_glob) if r.get("evalStatus") == "ok"]
    if filter_repeat is not None:
        rows = [r for r in rows if str(r.get("repeatIndex")) == str(filter_repeat)]
    mods = load_graph_moderators(graph_csv)

    mod_cols = list(PRIMARY_MODERATORS) + list(CONTROL_MODERATORS) + ["has_conflict", "has_cross_module"]
    out = out_dir / "h3_analysis_table.csv"
    cols = list(JOIN_KEYS) + list(CONTEXT_DIMS) + mod_cols
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            if r.get("pipeline") != "full":
                continue
            m = mods.get(r.get("reqId"))
            if m is None:
                continue
            out_row = {k: r.get(k) for k in JOIN_KEYS}
            for d in CONTEXT_DIMS:
                out_row[d] = r.get(d)
            for mc in mod_cols:
                out_row[mc] = m.get(mc)
            w.writerow(out_row)
    _write_metadata(out, {"graph_csv": _sha256(graph_csv)}, hypothesis="H3",
                    primary_moderators=PRIMARY_MODERATORS,
                    models=[f"score ~ C(mode)*{mod} + C(model) + C(pipeline), RE reqId"
                            for mod in PRIMARY_MODERATORS] +
                           ["score ~ C(mode)*has_conflict + C(model) + C(pipeline), RE reqId (binary robustness)"],
                    note="decomposed moderators; no aggregated fragmentation index")
    print(f"Wrote {out} (decomposed H3; test each primary moderator separately)")
    return out


# --------------------------------------------------------------------------- #
# H4 — retrieval-miss vs integration-miss decomposition — spec 5
# --------------------------------------------------------------------------- #
def run_h4(judge_glob: str, reference_json: str, graph_csv: str, out_dir: Path,
           filter_repeat: Optional[int] = 0, coverage_threshold: float = 0.5) -> Path:
    """H4 decomposition (Opció 1): for each requirement, the ground-truth element
    set is the HUMAN-VALIDATED `canonical_points_typed` from the frozen reference
    (NOT the cell's own resolved context — that would be circular, since a mode
    that failed to retrieve an element would have no element to miss).

    For every ground-truth element not covered by the test, classify:
      RETRIEVAL miss  = not present in this cell's evidence  (retriever's fault)
      INTEGRATION miss = present in the evidence but absent from the test (prompt's fault)
    Uses the SAME tokenizer as the objective coverage matcher (exp_core.obj_tokenize).
    """
    if E is None or not hasattr(E, "obj_tokenize"):
        raise SystemExit("H4 needs exp_core.obj_tokenize (the shared objective tokenizer).")
    tok = E.obj_tokenize
    stem = getattr(E, "obj_stemish", lambda t: t)

    def term_set(text: str) -> set[str]:
        return {stem(t) for t in tok(text or "")}

    canonical_thr = getattr(E, "OBJ_LINE_COVERAGE_THRESHOLD", None)
    thr = float(canonical_thr) if canonical_thr is not None else coverage_threshold

    ref = json.loads(Path(reference_json).read_text(encoding="utf-8"))
    status = {k: (v.get("reference_status") if isinstance(v, dict) else None) for k, v in ref.items()}
    not_validated = [k for k, s in status.items() if s != "human_validated"]
    if not_validated:
        print(f"WARNING: {len(not_validated)} reference profiles are not 'human_validated' "
              f"(e.g. {not_validated[:5]}). H4 ground truth must be validated first.",
              file=sys.stderr)

    # per-req typed ground-truth elements from the frozen reference
    gt: dict[str, list[dict]] = {}
    for req, prof in ref.items():
        if isinstance(prof, dict):
            gt[req] = prof.get("canonical_points_typed") or []

    rows = [r for r in _load_csv(judge_glob) if r.get("evalStatus") == "ok"]
    if filter_repeat is not None:
        rows = [r for r in rows if str(r.get("repeatIndex")) == str(filter_repeat)]

    ETYPES = ("local", "conflict", "gap", "cross_module", "supersede", "refine")
    out_rows = []
    for r in rows:
        req = r.get("reqId", "")
        pipeline = r.get("pipeline", "")
        excluded = (pipeline == "no_retrieval")
        elements = gt.get(req, [])
        evidence_terms = term_set(r.get("evidenceText", ""))
        gherkin_terms = term_set(r.get("gherkin", ""))

        retrieval_miss = integration_miss = 0
        by_type = defaultdict(lambda: [0, 0])
        for el in elements:
            el_terms = term_set(el.get("text", ""))
            if not el_terms:
                continue
            etype = el.get("element_type", "local")
            covered = len(el_terms & gherkin_terms) / len(el_terms) >= thr
            if covered:
                continue
            present = len(el_terms & evidence_terms) / len(el_terms) >= thr
            if present:
                integration_miss += 1
                by_type[etype][1] += 1
            else:
                retrieval_miss += 1
                by_type[etype][0] += 1
        total_miss = retrieval_miss + integration_miss
        out_rows.append({
            **{k: r.get(k) for k in JOIN_KEYS},
            "excluded_no_retrieval": int(excluded),
            "n_ground_truth_elements": len(elements),
            "retrieval_miss": retrieval_miss,
            "integration_miss": integration_miss,
            "total_miss": total_miss,
            "retrieval_miss_rate": round(retrieval_miss / total_miss, 4) if total_miss else "",
            "integration_miss_rate": round(integration_miss / total_miss, 4) if total_miss else "",
            **{f"{t}_ret_miss": by_type[t][0] for t in ETYPES},
            **{f"{t}_int_miss": by_type[t][1] for t in ETYPES},
        })
    out = out_dir / "miss_decomposition.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader(); w.writerows(out_rows)
    _write_metadata(out, {"reference_json": _sha256(reference_json)}, hypothesis="H4",
                    ground_truth="human_validated canonical_points_typed (Opció 1)",
                    tokenizer="exp_core.obj_tokenize + obj_stemish",
                    coverage_threshold=thr,
                    threshold_source=("exp_core.OBJ_LINE_COVERAGE_THRESHOLD" if canonical_thr is not None else "explicit default 0.5"),
                    n_not_validated=len(not_validated),
                    note="no_retrieval rows flagged excluded; aggregate mode comparison must drop them")
    print(f"Wrote {out} (Opció 1 ground truth, threshold={thr})")
    return out


# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description="Hypothesis & analysis layer (no LLM calls).")
    p.add_argument("--judge-input", default="evaluations/llm_eval_*.csv")
    p.add_argument("--objective-input", default="evaluations/*objective*.csv")
    p.add_argument("--graph-csv", default="graph_moderators.csv",
                   help="Neo4j export: reqId,n_neighbors,n_rel_types,n_specs,"
                        "n_docs_via_chunks,n_conflicts,n_affects,n_supersede")
    p.add_argument("--typed-elements", default="typed_elements.json",
                   help="Human-validated typed ground-truth elements (from 08_export_typed_elements) for H4.")
    p.add_argument("--out-dir", default="analysis")
    p.add_argument("--seed", type=int, default=20260705)
    p.add_argument("--filter-repeat", type=int, default=0,
                   help="Restrict analysis to this repeatIndex (default 0 = main round).")
    p.add_argument("--export-moderators", action="store_true",
                   help="Write cleaned per-reqId moderator table (primary+control+binary).")
    p.add_argument("--select-subsample", action="store_true")
    p.add_argument("--join-check", action="store_true")
    p.add_argument("--h1", action="store_true")
    p.add_argument("--h2", action="store_true")
    p.add_argument("--h3", action="store_true")
    p.add_argument("--h4", action="store_true")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    did = False
    if args.export_moderators:
        export_moderator_table(args.graph_csv, out_dir); did = True
    if args.select_subsample:
        select_subsample(args.graph_csv, args.seed, out_dir); did = True
    if args.join_check:
        join_check(args.judge_input, args.objective_input); did = True
    if args.h1:
        run_h1(args.judge_input, out_dir, args.filter_repeat); did = True
    if args.h2:
        run_h2(args.judge_input, args.objective_input, out_dir, args.filter_repeat); did = True
    if args.h3:
        run_h3(args.judge_input, args.graph_csv, out_dir, args.filter_repeat); did = True
    if args.h4:
        run_h4(args.judge_input, args.typed_elements, args.graph_csv, out_dir, args.filter_repeat); did = True

    if not did:
        p.print_help()


if __name__ == "__main__":
    main()
