#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
15_haiku_only_judge_mode.py — review M5/2: a judge×mode sign-reversal
generátoronkénti (Haiku-only / GPT-only / pooled) kétutas tesztje a párosított
keresztbírálói rétegen. Lokális statisztika, nulla API-hívás.

Futtatás (projektmappából):
  python 15_haiku_only_judge_mode.py ^
    --gemini "evaluations/llm_eval_runs_*.csv" ^
    --gpt "evaluations/cross_judge/llm_eval_runs_.csv_20260711_163447.csv"
"""
import argparse, glob
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

KEY = ["reqId", "testId", "mode", "pipeline", "model", "repeatIndex"]
DIMS = ["coverage", "evidence_grounding", "target_specificity"]
QUARANTINE_MARK = "20260711_163447"


def load(pattern, exclude_quarantine):
    frames = []
    for f in sorted(glob.glob(pattern)):
        if "summary" in f.lower():
            continue
        if exclude_quarantine and QUARANTINE_MARK in f:
            continue
        frames.append(pd.read_csv(f, dtype=str))
    d = pd.concat(frames, ignore_index=True)
    d = d[(d.evalStatus == "ok") & (d.repeatIndex == "0") & (d.pipeline == "full")]
    for c in DIMS:
        d[c] = d[c].astype(float)
    return d


def norm_model(s):
    s = str(s).lower()
    return "haiku" if ("haiku" in s or "claude" in s) else "gpt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemini", required=True)
    ap.add_argument("--gpt", required=True)
    args = ap.parse_args()

    gem = load(args.gemini, exclude_quarantine=True)
    gpt = load(args.gpt, exclude_quarantine=False)
    print(f"Gemini fo-reteg sorok: {len(gem)}; GPT keresztbiralo sorok: {len(gpt)}")

    pair = gpt[KEY].merge(gem[KEY + DIMS], on=KEY, how="inner")
    pair = pair.merge(gpt[KEY + DIMS], on=KEY, suffixes=("_gemini", "_gpt"))
    print(f"Parositott sorok: {len(pair)} (vart: ~1889 az attricio erejeig)")
    if pair[KEY].duplicated().any():
        raise SystemExit("HIBA: duplikalt kulcs a parositott tablaban.")

    # hosszu forma: 1 sor / (teszt, bíráló)
    longs = []
    for judge in ("gemini", "gpt"):
        t = pair[KEY].copy()
        for c in DIMS:
            t[c] = pair[f"{c}_{judge}"]
        t["judge"] = judge
        longs.append(t)
    L = pd.concat(longs, ignore_index=True)
    L["generator"] = L["model"].map(norm_model)
    # bírálón belüli z-score (skalahasznalat-kulonbseg kiszurese)
    for c in DIMS:
        L[f"z_{c}"] = L.groupby("judge")[c].transform(
            lambda v: (v - v.mean()) / v.std(ddof=0))

    def fit(sub, dep):
        m = smf.ols(f"{dep} ~ C(mode, Treatment('vector')) * C(judge, Treatment('gemini'))",
                    sub).fit(cov_type="cluster",
                             cov_kwds={"groups": sub["reqId"]}, use_t=True)
        out = {}
        for mode in ("graph", "hybrid"):
            t_int = [n for n in m.params.index if f"[T.{mode}]" in n and ":" in n][0]
            t_main = [n for n in m.params.index if f"[T.{mode}]" in n and ":" not in n][0]
            out[mode] = dict(judge_int_b=m.params[t_int], judge_int_p=m.pvalues[t_int],
                             gemini_effect_b=m.params[t_main], gemini_effect_p=m.pvalues[t_main])
        return out, int(sub.reqId.nunique())

    for gen in ("haiku", "gpt", "pooled"):
        sub = L if gen == "pooled" else L[L.generator == gen]
        print(f"\n=== GENERATOR: {gen}  (N={len(sub)} sor, G={sub.reqId.nunique()} klaszter) ===")
        print(f"{'dim':<22}{'skala':<7}{'graph x judge b':>16}{'p':>9}{'hybrid x judge b':>18}{'p':>9}")
        for dim in DIMS:
            for dep, label in ((dim, "nyers"), (f"z_{dim}", "z")):
                r, G = fit(sub, dep)
                print(f"{dim:<22}{label:<7}{r['graph']['judge_int_b']:>16.3f}"
                      f"{r['graph']['judge_int_p']:>9.4f}"
                      f"{r['hybrid']['judge_int_b']:>18.3f}"
                      f"{r['hybrid']['judge_int_p']:>9.4f}")
        # cellaatlag-rangsor biralonkent
        for judge in ("gemini", "gpt"):
            means = (sub[sub.judge == judge].groupby("mode")[DIMS].mean().mean(axis=1)
                     .sort_values(ascending=False))
            order = " > ".join(means.index)
            print(f"  rangsor ({judge}, 3 dim atlaga): {order}   "
                  + "  ".join(f"{m}:{v:.3f}" for m, v in means.items()))


if __name__ == "__main__":
    main()
