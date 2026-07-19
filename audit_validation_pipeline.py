#!/usr/bin/env python3
"""Read-only audit of human-validation samples against the main repeat-0 judge export.

No API calls, no LLM calls, and no source files are modified.
Outputs are written to analysis/validation_pipeline_audit/.
"""
from pathlib import Path
import argparse
import json
import pandas as pd

KEYS = ["reqId", "model", "mode", "testId"]
UNIT_KEYS = KEYS + ["element_type", "element_text"]


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def audit_sample(sample: pd.DataFrame, raw: pd.DataFrame, name: str):
    needed = KEYS + ["pipeline", "repeatIndex", "evidenceText", "evalStatus", "runId"]
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        raise ValueError(f"Raw judge CSV missing columns: {missing}")
    raw_small = raw[needed].copy()
    # A repeat-0 export may contain several pipelines with the same visible test key.
    # Preserve all candidates, then report ambiguity instead of silently choosing one.
    merged = sample.merge(raw_small, on=KEYS, how="left", indicator=True, suffixes=("_sample", "_raw"))
    matches_per_sample = merged.groupby("sample_id", dropna=False).size().rename("raw_match_count")
    sample_aug = sample.merge(matches_per_sample, left_on="sample_id", right_index=True, how="left")

    # If evidence_window is NO_EVIDENCE, no_retrieval is the intended provenance candidate.
    # Otherwise prefer full; retain ambiguity flags for transparency.
    def choose(group):
        no_ev = str(group.iloc[0].get("evidence_window", "")) == "NO_EVIDENCE"
        preferred = "no_retrieval" if no_ev else "full"
        cand = group[group["pipeline"] == preferred]
        if len(cand) == 1:
            row = cand.iloc[0].copy()
        elif len(group[group["repeatIndex"] == 0]) == 1:
            row = group[group["repeatIndex"] == 0].iloc[0].copy()
        else:
            row = group.iloc[0].copy()
        row["provenance_ambiguous"] = len(group) != 1 and len(cand) != 1
        row["candidate_pipelines"] = "|".join(sorted(set(group["pipeline"].dropna().astype(str))))
        return row

    matched = merged[merged["_merge"] == "both"].copy()
    chosen = matched.groupby("sample_id", group_keys=False).apply(choose, include_groups=False).reset_index(drop=True) if len(matched) else matched
    unmatched_ids = set(sample["sample_id"]) - set(chosen.get("sample_id", []))
    unmatched = sample[sample["sample_id"].isin(unmatched_ids)].copy()

    summary = {
        "sample": name,
        "sample_rows": int(len(sample)),
        "matched_sample_ids": int(chosen["sample_id"].nunique()) if len(chosen) else 0,
        "unmatched_sample_ids": int(len(unmatched)),
        "pipeline_counts": chosen["pipeline"].value_counts(dropna=False).to_dict() if len(chosen) else {},
        "repeat_counts": {str(k): int(v) for k, v in chosen["repeatIndex"].value_counts(dropna=False).items()} if len(chosen) else {},
        "ambiguous_provenance": int(chosen.get("provenance_ambiguous", pd.Series(dtype=bool)).fillna(False).sum()) if len(chosen) else 0,
    }
    return merged, chosen, unmatched, summary


def verdict_summary(df: pd.DataFrame):
    counts = df["human_verdict"].value_counts(dropna=False)
    n = int(len(df))
    return pd.DataFrame({
        "human_verdict": counts.index.astype(str),
        "n": counts.values,
        "percent": [round(100*x/n, 1) if n else None for x in counts.values],
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--evidence", default=Path("analysis/evidence_presence_sample_absent_semantic_final.csv"), type=Path)
    ap.add_argument("--conflict", default=Path("analysis/conflict_supersede_sample_reviewed_final_strict.csv"), type=Path)
    ap.add_argument("--out-dir", default=Path("analysis/validation_pipeline_audit"), type=Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_csv(args.raw)
    evidence = load_csv(args.evidence)
    conflict = load_csv(args.conflict)

    raw_profile = {
        "rows": int(len(raw)),
        "repeatIndex": {str(k): int(v) for k,v in raw["repeatIndex"].value_counts(dropna=False).items()},
        "pipeline": {str(k): int(v) for k,v in raw["pipeline"].value_counts(dropna=False).items()},
        "judgeModel": {str(k): int(v) for k,v in raw["judgeModel"].value_counts(dropna=False).items()},
        "judgePromptVersion": {str(k): int(v) for k,v in raw["judgePromptVersion"].value_counts(dropna=False).items()},
    }

    summaries = {"raw_profile": raw_profile}
    chosen_by_name = {}
    for name, sample in [("evidence_presence", evidence), ("conflict_supersede", conflict)]:
        merged, chosen, unmatched, summary = audit_sample(sample, raw, name)
        merged.to_csv(args.out_dir / f"{name}_all_source_candidates.csv", index=False)
        chosen.to_csv(args.out_dir / f"{name}_with_provenance.csv", index=False)
        unmatched.to_csv(args.out_dir / f"{name}_unmatched.csv", index=False)
        verdict_summary(sample).to_csv(args.out_dir / f"{name}_verdicts_original.csv", index=False)
        summaries[name] = summary
        chosen_by_name[name] = chosen

    # Conflict/supersede duplicate audit in the original sample.
    dup = conflict[conflict.duplicated(UNIT_KEYS, keep=False)].sort_values(UNIT_KEYS + ["sample_id"])
    dup.to_csv(args.out_dir / "conflict_supersede_duplicate_units.csv", index=False)
    summaries["conflict_supersede"]["duplicate_rows"] = int(len(dup))
    summaries["conflict_supersede"]["duplicate_units"] = int(dup.groupby(UNIT_KEYS).ngroups) if len(dup) else 0

    # Sensitivity: only unique, full-pipeline units; contradictory duplicate verdicts excluded rather than guessed.
    cprov = chosen_by_name["conflict_supersede"].copy()
    if len(cprov):
        full = cprov[cprov["pipeline"] == "full"].copy()
        unit_nverdict = full.groupby(UNIT_KEYS)["human_verdict"].nunique()
        conflict_units = unit_nverdict[unit_nverdict > 1].index
        if len(conflict_units):
            marker = full.set_index(UNIT_KEYS).index.isin(conflict_units)
            contradictory = full[marker].copy()
            full_clean = full[~marker].drop_duplicates(UNIT_KEYS, keep="first").copy()
        else:
            contradictory = full.iloc[0:0].copy()
            full_clean = full.drop_duplicates(UNIT_KEYS, keep="first").copy()
        contradictory.to_csv(args.out_dir / "conflict_supersede_contradictory_duplicates.csv", index=False)
        full_clean.to_csv(args.out_dir / "conflict_supersede_full_unique_clean.csv", index=False)
        verdict_summary(full_clean).to_csv(args.out_dir / "conflict_supersede_verdicts_full_unique_clean.csv", index=False)
        summaries["conflict_supersede"]["full_unique_clean_rows"] = int(len(full_clean))
        summaries["conflict_supersede"]["contradictory_duplicate_rows_excluded"] = int(len(contradictory))
        summaries["conflict_supersede"]["full_unique_clean_verdicts"] = full_clean["human_verdict"].value_counts().to_dict()

    with (args.out_dir / "audit_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)

    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    print(f"\nAudit outputs: {args.out_dir}")

if __name__ == "__main__":
    main()
