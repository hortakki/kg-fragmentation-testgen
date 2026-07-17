#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
16_third_judge_analysis.py — Addendum 3 elemzések (A–E), lokális, nulla API.

Futtatás (projektmappából):
  python 16_third_judge_analysis.py ^
    --gemini "evaluations/llm_eval_runs_*.csv" ^
    --gpt "evaluations/cross_judge/llm_eval_runs_.csv_20260711_163447.csv" ^
    --third "evaluations/third_judge/llm_eval_runs_*.csv" ^
    --h2 h2_export.csv
Kimenet: stdout + analysis/third_judge_analysis.json
"""
import argparse, glob, json
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats as st

KEY = ["reqId", "testId", "mode", "pipeline", "model", "repeatIndex"]
DIMS = ["requirement_alignment", "target_specificity", "evidence_grounding",
        "executability", "gherkin_quality", "coverage"]
CTX = ["target_specificity", "evidence_grounding", "coverage"]
QUARANTINE = "20260711_163447"
CONFLICT = {"R1", "R102d", "R103d", "R33", "R43", "R49", "R50", "R51",
            "R58c", "R60c", "R63", "R70", "R71", "R72b", "R79b", "R80"}


def load(pattern, exclude_quarantine):
    frames = []
    for f in sorted(glob.glob(pattern)):
        if "summary" in f.lower():
            continue
        if exclude_quarantine and QUARANTINE in f:
            continue
        frames.append(pd.read_csv(f, dtype=str))
    d = pd.concat(frames, ignore_index=True)
    d = d[(d.evalStatus == "ok") & (d.repeatIndex == "0") & (d.pipeline == "full")]
    for c in DIMS:
        d[c] = d[c].astype(float)
    return d[KEY + DIMS].copy()


def icc_2_1(x, y):
    n, k = len(x), 2
    if n < 2:
        return float("nan")
    grand = (x.mean() + y.mean()) / 2
    rows = (x + y) / 2
    ms_r = k * ((rows - grand) ** 2).sum() / (n - 1)
    ms_c = n * (((x.mean() - grand) ** 2) + ((y.mean() - grand) ** 2)) / (k - 1)
    ss_e = (((x - rows) ** 2) + ((y - rows) ** 2)).sum() - \
           (((x.mean() - grand) ** 2) * n + ((y.mean() - grand) ** 2) * n) + \
           0  # two-rater algebra below
    # direct two-way decomposition (k=2)
    ss_total = (((x - grand) ** 2) + ((y - grand) ** 2)).sum()
    ss_rows = k * ((rows - grand) ** 2).sum()
    ss_cols = n * (((x.mean() - grand) ** 2) + ((y.mean() - grand) ** 2))
    ms_e = (ss_total - ss_rows - ss_cols) / ((n - 1) * (k - 1))
    denom = ms_r + (k - 1) * ms_e + k * (ms_c - ms_e) / n
    return (ms_r - ms_e) / denom if denom else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemini", required=True)
    ap.add_argument("--gpt", required=True)
    ap.add_argument("--third", required=True)
    ap.add_argument("--h2", default="h2_export.csv")
    args = ap.parse_args()
    out = {}

    gem = load(args.gemini, True)
    gpt = load(args.gpt, False)
    thr = load(args.third, False)
    print(f"sorok: gemini={len(gem)} gpt={len(gpt)} third={len(thr)}")
    p = thr.merge(gem, on=KEY, suffixes=("_ds", "_gem"))
    p = p.merge(gpt.rename(columns={c: c + "_gpt" for c in DIMS}), on=KEY)
    print(f"haromszorosan parositott sorok: {len(p)}")
    p["gen"] = p.model.str.contains("haiku|claude", case=False).map(
        {True: "haiku", False: "gpt"})
    p["conflict"] = p.reqId.isin(CONFLICT).astype(int)
    JT = {"ds": "DeepSeek", "gem": "Gemini", "gpt": "GPT-cross"}

    # ---------- A) cellaátlag-rangsorok ----------
    print("\n=== A) MODE-RANGSOR biralonkent x generatoronkent ===")
    A = {}
    for dims, label in ((DIMS, "6dim"), (CTX, "3ctx")):
        for gen in ("haiku", "gpt"):
            sub = p[p.gen == gen]
            for j in ("gem", "gpt", "ds"):
                m = (sub.groupby("mode")[[f"{d}_{j}" for d in dims]]
                     .mean().mean(axis=1).sort_values(ascending=False))
                order = " > ".join(m.index)
                A[f"{label}|{gen}|{JT[j]}"] = {k: round(v, 3) for k, v in m.items()}
                print(f"  [{label}] gen={gen:<6} {JT[j]:<10} {order}   "
                      + "  ".join(f"{k}:{v:.3f}" for k, v in m.items()))
    out["A_orderings"] = A

    # ---------- B) páronkénti egyezés ----------
    print("\n=== B) PARONKENTI EGYEZES (dimenzionkent ICC(2,1); cella-Spearman) ===")
    B = {}
    pairs = [("ds", "gem"), ("ds", "gpt"), ("gem", "gpt")]
    print(f"{'dim':<24}" + "".join(f"{JT[a]}-{JT[b]:<14}" for a, b in pairs))
    for d in DIMS:
        vals = []
        for a, b in pairs:
            vals.append(icc_2_1(p[f"{d}_{a}"], p[f"{d}_{b}"]))
        B[d] = dict(zip([f"{a}-{b}" for a, b in pairs], [round(v, 3) for v in vals]))
        print(f"{d:<24}" + "".join(f"{v:>10.3f}            "[:24-10] if False else f"{v:>10.3f}    " for v in vals))
    cells = p.groupby(["reqId", "mode", "model"])[
        [f"{d}_{j}" for d in DIMS for j in ("ds", "gem", "gpt")]].mean()
    print("cella-szintu Spearman (6 dim atlaga cellankent):")
    for a, b in pairs:
        ca = cells[[f"{d}_{a}" for d in DIMS]].mean(axis=1)
        cb = cells[[f"{d}_{b}" for d in DIMS]].mean(axis=1)
        rho, pv = st.spearmanr(ca, cb)
        B[f"cellSpearman_{a}-{b}"] = round(float(rho), 3)
        print(f"  {JT[a]}-{JT[b]}: rho={rho:.3f} (p={pv:.4f}, n={len(ca)})")
    out["B_agreement"] = B

    # ---------- C) mode×conflict moderáció a harmadik bírálón ----------
    print("\n=== C) MODE x CONFLICT moderacio (DeepSeek; req-klaszter-robusztus OLS) ===")
    resC = {}
    for d in CTX:
        m = smf.ols(f"{d}_ds ~ C(mode, Treatment('vector')) * conflict + C(model)", p
                    ).fit(cov_type="cluster", cov_kwds={"groups": p["reqId"]}, use_t=True)
        row = {}
        for mode in ("graph", "hybrid"):
            t = [n for n in m.params.index if f"[T.{mode}]" in n and ":" in n][0]
            row[f"{mode}xconflict"] = dict(b=round(m.params[t], 3), p=round(m.pvalues[t], 4))
        resC[d] = row
        print(f"  {d:<22} graphxconf b={row['graphxconflict']['b']:>7} p={row['graphxconflict']['p']:<7} "
              f"hybridxconf b={row['hybridxconflict']['b']:>7} p={row['hybridxconflict']['p']}")
    out["C_moderation"] = resC

    # ---------- D) kritérium-validitás az objektív referencia ellen ----------
    print("\n=== D) KRITERIUM-VALIDITAS (sor-szintu Pearson/Spearman az objektiv pontok ellen) ===")
    h2 = pd.read_csv(args.h2)
    h2k = h2[["reqId", "testId", "mode", "model"] +
             ["coverage_score", "support_score", "objective_score"]]
    q = p.merge(h2k, on=["reqId", "testId", "mode", "model"], how="inner")
    print(f"  objektiv parositas: {len(q)}/{len(p)}")
    D = {}
    for j in ("ds", "gem", "gpt"):
        for d, obj in (("coverage", "coverage_score"),
                       ("evidence_grounding", "support_score"),
                       ("target_specificity", "objective_score")):
            r_p = q[f"{d}_{j}"].corr(q[obj])
            r_s = q[f"{d}_{j}"].corr(q[obj], method="spearman")
            D[f"{JT[j]}|{d}~{obj}"] = dict(pearson=round(r_p, 3), spearman=round(r_s, 3))
            print(f"  {JT[j]:<10} {d:<22} ~ {obj:<15} r={r_p:>6.3f}  rho={r_s:>6.3f}")
    out["D_criterion"] = D

    # ---------- E) judge×mode kétutas, Haiku-only ----------
    print("\n=== E) JUDGE x MODE (Haiku-only; DeepSeek vs masik biralo; nyers + z) ===")
    resE = {}
    hai = p[p.gen == "haiku"]
    for other in ("gem", "gpt"):
        longs = []
        for j in ("ds", other):
            t = hai[KEY].copy()
            for c in CTX:
                t[c] = hai[f"{c}_{j}"].values
            t["judge"] = j
            longs.append(t)
        L = pd.concat(longs, ignore_index=True)
        for c in CTX:
            L[f"z_{c}"] = L.groupby("judge")[c].transform(
                lambda v: (v - v.mean()) / v.std(ddof=0))
        print(f"  -- DeepSeek vs {JT[other]} --")
        for dim in CTX:
            for dep, lab in ((dim, "nyers"), (f"z_{dim}", "z")):
                m = smf.ols(f"{dep} ~ C(mode, Treatment('vector')) * C(judge, Treatment('{other}'))",
                            L).fit(cov_type="cluster",
                                   cov_kwds={"groups": L["reqId"]}, use_t=True)
                res = {}
                for mode in ("graph", "hybrid"):
                    t = [n for n in m.params.index if f"[T.{mode}]" in n and ":" in n][0]
                    res[mode] = (m.params[t], m.pvalues[t])
                resE[f"{other}|{dim}|{lab}"] = {k: (round(v[0], 3), round(v[1], 4))
                                             for k, v in res.items()}
                print(f"    {dim:<22}{lab:<7}graphxjudge b={res['graph'][0]:>7.3f} p={res['graph'][1]:<8.4f}"
                      f"hybridxjudge b={res['hybrid'][0]:>7.3f} p={res['hybrid'][1]:.4f}")
    out["E_haiku_only"] = resE

    with open("analysis/third_judge_analysis.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    print("\nMentve: analysis/third_judge_analysis.json")


if __name__ == "__main__":
    main()
