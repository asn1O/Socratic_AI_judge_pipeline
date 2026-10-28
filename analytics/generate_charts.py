#!/usr/bin/env python3
"""generate_charts.py - Generate publication-quality visualization charts for Socratic AI evaluation."""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_CHARTS_DIR = Path(__file__).resolve().parent / "charts"
ARTIFACT_DIR = Path("/home/ayaans/.gemini/antigravity/brain/c0433e3f-a1b5-406d-8e86-0ce82a4b738a")

WORKSPACE_CHARTS_DIR.mkdir(parents=True, exist_ok=True)
if ARTIFACT_DIR.is_dir():
    ARTIFACT_CHARTS_DIR = ARTIFACT_DIR / "charts"
    ARTIFACT_CHARTS_DIR.mkdir(parents=True, exist_ok=True)
else:
    ARTIFACT_CHARTS_DIR = None

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
benchmark_df = pd.read_csv(Path(__file__).resolve().parent / "model_benchmark_comparison.csv")
dist_df = pd.read_csv(Path(__file__).resolve().parent / "overall_score_distribution.csv")
agreement_df = pd.read_csv(Path(__file__).resolve().parent / "inter_judge_reliability.csv")


def save_plot(fig, filename):
    targets = [WORKSPACE_CHARTS_DIR]
    if ARTIFACT_CHARTS_DIR:
        targets.append(ARTIFACT_CHARTS_DIR)
        targets.append(ARTIFACT_DIR)
    for target_dir in targets:
        path = target_dir / filename
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"Saved {path}")
    plt.close(fig)


# -----------------------------------------------------------------------------
# Chart 1: Model Socratic Guidance Score
# -----------------------------------------------------------------------------
def plot_model_rankings():
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
    ax.set_title("Socratic Guidance: Model Benchmark Comparison (Clean N = 2,713)", fontsize=14, fontweight="bold", pad=15)
    
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
# Chart 2: 5-Evaluator Score Distribution Comparison (J1, J2, J3, JEV-1, JEV-2)
# -----------------------------------------------------------------------------
def plot_score_distributions():
    metrics = [
        "socratic_guidance", "scaffolding", "diagnosis", 
        "student_agency", "progression", "state_adaptation", "coherence"
    ]
    
    j1_s3, j2_s3, j3_s3, j1_ev_s3, j2_ev_s3 = [], [], [], [], []
    labels = []
    
    for m in metrics:
        sub = dist_df[dist_df["metric"] == m]
        s3_row = sub[sub["score"] == 3]
        if not s3_row.empty:
            j1_val = float(s3_row["judge_1_pct"].values[0].replace("%", ""))
            j2_val = float(s3_row["judge_2_pct"].values[0].replace("%", ""))
            j3_val = float(s3_row["judge_3_pct"].values[0].replace("%", ""))
            j1_ev_val = float(s3_row["jev_1_pct"].values[0].replace("%", "")) if "jev_1_pct" in s3_row.columns else 0.0
            j2_ev_val = float(s3_row["jev_2_pct"].values[0].replace("%", "")) if "jev_2_pct" in s3_row.columns else 0.0
            j1_s3.append(j1_val)
            j2_s3.append(j2_val)
            j3_s3.append(j3_val)
            j1_ev_s3.append(j1_ev_val)
            j2_ev_s3.append(j2_ev_val)
            labels.append(m.replace("_", " ").title())
            
    x = np.arange(len(labels))
    width = 0.16
    
    fig, ax = plt.subplots(figsize=(15, 6.5))
    bars1 = ax.bar(x - 2.0 * width, j1_s3, width, label="Judge 1 (beam:cloud)", color="#3182ce")
    bars2 = ax.bar(x - 1.0 * width, j2_s3, width, label="Judge 2 (gpt-oss:120b)", color="#805ad5")
    bars3 = ax.bar(x, j3_s3, width, label="Judge 3 (minimax-m3.1-flash)", color="#38a169")
    bars4 = ax.bar(x + 1.0 * width, j1_ev_s3, width, label="JEV-1 (imajev-4b Turns)", color="#e53e3e")
    bars5 = ax.bar(x + 2.0 * width, j2_ev_s3, width, label="JEV-2 (imajev-4b State/Reasoning)", color="#dd6b20")
    
    ax.set_ylabel("% of Conversations Awarded Top Score (3 / 3)", fontsize=11, fontweight="bold")
    ax.set_title("5-Evaluator Calibration: Proportion of Perfect Scores (Score 3) Awarded (N = 2,713)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=10)
    ax.set_ylim(0, 115)
    ax.legend(loc="upper left", frameon=True, fontsize=9.5)
    
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2, f"{bar.get_height():.0f}%", ha="center", va="bottom", fontsize=7, color="#2b6cb0")
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2, f"{bar.get_height():.0f}%", ha="center", va="bottom", fontsize=7, color="#6b46c1")
    for bar in bars3:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2, f"{bar.get_height():.0f}%", ha="center", va="bottom", fontsize=7, color="#276749")
    for bar in bars4:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2, f"{bar.get_height():.0f}%", ha="center", va="bottom", fontsize=7, color="#9b2c2c")
    for bar in bars5:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2, f"{bar.get_height():.0f}%", ha="center", va="bottom", fontsize=7, color="#c05621")
        
    save_plot(fig, "chart2_judge_calibration.png")


