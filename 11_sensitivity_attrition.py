#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attricios erzekenysegi elemzes: worst-case imputacio (kizart tesztek = 1, skala-minimum).
Repeat 0, full pipeline cellak; coverage + overall szinten."""
import csv, glob, collections

DIMS = ("requirement_alignment", "target_specificity", "evidence_grounding",
        "executability", "gherkin_quality", "coverage")
EXPECTED_PER_CELL = 650  # 65 req x 10 teszt

rows = [r for f in glob.glob("evaluations/llm_eval_runs_*.csv")
        for r in csv.DictReader(open(f, encoding="utf-8"))
        if r.get("evalStatus") == "ok" and r.get("repeatIndex") == "0"
        and r.get("pipeline") == "full"]

agg = collections.defaultdict(lambda: {"cov": [], "ovr": []})
for r in rows:
    try:
        cov = float(r["coverage"])
        ovr = sum(float(r[d]) for d in DIMS) / len(DIMS)
    except (KeyError, ValueError):
        continue
    a = agg[(r["model"], r["mode"])]
    a["cov"].append(cov)
    a["ovr"].append(ovr)

print(f"{'model':<28}{'mode':<8}{'n':>5}{'miss':>6}{'cov':>8}{'cov_wc':>8}{'ovr':>8}{'ovr_wc':>8}")
for (mo, md), a in sorted(agg.items()):
    n = len(a["cov"]); miss = EXPECTED_PER_CELL - n
    cov = sum(a["cov"]) / n
    ovr = sum(a["ovr"]) / n
    cov_wc = (sum(a["cov"]) + 1.0 * miss) / EXPECTED_PER_CELL
    ovr_wc = (sum(a["ovr"]) + 1.0 * miss) / EXPECTED_PER_CELL
    print(f"{mo:<28}{md:<8}{n:>5}{miss:>6}{cov:>8.3f}{cov_wc:>8.3f}{ovr:>8.3f}{ovr_wc:>8.3f}")
