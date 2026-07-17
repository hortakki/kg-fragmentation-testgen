#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
20_make_figures.py — a kézirat 3 ábrája (PDF+PNG, figures/ alá).
  Fig1 design-mátrix (nem igényel adatot)
  Fig2 miss-dekompozíció (analysis/miss_decomposition.csv)
  Fig3 három-bírálós egyezés (analysis/third_judge_analysis.json)
Futtatás: python 20_make_figures.py     (ha kell: pip install matplotlib)
"""
import json, os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.makedirs("figures", exist_ok=True)
plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
                     "figure.dpi": 150, "savefig.bbox": "tight"})
G_HAIKU, G_GPT = "#4878a8", "#c44e52"
GRAY = "#666666"


def save(fig, name):
    fig.savefig(f"figures/{name}.pdf")
    fig.savefig(f"figures/{name}.png", dpi=300)
    plt.close(fig)
    print(f"figures/{name}.pdf + .png")


# ---------- Fig 1: design matrix ----------
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.axis("off")
conds = ["vector", "graph", "hybrid", "hybrid\nno_resolution", "hybrid\nno_retrieval"]
gens = ["Claude Haiku 4.5", "GPT-4o-mini"]
XOFF = 0.45
for j, c in enumerate(conds):
    ax.text(XOFF + 1.6 + j * 1.15, 2.55, c, ha="center", va="bottom", fontsize=8)
for i, g in enumerate(gens):
    ax.text(0.0, 1.9 - i * 0.85, g, ha="left", va="center", fontsize=8, weight="bold")
    for j, c in enumerate(conds):
        reps = 3 if j < 3 else 1
        col = G_HAIKU if i == 0 else G_GPT
        for r in range(reps):
            ax.add_patch(plt.Rectangle((XOFF + 1.15 + j * 1.15 + r * 0.07, 1.62 - i * 0.85 + r * 0.07),
                                       0.86, 0.52, fill=True, alpha=0.35 if r else 0.85,
                                       facecolor=col, edgecolor="black", lw=0.6))
        ax.text(XOFF + 1.58 + j * 1.15, 1.88 - i * 0.85, "65 req\n×10 tests",
                ha="center", va="center", fontsize=6.5, color="white" if True else "k")
ax.text(1.15, 0.42, "Repeats: retrieval modes ×3 (stacked squares); ablations repeat-0 only.\n"
        "Cells: 2×5×65 = 650 repeat-0 + 2×(2×3×65) = 780 repeat-1/2 → 1,430 cells / 14,300 Gherkin tests.\n"
        "Evaluation: Gemini 2.5 Flash judge (frozen v4 prompt, blinded) · 622-point objective reference ·\n"
        "203 typed elements (H4) · cross-judge GPT-4o-mini + third-family judge DeepSeek V4 Flash on a 1,889-row stratum.",
        fontsize=7, va="top")
ax.set_xlim(0, 7.55); ax.set_ylim(0.0, 3.0)
ax.set_title("Fig. 1  Factorial design: 2 generators × 5 retrieval conditions × 65 requirements")
save(fig, "fig1_design")

# ---------- Fig 2: miss decomposition ----------
d = pd.read_csv("analysis/miss_decomposition.csv")
d = d[d.pipeline == "full"].copy()
d["rm"] = d.retrieval_miss / d.n_ground_truth_elements
d["im"] = d.integration_miss / d.n_ground_truth_elements
agg = d.groupby(["mode", "model"])[["rm", "im"]].mean().reindex(
    [("vector", m) for m in sorted(d.model.unique())] +
    [("graph", m) for m in sorted(d.model.unique())] +
    [("hybrid", m) for m in sorted(d.model.unique())])
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7, 2.9), gridspec_kw={"width_ratios": [1.25, 1]})
x = np.arange(len(agg))
labels = [f"{m}\n{'Haiku' if 'claude' in mo else 'GPT-4o-mini'}" for m, mo in agg.index]
a1.bar(x, agg.im * 100, color=[G_HAIKU if 'claude' in mo else G_GPT for _, mo in agg.index])
a1.bar(x, agg.rm * 100, bottom=agg.im * 100, color=GRAY)
from matplotlib.patches import Patch
a1.legend(handles=[Patch(facecolor=G_HAIKU, label="integration miss — Haiku"),
                   Patch(facecolor=G_GPT, label="integration miss — GPT-4o-mini"),
                   Patch(facecolor=GRAY, label="retrieval miss")],
          frameon=False, fontsize=6.5, loc="upper left")
for xi, (imv, rmv) in zip(x, zip(agg.im * 100, agg.rm * 100)):
    a1.text(xi, imv + rmv + 1, f"{imv+rmv:.1f}%", ha="center", fontsize=6.5)
a1.set_xticks(x); a1.set_xticklabels(labels, fontsize=6.5)
a1.set_ylabel("per-test miss rate (%)"); a1.set_ylim(0, 75)
a1.set_title("(a) Per-test miss decomposition (full pipeline)")

types = ["local", "conflict", "cross_module", "supersede", "refine"]
corpus_n = {"local": 65, "conflict": 18, "cross_module": 68, "supersede": 4, "refine": 48}
share, totn = [], []
for t in types:
    rm_ = d[f"{t}_ret_miss"].sum(); im_ = d[f"{t}_int_miss"].sum()
    share.append(im_ / (rm_ + im_) * 100 if rm_ + im_ else np.nan)
    totn.append(int(rm_ + im_))
xb = np.arange(len(types))
a2.bar(xb, share, color="#5a7d5a")
for xi, sh in zip(xb, share):
    a2.text(xi, sh + 1, f"{sh:.1f}%", ha="center", fontsize=6.5)
a2.set_xticks(xb); a2.set_xticklabels(types, fontsize=6.5, rotation=15)
note = "corpus elements / misses: " + " · ".join(
    f"{t} {corpus_n[t]}/{tn}" for t, tn in zip(types, totn))
a2.text(0.5, -0.32, note, transform=a2.transAxes, ha="center", fontsize=5.8)
a2.set_ylabel("integration share of misses (%)"); a2.set_ylim(0, 110)
a2.set_title("(b) Integration share by element type")
fig.suptitle("Fig. 2  H4 — post-retrieval failure decomposition", y=1.04, fontsize=9)
save(fig, "fig2_miss_decomposition")

# ---------- Fig 3: three-judge agreement ----------
J = json.load(open("analysis/third_judge_analysis.json", encoding="utf-8"))
B = J["B_agreement"]
dims = ["requirement_alignment", "target_specificity", "evidence_grounding",
        "executability", "gherkin_quality", "coverage"]
pairs = [("ds-gem", "DeepSeek–Gemini"), ("ds-gpt", "DeepSeek–GPT"), ("gem-gpt", "Gemini–GPT")]
M = np.array([[B[dim][k] for k, _ in pairs] for dim in dims], dtype=float)
fig, ax = plt.subplots(figsize=(4.7, 3.0))
im = ax.imshow(M, vmin=0, vmax=0.7, cmap="Blues", aspect="auto")
for i in range(len(dims)):
    for j in range(len(pairs)):
        ax.text(j, i, f"{(M[i,j] if abs(M[i,j]) >= 0.005 else 0.0):.2f}", ha="center", va="center",
                fontsize=7, color="black" if M[i, j] < 0.45 else "white")
ax.set_xticks(range(len(pairs))); ax.set_xticklabels([p for _, p in pairs], fontsize=7)
ax.set_yticks(range(len(dims))); ax.set_yticklabels(dims, fontsize=7)
sp = {k: J["B_agreement"].get(f"cellSpearman_{k}") for k, _ in pairs}
ax.set_title("Fig. 3  Pairwise inter-judge agreement, ICC(2,1) per dimension\n"
             f"cell-mean Spearman: DS–Gem {sp['ds-gem']:.2f} · DS–GPT {sp['ds-gpt']:.2f} · Gem–GPT {sp['gem-gpt']:.2f}",
             fontsize=8)
fig.colorbar(im, ax=ax, shrink=0.85, label="ICC(2,1)")
save(fig, "fig3_judge_agreement")

print("Kesz. A PDF-ek a kezirathoz, a PNG-k gyors ellenorzeshez.")
