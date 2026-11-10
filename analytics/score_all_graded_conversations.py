#!/usr/bin/env python3
"""score_all_graded_conversations.py

Scores every conversation in `data/` using the Judge 1 & Judge 3 ensemble
with the trained regression and decision tree models.

Each conversation JSON object gets a clean, single `score` field containing
predictions from Linear Regression, NNLS, and Decision Tree for both 5-point
and 10-point scales.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("score_all_conversations")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
WEIGHTS_FILE = BASE_DIR / "analytics" / "scoring_model_weights.json"
MODEL_SUMMARY_CSV = BASE_DIR / "analytics" / "model_scores_summary.csv"

NUMERIC_METRICS = [
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
]


def load_weights(weights_path: Path = WEIGHTS_FILE) -> Dict[str, Any]:
    if not weights_path.exists():
        raise FileNotFoundError(f"Missing weights file at {weights_path}")
    with open(weights_path, "r", encoding="utf-8") as f:
        return json.load(f)


def eval_tree(node: Dict[str, Any], features: Dict[str, float]) -> float:
    curr = node
    while curr.get("type") == "split":
        val = features.get(curr["feature"], 0.0)
        if val <= curr["threshold"]:
            curr = curr["left"]
        else:
            curr = curr["right"]
    return float(curr["value"])


def compute_scores_for_metrics(
    metrics: Dict[str, float],
    weights: Dict[str, Any],
) -> Dict[str, Any]:
    """Computes scores using Linear Regression (OLS), NNLS, and Decision Tree for J1 & J3 ensemble features."""
    m5 = weights["models"]["out_of_5"]
    m10 = weights["models"]["out_of_10"]

    # 1. OLS 5 and 10
    ols_5_weights = m5["ols_linear_regression"]["production_weights"]
    ols_5_val = ols_5_weights["intercept"] + sum(
        ols_5_weights["coefficients"][k] * metrics.get(k, 0.0) for k in NUMERIC_METRICS
    )
    ols_5_val = max(0.0, min(5.0, round(ols_5_val, 2)))

    ols_10_weights = m10["ols_linear_regression"]["production_weights"]
    ols_10_val = ols_10_weights["intercept"] + sum(
        ols_10_weights["coefficients"][k] * metrics.get(k, 0.0) for k in NUMERIC_METRICS
    )
    ols_10_val = max(0.0, min(10.0, round(ols_10_val, 2)))

    # 2. NNLS 5 and 10
    nnls_5_weights = m5["nnls_regression"]["production_weights"]
    nnls_5_val = nnls_5_weights["intercept"] + sum(
        nnls_5_weights["coefficients"][k] * metrics.get(k, 0.0) for k in NUMERIC_METRICS
    )
    nnls_5_val = max(0.0, min(5.0, round(nnls_5_val, 2)))

    nnls_10_weights = m10["nnls_regression"]["production_weights"]
    nnls_10_val = nnls_10_weights["intercept"] + sum(
        nnls_10_weights["coefficients"][k] * metrics.get(k, 0.0) for k in NUMERIC_METRICS
    )
    nnls_10_val = max(0.0, min(10.0, round(nnls_10_val, 2)))

    # 3. Decision Tree 5 and 10
    dt_5_tree = m5["decision_tree"]["production_tree"]
    dt_5_val = round(eval_tree(dt_5_tree, metrics), 2)

    dt_10_tree = m10["decision_tree"]["production_tree"]
    dt_10_val = round(eval_tree(dt_10_tree, metrics), 2)

    return {
        "linear_regression_out_of_5": ols_5_val,
        "linear_regression_out_of_10": ols_10_val,
        "nnls_regression_out_of_5": nnls_5_val,
        "nnls_regression_out_of_10": nnls_10_val,
        "decision_tree_out_of_5": dt_5_val,
        "decision_tree_out_of_10": dt_10_val,
        "linear_regression": {
            "score_out_of_5": ols_5_val,
            "score_out_of_10": ols_10_val,
        },
        "nnls_regression": {
            "score_out_of_5": nnls_5_val,
            "score_out_of_10": nnls_10_val,
        },
        "decision_tree": {
            "score_out_of_5": dt_5_val,
            "score_out_of_10": dt_10_val,
        },
    }


def score_all_conversations(
    dry_run: bool = False,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    weights = load_weights()
    model_dirs = sorted([d for d in DATA_DIR.iterdir() if d.is_dir()])

    total_files_scored = 0
    total_convos_scored = 0
    all_scored_records: List[Dict[str, Any]] = []

    for m_dir in model_dirs:
        model_name = m_dir.name
        out_m_dir = OUTPUT_DIR / model_name
        if not out_m_dir.exists():
            logger.warning("No output folder found for model: %s", model_name)
            continue

        json_files = sorted(m_dir.glob("*.json"))
        for d_path in json_files:
            if "flagged" in d_path.name:
                continue

            o_path = out_m_dir / d_path.name
            if not o_path.exists():
                logger.warning("Matching output file not found: %s", o_path)
                continue

            try:
                with open(d_path, "r", encoding="utf-8") as fp:
                    data_items = json.load(fp)
                with open(o_path, "r", encoding="utf-8") as fp:
                    out_items = json.load(fp)
            except Exception as e:
                logger.error("Error loading %s or %s: %s", d_path, o_path, e)
                continue

            if not isinstance(data_items, list) or not isinstance(out_items, list):
                continue

            modified = False
            for idx, item in enumerate(data_items):
                if not isinstance(item, dict):
                    continue

                o_item = None
                if idx < len(out_items) and out_items[idx].get("conversation_index", idx) == idx:
                    o_item = out_items[idx]
                else:
                    for cand in out_items:
                        if isinstance(cand, dict) and cand.get("conversation_index") == idx:
                            o_item = cand
                            break

                if not o_item:
                    continue

                # Compute Judge 1 and Judge 3 ensemble average strictly
                j1_eval = o_item.get("judge_1", {}).get("evaluation") if isinstance(o_item.get("judge_1"), dict) else {}
                j3_eval = o_item.get("judge_3", {}).get("evaluation") if isinstance(o_item.get("judge_3"), dict) else {}

                ensemble_metrics: Dict[str, float] = {}
                for nm in NUMERIC_METRICS:
                    val_1 = float(j1_eval.get(nm, 0.0)) if isinstance(j1_eval, dict) and j1_eval.get(nm) is not None else 0.0
                    val_3 = float(j3_eval.get(nm, 0.0)) if isinstance(j3_eval, dict) and j3_eval.get(nm) is not None else 0.0
                    ensemble_metrics[nm] = (val_1 + val_3) / 2.0

                # Compute single consensus score dictionary
                score_dict = compute_scores_for_metrics(ensemble_metrics, weights)

                # Set score field directly (no per-judge scores)
                item["score"] = score_dict
                modified = True
                total_convos_scored += 1

                all_scored_records.append({
                    "model": model_name,
                    "file": d_path.name,
                    "index": idx,
                    "domain": item.get("domain", ""),
                    "topic": item.get("topic", ""),
                    "linear_regression_5": score_dict["linear_regression_out_of_5"],
                    "linear_regression_10": score_dict["linear_regression_out_of_10"],
                    "nnls_regression_5": score_dict["nnls_regression_out_of_5"],
                    "nnls_regression_10": score_dict["nnls_regression_out_of_10"],
                    "decision_tree_5": score_dict["decision_tree_out_of_5"],
                    "decision_tree_10": score_dict["decision_tree_out_of_10"],
                })

            if modified and not dry_run:
                with open(d_path, "w", encoding="utf-8") as fp:
                    json.dump(data_items, fp, indent=2, ensure_ascii=False)
                total_files_scored += 1
            elif modified and dry_run:
                total_files_scored += 1

    return total_files_scored, total_convos_scored, all_scored_records


def generate_benchmark_summary(records: List[Dict[str, Any]], output_path: Path = MODEL_SUMMARY_CSV) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    summary = df.groupby("model").agg(
        conversations=("index", "count"),
        avg_score_5_ols=("linear_regression_5", "mean"),
        avg_score_5_nnls=("nnls_regression_5", "mean"),
        avg_score_5_tree=("decision_tree_5", "mean"),
        avg_score_10_ols=("linear_regression_10", "mean"),
        avg_score_10_nnls=("nnls_regression_10", "mean"),
        avg_score_10_tree=("decision_tree_10", "mean"),
    ).reset_index()

    summary = summary.sort_values(by="avg_score_10_nnls", ascending=False).round(2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)
    logger.info("Saved model score benchmark summary to %s", output_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Score all graded conversations in data/ using J1 & J3 ensemble.")
    parser.add_argument("--dry-run", action="store_true", help="Perform scoring without writing to files")
    args = parser.parse_args()

    logger.info("Starting scoring of all conversations in %s (dry_run=%s)", DATA_DIR, args.dry_run)
    files_count, convos_count, records = score_all_conversations(dry_run=args.dry_run)
    logger.info("Scoring completed: %d files, %d conversations processed", files_count, convos_count)

    summary = generate_benchmark_summary(records)
    print("\n" + "=" * 80)
    print("MODEL BENCHMARK ACROSS ALL GRADED CONVERSATIONS (JUDGE 1 & 3 ENSEMBLE)")
    print("=" * 80)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
