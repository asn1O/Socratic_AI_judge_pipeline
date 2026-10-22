#!/usr/bin/env python3
"""generate_charts.py - Generate publication-quality visualization charts for Socratic AI evaluation."""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ARTIFACT_DIR = Path("/Users/user/.gemini/antigravity-ide/brain/f9f3f49b-d02e-4a18-8bbc-a233619a1e28")
WORKSPACE_CHARTS_DIR = Path("/Users/user/Socratic-AI/Judge/analytics/charts")

ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Set high-quality visual style
plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "axes.edgecolor": "#cccccc",
    "axes.linewidth": 0.8,
    "grid.color": "#ebebeb",
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
})

# Load data
benchmark_df = pd.read_csv("analytics/model_benchmark_comparison.csv")
dist_df = pd.read_csv("analytics/overall_score_distribution.csv")
agreement_df = pd.read_csv("analytics/inter_judge_reliability.csv")


def save_plot(fig, filename):
    for target_dir in [ARTIFACT_DIR, WORKSPACE_CHARTS_DIR]:
        path = target_dir / filename
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"Saved {path}")
    plt.close(fig)


# -----------------------------------------------------------------------------
# Chart 1: Model Socratic Guidance Score
# -----------------------------------------------------------------------------
def plot_model_rankings():
    # Filter or sort
    df = benchmark_df.copy()
    # Clean up model names for readability
    df["display_name"] = df["model_name"].str.replace("OpenRouter_", "OR: ").str.replace("Google_", "").str.replace("NVIDIA_", "")
    df = df.sort_values("socratic_guidance_mean", ascending=True)

    fig, ax = plt.subplots(figsize=(11, 8))
    
    # Color palette based on sample size confidence
    colors = ["#2b6cb0" if n >= 50 else "#a0aec0" for n in df["conversations_evaluated"]]
    
    bars = ax.barh(df["display_name"], df["socratic_guidance_mean"], color=colors, height=0.65, edgecolor="none")
    
    ax.set_xlim(2.0, 3.1)
    ax.set_xlabel("Socratic Guidance Score (0.0 to 3.0 Scale)", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_title("Socratic Guidance: Model Benchmark Comparison", fontsize=14, fontweight="bold", pad=15)
    
    # Value annotations on bars
    for bar, score, n in zip(bars, df["socratic_guidance_mean"], df["conversations_evaluated"]):
        ax.text(
            bar.get_width() + 0.008,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.2f} (N={n})",
            va="center",
            ha="left",
            fontsize=9,
            fontweight="bold" if n >= 50 else "normal",
            color="#2d3748" if n >= 50 else "#718096"
        )

    # Custom legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#2b6cb0", label="Robust Sample Size (N ≥ 50)"),
        Patch(facecolor="#a0aec0", label="Preliminary Sample Size (N < 50)")
    ]
    ax.legend(handles=legend_elements, loc="lower right", frameon=True, framealpha=0.9)
    
    save_plot(fig, "chart1_model_rankings.png")


# -----------------------------------------------------------------------------
# Chart 2: Judge 1 vs Judge 2 Score Distribution Comparison
# -----------------------------------------------------------------------------
def plot_score_distributions():
    metrics = [
        "socratic_guidance", "scaffolding", "diagnosis", 
        "student_agency", "progression", "state_adaptation", "coherence"
    ]
    
    # We want to compare Score 3 % between Judge 1 and Judge 2
    j1_s3 = []
    j2_s3 = []
    labels = []
    
    for m in metrics:
        sub = dist_df[dist_df["metric"] == m]
        s3_row = sub[sub["score"] == 3]
        if not s3_row.empty:
            j1_val = float(s3_row["judge_1_pct"].values[0].replace("%", ""))
            j2_val = float(s3_row["judge_2_pct"].values[0].replace("%", ""))
            j1_s3.append(j1_val)
            j2_s3.append(j2_val)
            labels.append(m.replace("_", " ").title())
            
    x = np.arange(len(labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width/2, j1_s3, width, label="Judge 1 (beam:cloud)", color="#3182ce")
    bars2 = ax.bar(x + width/2, j2_s3, width, label="Judge 2 (gpt-oss:120b)", color="#805ad5")
    
    ax.set_ylabel("% of Conversations Awarded Top Score (3 / 3)", fontsize=11, fontweight="bold")
    ax.set_title("Inter-Judge Calibration: Proportion of Perfect Scores (Score 3) Awarded", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=10)
    ax.set_ylim(0, 112)
    ax.legend(loc="upper left", frameon=True, fontsize=10)
    
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5, f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8.5, color="#2b6cb0")
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5, f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8.5, color="#6b46c1")
        
    save_plot(fig, "chart2_judge_calibration.png")


