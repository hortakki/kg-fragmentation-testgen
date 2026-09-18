"""Judge-dependence families (§4.7): six judge x mode x conflict terms and six
judge x mode terms on the paired 1,889-row stratum, Holm-corrected within family.

Inputs : analysis/h3_analysis_table.csv (Gemini scores + has_conflict, commit 6fb45e7)
         evaluations/llm_eval_runs__csv_20260711_163447.csv (GPT-4o-mini cross-judge)
Model  : OLS, stacked long by judge (judge=1 for the cross-judge),
         score ~ (is_graph + is_hybrid) * conflict * judge   [three-way family]
         z     ~ (is_graph + is_hybrid) * judge              [judge x mode family,
                                                              z standardized within judge]
         requirement-cluster-robust SEs (G=32), t inference on G-1 df;
         restricted wild-cluster bootstrap (Rademacher, B=999) on the three-way terms.
Gates  : hybrid x conflict x judge = +0.72 (coverage) / +0.78 (target_specificity),
         analytic p = .006 / .004 as published.
Run    : python row5_judge_dependence_holm.py analysis/h3_analysis_table.csv evaluations/llm_eval_runs__csv_20260711_163447.csv
"""
import csv
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

csv.field_size_limit(sys.maxsize)
SEED, B = 20260712, 999
H3 = sys.argv[1] if len(sys.argv) > 1 else "h3_analysis_table.csv"
XJ = sys.argv[2] if len(sys.argv) > 2 else "llm_eval_runs__csv_20260711_163447.csv"
DIMS = ["coverage", "evidence_grounding", "target_specificity"]

x = pd.read_csv(XJ, engine="python", usecols=["reqId", "testId", "mode", "model"] + DIMS)
h = pd.read_csv(H3)
g = h[h.reqId.isin(set(x.reqId))][["reqId", "testId", "mode", "model", "has_conflict"] + DIMS]
x = x.merge(g[["reqId", "testId", "mode", "model", "has_conflict"]], on=["reqId", "testId", "mode", "model"])
assert len(g) == len(x) == 1889
L = pd.concat([g.assign(judge=0), x.assign(judge=1)], ignore_index=True)
L["is_graph"] = (L["mode"] == "graph").astype(int)
L["is_hybrid"] = (L["mode"] == "hybrid").astype(int)
L["conflict"] = L.has_conflict.astype(int)
for d in DIMS:
    L[d + "_z"] = L.groupby("judge")[d].transform(lambda s: (s - s.mean()) / s.std(ddof=1))
groups = L.reqId.values
fit = lambda f: smf.ols(f, L).fit(cov_type="cluster", cov_kwds={"groups": groups}, use_t=True)


def wild_boot_p(formula, term, rng):
    """Restricted wild-cluster bootstrap p for one coefficient (Rademacher, per cluster)."""
    full = fit(formula)
    t_obs = full.tvalues[term]
    X = full.model.exog
    j = list(full.model.exog_names).index(term)
    Xr = np.delete(X, j, axis=1)
    y = full.model.endog
    br = np.linalg.lstsq(Xr, y, rcond=None)[0]
    yr, er = Xr @ br, y - Xr @ br
    codes, inv = np.unique(groups, return_inverse=True)
    cnt = 0
    for _ in range(B):
        w = rng.choice([-1.0, 1.0], size=len(codes))[inv]
        res = sm.OLS(yr + w * er, X).fit(cov_type="cluster", cov_kwds={"groups": groups}, use_t=True)
        cnt += abs(res.tvalues[j]) >= abs(t_obs)
    return cnt / B


rng = np.random.default_rng(SEED)
rows = []
for d in DIMS:
    f = f"{d} ~ (is_graph + is_hybrid) * conflict * judge"
    r = fit(f)
    for term in ["is_graph:conflict:judge", "is_hybrid:conflict:judge"]:
        rows.append(dict(family="judge x mode x conflict", dim=d, term=term, b=r.params[term], p=r.pvalues[term],
                         p_boot=wild_boot_p(f, term, rng)))
tw = pd.DataFrame(rows)
assert abs(tw.loc[(tw.dim == "coverage") & tw.term.str.startswith("is_hybrid"), "b"].iloc[0] - 0.72) < 0.01
assert abs(tw.loc[(tw.dim == "target_specificity") & tw.term.str.startswith("is_hybrid"), "b"].iloc[0] - 0.78) < 0.01
tw["p_holm"] = multipletests(tw.p, method="holm")[1]
tw["p_boot_holm"] = multipletests(tw.p_boot, method="holm")[1]

rows = []
for d in DIMS:
    r = fit(f"{d}_z ~ (is_graph + is_hybrid) * judge")
    for term in ["is_graph:judge", "is_hybrid:judge"]:
        rows.append(dict(family="judge x mode (within-judge z)", dim=d, term=term, b=r.params[term], p=r.pvalues[term]))
jm = pd.DataFrame(rows)
jm["p_holm"] = multipletests(jm.p, method="holm")[1]

pd.set_option("display.width", 200)
print(tw.round(4).to_string(index=False))
print(jm.round(4).to_string(index=False))
print(f"(bootstrap: restricted wild-cluster, Rademacher, B={B}, seed={SEED}; Holm over the six terms of each family)")
