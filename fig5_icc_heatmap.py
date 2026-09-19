"""Figure 5 — pairwise inter-judge agreement on the paired 1,889-row stratum.

Input : analysis/third_judge_analysis.json (section B_agreement: raw-score ICC(2,1)
        per dimension for the three judge pairs, plus cell-mean Spearman per pair)
Output: figures/figure5_icc_heatmap.png (300 dpi)
Run   : python fig5_icc_heatmap.py analysis/third_judge_analysis.json figures/figure5_icc_heatmap.png
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

src = sys.argv[1] if len(sys.argv) > 1 else "third_judge_analysis.json"
out = sys.argv[2] if len(sys.argv) > 2 else "figure5_icc_heatmap.png"

B = json.load(open(src, encoding="utf-8"))["B_agreement"]
DIMS = ["requirement_alignment", "target_specificity", "evidence_grounding",
        "executability", "gherkin_quality", "coverage"]
PAIRS = [("ds-gem", "DeepSeek–Gemini"), ("ds-gpt", "DeepSeek–GPT"), ("gem-gpt", "Gemini–GPT")]

M = np.array([[B[d][k] for k, _ in PAIRS] for d in DIMS])

fig, ax = plt.subplots(figsize=(8.5, 4.45), dpi=300)
im = ax.imshow(M, cmap="Blues", vmin=0, vmax=0.7, aspect="auto")
ax.set_yticks(range(len(DIMS)))
ax.set_yticklabels(DIMS, fontsize=10)
ax.set_xticks(range(len(PAIRS)))
ax.set_xticklabels([f"{lab}\ncell-mean Spearman \nρ = {B['cellSpearman_' + k]:.2f}" for k, lab in PAIRS], fontsize=10)
ax.xaxis.tick_top()
for i in range(len(DIMS)):
    for j in range(len(PAIRS)):
        v = M[i, j]
        label = f"{abs(v):.2f}" if abs(v) < 0.005 else f"{v:.2f}"   # avoid "-0.00"
        ax.text(j, i, label, ha="center", va="center", fontsize=10, color="white" if v > 0.45 else "black")
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
cb.set_label("ICC(2,1)", fontsize=10)
fig.tight_layout()
fig.savefig(out, dpi=300)
print(f"wrote {out}")
