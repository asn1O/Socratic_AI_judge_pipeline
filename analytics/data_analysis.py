#!/usr/bin/env python3
"""data_analysis.py - Comprehensive evaluation and data analysis on judge outputs.

Processes all model evaluation folders in `output/`, filters set files (*-set[*.json),
ignores state tracking files (evaluation_state*.json), extracts scores from Judge 1 and Judge 2,
converts evaluations to standard CSV format per model, computes statistical metrics,
benchmarks model performance, and evaluates inter-judge agreement.
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


def safe_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


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
    
    # Contingency table: [both True, x True & y False, x False & y True, both False]
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
    """Process a single model folder and extract evaluation rows and summary stats."""
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

            j1 = item.get("judge_1", {})
            j2 = item.get("judge_2", {})
            j1_eval = j1.get("evaluation", {}) if isinstance(j1, dict) else {}
            j2_eval = j2.get("evaluation", {}) if isinstance(j2, dict) else {}

            j1_tokens = j1.get("total_tokens", 0) if isinstance(j1, dict) else 0
            j2_tokens = j2.get("total_tokens", 0) if isinstance(j2, dict) else 0

            row: Dict[str, Any] = {
                "conversation_id": convo_id,
                "file_name": file_path.name,
                "conversation_index": convo_idx,
            }

            # Numerical metrics: consensus average + individual judges
            for nm in NUMERIC_METRICS:
                v1 = j1_eval.get(nm)
                v2 = j2_eval.get(nm)
                row[f"judge_1_{nm}"] = v1
                row[f"judge_2_{nm}"] = v2

                if v1 is not None and v2 is not None:
                    avg_v = round((float(v1) + float(v2)) / 2.0, 2)
                    row[nm] = avg_v
                elif v1 is not None:
                    row[nm] = float(v1)
                elif v2 is not None:
                    row[nm] = float(v2)
                else:
                    row[nm] = None

            # Boolean metrics: consensus + individual judges
            for bm in BOOLEAN_METRICS:
                b1 = j1_eval.get(bm)
                b2 = j2_eval.get(bm)
                row[f"judge_1_{bm}"] = b1
                row[f"judge_2_{bm}"] = b2

                if b1 is not None and b2 is not None:
                    # For correctness: both agree True => True; otherwise False
                    if bm == "correctness":
                        row[bm] = bool(b1 and b2)
                        row[f"{bm}_rate"] = 1.0 if (b1 and b2) else (0.5 if (b1 or b2) else 0.0)
                    else:
                        # For risk metrics (premature_answer, hallucination): flagged if either detects
                        row[bm] = bool(b1 or b2)
                        row[f"{bm}_rate"] = 1.0 if (b1 and b2) else (0.5 if (b1 or b2) else 0.0)
                elif b1 is not None:
                    row[bm] = bool(b1)
                    row[f"{bm}_rate"] = 1.0 if b1 else 0.0
                elif b2 is not None:
                    row[bm] = bool(b2)
                    row[f"{bm}_rate"] = 1.0 if b2 else 0.0
                else:
                    row[bm] = None
                    row[f"{bm}_rate"] = None

            row["judge_1_tokens"] = j1_tokens
            row["judge_2_tokens"] = j2_tokens
            row["total_tokens"] = j1_tokens + j2_tokens

            rows.append(row)

    # Compute model-level summary statistics
    summary = compute_summary_statistics(model_name, rows, len(set_files))
    return rows, summary


def compute_summary_statistics(
    model_name: str, rows: List[Dict[str, Any]], num_set_files: int
) -> Dict[str, Any]:
    """Compute comprehensive statistical metrics for a model's evaluations."""
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

    # Numerical metrics stats
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
    t1_vals = [r["judge_1_tokens"] for r in rows if r.get("judge_1_tokens")]
    t2_vals = [r["judge_2_tokens"] for r in rows if r.get("judge_2_tokens")]
    tot_vals = [r["total_tokens"] for r in rows if r.get("total_tokens")]

    summary["tokens"] = {
        "avg_judge_1_tokens": round(statistics.mean(t1_vals), 1) if t1_vals else 0,
        "avg_judge_2_tokens": round(statistics.mean(t2_vals), 1) if t2_vals else 0,
        "avg_total_tokens_per_convo": round(statistics.mean(tot_vals), 1) if tot_vals else 0,
    }

    return summary