# -----------------------------------------------------------------------------
# Chart 3: Socratic Guidance vs Premature Answering Trade-off
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
    ax.set_title("Socratic Guidance vs. Premature Answer Risk (Bubble Size = Clean Sample Size N)", fontsize=13, fontweight="bold", pad=14)
    
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
        
    ax.axvspan(-0.1, 2, color="#48bb78", alpha=0.1, label="Low Premature Risk Zone (< 2%)")
    ax.legend(loc="lower left", frameon=True)
    
    save_plot(fig, "chart3_socratic_vs_premature.png")


# -----------------------------------------------------------------------------
# Chart 4: Multi-Evaluator Reliability Metrics Matrix (J1, J2, J3, JEV-1, JEV-2)
# -----------------------------------------------------------------------------
def plot_inter_judge_matrix():
    num_df = agreement_df[agreement_df["type"] == "numerical"].copy()
    
    metrics = [m.replace("_", " ").title() for m in num_df["metric"]]
    exact_match = [float(v) for v in num_df["all_3_exact_pct"]]
    within_1 = [float(v) for v in num_df["all_3_within_1_pct"]]
    j1_mean = [float(v) * (100 / 3.0) for v in num_df["judge_1_mean"]]
    j2_mean = [float(v) * (100 / 3.0) for v in num_df["judge_2_mean"]]
    j3_mean = [float(v) * (100 / 3.0) for v in num_df["judge_3_mean"]]
    
    has_jev1 = "jev_1_mean" in num_df.columns and not num_df["jev_1_mean"].isna().all()
    has_jev2 = "jev_2_mean" in num_df.columns and not num_df["jev_2_mean"].isna().all()
    
    rows_list = [exact_match, within_1, j1_mean, j2_mean, j3_mean]
    yticklabels = [
        "All 3 Exact %", "All 3 Within ±1 %",
        "Judge 1 Mean (Scaled)", "Judge 2 Mean (Scaled)", "Judge 3 Mean (Scaled)"
    ]
    if has_jev1:
        jev1_mean = [float(v) * (100 / 3.0) for v in num_df["jev_1_mean"]]
        rows_list.append(jev1_mean)
        yticklabels.append("JEV-1 Mean (Scaled)")
    if has_jev2:
        jev2_mean = [float(v) * (100 / 3.0) for v in num_df["jev_2_mean"]]
        rows_list.append(jev2_mean)
        yticklabels.append("JEV-2 Mean (Scaled)")
    
    matrix = np.array(rows_list)
    fig, ax = plt.subplots(figsize=(11, 6.0))
    
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".1f",
        cmap="YlGnBu",
        xticklabels=metrics,
        yticklabels=yticklabels,
        cbar_kws={"label": "Percentage / Scaled Score (0-100)"},
        ax=ax,
        linewidths=1.0,
        linecolor="white",
        vmin=40,
        vmax=100
    )
    
    ax.set_title("Multi-Evaluator Agreement & Calibration Matrix (N = 2,713)", fontsize=13, fontweight="bold", pad=12)
    plt.xticks(rotation=20, ha="right", fontsize=9.5)
    plt.yticks(rotation=0, fontsize=9.5)
    
    save_plot(fig, "chart4_judge_reliability_matrix.png")


if __name__ == "__main__":
    plot_model_rankings()
    plot_score_distributions()
    plot_quality_vs_premature()
    plot_inter_judge_matrix()
    print("All charts generated successfully.")