# -----------------------------------------------------------------------------
# Chart 3: Socratic Quality vs Premature Answering Trade-off
# -----------------------------------------------------------------------------
def plot_quality_vs_premature():
    df = benchmark_df[benchmark_df["conversations_evaluated"] >= 20].copy()
    df["display_name"] = df["model_name"].str.replace("OpenRouter_", "OR: ").str.replace("Google_", "").str.replace("NVIDIA_", "")
    
    fig, ax = plt.subplots(figsize=(10, 6.5))
    
    scatter = ax.scatter(
        df["premature_answer_pct"],
        df["socratic_guidance_mean"],
        s=df["conversations_evaluated"] * 2.2,
        c=df["correctness_pct"],
        cmap="viridis",
        alpha=0.85,
        edgecolors="#2d3748",
        linewidths=1.2,
    )
    
    cbar = plt.colorbar(scatter)
    cbar.set_label("Correctness Rate (%)", fontsize=10, fontweight="bold")
    
    ax.set_xlabel("Premature Answer Rate (%) [Lower is Better]", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_ylabel("Socratic Guidance Score (0-3) [Higher is Better]", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_title("Socratic Guidance vs. Premature Answer Risk (Bubble Size = Sample Size N)", fontsize=13, fontweight="bold", pad=14)
    
    # Annotate key models
    for _, row in df.iterrows():
        offset_y = 0.008 if "ultra" not in row["display_name"].lower() else -0.012
        ax.annotate(
            row["display_name"],
            (row["premature_answer_pct"], row["socratic_guidance_mean"] + offset_y),
            fontsize=8.5,
            fontweight="bold" if "3.1" in row["display_name"] or "ultra" in row["display_name"] else "normal",
            ha="center",
            alpha=0.9
        )
        
    # Shaded optimal quadrant
    ax.axvspan(0, 3, color="#48bb78", alpha=0.1, label="Low Premature Risk Zone (< 3%)")
    ax.legend(loc="lower left", frameon=True)
    
    save_plot(fig, "chart3_socratic_vs_premature.png")


# -----------------------------------------------------------------------------
# Chart 4: Inter-Judge Reliability Metrics Matrix
# -----------------------------------------------------------------------------
def plot_inter_judge_matrix():
    num_df = agreement_df[agreement_df["type"] == "numerical"].copy()
    
    metrics = [m.replace("_", " ").title() for m in num_df["metric"]]
    exact_match = [float(v) for v in num_df["exact_match_pct"]]
    within_1 = [float(v) for v in num_df["within_1_pct"]]
    pearson_r = [float(v) * 100 for v in num_df["pearson_r"]]
    
    matrix = np.array([exact_match, within_1, pearson_r])
    
    fig, ax = plt.subplots(figsize=(10, 4.5))
    
    cmap = sns.light_palette("#2b6cb0", as_cmap=True)
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".1f",
        cmap="YlGnBu",
        xticklabels=metrics,
        yticklabels=["Exact Match %", "Within ±1 %", "Pearson r (×100)"],
        cbar_kws={"label": "Percentage / Scaled Score"},
        ax=ax,
        linewidths=1.0,
        linecolor="white",
        vmin=0,
        vmax=100
    )
    
    ax.set_title("Inter-Judge Agreement & Correlation Metrics (N = 3,007)", fontsize=13, fontweight="bold", pad=12)
    plt.xticks(rotation=20, ha="right", fontsize=9.5)
    plt.yticks(rotation=0, fontsize=10)
    
    save_plot(fig, "chart4_judge_reliability_matrix.png")


if __name__ == "__main__":
    plot_model_rankings()
    plot_score_distributions()
    plot_quality_vs_premature()
    plot_inter_judge_matrix()
    print("All charts generated successfully.")
