from pathlib import Path

import pandas as pd
from scipy.stats import wilcoxon
from statsmodels.stats.multitest import multipletests


INPUT_FILE = Path("analysis/miss_decomposition.csv")
OUTPUT_FILE = Path("analysis/resolution_ablation_wilcoxon.csv")


def main():
    df = pd.read_csv(INPUT_FILE)

    required_columns = {
        "reqId",
        "model",
        "mode",
        "pipeline",
        "n_ground_truth_elements",
        "integration_miss",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Hiányzó oszlopok: {sorted(missing_columns)}"
        )

    df = df[
        (df["mode"] == "hybrid")
        & (df["pipeline"].isin(["full", "no_resolution"]))
    ].copy()

    if df.empty:
        raise ValueError("Nincsenek megfelelő hybrid sorok.")

    if (df["n_ground_truth_elements"] <= 0).any():
        raise ValueError(
            "Nulla vagy negatív ground-truth elemszám található."
        )

    # Abszolút integration-miss arány:
    # kihagyott integrációs elemek / összes ground-truth elem.
    df["absolute_integration_miss_rate"] = (
        df["integration_miss"]
        / df["n_ground_truth_elements"]
    )

    results = []

    for model in sorted(df["model"].dropna().unique()):
        model_data = df[df["model"] == model].copy()

        # Requirement-szintű átlag a tesztek felett.
        requirement_rates = (
            model_data
            .groupby(
                ["reqId", "pipeline"],
                as_index=False,
            )
            .agg(
                integration_miss_rate=(
                    "absolute_integration_miss_rate",
                    "mean",
                ),
                n_tests=(
                    "absolute_integration_miss_rate",
                    "count",
                ),
            )
        )

        paired = requirement_rates.pivot(
            index="reqId",
            columns="pipeline",
            values="integration_miss_rate",
        )

        paired = paired.reindex(
            columns=["full", "no_resolution"]
        )

        incomplete = paired.isna().any(axis=1)

        if incomplete.any():
            print(f"\n{model}: hiányos párok:")
            print(paired[incomplete].to_string())

        paired = paired.dropna()

        if paired.empty:
            raise ValueError(
                f"{model}: nincs teljes requirement-pár."
            )

        full_rates = paired["full"]
        no_resolution_rates = paired["no_resolution"]

        # Pozitív különbség:
        # a full pipeline több integration misst tartalmaz.
        differences = full_rates - no_resolution_rates

        if (differences != 0).sum() == 0:
            statistic = 0.0
            p_value = 1.0
        else:
            test_result = wilcoxon(
                full_rates,
                no_resolution_rates,
                alternative="two-sided",
                zero_method="wilcox",
                correction=False,
                method="auto",
            )

            statistic = float(test_result.statistic)
            p_value = float(test_result.pvalue)

        results.append({
            "model": model,
            "n_pairs": len(paired),
            "full_mean": full_rates.mean(),
            "no_resolution_mean": no_resolution_rates.mean(),
            "full_median": full_rates.median(),
            "no_resolution_median": no_resolution_rates.median(),
            "mean_paired_difference": differences.mean(),
            "median_paired_difference": differences.median(),
            "positive_differences": int(
                (differences > 0).sum()
            ),
            "negative_differences": int(
                (differences < 0).sum()
            ),
            "zero_differences": int(
                (differences == 0).sum()
            ),
            "wilcoxon_statistic": statistic,
            "p_value_raw": p_value,
        })

    output = pd.DataFrame(results)

    output["p_value_holm"] = multipletests(
        output["p_value_raw"],
        method="holm",
    )[1]

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\nVégső eredmény:")
    print(output.to_string(index=False))

    print(f"\nMentve ide: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()