#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""21_fig4_mode_rankings_by_judge.py — judge-fuggo retrieval-mode rangsor
ketpaneles interakcios plot (Haiku / GPT-4o-mini). Forras: a harmadik-judge
elemzes A_orderings blokkja (mod-atlagok judge-onkent es generatoronkent).
Futtatas: python 19_fig4_mode_rankings_by_judge.py

Megjegyzes: a pontok az A_orderings mod-ATLAGAI, judge-onkent a sajat 3-modos
atlagara centralva (igy a harom judge egy tengelyen osszevetheto, es csak a
mod-mintazat/keresztezes latszik). A caption szerinti within-judge z-score +
requirement-cluster bootstrap 95% CI ehhez teszt-szintu, MINDHAROM judge-ot
tartalmazo score-tabla kellene; ez a szkript szandekosan a mar meglevo
osszesitesbol dolgozik, CI nelkul."""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INPUT_FILE = Path("analysis/third_judge_analysis.json")
OUTPUT_FILE = Path("figures/fig4_mode_rankings_by_judge.pdf")

DIMSET = "6dim"                      # "6dim" (teljes judge-score) vagy "3ctx"
MODES = ["vector", "graph", "hybrid"]
JUDGES = ["Gemini", "GPT-cross", "DeepSeek"]
GENS = [("haiku", "Haiku-generated tests"),
        ("gpt", "GPT-4o-mini-generated tests")]
# Okabe-Ito colorblind-safe paletta
COL = {"Gemini": "#0072B2", "GPT-cross": "#D55E00", "DeepSeek": "#009E73"}
MRK = {"Gemini": "o", "GPT-cross": "s", "DeepSeek": "^"}


def main():
    A = json.loads(INPUT_FILE.read_text(encoding="utf-8"))["A_orderings"]

    plt.rcParams.update({
        "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
        "legend.fontsize": 9, "xtick.labelsize": 9.5, "ytick.labelsize": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.family": "DejaVu Sans", "figure.dpi": 150,
    })

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.9), sharey=True)

    for ax, (gen, gtitle) in zip(axes, GENS):
        for judge in JUDGES:
            vals = np.array([A[f"{DIMSET}|{gen}|{judge}"][m] for m in MODES], float)
            centered = vals - vals.mean()          # within-judge kozepre igazitas
            ax.plot(range(len(MODES)), centered, marker=MRK[judge], color=COL[judge],
                    lw=2, ms=7, label=judge, clip_on=False, zorder=3)
        ax.axhline(0, color="0.8", lw=0.8, zorder=0)
        ax.set_xticks(range(len(MODES)))
        ax.set_xticklabels([m.capitalize() for m in MODES])
        #--ax.set_title(gtitle, pad=8)
        ax.set_xlim(-0.25, len(MODES) - 0.75)
        ax.margins(y=0.22)

    axes[0].set_ylabel("Within-judge centered score\n(native 1-5 units, mean-subtracted)")
    # Kozos legend a panelek ALATT, a rajzteruleten kivul (nem utkozik az adattal)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, title="Judge", frameon=False, ncol=3,
               loc="lower center", bbox_to_anchor=(0.5, -0.04))
   #-- fig.suptitle(f"Retrieval-mode preference by judge and generator ({DIMSET} composite)",
    #--             y=1.02, fontsize=11.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0.06, 1, 1))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_FILE, bbox_inches="tight")
    fig.savefig(OUTPUT_FILE.with_suffix(".png"), dpi=300, bbox_inches="tight")
    print(f"Mentve: {OUTPUT_FILE}")

    # Ellenorzo kiiras: mod-sorrend judge-onkent (nyers atlagok)
    print(f"\nMod-sorrend judge-onkent ({DIMSET}, nyers atlagok):")
    for gen, _ in GENS:
        print(f" [{gen}]")
        for judge in JUDGES:
            d = A[f"{DIMSET}|{gen}|{judge}"]
            order = sorted(MODES, key=lambda m: -d[m])
            print(f"   {judge:<10}: " + " > ".join(f"{m}({d[m]:.3f})" for m in order))


if __name__ == "__main__":
    main()
