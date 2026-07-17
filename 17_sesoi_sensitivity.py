#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
17_sesoi_sensitivity.py — TOST-ekvivalencia több margóval (d=0.1/0.2/0.3),
a konfirmatorikus H1-modell kontrasztjaiból (analysis/h1_contrasts.csv).
Lokális, determinisztikus, nulla API.

Futtatás:  python 17_sesoi_sensitivity.py
"""
import pandas as pd
from scipy.stats import norm

MARGINS = (0.1, 0.2, 0.3)
CTX = ["target_specificity", "evidence_grounding", "coverage"]
FORMAL = ["requirement_alignment", "gherkin_quality", "executability"]

d = pd.read_csv("analysis/h1_contrasts.csv")
d = d[d.tier == "averaged"].copy()

def tost_p(est, se, m_raw):
    # H0: |effect| >= margin; ekvivalencia, ha MINDKET egyoldali elutasit
    p_lo = norm.cdf(-(est + m_raw) / se)   # teszt: effect > -m
    p_hi = norm.cdf((est - m_raw) / se)    # teszt: effect < +m
    return max(p_lo, p_hi)

rows = []
for _, r in d.iterrows():
    row = dict(endpoint=r.endpoint, contrast=r.contrast,
               d_hat=round(r.std_effect, 3))
    for m in MARGINS:
        m_raw = m * r.pooled_sd
        p = tost_p(r.raw_diff, r.se, m_raw)
        row[f"TOST_p(d={m})"] = round(p, 4)
        row[f"equiv(d={m})"] = "IGEN" if p < 0.05 else "nem"
    rows.append(row)
out = pd.DataFrame(rows)
order = CTX + ["coverage_score"] + FORMAL
out["ord"] = out.endpoint.map({e: i for i, e in enumerate(order)})
out = out.sort_values(["ord", "contrast"]).drop(columns="ord")

print("=== TOST-erzekenyseg (konfirmatorikus kontrasztokbol; Wald, cluster-aware SE) ===")
print(out.to_string(index=False))
print("\nEllenorzes: a d=0.2 oszlopnak egyeznie kell a kezirat T3-verdiktjeivel.")
out.to_csv("analysis/sesoi_sensitivity.csv", index=False)
print("Mentve: analysis/sesoi_sensitivity.csv")
