#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INPUT_FILE = Path("analysis/miss_decomposition.csv")
OUTPUT_FILE = Path("figures/fig5_suite_noncoverage_by_element_type.pdf")

TYPES = ["cross_module", "refine", "conflict", "local", "supersede"]
LABELS = {"local": "Local", "refine": "Refine", "conflict": "Conflict",
          "cross_module": "Cross-module", "supersede": "Supersede*"}
GEN = {"claude-haiku-4-5-20251001": "Haiku", "gpt-4o-mini": "GPT-4o-mini"}
COL_GEN = {"Haiku": "#0072B2", "GPT-4o-mini": "#D55E00"}
COL_MODE = {"vector": "#CC79A7", "graph": "#009E73", "hybrid": "#E69F00"}
OFF_MODE = {"vector": 0.20, "graph": 0.0, "hybrid": -0.20}


def main():
    df = pd.read_csv(INPUT_FILE)
    full = df[df.pipeline == "full"].copy()
    for t in TYPES:
        full[f"{t}_unc"] = full[f"{t}_ret_miss"] + full[f"{t}_int_miss"]
    full["gen"] = full["model"].map(GEN)

    panelA = full.groupby("gen")[[f"{t}_unc" for t in TYPES]].mean()
    panelB = full.groupby("mode")[[f"{t}_unc" for t in TYPES]].mean()
    totA = full.groupby("gen")[[f"{t}_unc" for t in TYPES]].sum()
    totB = full.groupby("mode")[[f"{t}_unc" for t in TYPES]].sum()
    xmax = max(panelA.values.max(), panelB.values.max()) * 1.22

    plt.rcParams.update({
        "font.size": 10, "axes.labelsize": 10, "legend.fontsize": 9,
        "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.family": "DejaVu Sans", "figure.dpi": 150,
    })
    y = np.arange(len(TYPES))
    fig, (a, b) = plt.subplots(2, 1, figsize=(6.8, 8.0), sharex=True)

    # Panel (a): generator fokusz
    off = 0.15
    for i, g in enumerate(["Haiku", "GPT-4o-mini"]):
        xs = [panelA.loc[g, f"{t}_unc"] for t in TYPES]
        yy = y + (off if i == 0 else -off)
        a.scatter(xs, yy, color=COL_GEN[g], s=58, label=g, zorder=3, clip_on=False)
        for j, t in enumerate(TYPES):
            a.annotate(f"{int(totA.loc[g, t + '_unc'])}", (xs[j], yy[j]),
                       textcoords="offset points", xytext=(7, 0), va="center",
                       fontsize=7.5, color=COL_GEN[g])
    a.set_yticks(y); a.set_yticklabels([LABELS[t] for t in TYPES]); a.invert_yaxis()
    a.set_xlim(0, xmax)
    a.set_title("(a) By generator (retrieval modes pooled)", fontsize=10.5, pad=6, loc="left")
    a.legend(loc="lower right", ncol=2, frameon=False,
             columnspacing=1.4, handletextpad=0.4)
    a.margins(y=0.12)

    # Panel (b): mod fokusz  (MOST szamokkal)
    for m in ["vector", "graph", "hybrid"]:
        xs = [panelB.loc[m, f"{t}_unc"] for t in TYPES]
        yy = y + OFF_MODE[m]
        b.scatter(xs, yy, color=COL_MODE[m], s=58,
                  label=m.capitalize(), zorder=3, clip_on=False)
        for j, t in enumerate(TYPES):
            b.annotate(f"{int(totB.loc[m, t + '_unc'])}", (xs[j], yy[j]),
                       textcoords="offset points", xytext=(7, 0), va="center",
                       fontsize=7.5, color=COL_MODE[m])
    b.set_yticks(y); b.set_yticklabels([LABELS[t] for t in TYPES]); b.invert_yaxis()
   # b.set_xlabel("Mean uncovered elements per test"); b.set_xlim(0, xmax)
    b.set_title("(b) By retrieval mode (generators pooled)", fontsize=10.5, pad=6, loc="left")
    b.legend(loc="lower right", ncol=3, frameon=False,
             columnspacing=1.4, handletextpad=0.4)
    b.margins(y=0.12)

    fig.text(0.5, -0.10, 
             "*Supersede rests on a very small corpus base - read descriptively.",
             ha="center", fontsize=7.2, color="0.35")
    fig.tight_layout()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_FILE, bbox_inches="tight")
    fig.savefig(OUTPUT_FILE.with_suffix(".png"), dpi=300, bbox_inches="tight")
    print(f"Mentve: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
