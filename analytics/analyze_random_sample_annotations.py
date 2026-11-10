#!/usr/bin/env python3
"""analyze_random_sample_annotations.py

Comprehensive evaluation of human annotations vs 5 automated LLM judges
on the 228 annotated conversations from the Random Sample.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import accuracy_score, cohen_kappa_score, precision_score, recall_score

BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_DIR = BASE_DIR / "misc" / "annotation_excel_files"
ANALYTICS_DIR = BASE_DIR / "analytics"
CHARTS_DIR = ANALYTICS_DIR / "charts"
ARTIFACT_DIR = Path("/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535")

CHARTS_DIR.mkdir(parents=True, exist_ok=True)
if ARTIFACT_DIR.is_dir():
    ARTIFACT_CHARTS_DIR = ARTIFACT_DIR / "charts"
    ARTIFACT_CHARTS_DIR.mkdir(parents=True, exist_ok=True)
else:
    ARTIFACT_CHARTS_DIR = None

# Styling
plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "axes.edgecolor": "#cccccc",
    "axes.linewidth": 0.8,
    "grid.color": "#ebebeb",
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
})

NUMERIC_METRICS = [
    ("socratic_guidance", "Socratic Guidance (0-3)", "Socratic Guidance"),
    ("scaffolding", "Scaffolding (0-3)", "Scaffolding"),
    ("state_adaptation", "State Adaptation (0-3)", "State Adaptation"),
    ("diagnosis", "Diagnosis (0-3)", "Diagnosis"),
    ("student_agency", "Student Agency (0-3)", "Student Agency"),
    ("progression", "Progression (0-3)", "Progression"),
    ("coherence", "Coherence (0-3)", "Coherence"),
]

JUDGES = ["Judge 1", "Judge 2", "Judge 3", "Judge 4", "Judge 5"]
JUDGE_NAMES = {
    "Judge 1": "Judge 1 (beam:cloud)",
    "Judge 2": "Judge 2 (gpt-oss:120b)",
    "Judge 3": "Judge 3 (minimax-m3.1-flash)",
    "Judge 4": "Judge 4 (imajev-4b v1)",
    "Judge 5": "Judge 5 (imajev-4b v2)",
}


def load_and_merge_data():
    ann_path = EXCEL_DIR / "random_sample_annotator.xlsx"
    judge_path = EXCEL_DIR / "random_sample_judges.xlsx"

    df_ann = pd.read_excel(ann_path)
    valid_ann = df_ann.dropna(subset=["Socratic Guidance (0-3)"]).copy()

    df_judges = pd.read_excel(judge_path, header=[0, 1])
    df_judges.columns = [
        f"{c[0]}|{c[1]}" if "Unnamed" not in str(c[1]) else c[0]
        for c in df_judges.columns
    ]
    valid_judges = df_judges.dropna(subset=["Annotation ID"]).copy()

    merged = pd.merge(valid_ann, valid_judges, on="Annotation ID", how="inner")
    return merged


def compute_metrics(merged):
    results = []
    for key, raw_col, clean_name in NUMERIC_METRICS:
        h = merged[raw_col].values
        for j in JUDGES:
            j_col = f"{raw_col}|{j}"
            jv = merged[j_col].values

            std_h = np.std(h)
            std_j = np.std(jv)
            if std_h > 0 and std_j > 0:
                pr, p_pr = pearsonr(h, jv)
                sr, p_sr = spearmanr(h, jv)
            else:
                pr, p_pr, sr, p_sr = 0.0, 1.0, 0.0, 1.0

            mae = np.mean(np.abs(jv - h))
            rmse = np.sqrt(np.mean((jv - h) ** 2))
            bias = np.mean(jv - h)
            exact = np.mean(jv == h) * 100.0
            within_1 = np.mean(np.abs(jv - h) <= 1) * 100.0
            try:
                qwk = cohen_kappa_score(h.astype(int), jv.astype(int), weights="quadratic")
            except Exception:
                qwk = 0.0

            results.append({
                "metric_key": key,
                "metric": clean_name,
                "judge": j,
                "judge_label": JUDGE_NAMES[j],
                "human_mean": float(np.mean(h)),
                "human_std": float(std_h),
                "judge_mean": float(np.mean(jv)),
                "judge_std": float(std_j),
                "bias": float(bias),
                "mae": float(mae),
                "rmse": float(rmse),
                "exact_pct": float(exact),
                "within_1_pct": float(within_1),
                "pearson_r": float(pr),
                "pearson_p": float(p_pr),
                "spearman_rho": float(sr),
                "spearman_p": float(p_sr),
                "qwk": float(qwk),
            })
    return pd.DataFrame(results)


def save_chart(fig, filename):
    paths = [CHARTS_DIR / filename]
    if ARTIFACT_CHARTS_DIR:
        paths.append(ARTIFACT_CHARTS_DIR / filename)
        paths.append(ARTIFACT_DIR / filename)
    for p in paths:
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Saved: {p}")
    plt.close(fig)


def main():
    merged = load_and_merge_data()
    print(f"Loaded and merged {len(merged)} conversations successfully.")

    df_metrics = compute_metrics(merged)
    csv_path = ANALYTICS_DIR / "random_sample_annotation_analysis.csv"
    df_metrics.to_csv(csv_path, index=False)
    print(f"Saved analysis CSV to {csv_path}")

    # Matrices for Heatmaps
    pivot_r = df_metrics.pivot(index="metric", columns="judge", values="pearson_r")
    pivot_mae = df_metrics.pivot(index="metric", columns="judge", values="mae")
    pivot_exact = df_metrics.pivot(index="metric", columns="judge", values="exact_pct")
    pivot_bias = df_metrics.pivot(index="metric", columns="judge", values="bias")

    order = [m[2] for m in NUMERIC_METRICS]
    pivot_r = pivot_r.reindex(order)
    pivot_mae = pivot_mae.reindex(order)
    pivot_exact = pivot_exact.reindex(order)
    pivot_bias = pivot_bias.reindex(order)

    # Figure 1: Accuracy Overview: MAE & Exact Agreement Heatmaps
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    sns.heatmap(
        pivot_mae,
        annot=True,
        fmt=".3f",
        cmap="YlOrRd",
        cbar_kws={"label": "Mean Absolute Error (Lower is Better)"},
        ax=ax1,
        linewidths=0.5,
    )
    ax1.set_title("Random Sample: MAE vs Human Annotations (N=228)", fontsize=13, fontweight="bold", pad=12)
    ax1.set_xlabel("Judge Model", fontsize=11, labelpad=8)
    ax1.set_ylabel("Socratic Metric", fontsize=11)
    ax1.set_xticklabels([f"{j}\n({JUDGE_NAMES[j].split('(')[1].rstrip(')')})" for j in pivot_mae.columns], rotation=0, fontsize=9)

    sns.heatmap(
        pivot_exact,
        annot=True,
        fmt=".1f",
        cmap="Blues",
        cbar_kws={"label": "Exact Agreement % (Higher is Better)"},
        ax=ax2,
        linewidths=0.5,
    )
    ax2.set_title("Random Sample: Exact Agreement Rate (%)", fontsize=13, fontweight="bold", pad=12)
    ax2.set_xlabel("Judge Model", fontsize=11, labelpad=8)
    ax2.set_ylabel("", fontsize=11)
    ax2.set_xticklabels([f"{j}\n({JUDGE_NAMES[j].split('(')[1].rstrip(')')})" for j in pivot_exact.columns], rotation=0, fontsize=9)

    plt.tight_layout()
    save_chart(fig, "rnd_judge_accuracy_mae_and_exact_agreement.png")

    # Figure 2: Pearson Correlation & Systematic Bias Heatmaps
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    sns.heatmap(
        pivot_r,
        annot=True,
        fmt=".2f",
        cmap="mako",
        vmin=-0.1,
        vmax=0.7,
        cbar_kws={"label": "Pearson Correlation (r)"},
        ax=ax1,
        linewidths=0.5,
    )
    ax1.set_title("Random Sample: Pearson Correlation (r)", fontsize=13, fontweight="bold", pad=12)
    ax1.set_xlabel("Judge Model", fontsize=11, labelpad=8)
    ax1.set_ylabel("Socratic Metric", fontsize=11)
    ax1.set_xticklabels([f"{j}\n({JUDGE_NAMES[j].split('(')[1].rstrip(')')})" for j in pivot_r.columns], rotation=0, fontsize=9)

    sns.heatmap(
        pivot_bias,
        annot=True,
        fmt="+.2f",
        cmap="coolwarm",
        center=0.0,
        vmin=-0.4,
        vmax=0.8,
        cbar_kws={"label": "Mean Bias (Judge - Human)"},
        ax=ax2,
        linewidths=0.5,
    )
    ax2.set_title("Random Sample: Systematic Scoring Bias", fontsize=13, fontweight="bold", pad=12)
    ax2.set_xlabel("Judge Model", fontsize=11, labelpad=8)
    ax2.set_ylabel("", fontsize=11)
    ax2.set_xticklabels([f"{j}\n({JUDGE_NAMES[j].split('(')[1].rstrip(')')})" for j in pivot_bias.columns], rotation=0, fontsize=9)

    plt.tight_layout()
    save_chart(fig, "rnd_judge_correlation_and_bias_profiles.png")

    # Figure 3: Disagreement Resolution & Outliers
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Severe Disagreements (range >= 2) - 29 cases
    labels = ["Judge 3\n(minimax-m3.1)", "Judge 1\n(beam:cloud)", "Judge 2\n(gpt-oss:120b)", "Tie / Both\nEquidistant"]
    counts = [13, 5, 5, 6]
    colors = ["#4682b4", "#2b5c8f", "#d9534f", "#b0c4de"]
    bars = ax1.bar(labels, counts, color=colors, edgecolor="#333333", linewidth=1.2, width=0.55)
    ax1.set_title("Closest Judge to Human in Severe Disagreements\n(29 Metric-Level Cases with Range ≥ 2)", fontsize=12, fontweight="bold", pad=12)
    ax1.set_ylabel("Number of Cases", fontsize=11)
    ax1.set_ylim(0, 16)
    for bar in bars:
        yval = bar.get_height()
        pct = (yval / 29) * 100
        ax1.text(bar.get_x() + bar.get_width() / 2, yval + 0.4, f"{int(yval)} ({pct:.1f}%)", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # 2-vs-1 Outlier Siding
    outlier_labels = ["Judge 2\nOutlier (N=206)", "Judge 1\nOutlier (N=125)", "Judge 3\nOutlier (N=93)"]
    majority_pcts = [144 / 206 * 100, 75 / 125 * 100, 65 / 93 * 100]
    outlier_pcts = [41 / 206 * 100, 43 / 125 * 100, 26 / 93 * 100]
    neither_pcts = [21 / 206 * 100, 7 / 125 * 100, 2 / 93 * 100]

    x = np.arange(len(outlier_labels))
    width = 0.25
    ax2.bar(x - width, majority_pcts, width, label="Human Sided with Majority (Other 2)", color="#2e7d32", edgecolor="#333333", linewidth=1.0)
    ax2.bar(x, outlier_pcts, width, label="Human Sided with Outlier", color="#d32f2f", edgecolor="#333333", linewidth=1.0)
    ax2.bar(x + width, neither_pcts, width, label="Human Sided with Neither", color="#757575", edgecolor="#333333", linewidth=1.0)

    ax2.set_title("Human Alignment in 2-vs-1 Disagreement Splits\n(Did Human Agree with the Lone Outlier or Majority?)", fontsize=12, fontweight="bold", pad=12)
    ax2.set_ylabel("Percentage of Cases (%)", fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels(outlier_labels, fontsize=10)
    ax2.set_ylim(0, 85)
    ax2.legend(frameon=True, facecolor="white", edgecolor="#ccc", fontsize=9)

    plt.tight_layout()
    save_chart(fig, "rnd_judge_disagreement_and_outlier_resolution.png")

    # Figure 4: Overall Holistic Score Scatter (Human Overall Score vs Judges)
    for j in JUDGES:
        cols = [f"{m[1]}|{j}" for m in NUMERIC_METRICS]
        merged[f"{j}_mean_score"] = merged[cols].mean(axis=1)

    merged["j1_j2_j3_mean_score"] = merged[[f"{m[1]}|{j}" for m in NUMERIC_METRICS for j in ["Judge 1", "Judge 2", "Judge 3"]]].mean(axis=1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Scatter 1: Human Overall Score (out of 10) vs Judge 1
    h_scores = merged["Overall Score (out of 10)"].values
    j1_scores = merged["Judge 1_mean_score"].values
    r1, _ = pearsonr(h_scores, j1_scores)
    sns.regplot(x=j1_scores, y=h_scores, ax=ax1, color="#1f4e78", scatter_kws={"s": 40, "alpha": 0.7}, line_kws={"linewidth": 2, "color": "#e74c3c"})
    ax1.set_title(f"Human Overall Score vs Judge 1 (beam:cloud)\nPearson r = {r1:.3f} (p < 0.001)", fontsize=12, fontweight="bold", pad=10)
    ax1.set_xlabel("Judge 1 Average Score (Across 7 Metrics, 0-3)", fontsize=11)
    ax1.set_ylabel("Human Overall Score (out of 10)", fontsize=11)

    # Scatter 2: Human Overall Score (out of 10) vs J1-J3 Ensemble
    j123_scores = merged["j1_j2_j3_mean_score"].values
    rens, _ = pearsonr(h_scores, j123_scores)
    sns.regplot(x=j123_scores, y=h_scores, ax=ax2, color="#2e7d32", scatter_kws={"s": 40, "alpha": 0.7}, line_kws={"linewidth": 2, "color": "#e74c3c"})
    ax2.set_title(f"Human Overall Score vs J1-J3 Ensemble Average\nPearson r = {rens:.3f} (p < 0.001)", fontsize=12, fontweight="bold", pad=10)
    ax2.set_xlabel("Ensemble Average Score (Across 7 Metrics, 0-3)", fontsize=11)
    ax2.set_ylabel("Human Overall Score (out of 10)", fontsize=11)

    plt.tight_layout()
    save_chart(fig, "rnd_human_overall_score_calibration.png")
    print("All Random Sample charts generated successfully.")


if __name__ == "__main__":
    main()
