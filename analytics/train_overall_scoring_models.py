#!/usr/bin/env python3
"""train_overall_scoring_models.py

Trains, evaluates, and exports regression and decision tree models to predict:
1. Overall Score (out of 5)
2. Overall Score (out of 10)
using the Judge 1 & Judge 3 ensemble average for the 7 pedagogical sub-metrics
across the 362 human-annotated conversations.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, train_test_split
from sklearn.tree import DecisionTreeRegressor, export_text, _tree

LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("train_scoring_models")

BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_DIR = BASE_DIR / "misc" / "annotation_excel_files"
OUTPUT_WEIGHTS_FILE = BASE_DIR / "analytics" / "scoring_model_weights.json"

METRIC_MAP = [
    ("socratic_guidance", "Socratic Guidance (0-3)"),
    ("scaffolding", "Scaffolding (0-3)"),
    ("state_adaptation", "State Adaptation (0-3)"),
    ("diagnosis", "Diagnosis (0-3)"),
    ("student_agency", "Student Agency (0-3)"),
    ("progression", "Progression (0-3)"),
    ("coherence", "Coherence (0-3)"),
]

FEATURE_KEYS = [k for k, _ in METRIC_MAP]

ANNOTATION_SETS = [
    ("random_sample_annotator.xlsx", "random_sample_judges.xlsx", "random_sample"),
    ("metric_profile_sample_annotator.xlsx", "metric_profile_sample_judges.xlsx", "metric_profile"),
    ("judge_disagreement_sample_annotator.xlsx", "judge_disagreement_sample_judges.xlsx", "judge_disagreement"),
]


def load_j1_j3_annotation_dataset() -> pd.DataFrame:
    """Loads 362 human-annotated records and computes features as average of Judge 1 & Judge 3."""
    dfs: List[pd.DataFrame] = []

    for ann_file, judge_file, strategy in ANNOTATION_SETS:
        ann_path = EXCEL_DIR / ann_file
        judge_path = EXCEL_DIR / judge_file

        if not ann_path.exists() or not judge_path.exists():
            raise FileNotFoundError(f"Missing file: {ann_path} or {judge_path}")

        df_ann = pd.read_excel(ann_path)
        valid_ann = df_ann.dropna(subset=["Overall Score (out of 5)", "Overall Score (out of 10)"]).copy()
        valid_ann["Annotation ID"] = valid_ann["Annotation ID"].astype(str).str.strip()

        df_j = pd.read_excel(judge_path, header=[0, 1])
        df_j.columns = [
            f"{c[0]}|{c[1]}" if "Unnamed" not in str(c[1]) else c[0]
            for c in df_j.columns
        ]
        id_col = [c for c in df_j.columns if "Annotation ID" in c][0]
        df_j["Annotation ID"] = df_j[id_col].astype(str).str.strip()

        merged = pd.merge(valid_ann, df_j, on="Annotation ID", how="inner")
        merged["sampling_strategy"] = strategy
        logger.info("Loaded %d records for strategy: %s", len(merged), strategy)
        dfs.append(merged)

    combined = pd.concat(dfs, ignore_index=True)
    logger.info("Total merged records with Judge 1 & 3: %d", len(combined))

    # Compute J1 & J3 ensemble average for each metric
    for k, raw in METRIC_MAP:
        j1_col = f"{raw}|Judge 1"
        j3_col = f"{raw}|Judge 3"
        combined[k] = (combined[j1_col].astype(float) + combined[j3_col].astype(float)) / 2.0

    return combined


def tree_to_dict(tree: Any, feature_names: List[str]) -> Dict[str, Any]:
    """Serializes a DecisionTreeRegressor into a pure dictionary for evaluation without sklearn."""
    tree_ = tree.tree_

    def recurse(node: int) -> Dict[str, Any]:
        if tree_.feature[node] != _tree.TREE_UNDEFINED:
            name = feature_names[tree_.feature[node]]
            threshold = float(round(tree_.threshold[node], 4))
            return {
                "type": "split",
                "feature": name,
                "threshold": threshold,
                "left": recurse(tree_.children_left[node]),
                "right": recurse(tree_.children_right[node]),
            }
        else:
            val = float(round(tree_.value[node][0][0], 4))
            return {
                "type": "leaf",
                "value": val,
            }

    return recurse(0)


def train_and_evaluate(
    df: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Trains and evaluates models using Judge 1 & Judge 3 average features."""
    X = df[FEATURE_KEYS].values
    y5 = df["Overall Score (out of 5)"].values
    y10 = df["Overall Score (out of 10)"].values
    strats = df["sampling_strategy"].values

    train_idx, test_idx = train_test_split(
        np.arange(len(df)), test_size=test_size, random_state=random_state, stratify=strats
    )

    X_train, X_test = X[train_idx], X[test_idx]

    results: Dict[str, Any] = {
        "dataset_size": len(df),
        "train_size": len(train_idx),
        "test_size": len(test_idx),
        "ensemble": "Judge 1 & Judge 3 average (j1_j3_ensemble)",
        "features": FEATURE_KEYS,
        "models": {},
    }

    for target_key, scale_max, y in [("out_of_5", 5.0, y5), ("out_of_10", 10.0, y10)]:
        y_train, y_test = y[train_idx], y[test_idx]
        logger.info("Training models for target: %s (Scale: 0-%s)", target_key, scale_max)

        # 1. OLS Linear Regression
        lr = LinearRegression().fit(X_train, y_train)
        pred_ols_test = lr.predict(X_test)

        mae_ols = float(mean_absolute_error(y_test, pred_ols_test))
        rmse_ols = float(np.sqrt(mean_squared_error(y_test, pred_ols_test)))
        r2_ols = float(r2_score(y_test, pred_ols_test))
        pr_ols, _ = pearsonr(y_test, pred_ols_test)
        sr_ols, _ = spearmanr(y_test, pred_ols_test)

        # 5-fold CV for OLS
        kf = KFold(n_splits=5, shuffle=True, random_state=random_state)
        cv_r2, cv_mae = [], []
        for tr_i, te_i in kf.split(X):
            m = LinearRegression().fit(X[tr_i], y[tr_i])
            p = m.predict(X[te_i])
            cv_r2.append(r2_score(y[te_i], p))
            cv_mae.append(mean_absolute_error(y[te_i], p))

        # Full dataset fit for production
        lr_full = LinearRegression().fit(X, y)

        # 2. NNLS Regression (Non-Negative Least Squares)
        X_train_ones = np.column_stack([np.ones(len(X_train)), X_train])
        X_test_ones = np.column_stack([np.ones(len(X_test)), X_test])
        w_nnls_tr, _ = nnls(X_train_ones, y_train)
        pred_nnls_test = X_test_ones @ w_nnls_tr

        mae_nnls = float(mean_absolute_error(y_test, pred_nnls_test))
        rmse_nnls = float(np.sqrt(mean_squared_error(y_test, pred_nnls_test)))
        r2_nnls = float(r2_score(y_test, pred_nnls_test))
        pr_nnls, _ = pearsonr(y_test, pred_nnls_test)
        sr_nnls, _ = spearmanr(y_test, pred_nnls_test)

        # Full dataset NNLS
        X_full_ones = np.column_stack([np.ones(len(X)), X])
        w_nnls_full, _ = nnls(X_full_ones, y)

        # 3. Decision Tree Regressor
        dt = DecisionTreeRegressor(max_depth=3, min_samples_leaf=10, random_state=random_state).fit(X_train, y_train)
        pred_dt_test = dt.predict(X_test)

        mae_dt = float(mean_absolute_error(y_test, pred_dt_test))
        rmse_dt = float(np.sqrt(mean_squared_error(y_test, pred_dt_test)))
        r2_dt = float(r2_score(y_test, pred_dt_test))
        pr_dt, _ = pearsonr(y_test, pred_dt_test)
        sr_dt, _ = spearmanr(y_test, pred_dt_test)

        dt_full = DecisionTreeRegressor(max_depth=3, min_samples_leaf=10, random_state=random_state).fit(X, y)
        dt_dict = tree_to_dict(dt_full, FEATURE_KEYS)

        results["models"][target_key] = {
            "scale_max": scale_max,
            "ols_linear_regression": {
                "test_metrics": {
                    "mae": round(mae_ols, 4),
                    "rmse": round(rmse_ols, 4),
                    "r2": round(r2_ols, 4),
                    "pearson_r": round(float(pr_ols), 4),
                    "spearman_rho": round(float(sr_ols), 4),
                    "within_0.5": round(float(np.mean(np.abs(y_test - pred_ols_test) <= 0.5) * 100), 2),
                    "within_1.0": round(float(np.mean(np.abs(y_test - pred_ols_test) <= 1.0) * 100), 2),
                    "cv_5fold_r2_mean": round(float(np.mean(cv_r2)), 4),
                    "cv_5fold_r2_std": round(float(np.std(cv_r2)), 4),
                    "cv_5fold_mae_mean": round(float(np.mean(cv_mae)), 4),
                },
                "production_weights": {
                    "intercept": round(float(lr_full.intercept_), 5),
                    "coefficients": {k: round(float(c), 5) for k, c in zip(FEATURE_KEYS, lr_full.coef_)},
                },
            },
            "nnls_regression": {
                "test_metrics": {
                    "mae": round(mae_nnls, 4),
                    "rmse": round(rmse_nnls, 4),
                    "r2": round(r2_nnls, 4),
                    "pearson_r": round(float(pr_nnls), 4),
                    "spearman_rho": round(float(sr_nnls), 4),
                    "within_0.5": round(float(np.mean(np.abs(y_test - pred_nnls_test) <= 0.5) * 100), 2),
                    "within_1.0": round(float(np.mean(np.abs(y_test - pred_nnls_test) <= 1.0) * 100), 2),
                },
                "production_weights": {
                    "intercept": round(float(w_nnls_full[0]), 5),
                    "coefficients": {k: round(float(c), 5) for k, c in zip(FEATURE_KEYS, w_nnls_full[1:])},
                },
            },
            "decision_tree": {
                "test_metrics": {
                    "mae": round(mae_dt, 4),
                    "rmse": round(rmse_dt, 4),
                    "r2": round(r2_dt, 4),
                    "pearson_r": round(float(pr_dt), 4),
                    "spearman_rho": round(float(sr_dt), 4),
                    "within_0.5": round(float(np.mean(np.abs(y_test - pred_dt_test) <= 0.5) * 100), 2),
                    "within_1.0": round(float(np.mean(np.abs(y_test - pred_dt_test) <= 1.0) * 100), 2),
                },
                "production_tree": dt_dict,
                "feature_importances": {
                    k: round(float(imp), 4) for k, imp in zip(FEATURE_KEYS, dt_full.feature_importances_)
                },
            },
        }

    return results