def write_csv(filepath: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    """Write list of dict rows to CSV file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def compute_inter_judge_agreement(all_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute agreement metrics between Judge 1 (beam:cloud) and Judge 2 (gpt-oss:120b)."""
    agreement_report: Dict[str, Any] = {
        "total_evaluated_conversations": len(all_rows),
        "numerical_metrics": {},
        "boolean_metrics": {},
    }

    # Numerical metrics agreement
    for nm in NUMERIC_METRICS:
        j1_scores = []
        j2_scores = []
        exact = 0
        within_1 = 0

        for r in all_rows:
            v1 = r.get(f"judge_1_{nm}")
            v2 = r.get(f"judge_2_{nm}")
            if v1 is not None and v2 is not None:
                j1_scores.append(float(v1))
                j2_scores.append(float(v2))
                diff = abs(float(v1) - float(v2))
                if diff == 0:
                    exact += 1
                if diff <= 1.0:
                    within_1 += 1

        n = len(j1_scores)
        if n > 0:
            mae = round(calculate_mae(j1_scores, j2_scores), 3)
            r_val = round(calculate_pearson_r(j1_scores, j2_scores), 3)
            agreement_report["numerical_metrics"][nm] = {
                "n": n,
                "exact_match_pct": round(exact / n * 100.0, 2),
                "within_1_pct": round(within_1 / n * 100.0, 2),
                "mae": mae,
                "pearson_r": r_val,
                "j1_mean": round(statistics.mean(j1_scores), 3),
                "j2_mean": round(statistics.mean(j2_scores), 3),
            }

    # Boolean metrics agreement
    for bm in BOOLEAN_METRICS:
        j1_bools = []
        j2_bools = []
        matches = 0

        for r in all_rows:
            b1 = r.get(f"judge_1_{bm}")
            b2 = r.get(f"judge_2_{bm}")
            if b1 is not None and b2 is not None:
                b1 = bool(b1)
                b2 = bool(b2)
                j1_bools.append(b1)
                j2_bools.append(b2)
                if b1 == b2:
                    matches += 1

        n = len(j1_bools)
        if n > 0:
            kappa = round(calculate_cohen_kappa(j1_bools, j2_bools), 3)
            agreement_report["boolean_metrics"][bm] = {
                "n": n,
                "agreement_pct": round(matches / n * 100.0, 2),
                "cohen_kappa": kappa,
                "j1_positive_pct": round(sum(j1_bools) / n * 100.0, 2),
                "j2_positive_pct": round(sum(j2_bools) / n * 100.0, 2),
            }

    return agreement_report


def run_analysis(
    output_dir: Path, analytics_dir: Path
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run full analysis across all model output folders and generate all CSVs and summaries."""
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

    csv_fields = (
        ["conversation_id", "file_name", "conversation_index"]
        + NUMERIC_METRICS
        + BOOLEAN_METRICS
        + [f"judge_1_{m}" for m in NUMERIC_METRICS + BOOLEAN_METRICS]
        + ["judge_1_tokens"]
        + [f"judge_2_{m}" for m in NUMERIC_METRICS + BOOLEAN_METRICS]
        + ["judge_2_tokens", "total_tokens"]
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

        # Write CSV in analytics directory only: analytics/models/<model_folder>.csv
        analytics_model_csv = models_analytics_dir / f"{model_name}.csv"
        write_csv(analytics_model_csv, rows, csv_fields)

        logger.info(
            "Processed %-45s | Files: %2d | Conversations: %4d | Saved to %s",
            model_name,
            summary["total_files"],
            len(rows),
            analytics_model_csv,
        )

    # 3. Build Benchmark Comparison Table across all models
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
            "avg_total_tokens": s.get("tokens", {}).get("avg_total_tokens_per_convo"),
        }
        benchmark_rows.append(row)

    # Sort benchmark by sample size descending, then by model_name
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
        "avg_total_tokens",
    ]

    benchmark_csv = analytics_dir / "model_benchmark_comparison.csv"
    write_csv(benchmark_csv, benchmark_rows, benchmark_fields)
    logger.info("Saved benchmark comparison to %s", benchmark_csv)

    # 4. Inter-Judge Agreement Analysis
    agreement = compute_inter_judge_agreement(all_conversations)
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
                "exact_match_pct": stats["exact_match_pct"],
                "within_1_pct": stats["within_1_pct"],
                "mae": stats["mae"],
                "pearson_r": stats["pearson_r"],
                "judge_1_mean": stats["j1_mean"],
                "judge_2_mean": stats["j2_mean"],
                "cohen_kappa": "N/A",
            }
        )
    for bm, stats in agreement["boolean_metrics"].items():
        agreement_csv_rows.append(
            {
                "metric": bm,
                "type": "boolean",
                "sample_size": stats["n"],
                "exact_match_pct": stats["agreement_pct"],
                "within_1_pct": "100.0",
                "mae": "N/A",
                "pearson_r": "N/A",
                "judge_1_mean": f"{stats['j1_positive_pct']}%",
                "judge_2_mean": f"{stats['j2_positive_pct']}%",
                "cohen_kappa": stats["cohen_kappa"],
            }
        )

    agreement_csv_fields = [
        "metric",
        "type",
        "sample_size",
        "exact_match_pct",
        "within_1_pct",
        "mae",
        "pearson_r",
        "judge_1_mean",
        "judge_2_mean",
        "cohen_kappa",
    ]
    agreement_csv = analytics_dir / "inter_judge_reliability.csv"
    write_csv(agreement_csv, agreement_csv_rows, agreement_csv_fields)
    logger.info("Saved inter-judge reliability to %s", agreement_csv)

    # 5. Save comprehensive summary JSON
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
    print("\n" + "=" * 135)
    print("SOCRATIC AI EVALUATION BENCHMARK - MODEL RANKINGS & DATA ANALYSIS")
    print("=" * 135)

    hdr = "%-46s | %-4s | %-7s | %-7s | %-7s | %-7s | %-7s | %-7s | %-8s | %-7s | %-7s" % (
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
    print("-" * 135)

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
            "%-46s | %4d | %7s | %7s | %7s | %7s | %7s | %7s | %8s | %7s | %7s"
            % (
                r["model_name"][:46],
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

    print("-" * 135)
    print("\nINTER-JUDGE AGREEMENT (Judge 1: beam:cloud vs Judge 2: gpt-oss:120b | N = %d)" % agreement["total_evaluated_conversations"])
    print("-" * 105)
    print(
        "%-22s | %-12s | %-12s | %-8s | %-10s | %-12s | %-12s"
        % ("Metric", "Exact Match", "Within ±1", "MAE", "Pearson r", "Judge 1 Mean", "Judge 2 Mean")
    )
    print("-" * 105)
    for nm, s in agreement["numerical_metrics"].items():
        print(
            "%-22s | %10.1f%% | %10.1f%% | %8.3f | %10.3f | %12.2f | %12.2f"
            % (
                nm,
                s["exact_match_pct"],
                s["within_1_pct"],
                s["mae"],
                s["pearson_r"],
                s["j1_mean"],
                s["j2_mean"],
            )
        )
    print("-" * 105)
    print(
        "%-22s | %-12s | %-12s | %-12s | %-14s"
        % ("Boolean Metric", "Agreement", "Cohen Kappa", "Judge 1 True%", "Judge 2 True%")
    )
    print("-" * 105)
    for bm, s in agreement["boolean_metrics"].items():
        print(
            "%-22s | %10.1f%% | %12.3f | %11.1f%% | %11.1f%%"
            % (
                bm,
                s["agreement_pct"],
                s["cohen_kappa"],
                s["j1_positive_pct"],
                s["j2_positive_pct"],
            )
        )
    print("=" * 105 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run data analysis and generate CSV reports for all model evaluation outputs."
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
