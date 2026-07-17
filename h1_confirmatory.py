#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
H1 CONFIRMATORY ANALYSIS — runs the preregistered per-dimension MixedLM.
Implements the frozen plan (H1_analysis_plan.txt, Sections 1-15) with decisions:
  D1: confirmatory Holm family = six averaged contrasts {A1,A2} x {target_specificity,
      evidence_grounding, coverage}
  D2: objective coverage_score = pre-specified corroborating endpoint, reported
      separately, NOT in the Holm family
  D3: requirement_alignment = FORMAL (manipulation-check)
  D4: standardization denominator = within-cell pooled SD (cell = reqId x mode x model)
  D5: primary reporting = averaged contrasts; generator-specific C1-C4 secondary
Local statistics only. Zero LLM/API calls. Read-only on inputs.

Usage:
  python h1_confirmatory.py --h1 h1_export.csv --h2 h2_export.csv --out analysis
"""
import argparse, hashlib, json, sys, platform
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import scipy
import scipy.stats as st
import statsmodels
import statsmodels.formula.api as smf

KEY = ["reqId", "testId", "mode", "model"]
MODES = ["vector", "graph", "hybrid"]
PRIMARY = ["target_specificity", "evidence_grounding", "coverage"]
FORMAL = ["requirement_alignment", "gherkin_quality", "executability"]
OBJECTIVE = "coverage_score"
SECONDARY = "overall_score"  # skipped with a note if absent from export
ALPHA = 0.05


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def die(msg):
    print("\n*** ABORT: " + msg, file=sys.stderr)
    sys.exit(1)


def check_key_unique(df, name):
    dup = df.duplicated(subset=KEY, keep=False)
    if dup.any():
        ex = df.loc[dup, KEY].head(10)
        die(f"{name}: join key {KEY} is NOT unique ({dup.sum()} rows involved). "
            f"Likely the export contains multiple pipelines/repeats without a "
            f"disambiguating column. Re-export with a pipeline/repeat column or "
            f"pre-filtered to repeat-0 full-pipeline.\nExamples:\n{ex.to_string(index=False)}")


def pooled_within_cell_sd(df, endpoint):
    g = df.groupby(["reqId", "mode", "model"])[endpoint]
    stats = g.agg(["count", "var"]).dropna()
    stats = stats[stats["count"] > 1]
    num = ((stats["count"] - 1) * stats["var"]).sum()
    den = (stats["count"] - 1).sum()
    return float(np.sqrt(num / den)) if den > 0 else float("nan")


def fit_endpoint(df, endpoint):
    """Fit MixedLM per plan Sec.4; fallback per Sec.12. Returns (params, cov, meta)."""
    d = df[["reqId", "mode", "model", endpoint]].dropna().copy()
    d = d.rename(columns={endpoint: "score"})
    formula = "score ~ C(mode, Treatment('vector')) * C(model, Treatment('haiku'))"
    meta = {"endpoint": endpoint, "n": int(len(d)), "estimator": "MixedLM(REML)",
            "converged": None, "re_var": None, "fallback": None}
    res = None
    try:
        m = smf.mixedlm(formula, d, groups=d["reqId"])
        res = m.fit(reml=True)
        if not res.converged:
            res = m.fit(reml=True, method=["lbfgs", "nm"])
    except Exception as e:
        meta["fallback"] = f"MixedLM raised: {e}"
        res = None
    if res is not None:
        meta["converged"] = bool(res.converged)
        re_var = float(np.asarray(res.cov_re).ravel()[0])
        meta["re_var"] = re_var
        singular = (not res.converged) or re_var < 1e-8
        if not singular:
            names = list(res.fe_params.index)
            params = res.fe_params.values
            cov = pd.DataFrame(np.asarray(res.cov_params())[:len(names), :len(names)],
                               index=names, columns=names)
            return names, params, cov, meta
        meta["fallback"] = (meta["fallback"] or "") + \
            f" singular/non-converged fit (re_var={meta['re_var']});"
    # Sec.12(b): OLS with requirement-cluster-robust SEs, df = G-1
    ols = smf.ols(formula, d).fit(cov_type="cluster",
                                  cov_kwds={"groups": d["reqId"]}, use_t=True)
    meta["estimator"] = "OLS cluster-robust (fallback, cluster=reqId, df=G-1)"
    meta["fallback"] = (meta["fallback"] or "") + " -> OLS cluster-robust fallback used"
    names = list(ols.params.index)
    return names, ols.params.values, pd.DataFrame(ols.cov_params(),
                                                  index=names, columns=names), meta


def term(names, must_contain):
    if ":" in must_contain:
        hits = [n for n in names if all(s in n for s in must_contain)]
    else:  # main effect: exclude interaction terms
        hits = [n for n in names if all(s in n for s in must_contain) and ":" not in n]
    if len(hits) != 1:
        die(f"could not uniquely identify term {must_contain} among {names}")
    return names.index(hits[0])


def contrast_row(names, params, cov, spec):
    a = np.zeros(len(names))
    for must, w in spec:
        a[term(names, must)] = w
    est = float(a @ params)
    se = float(np.sqrt(a @ cov.values @ a))
    z = est / se
    p = 2 * (1 - st.norm.cdf(abs(z)))
    return est, se, est - 1.96 * se, est + 1.96 * se, p


def holm(pvals):
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (len(pvals) - rank) * pvals[idx])
        adj[idx] = min(1.0, running)
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--h1", required=True)
    ap.add_argument("--h2", required=True)
    ap.add_argument("--out", default="analysis")
    args = ap.parse_args()
    import os
    os.makedirs(args.out, exist_ok=True)

    h1 = pd.read_csv(args.h1)
    h2 = pd.read_csv(args.h2)

    # --- Sec.1/2: population, join, validation -----------------------------
    for c in KEY + PRIMARY + FORMAL:
        if c not in h1.columns:
            die(f"h1_export missing column: {c}")
    if OBJECTIVE not in h2.columns:
        die(f"h2_export missing column: {OBJECTIVE}")
    bad_mode = set(h1["mode"].unique()) - set(MODES)
    if bad_mode:
        die(f"h1_export contains unexpected modes {bad_mode}. Plan expects the "
            f"pre-filtered repeat-0 full-pipeline export (modes {MODES} only).")

    # normalize model labels to haiku/gpt
    def norm_model(s):
        s = str(s).lower()
        if "haiku" in s or "claude" in s: return "haiku"
        if "gpt" in s: return "gpt"
        die(f"unrecognized model label: {s}")
    h1["model"] = h1["model"].map(norm_model)
    h2m = h2.copy(); h2m["model"] = h2m["model"].map(norm_model)

    check_key_unique(h1, "h1_export")
    check_key_unique(h2m, "h2_export")

    joined = h1.merge(h2m[KEY + [OBJECTIVE] +
                          [c for c in ["evidence_grounding", "coverage",
                                       "target_specificity"] if c in h2m.columns]],
                      on=KEY, how="left", suffixes=("", "_h2"))
    unmatched = int(joined[OBJECTIVE].isna().sum())
    if unmatched > 0:
        die(f"join: {unmatched} h1 rows have no h2 match (plan requires 0).")

    # integrity: shared judge columns must agree between the two exports
    mism = {}
    for c in ["evidence_grounding", "coverage", "target_specificity"]:
        c2 = c + "_h2"
        if c2 in joined.columns:
            mism[c] = int((joined[c] != joined[c2]).sum())
    if any(v > 0 for v in mism.values()):
        die(f"h1/h2 shared judge columns DISAGREE on joined keys: {mism} "
            f"(of {len(joined)} rows). The two exports were not drawn from the "
            f"same rows; do not model until this is resolved.")

    n = len(joined)
    print(f"Analysis population: N={n} (plan expected ~3,846)")
    cells = joined.groupby(["mode", "model"]).size().unstack()
    print("Per mode x model counts (plan: ~624-650 each):")
    print(cells.to_string(), "\n")
    if not (3500 <= n <= 4000):
        die(f"N={n} far from expected 3,846 — wrong export?")

    # --- Sec.4-8: models + contrasts ---------------------------------------
    endpoints = ([(e, "primary") for e in PRIMARY] +
                 [(OBJECTIVE, "objective-corroborating")] +
                 [(e, "formal-manipulation-check") for e in FORMAL])
    if SECONDARY in joined.columns:
        endpoints.append((SECONDARY, "secondary"))
    else:
        print(f"NOTE: '{SECONDARY}' not in export -> secondary endpoint skipped.\n")

    CONTRASTS = [
        ("A1 graph-vector (avg)",  [(["[T.graph]"], 1.0), (["[T.graph]", ":"], 0.5)], "averaged"),
        ("A2 hybrid-vector (avg)", [(["[T.hybrid]"], 1.0), (["[T.hybrid]", ":"], 0.5)], "averaged"),
        ("C1 graph-vector | Haiku",  [(["[T.graph]"], 1.0)], "generator-specific"),
        ("C2 hybrid-vector | Haiku", [(["[T.hybrid]"], 1.0)], "generator-specific"),
        ("C3 graph-vector | GPT",  [(["[T.graph]"], 1.0), (["[T.graph]", ":"], 1.0)], "generator-specific"),
        ("C4 hybrid-vector | GPT", [(["[T.hybrid]"], 1.0), (["[T.hybrid]", ":"], 1.0)], "generator-specific"),
    ]

    model_rows, contrast_rows, conv_log = [], [], []
    for endpoint, role in endpoints:
        names, params, cov, meta = fit_endpoint(joined, endpoint)
        conv_log.append(meta)
        sd = pooled_within_cell_sd(joined, endpoint)
        se_all = np.sqrt(np.diag(cov.values))
        for nm, b, s in zip(names, params, se_all):
            z = b / s
            model_rows.append(dict(endpoint=endpoint, role=role, term=nm, coef=b,
                                   se=s, z=z, p=2 * (1 - st.norm.cdf(abs(z))),
                                   ci_lo=b - 1.96 * s, ci_hi=b + 1.96 * s,
                                   estimator=meta["estimator"],
                                   converged=meta["converged"], re_var=meta["re_var"]))
        for label, spec, tier in CONTRASTS:
            est, se, lo, hi, p = contrast_row(names, params, cov, spec)
            direction_ok = (est > 0)  # prereg: graph>vector, hybrid>vector
            contrast_rows.append(dict(endpoint=endpoint, role=role, contrast=label,
                                      tier=tier, raw_diff=est, se=se,
                                      pooled_sd=sd, std_effect=est / sd,
                                      ci_lo=lo, ci_hi=hi, p=p,
                                      direction_vs_prereg=("as-predicted" if direction_ok
                                                           else "opposite")))
    con = pd.DataFrame(contrast_rows)

    # --- Sec.9 (D1/D2): Holm over the six averaged primary contrasts -------
    fam = (con["role"] == "primary") & (con["tier"] == "averaged")
    con["holm_p"] = np.nan
    con.loc[fam, "holm_p"] = holm(con.loc[fam, "p"].values)
    def verdict(r):
        if not (r["role"] == "primary" and r["tier"] == "averaged"):
            return ""
        return ("confirmed" if (r["holm_p"] < ALPHA and
                                r["direction_vs_prereg"] == "as-predicted")
                else "not confirmed")
    con["verdict"] = con.apply(verdict, axis=1)

    # --- Sec.11: cell-median Wilcoxon sensitivity ---------------------------
    sens_rows = []
    for endpoint, role in endpoints:
        med = (joined.groupby(["reqId", "model", "mode"])[endpoint]
               .median().unstack("mode"))
        for mode in ["graph", "hybrid"]:
            pair = med[[mode, "vector"]].dropna()
            diff = pair[mode] - pair["vector"]
            if (diff != 0).sum() == 0:
                stat, p = np.nan, 1.0
            else:
                stat, p = st.wilcoxon(pair[mode], pair["vector"])
            sens_rows.append(dict(endpoint=endpoint, contrast=f"{mode}-vector",
                                  n_cells=len(pair), median_diff=float(diff.median()),
                                  wilcoxon_stat=float(stat) if stat == stat else np.nan,
                                  p=float(p)))
    sens = pd.DataFrame(sens_rows)

    # --- Sec.14/15: outputs --------------------------------------------------
    pd.DataFrame(model_rows).to_csv(f"{args.out}/h1_mixedlm_results.csv", index=False)
    con.to_csv(f"{args.out}/h1_contrasts.csv", index=False)
    sens.to_csv(f"{args.out}/h1_sensitivity.csv", index=False)
    meta = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                inputs={args.h1: sha256(args.h1), args.h2: sha256(args.h2)},
                n=n, per_cell=cells.to_dict(),
                formula="score ~ C(mode, Treatment('vector')) * C(model, Treatment('haiku'))",
                random="intercept | reqId (REML)",
                decisions=dict(D1="Holm over six averaged primary contrasts",
                               D2="coverage_score corroborating, outside Holm family",
                               D3="requirement_alignment = formal",
                               D4="within-cell pooled SD (reqId x mode x model)",
                               D5="averaged primary, generator-specific secondary"),
                convergence=conv_log,
                versions=dict(python=platform.python_version(),
                              statsmodels=statsmodels.__version__,
                              numpy=np.__version__, scipy=scipy.__version__,
                              pandas=pd.__version__))
    with open(f"{args.out}/h1_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)

    # --- stdout summary ------------------------------------------------------
    print("=== CONVERGENCE ===")
    for m in conv_log:
        print(f"  {m['endpoint']:<24} {m['estimator']:<45} "
              f"converged={m['converged']} re_var={m['re_var']}"
              + (f"  [{m['fallback']}]" if m["fallback"] else ""))
    print("\n=== CONFIRMATORY FAMILY (Holm, D1) ===")
    cols = ["endpoint", "contrast", "raw_diff", "std_effect", "ci_lo", "ci_hi",
            "p", "holm_p", "direction_vs_prereg", "verdict"]
    print(con.loc[fam, cols].to_string(index=False,
          float_format=lambda x: f"{x: .4f}"))
    print("\n=== OBJECTIVE CORROBORATING (D2, outside family) ===")
    ob = (con["endpoint"] == OBJECTIVE) & (con["tier"] == "averaged")
    print(con.loc[ob, cols[:-2] + ["direction_vs_prereg"]].to_string(index=False,
          float_format=lambda x: f"{x: .4f}"))
    print("\n=== FORMAL / MANIPULATION-CHECK (equivalence-style, descriptive) ===")
    fm = (con["role"] == "formal-manipulation-check") & (con["tier"] == "averaged")
    print(con.loc[fm, ["endpoint", "contrast", "raw_diff", "std_effect",
                       "ci_lo", "ci_hi", "p"]].to_string(index=False,
          float_format=lambda x: f"{x: .4f}"))
    print("\n=== SENSITIVITY (cell-median Wilcoxon) ===")
    print(sens.to_string(index=False, float_format=lambda x: f"{x: .4f}"))
    print("\nDone. Outputs in", args.out)


if __name__ == "__main__":
    main()