def save_weights(results: Dict[str, Any], output_path: Path = OUTPUT_WEIGHTS_FILE) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info("Saved scoring models weights and metadata to %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate scoring models using Judge 1 & 3 ensemble.")
    parser.add_argument("--export", type=str, default=str(OUTPUT_WEIGHTS_FILE), help="Path to export weights JSON")
    args = parser.parse_args()

    df = load_j1_j3_annotation_dataset()
    results = train_and_evaluate(df)
    save_weights(results, Path(args.export))

    print("\n" + "=" * 70)
    print("TRAINING & EVALUATION COMPLETE (JUDGE 1 & JUDGE 3 ENSEMBLE)")
    print("=" * 70)
    for tgt in ["out_of_5", "out_of_10"]:
        m_info = results["models"][tgt]
        print(f"\nTarget: {tgt} (Scale max: {m_info['scale_max']})")
        print("  OLS Test R2:", m_info["ols_linear_regression"]["test_metrics"]["r2"], "MAE:", m_info["ols_linear_regression"]["test_metrics"]["mae"])
        print("  NNLS Test R2:", m_info["nnls_regression"]["test_metrics"]["r2"], "MAE:", m_info["nnls_regression"]["test_metrics"]["mae"])
        print("  Decision Tree Test R2:", m_info["decision_tree"]["test_metrics"]["r2"], "MAE:", m_info["decision_tree"]["test_metrics"]["mae"])


if __name__ == "__main__":
    main()
