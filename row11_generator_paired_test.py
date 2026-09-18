"""Generator gap in suite-level local-element non-coverage (Table 4, §5.1).

Input : miss_decomposition.csv (frozen script-07 output, commit 6b68982).
Output: pooled per-generator rates with 95% Clopper-Pearson CIs, the paired
        difference with a requirement-level cluster-bootstrap CI, an exact
        requirement-level sign test (test of record), an exact Wilcoxon
        signed-rank test, and an exact McNemar test over the 195 requirement x
        mode cell pairs (sensitivity). No generation, judging, or LLM calls.
Run   : python row11_generator_paired_test.py miss_decomposition.csv
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats

SEED, B = 20260719, 20000
path = sys.argv[1] if len(sys.argv) > 1 else "miss_decomposition.csv"
d = pd.read_csv(path)
f = d[d.pipeline == "full"].copy()
f["local_miss"] = (f.local_ret_miss + f.local_int_miss) > 0
# suite-level indicator: local element uncovered by every valid test of the cell
s = f.groupby(["reqId", "mode", "model"]).local_miss.all().reset_index()
assert len(s) == 390 and s.local_miss.sum() == 27, "reconciliation gate failed"
hk = s[s.model.str.contains("haiku")].set_index(["reqId", "mode"]).local_miss
gp = s[s.model == "gpt-4o-mini"].set_index(["reqId", "mode"]).local_miss
P = pd.concat([hk.rename("h"), gp.rename("g")], axis=1)
assert len(P) == 195 and not P.isna().any().any()


def clopper_pearson(k, n):
    lo = stats.beta.ppf(0.025, k, n - k + 1) if k else 0.0
    hi = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return lo, hi


for lab, col in (("Haiku", "h"), ("GPT-4o-mini", "g")):
    k, n = int(P[col].sum()), len(P)
    print(f"{lab}: {k}/{n} = {k/n:.3%}, 95% CI {clopper_pearson(k, n)[0]:.3%}-{clopper_pearson(k, n)[1]:.3%}")

# requirement-level paired comparison (unit = requirement, 0-3 uncovered suites)
R = P.reset_index().groupby("reqId").agg(h=("h", "sum"), g=("g", "sum"))
pos, neg = int((R.g > R.h).sum()), int((R.g < R.h).sum())
print(f"requirement-level: GPT worse {pos}, Haiku worse {neg}, ties {len(R)-pos-neg}")
print(f"exact sign test p = {stats.binomtest(min(pos, neg), pos + neg, 0.5).pvalue:.4f}")
print(f"exact Wilcoxon signed-rank p = {stats.wilcoxon(R.g, R.h, method='exact').pvalue:.4f}")

rng = np.random.default_rng(SEED)
diff = (R.g.sum() - R.h.sum()) / (3 * len(R))
boot = [(lambda sub: (sub.g.sum() - sub.h.sum()) / (3 * len(sub)))(R.iloc[rng.integers(0, len(R), len(R))]) for _ in range(B)]
lo, hi = np.percentile(boot, [2.5, 97.5])
print(f"difference {diff:.3%}, requirement-level cluster-bootstrap 95% CI {lo:.3%}-{hi:.3%} (B={B}, seed={SEED})")

# sensitivity: exact McNemar over the 195 requirement x mode cell pairs
b, c = int(((~P.h) & P.g).sum()), int((P.h & (~P.g)).sum())
print(f"McNemar discordant pairs: GPT-only miss {b}, Haiku-only miss {c}, exact p = {stats.binomtest(min(b, c), b + c, 0.5).pvalue:.4f}")
