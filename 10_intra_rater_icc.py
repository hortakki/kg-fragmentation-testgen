#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10_intra_rater_icc.py — intra-rater megbizhatosag (Gemini judge vs onmaga).

Parositas: JOIN_KEYS szerint a fo (judge-repeat 0) es az ujrabiralt
(judge-repeat 1) sorok kozott. Dimenzionkent: ICC(2,1) (two-way random,
absolute agreement, single rater), Pearson r, pontos egyezes %, ±1 egyezes %.

Futtatas:
  python 10_intra_rater_icc.py ^
    --main "evaluations/llm_eval_runs_*.csv" ^
    --rejudge "evaluations/icc/llm_eval_runs_*.csv"
"""
import argparse, csv, glob, sys
from statistics import mean

JOIN_KEYS = ("reqId", "testId", "mode", "pipeline", "model", "repeatIndex")
DIMS = ("requirement_alignment", "target_specificity", "evidence_grounding",
        "executability", "gherkin_quality", "coverage")

def load(pattern):
    rows = []
    for f in glob.glob(pattern):
        with open(f, encoding="utf-8") as fh:
            rows += [r for r in csv.DictReader(fh) if r.get("evalStatus") == "ok"]
    return rows

def icc_2_1(pairs):
    """ICC(2,1) two-way random effects, absolute agreement, single measures.
    pairs: list of (x, y) — n targets, k=2 raters."""
    n = len(pairs); k = 2
    if n < 2: return float("nan")
    grand = mean([v for p in pairs for v in p])
    row_means = [mean(p) for p in pairs]
    col_means = [mean([p[j] for p in pairs]) for j in range(k)]
    ss_total = sum((v - grand) ** 2 for p in pairs for v in p)
    ss_rows = k * sum((rm - grand) ** 2 for rm in row_means)
    ss_cols = n * sum((cm - grand) ** 2 for cm in col_means)
    ss_err = ss_total - ss_rows - ss_cols
    ms_r = ss_rows / (n - 1)
    ms_c = ss_cols / (k - 1)
    ms_e = ss_err / ((n - 1) * (k - 1))
    denom = ms_r + (k - 1) * ms_e + k * (ms_c - ms_e) / n
    return (ms_r - ms_e) / denom if denom else float("nan")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--rejudge", required=True)
    args = ap.parse_args()

    main_rows = {tuple(r.get(k, "") for k in JOIN_KEYS): r for r in load(args.main)}
    re_rows = load(args.rejudge)
    if not re_rows:
        sys.exit("Nincs ujrabiralt sor a megadott mintaban.")

    matched, missing = [], 0
    for r in re_rows:
        key = tuple(r.get(k, "") for k in JOIN_KEYS)
        m = main_rows.get(key)
        if m is None:
            missing += 1
            continue
        matched.append((m, r))
    print(f"Ujrabiralt sorok: {len(re_rows)} | parositva: {len(matched)} | parositatlan: {missing}")
    if missing:
        print("FIGYELEM: parositatlan sorok — ellenorizd a bemeneti mintakat!", file=sys.stderr)

    print(f"\n{'dimenzio':<24}{'n':>5}{'ICC(2,1)':>10}{'r':>7}{'egyezes%':>10}{'+-1%':>7}{'atl0':>6}{'atl1':>6}")
    for dim in DIMS:
        pairs = []
        for m, r in matched:
            try:
                pairs.append((float(m[dim]), float(r[dim])))
            except (KeyError, ValueError):
                continue
        if not pairs:
            print(f"{dim:<24}{'—':>5}")
            continue
        icc = icc_2_1(pairs)
        mx = mean(p[0] for p in pairs); my = mean(p[1] for p in pairs)
        sx = (sum((p[0]-mx)**2 for p in pairs)) ** 0.5
        sy = (sum((p[1]-my)**2 for p in pairs)) ** 0.5
        sxy = sum((p[0]-mx)*(p[1]-my) for p in pairs)
        r_ = sxy / (sx * sy) if sx and sy else float("nan")
        exact = mean(1 if p[0] == p[1] else 0 for p in pairs) * 100
        within1 = mean(1 if abs(p[0]-p[1]) <= 1 else 0 for p in pairs) * 100
        print(f"{dim:<24}{len(pairs):>5}{icc:>10.3f}{r_:>7.3f}{exact:>9.1f}%{within1:>6.1f}%{mx:>6.2f}{my:>6.2f}")

    # binaris flagek egyezese
    for flag in ("is_generic", "drift_detected"):
        pairs = [(m.get(flag, ""), r.get(flag, "")) for m, r in matched if m.get(flag, "") != "" and r.get(flag, "") != ""]
        if pairs:
            agree = mean(1 if a == b else 0 for a, b in pairs) * 100
            print(f"{flag:<24}{len(pairs):>5}{'':>10}{'':>7}{agree:>9.1f}%")

if __name__ == "__main__":
    main()
