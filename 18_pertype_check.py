#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""18_pertype_check.py — tipusonkenti per-test integration share a
miss_decomposition.csv-bol (full pipeline). Futtatas: python 18_pertype_check.py"""
import pandas as pd

d = pd.read_csv("analysis/miss_decomposition.csv")
d = d[d.pipeline == "full"]
print(f"{'tipus':<14}{'ret_miss':>9}{'int_miss':>9}{'int_share%':>11}")
for t in ("local", "conflict", "gap", "cross_module", "supersede", "refine"):
    rm = int(d[f"{t}_ret_miss"].sum())
    im = int(d[f"{t}_int_miss"].sum())
    tot = rm + im
    share = im / tot * 100 if tot else float("nan")
    print(f"{t:<14}{rm:>9}{im:>9}{share:>10.1f}%")
