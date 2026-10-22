#!/usr/bin/env python3
"""data_analysis.py - Comprehensive evaluation and data analysis on 3-judge outputs.

Processes all model evaluation folders in `output/`, filters set files (*-set[*.json),
ignores state tracking files (evaluation_state*.json), extracts scores from Judge 1, Judge 2,
and Judge 3, converts evaluations to standard CSV format per model (stored solely under analytics/),
computes statistical metrics, benchmarks model performance, and evaluates inter-judge agreement.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("data_analysis")

NUMERIC_METRICS = [
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
]

BOOLEAN_METRICS = [
    "correctness",
    "premature_answer",
    "hallucination",
]

ALL_METRICS = NUMERIC_METRICS + BOOLEAN_METRICS
JUDGES = [1, 2, 3]


def natural_sort_key(s: str) -> list[Any]:
    """Sort strings containing numbers in natural human order (e.g., set[2] before set[10])."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def is_set_file(filename: str) -> bool:
    """Return True if filename matches a set output file and is not a state file."""
    if not filename.endswith(".json"):
        return False
    lower = filename.lower()
    if "evaluation_state" in lower:
        return False
    return "set" in lower and ("[" in lower or "set_" in lower or "set-" in lower)


def calculate_pearson_r(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient between two lists of numbers."""
    n = len(x)
    if n < 2 or len(y) != n:
        return 0.0
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    if var_x == 0 or var_y == 0:
        return 0.0
    cov_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    return cov_xy / math.sqrt(var_x * var_y)


def calculate_mae(x: list[float], y: list[float]) -> float:
    """Compute Mean Absolute Error between two lists of numbers."""
    if not x or len(x) != len(y):
        return 0.0
    return sum(abs(xi - yi) for xi, yi in zip(x, y)) / len(x)


def calculate_cohen_kappa(x: list[bool], y: list[bool]) -> float:
    """Compute Cohen's Kappa for two binary ratings."""
    n = len(x)
    if n == 0 or len(y) != n:
        return 0.0
    
    tt = sum(1 for xi, yi in zip(x, y) if xi and yi)
    tf = sum(1 for xi, yi in zip(x, y) if xi and not yi)
    ft = sum(1 for xi, yi in zip(x, y) if not xi and yi)
    ff = sum(1 for xi, yi in zip(x, y) if not xi and not yi)
    
    po = (tt + ff) / n
    p_yes = ((tt + tf) / n) * ((tt + ft) / n)
    p_no = ((ft + ff) / n) * ((tf + ff) / n)
    pe = p_yes + p_no
    
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def process_model_folder(
    model_dir: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Process a single model folder and extract evaluation rows across all 3 judges."""
    model_name = model_dir.name
    set_files = sorted(
        [f for f in model_dir.iterdir() if f.is_file() and is_set_file(f.name)],
        key=lambda f: natural_sort_key(f.name),
    )

    rows: List[Dict[str, Any]] = []

    for file_path in set_files:
        try:
            with open(file_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, list):
                logger.warning("Skipping %s: not a JSON array", file_path)
                continue
        except Exception as exc:
            logger.error("Error reading %s: %s", file_path, exc)
            continue

        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue

            convo_idx = item.get("conversation_index", idx)
            convo_id = f"{file_path.name}:{convo_idx}"

            j1 = item.get("judge_1", {}) if isinstance(item.get("judge_1"), dict) else {}
            j2 = item.get("judge_2", {}) if isinstance(item.get("judge_2"), dict) else {}
            j3 = item.get("judge_3", {}) if isinstance(item.get("judge_3"), dict) else {}

            j1_eval = j1.get("evaluation", {}) if isinstance(j1.get("evaluation"), dict) else {}
            j2_eval = j2.get("evaluation", {}) if isinstance(j2.get("evaluation"), dict) else {}
            j3_eval = j3.get("evaluation", {}) if isinstance(j3.get("evaluation"), dict) else {}

            j1_tokens = j1.get("total_tokens", 0) or 0
            j2_tokens = j2.get("total_tokens", 0) or 0
            j3_tokens = j3.get("total_tokens", 0) or 0

            row: Dict[str, Any] = {
                "conversation_id": convo_id,
                "file_name": file_path.name,
                "conversation_index": convo_idx,
            }

            # Numerical metrics: Mean across all present judges
            for nm in NUMERIC_METRICS:
                v1 = j1_eval.get(nm)
                v2 = j2_eval.get(nm)
                v3 = j3_eval.get(nm)

                row[f"judge_1_{nm}"] = v1
                row[f"judge_2_{nm}"] = v2
                row[f"judge_3_{nm}"] = v3

                vals = [float(v) for v in (v1, v2, v3) if v is not None]
                if vals:
                    row[nm] = round(statistics.mean(vals), 2)
                else:
                    row[nm] = None

            # Boolean metrics: Majority vote across all present judges + rate
            for bm in BOOLEAN_METRICS:
                b1 = j1_eval.get(bm)
                b2 = j2_eval.get(bm)
                b3 = j3_eval.get(bm)

                row[f"judge_1_{bm}"] = b1
                row[f"judge_2_{bm}"] = b2
                row[f"judge_3_{bm}"] = b3

                bool_vals = [bool(b) for b in (b1, b2, b3) if b is not None]
                if bool_vals:
                    true_count = sum(1 for b in bool_vals if b)
                    # Majority consensus
                    row[bm] = true_count >= (len(bool_vals) / 2.0)
                    row[f"{bm}_rate"] = round(true_count / len(bool_vals), 3)
                else:
                    row[bm] = None
                    row[f"{bm}_rate"] = None

            row["judge_1_tokens"] = j1_tokens
            row["judge_2_tokens"] = j2_tokens
            row["judge_3_tokens"] = j3_tokens
            row["total_tokens"] = j1_tokens + j2_tokens + j3_tokens

            rows.append(row)

    summary = compute_summary_statistics(model_name, rows, len(set_files))
    return rows, summary


def compute_summary_statistics(
    model_name: str, rows: List[Dict[str, Any]], num_set_files: int
) -> Dict[str, Any]:
    """Compute statistical metrics across 3-judge evaluations."""
    total_convos = len(rows)
    if total_convos == 0:
        return {
            "model_name": model_name,
            "total_files": num_set_files,
            "total_conversations": 0,
        }

    summary: Dict[str, Any] = {
        "model_name": model_name,
        "total_files": num_set_files,
        "total_conversations": total_convos,
        "metrics": {},
    }

    # Numerical metrics stats (mean of the 3-judge average)
    for nm in NUMERIC_METRICS:
        vals = [r[nm] for r in rows if r.get(nm) is not None]
        if vals:
            summary["metrics"][nm] = {
                "mean": round(statistics.mean(vals), 3),
                "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
                "median": round(statistics.median(vals), 3),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
            }
        else:
            summary["metrics"][nm] = None

    # Boolean metrics stats
    for bm in BOOLEAN_METRICS:
        vals = [r[bm] for r in rows if r.get(bm) is not None]
        rate_vals = [r[f"{bm}_rate"] for r in rows if r.get(f"{bm}_rate") is not None]
        if vals:
            true_count = sum(1 for v in vals if v is True)
            pct = round(true_count / len(vals) * 100.0, 2)
            mean_rate = round(statistics.mean(rate_vals), 3) if rate_vals else 0.0
            summary["metrics"][bm] = {
                "true_count": true_count,
                "total_count": len(vals),
                "percentage": pct,
                "mean_rate": mean_rate,
            }
        else:
            summary["metrics"][bm] = None

    # Token stats
    t1 = [r["judge_1_tokens"] for r in rows if r.get("judge_1_tokens")]
    t2 = [r["judge_2_tokens"] for r in rows if r.get("judge_2_tokens")]
    t3 = [r["judge_3_tokens"] for r in rows if r.get("judge_3_tokens")]
    tot = [r["total_tokens"] for r in rows if r.get("total_tokens")]

    summary["tokens"] = {
        "avg_judge_1_tokens": round(statistics.mean(t1), 1) if t1 else 0,
        "avg_judge_2_tokens": round(statistics.mean(t2), 1) if t2 else 0,
        "avg_judge_3_tokens": round(statistics.mean(t3), 1) if t3 else 0,
        "avg_total_tokens_per_convo": round(statistics.mean(tot), 1) if tot else 0,
    }

    return summary


def write_csv(filepath: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    """Write dict rows to CSV file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def compute_inter_judge_agreement_3judges(all_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute pairwise and 3-judge agreement metrics across all conversations."""
    total_convos = len(all_rows)
    agreement_report: Dict[str, Any] = {
        "total_evaluated_conversations": total_convos,
        "judge_models": {
            "judge_1": "beam:cloud",
            "judge_2": "gpt-oss:120b",
            "judge_3": "minimax-m3.1-flash",
        },
        "numerical_metrics": {},
        "boolean_metrics": {},
    }

    for nm in NUMERIC_METRICS:
        j1_vals, j2_vals, j3_vals = [], [], []
        exact_all_3 = 0
        within_1_span = 0

        exact_12, within_12 = 0, 0
        exact_13, within_13 = 0, 0
        exact_23, within_23 = 0, 0

        for r in all_rows:
            v1 = r.get(f"judge_1_{nm}")
            v2 = r.get(f"judge_2_{nm}")
            v3 = r.get(f"judge_3_{nm}")

            if v1 is not None and v2 is not None and v3 is not None:
                f1, f2, f3 = float(v1), float(v2), float(v3)
                j1_vals.append(f1)
                j2_vals.append(f2)
                j3_vals.append(f3)

                if f1 == f2 == f3:
                    exact_all_3 += 1
                if max(f1, f2, f3) - min(f1, f2, f3) <= 1.0:
                    within_1_span += 1

                if f1 == f2: exact_12 += 1
                if abs(f1 - f2) <= 1.0: within_12 += 1

                if f1 == f3: exact_13 += 1
                if abs(f1 - f3) <= 1.0: within_13 += 1

                if f2 == f3: exact_23 += 1
                if abs(f2 - f3) <= 1.0: within_23 += 1

        n = len(j1_vals)
        if n > 0:
            agreement_report["numerical_metrics"][nm] = {
                "n": n,
                "all_3_exact_match_pct": round(exact_all_3 / n * 100.0, 2),
                "all_3_within_1_pct": round(within_1_span / n * 100.0, 2),
                "j1_mean": round(statistics.mean(j1_vals), 3),
                "j2_mean": round(statistics.mean(j2_vals), 3),
                "j3_mean": round(statistics.mean(j3_vals), 3),
                "pairwise": {
                    "j1_vs_j2": {
                        "exact_match_pct": round(exact_12 / n * 100.0, 2),
                        "within_1_pct": round(within_12 / n * 100.0, 2),
                        "mae": round(calculate_mae(j1_vals, j2_vals), 3),
                        "pearson_r": round(calculate_pearson_r(j1_vals, j2_vals), 3),
                    },
                    "j1_vs_j3": {
                        "exact_match_pct": round(exact_13 / n * 100.0, 2),
                        "within_1_pct": round(within_13 / n * 100.0, 2),
                        "mae": round(calculate_mae(j1_vals, j3_vals), 3),
                        "pearson_r": round(calculate_pearson_r(j1_vals, j3_vals), 3),
                    },
                    "j2_vs_j3": {
                        "exact_match_pct": round(exact_23 / n * 100.0, 2),
                        "within_1_pct": round(within_13 / n * 100.0, 2),
                        "mae": round(calculate_mae(j2_vals, j3_vals), 3),
                        "pearson_r": round(calculate_pearson_r(j2_vals, j3_vals), 3),
                    },
                },
            }

    for bm in BOOLEAN_METRICS:
        b1_vals, b2_vals, b3_vals = [], [], []
        unanimous = 0
        agree_12, agree_13, agree_23 = 0, 0, 0

        for r in all_rows:
            v1 = r.get(f"judge_1_{bm}")
            v2 = r.get(f"judge_2_{bm}")
            v3 = r.get(f"judge_3_{bm}")

            if v1 is not None and v2 is not None and v3 is not None:
                b1, b2, b3 = bool(v1), bool(v2), bool(v3)
                b1_vals.append(b1)
                b2_vals.append(b2)
                b3_vals.append(b3)

                if b1 == b2 == b3:
                    unanimous += 1
                if b1 == b2: agree_12 += 1
                if b1 == b3: agree_13 += 1
                if b2 == b3: agree_23 += 1

        n = len(b1_vals)
        if n > 0:
            agreement_report["boolean_metrics"][bm] = {
                "n": n,
                "all_3_unanimous_pct": round(unanimous / n * 100.0, 2),
                "j1_true_pct": round(sum(b1_vals) / n * 100.0, 2),
                "j2_true_pct": round(sum(b2_vals) / n * 100.0, 2),
                "j3_true_pct": round(sum(b3_vals) / n * 100.0, 2),
                "pairwise_cohen_kappa": {
                    "j1_vs_j2": round(calculate_cohen_kappa(b1_vals, b2_vals), 3),
                    "j1_vs_j3": round(calculate_cohen_kappa(b1_vals, b3_vals), 3),
                    "j2_vs_j3": round(calculate_cohen_kappa(b2_vals, b3_vals), 3),
                },
            }

    return agreement_report


def generate_overall_score_distribution_csv(all_rows: List[Dict[str, Any]], filepath: Path) -> None:
    """Generate overall distribution table for Judge 1, Judge 2, Judge 3, and 3-judge mean."""
    total = len(all_rows)
    dist_rows = []

    for m in NUMERIC_METRICS:
        j1_c = Counter([r.get(f"judge_1_{m}") for r in all_rows if r.get(f"judge_1_{m}") is not None])
        j2_c = Counter([r.get(f"judge_2_{m}") for r in all_rows if r.get(f"judge_2_{m}") is not None])
        j3_c = Counter([r.get(f"judge_3_{m}") for r in all_rows if r.get(f"judge_3_{m}") is not None])

        for score in [3, 2, 1, 0]:
            dist_rows.append({
                "metric": m,
                "score": score,
                "judge_1_count": j1_c.get(score, 0),
                "judge_1_pct": f"{j1_c.get(score, 0) / total * 100:.2f}%",
                "judge_2_count": j2_c.get(score, 0),
                "judge_2_pct": f"{j2_c.get(score, 0) / total * 100:.2f}%",
                "judge_3_count": j3_c.get(score, 0),
                "judge_3_pct": f"{j3_c.get(score, 0) / total * 100:.2f}%",
            })

    write_csv(
        filepath,
        dist_rows,
        ["metric", "score", "judge_1_count", "judge_1_pct", "judge_2_count", "judge_2_pct", "judge_3_count", "judge_3_pct"],
    )
    logger.info("Saved 3-judge overall score distribution to %s", filepath)


def run_analysis(
    output_dir: Path, analytics_dir: Path
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Execute analysis across output folders and persist all results strictly under analytics/."""
    logger.info("Scanning model folders in %s...", output_dir)

    model_subdirs = sorted(
        [
            d
            for d in output_dir.iterdir()
            if d.is_dir() and d.name != "logs" and not d.name.startswith(".")
        ],
        key=lambda d: d.name.lower(),
    )

    logger.info("Found %d model directories.", len(model_subdirs))

    # All fields for the per-model CSV
    csv_fields = (
        ["conversation_id", "file_name", "conversation_index"]
        + NUMERIC_METRICS
        + BOOLEAN_METRICS
        + [f"judge_1_{m}" for m in NUMERIC_METRICS + BOOLEAN_METRICS]
        + ["judge_1_tokens"]
        + [f"judge_2_{m}" for m in NUMERIC_METRICS + BOOLEAN_METRICS]
        + ["judge_2_tokens"]
        + [f"judge_3_{m}" for m in NUMERIC_METRICS + BOOLEAN_METRICS]
        + ["judge_3_tokens", "total_tokens"]
    )

    all_models_summary: List[Dict[str, Any]] = []
    all_conversations: List[Dict[str, Any]] = []

    models_analytics_dir = analytics_dir / "models"
    models_analytics_dir.mkdir(parents=True, exist_ok=True)

    for model_dir in model_subdirs:
        model_name = model_dir.name
        rows, summary = process_model_folder(model_dir)
        all_models_summary.append(summary)
        all_conversations.extend(rows)

        if not rows:
            logger.warning("No conversation records found in %s", model_name)
            continue

        # Save solely in analytics/models/<model_folder>.csv (NOT inside output directory)
        analytics_model_csv = models_analytics_dir / f"{model_name}.csv"
        write_csv(analytics_model_csv, rows, csv_fields)

        logger.info(
            "Processed %-45s | Files: %2d | Conversations: %4d | Saved to %s",
            model_name,
            summary["total_files"],
            len(rows),
            analytics_model_csv,
        )

    # 1. Benchmark Comparison Table across all models (sorted by sample size N descending)
    benchmark_rows = []
    for s in all_models_summary:
        m_name = s["model_name"]
        n_convos = s["total_conversations"]
        if n_convos == 0:
            continue

        m_metrics = s["metrics"]
        row = {
            "model_name": m_name,
            "conversations_evaluated": n_convos,
            "set_files_count": s["total_files"],
            "socratic_guidance_mean": m_metrics.get("socratic_guidance", {}).get("mean"),
            "scaffolding_mean": m_metrics.get("scaffolding", {}).get("mean"),
            "state_adaptation_mean": m_metrics.get("state_adaptation", {}).get("mean"),
            "diagnosis_mean": m_metrics.get("diagnosis", {}).get("mean"),
            "student_agency_mean": m_metrics.get("student_agency", {}).get("mean"),
            "progression_mean": m_metrics.get("progression", {}).get("mean"),
            "coherence_mean": m_metrics.get("coherence", {}).get("mean"),
            "correctness_pct": m_metrics.get("correctness", {}).get("percentage"),
            "premature_answer_pct": m_metrics.get("premature_answer", {}).get("percentage"),
            "hallucination_pct": m_metrics.get("hallucination", {}).get("percentage"),
            "avg_judge_1_tokens": s.get("tokens", {}).get("avg_judge_1_tokens"),
            "avg_judge_2_tokens": s.get("tokens", {}).get("avg_judge_2_tokens"),
            "avg_judge_3_tokens": s.get("tokens", {}).get("avg_judge_3_tokens"),
            "avg_total_tokens": s.get("tokens", {}).get("avg_total_tokens_per_convo"),
        }
        benchmark_rows.append(row)

    benchmark_rows.sort(
        key=lambda r: (r["conversations_evaluated"], r["model_name"]),
        reverse=True,
    )

    benchmark_fields = [
        "model_name",
        "conversations_evaluated",
        "set_files_count",
        "socratic_guidance_mean",
        "scaffolding_mean",
        "state_adaptation_mean",
        "diagnosis_mean",
        "student_agency_mean",
        "progression_mean",
        "coherence_mean",
        "correctness_pct",
        "premature_answer_pct",
        "hallucination_pct",
        "avg_judge_1_tokens",
        "avg_judge_2_tokens",
        "avg_judge_3_tokens",
        "avg_total_tokens",
    ]
    benchmark_csv = analytics_dir / "model_benchmark_comparison.csv"
    write_csv(benchmark_csv, benchmark_rows, benchmark_fields)
    logger.info("Saved benchmark comparison to %s", benchmark_csv)

    # 2. Score distribution CSV for Judge 1, Judge 2, and Judge 3
    distribution_csv = analytics_dir / "overall_score_distribution.csv"
    generate_overall_score_distribution_csv(all_conversations, distribution_csv)

    # 3. Inter-Judge Agreement Analysis across all 3 judges
    agreement = compute_inter_judge_agreement_3judges(all_conversations)
    agreement_json = analytics_dir / "inter_judge_agreement.json"
    with open(agreement_json, "w", encoding="utf-8") as fp:
        json.dump(agreement, fp, indent=2)

    agreement_csv_rows = []
    for nm, stats in agreement["numerical_metrics"].items():
        agreement_csv_rows.append(
            {
                "metric": nm,
                "type": "numerical",
                "sample_size": stats["n"],
                "all_3_exact_pct": stats["all_3_exact_match_pct"],
                "all_3_within_1_pct": stats["all_3_within_1_pct"],
                "judge_1_mean": stats["j1_mean"],
                "judge_2_mean": stats["j2_mean"],
                "judge_3_mean": stats["j3_mean"],
                "j1_vs_j2_exact_pct": stats["pairwise"]["j1_vs_j2"]["exact_match_pct"],
                "j1_vs_j2_within_1_pct": stats["pairwise"]["j1_vs_j2"]["within_1_pct"],
                "j1_vs_j2_r": stats["pairwise"]["j1_vs_j2"]["pearson_r"],
                "j1_vs_j3_exact_pct": stats["pairwise"]["j1_vs_j3"]["exact_match_pct"],
                "j1_vs_j3_within_1_pct": stats["pairwise"]["j1_vs_j3"]["within_1_pct"],
                "j1_vs_j3_r": stats["pairwise"]["j1_vs_j3"]["pearson_r"],
                "j2_vs_j3_exact_pct": stats["pairwise"]["j2_vs_j3"]["exact_match_pct"],
                "j2_vs_j3_within_1_pct": stats["pairwise"]["j2_vs_j3"]["within_1_pct"],
                "j2_vs_j3_r": stats["pairwise"]["j2_vs_j3"]["pearson_r"],
            }
        )
    for bm, stats in agreement["boolean_metrics"].items():
        agreement_csv_rows.append(
            {
                "metric": bm,
                "type": "boolean",
                "sample_size": stats["n"],
                "all_3_exact_pct": stats["all_3_unanimous_pct"],
                "all_3_within_1_pct": "100.0",
                "judge_1_mean": f"{stats['j1_true_pct']}%",
                "judge_2_mean": f"{stats['j2_true_pct']}%",
                "judge_3_mean": f"{stats['j3_true_pct']}%",
                "j1_vs_j2_exact_pct": "N/A",
                "j1_vs_j2_within_1_pct": "N/A",
                "j1_vs_j2_r": f"kappa={stats['pairwise_cohen_kappa']['j1_vs_j2']}",
                "j1_vs_j3_exact_pct": "N/A",
                "j1_vs_j3_within_1_pct": "N/A",
                "j1_vs_j3_r": f"kappa={stats['pairwise_cohen_kappa']['j1_vs_j3']}",
                "j2_vs_j3_exact_pct": "N/A",
                "j2_vs_j3_within_1_pct": "N/A",
                "j2_vs_j3_r": f"kappa={stats['pairwise_cohen_kappa']['j2_vs_j3']}",
            }
        )

    agreement_csv_fields = [
        "metric",
        "type",
        "sample_size",
        "all_3_exact_pct",
        "all_3_within_1_pct",
        "judge_1_mean",
        "judge_2_mean",
        "judge_3_mean",
        "j1_vs_j2_exact_pct",
        "j1_vs_j2_within_1_pct",
        "j1_vs_j2_r",
        "j1_vs_j3_exact_pct",
        "j1_vs_j3_within_1_pct",
        "j1_vs_j3_r",
        "j2_vs_j3_exact_pct",
        "j2_vs_j3_within_1_pct",
        "j2_vs_j3_r",
    ]
    agreement_csv = analytics_dir / "inter_judge_reliability.csv"
    write_csv(agreement_csv, agreement_csv_rows, agreement_csv_fields)
    logger.info("Saved 3-judge inter-judge reliability to %s", agreement_csv)

    # 4. Save comprehensive summary JSON
    summary_path = analytics_dir / "full_analysis_summary.json"
    full_report = {
        "benchmark_summary": benchmark_rows,
        "inter_judge_agreement": agreement,
        "model_summaries": all_models_summary,
    }
    with open(summary_path, "w", encoding="utf-8") as fp:
        json.dump(full_report, fp, indent=2)
    logger.info("Saved full summary JSON to %s", summary_path)

    return benchmark_rows, agreement


def print_cli_summary(
    benchmark_rows: List[Dict[str, Any]], agreement: Dict[str, Any]
) -> None:
    """Print clean terminal report for the user."""
    print("\n" + "=" * 140)
    print("SOCRATIC AI EVALUATION BENCHMARK - 3-JUDGE MODEL EVALUATIONS")
    print("Judges: 1 = beam:cloud | 2 = gpt-oss:120b | 3 = minimax-m3.1-flash")
    print("=" * 140)

    hdr = "%-45s | %-4s | %-7s | %-7s | %-7s | %-7s | %-7s | %-7s | %-8s | %-7s | %-7s" % (
        "Model Name",
        "N",
        "Guidnc",
        "Scaff",
        "Adapt",
        "Diagn",
        "Agency",
        "Progr",
        "Correct",
        "Premat",
        "Halluc",
    )
    print(hdr)
    print("-" * 140)

    for r in benchmark_rows:
        g = "%.2f" % r["socratic_guidance_mean"] if r["socratic_guidance_mean"] else "N/A"
        sc = "%.2f" % r["scaffolding_mean"] if r["scaffolding_mean"] else "N/A"
        ad = "%.2f" % r["state_adaptation_mean"] if r["state_adaptation_mean"] else "N/A"
        di = "%.2f" % r["diagnosis_mean"] if r["diagnosis_mean"] else "N/A"
        ag = "%.2f" % r["student_agency_mean"] if r["student_agency_mean"] else "N/A"
        pr = "%.2f" % r["progression_mean"] if r["progression_mean"] else "N/A"
        corr = "%.1f%%" % r["correctness_pct"] if r["correctness_pct"] is not None else "N/A"
        prem = "%.1f%%" % r["premature_answer_pct"] if r["premature_answer_pct"] is not None else "N/A"
        hal = "%.1f%%" % r["hallucination_pct"] if r["hallucination_pct"] is not None else "N/A"

        print(
            "%-45s | %4d | %7s | %7s | %7s | %7s | %7s | %7s | %8s | %7s | %7s"
            % (
                r["model_name"][:45],
                r["conversations_evaluated"],
                g,
                sc,
                ad,
                di,
                ag,
                pr,
                corr,
                prem,
                hal,
            )
        )

    print("-" * 140)
    print("\nTRI-JUDGE RELIABILITY & CALIBRATION (N = %d)" % agreement["total_evaluated_conversations"])
    print("-" * 115)
    print(
        "%-20s | %-12s | %-14s | %-10s | %-10s | %-10s | %-10s"
        % ("Metric", "All 3 Exact", "All 3 Within±1", "J1 Mean", "J2 Mean", "J3 Mean", "J1-J2 r")
    )
    print("-" * 115)
    for nm, s in agreement["numerical_metrics"].items():
        print(
            "%-20s | %10.1f%% | %12.1f%% | %10.2f | %10.2f | %10.2f | %10.3f"
            % (
                nm,
                s["all_3_exact_match_pct"],
                s["all_3_within_1_pct"],
                s["j1_mean"],
                s["j2_mean"],
                s["j3_mean"],
                s["pairwise"]["j1_vs_j2"]["pearson_r"],
            )
        )
    print("-" * 115)
    print(
        "%-20s | %-16s | %-10s | %-10s | %-10s"
        % ("Boolean Metric", "All 3 Unanimous", "J1 True%", "J2 True%", "J3 True%")
    )
    print("-" * 115)
    for bm, s in agreement["boolean_metrics"].items():
        print(
            "%-20s | %14.1f%% | %9.1f%% | %9.1f%% | %9.1f%%"
            % (
                bm,
                s["all_3_unanimous_pct"],
                s["j1_true_pct"],
                s["j2_true_pct"],
                s["j3_true_pct"],
            )
        )
    print("=" * 115 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run 3-judge data analysis and generate CSV reports strictly under analytics/."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Root output directory containing model folders (default: output)",
    )
    parser.add_argument(
        "--analytics-dir",
        type=Path,
        default=Path("analytics"),
        help="Target analytics directory for reports and consolidated CSVs (default: analytics)",
    )
    args = parser.parse_args()

    benchmark_rows, agreement = run_analysis(args.output_dir, args.analytics_dir)
    print_cli_summary(benchmark_rows, agreement)


if __name__ == "__main__":
    main()
