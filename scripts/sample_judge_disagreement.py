#!/usr/bin/env python3
"""
Select 40 judge-disagreement conversations for human annotation.

Identifies conversations where the three LLM judges meaningfully disagree
across the seven metric scores, strictly excluding conversations already
selected in random_sample (240) and metric_profile_sample (120).
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

NUMERIC_METRICS = [
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
]


def load_previous_sample_references(
    random_sample_path: Union[str, Path],
    metric_profile_path: Union[str, Path],
) -> Set[Tuple[str, int]]:
    """
    Read previous annotation sets and return a combined set of (relative_path, index) tuples.
    Raises FileNotFoundError if either file does not exist.
    """
    rand_file = Path(random_sample_path)
    if not rand_file.exists():
        raise FileNotFoundError(
            f"Random sample file not found at '{rand_file}'. "
            "Cannot enforce exclusion of previous random sample."
        )

    mp_file = Path(metric_profile_path)
    if not mp_file.exists():
        raise FileNotFoundError(
            f"Metric profile sample file not found at '{mp_file}'. "
            "Cannot enforce exclusion of previous metric profile sample."
        )

    excluded: Set[Tuple[str, int]] = set()

    with open(rand_file, "r", encoding="utf-8") as f:
        rand_records = json.load(f)
    if not isinstance(rand_records, list):
        raise ValueError(f"Expected JSON array in '{rand_file}', got {type(rand_records).__name__}")
    for item in rand_records:
        src = item.get("source", {})
        if "relative_path" in src and "index" in src:
            excluded.add((src["relative_path"], int(src["index"])))

    with open(mp_file, "r", encoding="utf-8") as f:
        mp_records = json.load(f)
    if not isinstance(mp_records, list):
        raise ValueError(f"Expected JSON array in '{mp_file}', got {type(mp_records).__name__}")
    for item in mp_records:
        src = item.get("source", {})
        if "relative_path" in src and "index" in src:
            excluded.add((src["relative_path"], int(src["index"])))

    return excluded


def calculate_disagreement_features(
    output_item: Dict[str, Any],
    jev_item: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate comprehensive disagreement features across the 3 LLM judges and JEV.
    """
    metric_ranges: Dict[str, int] = {}
    metric_stdevs: Dict[str, float] = {}
    metric_unanimous: Dict[str, bool] = {}
    metric_range_ge_2: Dict[str, bool] = {}
    metric_low_vs_high: Dict[str, bool] = {}
    metric_means: Dict[str, float] = {}
    metric_medians: Dict[str, int] = {}
    judge_scores: Dict[str, List[int]] = {}
    outlier_judges_per_metric: Dict[str, Optional[int]] = {}

    judge_outlier_counts = Counter()

    for m in NUMERIC_METRICS:
        s1 = output_item.get("judge_1", {}).get("evaluation", {}).get(m)
        s2 = output_item.get("judge_2", {}).get("evaluation", {}).get(m)
        s3 = output_item.get("judge_3", {}).get("evaluation", {}).get(m)

        vals = [int(v) for v in (s1, s2, s3) if v is not None]
        if len(vals) < 3:
            raise ValueError(f"Incomplete judge scores for metric '{m}'")

        judge_scores[m] = vals
        rng = max(vals) - min(vals)
        metric_ranges[m] = rng
        metric_stdevs[m] = round(statistics.stdev(vals), 3)
        metric_unanimous[m] = (rng == 0)
        metric_range_ge_2[m] = (rng >= 2)
        metric_low_vs_high[m] = (min(vals) <= 1 and max(vals) >= 2)
        metric_means[m] = round(sum(vals) / 3.0, 3)
        metric_medians[m] = sorted(vals)[1]

        # Identify outlier judge on metric m (if 2 judges agree and 1 differs)
        if vals[0] != vals[1] and vals[0] != vals[2] and vals[1] == vals[2]:
            outlier_judges_per_metric[m] = 1
            judge_outlier_counts[1] += 1
        elif vals[1] != vals[0] and vals[1] != vals[2] and vals[0] == vals[2]:
            outlier_judges_per_metric[m] = 2
            judge_outlier_counts[2] += 1
        elif vals[2] != vals[0] and vals[2] != vals[1] and vals[0] == vals[1]:
            outlier_judges_per_metric[m] = 3
            judge_outlier_counts[3] += 1
        else:
            outlier_judges_per_metric[m] = None

    # Overall profile distances between pairs of judges across the 7 metrics
    d12 = sum(abs(judge_scores[m][0] - judge_scores[m][1]) for m in NUMERIC_METRICS)
    d13 = sum(abs(judge_scores[m][0] - judge_scores[m][2]) for m in NUMERIC_METRICS)
    d23 = sum(abs(judge_scores[m][1] - judge_scores[m][2]) for m in NUMERIC_METRICS)

    total_pairwise_diff = d12 + d13 + d23
    mean_pairwise_diff = round(total_pairwise_diff / 21.0, 4)

    num_disagreed = sum(1 for m in NUMERIC_METRICS if metric_ranges[m] >= 1)
    num_range_ge_2 = sum(1 for m in NUMERIC_METRICS if metric_ranges[m] >= 2)
    num_low_vs_high = sum(1 for m in NUMERIC_METRICS if metric_low_vs_high[m])
    max_range = max(metric_ranges.values())

    # JEV comparisons
    jev_answers = jev_item.get("evaluation", {}).get("answers", {})
    jev_expected: Dict[str, float] = {}
    jev_argmax: Dict[str, int] = {}
    jev_contrasts: Dict[str, float] = {}

    for m in NUMERIC_METRICS:
        m_ans = jev_answers.get(m, {})
        c_score = float(m_ans.get("score", 0.0))
        jev_expected[m] = c_score
        probs = m_ans.get("probabilities", {})
        if probs:
            am = int(max(probs.items(), key=lambda kv: (float(kv[1]), int(kv[0])))[0])
            jev_argmax[m] = am
        else:
            jev_argmax[m] = int(round(c_score))
        jev_contrasts[m] = round(abs(c_score - metric_means[m]), 3)

    mean_jev_contrast = round(sum(jev_contrasts.values()) / 7.0, 3)

    # Machine-generated concise disagreement summary
    summary_parts = []
    severe_parts = []
    for m in NUMERIC_METRICS:
        if metric_ranges[m] >= 2:
            severe_parts.append(f"{m} (J1={judge_scores[m][0]}, J2={judge_scores[m][1]}, J3={judge_scores[m][2]})")
    if severe_parts:
        summary_parts.append(f"Strong disagreements (range>=2): {', '.join(severe_parts)}")

    summary_parts.append(f"{num_disagreed}/7 metrics disagreed (mean pairwise diff={mean_pairwise_diff:.2f})")

    outlier_parts = []
    for j_num in [1, 2, 3]:
        if judge_outlier_counts[j_num] > 0:
            outlier_parts.append(f"Judge {j_num}: {judge_outlier_counts[j_num]}")
    if outlier_parts:
        summary_parts.append(f"Outlier counts: {', '.join(outlier_parts)}")

    high_jev = [m for m in NUMERIC_METRICS if jev_contrasts[m] >= 0.6]
    if high_jev:
        summary_parts.append(f"JEV contrast on {', '.join(high_jev)}")

    disagreement_summary = "; ".join(summary_parts)

    return {
        "judge_scores": judge_scores,
        "metric_ranges": metric_ranges,
        "metric_stdevs": metric_stdevs,
        "metric_unanimous": metric_unanimous,
        "metric_range_ge_2": metric_range_ge_2,
        "metric_low_vs_high": metric_low_vs_high,
        "metric_means": metric_means,
        "metric_medians": metric_medians,
        "pairwise_profile_distances": {
            "judge_1_vs_judge_2": d12,
            "judge_1_vs_judge_3": d13,
            "judge_2_vs_judge_3": d23,
        },
        "max_pairwise_profile_distance": max(d12, d13, d23),
        "mean_pairwise_score_difference": mean_pairwise_diff,
        "num_disagreed_metrics": num_disagreed,
        "num_range_ge_2_metrics": num_range_ge_2,
        "num_low_vs_high_metrics": num_low_vs_high,
        "max_individual_metric_range": max_range,
        "outlier_judges_per_metric": outlier_judges_per_metric,
        "judge_outlier_counts": dict(judge_outlier_counts),
        "jev_expected": jev_expected,
        "jev_argmax": jev_argmax,
        "jev_contrasts": jev_contrasts,
        "mean_jev_contrast": mean_jev_contrast,
        "disagreement_summary": disagreement_summary,
    }


def assign_disagreement_categories(features: Dict[str, Any]) -> List[str]:
    """
    Assign all applicable disagreement categories based on calculated features.
    """
    categories: List[str] = []

    if features["max_individual_metric_range"] >= 2:
        categories.append("strong_metric_disagreement")
    if features["max_individual_metric_range"] >= 3:
        categories.append("extreme_metric_disagreement")

    if features["num_low_vs_high_metrics"] >= 1:
        categories.append("low_vs_high_disagreement")

    if features["num_disagreed_metrics"] >= 3:
        categories.append("multi_metric_disagreement")
    if features["num_disagreed_metrics"] >= 5:
        categories.append("broad_multi_metric_disagreement")

    if features["max_pairwise_profile_distance"] >= 4 or features["mean_pairwise_score_difference"] >= 0.25:
        categories.append("profile_level_disagreement")

    # Metric specific disagreement categories
    for m in NUMERIC_METRICS:
        if features["metric_ranges"][m] >= 2:
            categories.append(f"severe_disagreement_{m}")
        elif features["metric_ranges"][m] >= 1:
            categories.append(f"disagreement_{m}")

    # Outlier patterns
    outlier_counts = features["judge_outlier_counts"]
    for j in [1, 2, 3]:
        if outlier_counts.get(j, 0) >= 2:
            categories.append(f"judge_{j}_outlier")

    active_outliers = sum(1 for j in [1, 2, 3] if outlier_counts.get(j, 0) >= 1)
    if active_outliers >= 2:
        categories.append("mixed_outliers")

    if features["mean_jev_contrast"] >= 0.40 or any(c >= 0.60 for c in features["jev_contrasts"].values()):
        categories.append("jev_contrast")

    if not categories:
        categories.append("minor_disagreement")

    return categories


def build_disagreement_candidates(
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    excluded_refs: Set[Tuple[str, int]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Discover all conversations, exclude previous samples, and compute disagreement features.
    """
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    jev_path = Path(jev_dir)

    all_json_files: List[Path] = []
    for root, _, files in os.walk(data_path):
        for fname in files:
            if fname.endswith(".json"):
                all_json_files.append(Path(root) / fname)
    all_json_files.sort()

    candidates: List[Dict[str, Any]] = []
    total_discovered = 0
    total_excluded = 0

    metric_range_distributions: Dict[str, Counter] = {m: Counter() for m in NUMERIC_METRICS}
    disagreed_count_dist: Counter = Counter()
    low_high_count_dist: Counter = Counter()
    max_range_dist: Counter = Counter()

    for file_path in all_json_files:
        rel_path = file_path.relative_to(data_path).as_posix()
        o_file = output_path / rel_path
        j_file = jev_path / rel_path

        if not o_file.exists():
            raise FileNotFoundError(f"Missing output file: '{o_file}'")
        if not j_file.exists():
            raise FileNotFoundError(f"Missing JEV file: '{j_file}'")

        with open(file_path, "r", encoding="utf-8") as f:
            d_records = json.load(f)
        with open(o_file, "r", encoding="utf-8") as f:
            o_records = json.load(f)
        with open(j_file, "r", encoding="utf-8") as f:
            j_records = json.load(f)

        for idx in range(len(d_records)):
            total_discovered += 1
            if (rel_path, idx) in excluded_refs:
                total_excluded += 1
                continue

            feats = calculate_disagreement_features(o_records[idx], j_records[idx])
            categories = assign_disagreement_categories(feats)

            # Record distributions
            for m in NUMERIC_METRICS:
                metric_range_distributions[m][feats["metric_ranges"][m]] += 1
            disagreed_count_dist[feats["num_disagreed_metrics"]] += 1
            low_high_count_dist[feats["num_low_vs_high_metrics"]] += 1
            max_range_dist[feats["max_individual_metric_range"]] += 1

            candidates.append({
                "rel_path": rel_path,
                "index": idx,
                "subfolder": Path(rel_path).parent.as_posix(),
                "ranges": [feats["metric_ranges"][m] for m in NUMERIC_METRICS],
                "features": feats,
                "disagreement_categories": categories,
                "disagreement_summary": feats["disagreement_summary"],
            })

    # Sort deterministically before any selection
    candidates.sort(key=lambda c: (c["rel_path"], c["index"]))

    stats = {
        "total_discovered": total_discovered,
        "total_excluded": total_excluded,
        "eligible_candidates_count": len(candidates),
        "metric_range_distributions": {
            m: {str(r): metric_range_distributions[m][r] for r in [0, 1, 2, 3]}
            for m in NUMERIC_METRICS
        },
        "disagreed_count_distribution": {str(k): disagreed_count_dist[k] for k in sorted(disagreed_count_dist)},
        "low_vs_high_count_distribution": {str(k): low_high_count_dist[k] for k in sorted(low_high_count_dist)},
        "max_range_distribution": {str(k): max_range_dist[k] for k in sorted(max_range_dist)},
    }

    return candidates, stats


def range_vector_distance(v1: Sequence[int], v2: Sequence[int]) -> float:
    """Normalized Manhattan distance between two 7D metric range vectors (range [0, 3])."""
    return sum(abs(a - b) for a, b in zip(v1, v2)) / float(len(v1))


def select_diverse_disagreement_cases(
    candidates: List[Dict[str, Any]],
    target_count: int = 40,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Select diverse, high-value judge disagreement cases:
    1. Seed selection with rare strong disagreements (progression, diagnosis, coherence, state_adaptation).
    2. Fill remainder using greedy max-min diversity over 7D range vectors, weighted by
       disagreement intensity, subfolder balancing penalty, JEV contrast, and seeded jitter.
    """
    reallocation_notes: List[str] = []
    if len(candidates) <= target_count:
        reallocation_notes.append(
            f"Candidate pool had only {len(candidates)} records; all selected."
        )
        return list(candidates), reallocation_notes

    selected: List[Dict[str, Any]] = []
    selected_keys: Set[Tuple[str, int]] = set()
    subfolder_counts: Counter = Counter()

    # Priority 1: Progression range >= 2 (very rare in dataset, 1 candidate)
    prog_cands = [c for c in candidates if c["features"]["metric_ranges"]["progression"] >= 2]
    for c in prog_cands:
        if len(selected) < target_count:
            selected.append(c)
            selected_keys.add((c["rel_path"], c["index"]))
            subfolder_counts[c["subfolder"]] += 1

    # Priority 2: Diagnosis range >= 2 (rare in dataset, 3 candidates)
    diag_cands = [
        c for c in candidates
        if c["features"]["metric_ranges"]["diagnosis"] >= 2 and (c["rel_path"], c["index"]) not in selected_keys
    ]
    for c in diag_cands:
        if len(selected) < target_count:
            selected.append(c)
            selected_keys.add((c["rel_path"], c["index"]))
            subfolder_counts[c["subfolder"]] += 1

    # Priority 3: Coherence range >= 2 (rare in dataset, 4 candidates)
    coh_cands = [
        c for c in candidates
        if c["features"]["metric_ranges"]["coherence"] >= 2 and (c["rel_path"], c["index"]) not in selected_keys
    ]
    coh_cands.sort(
        key=lambda c: (c["features"]["mean_pairwise_score_difference"], c["features"]["mean_jev_contrast"]),
        reverse=True,
    )
    for c in coh_cands[:2]:
        if len(selected) < target_count:
            selected.append(c)
            selected_keys.add((c["rel_path"], c["index"]))
            subfolder_counts[c["subfolder"]] += 1

    # Priority 4: State adaptation range >= 1 with high multi-metric disagreement
    sa_cands = [
        c for c in candidates
        if c["features"]["metric_ranges"]["state_adaptation"] >= 1 and (c["rel_path"], c["index"]) not in selected_keys
    ]
    sa_cands.sort(
        key=lambda c: (c["features"]["num_disagreed_metrics"], c["features"]["mean_pairwise_score_difference"]),
        reverse=True,
    )
    for c in sa_cands[:2]:
        if len(selected) < target_count:
            selected.append(c)
            selected_keys.add((c["rel_path"], c["index"]))
            subfolder_counts[c["subfolder"]] += 1

    # Filter candidates to those with meaningful disagreement
    meaningful_pool = [
        c for c in candidates
        if (c["rel_path"], c["index"]) not in selected_keys
        and (
            c["features"]["max_individual_metric_range"] >= 2
            or c["features"]["num_disagreed_metrics"] >= 3
            or c["features"]["num_low_vs_high_metrics"] >= 1
        )
    ]

    # Precompute candidate jitter for deterministic tie breaking
    candidate_jitter = {
        (c["rel_path"], c["index"]): (hash((c["rel_path"], c["index"], seed)) % 1000) / 10000.0
        for c in meaningful_pool
    }

    # Greedy max-min diversity selection
    while len(selected) < target_count and meaningful_pool:
        best_cand = None
        best_score = -float("inf")

        for c in meaningful_pool:
            key = (c["rel_path"], c["index"])
            if key in selected_keys:
                continue

            f = c["features"]
            if selected:
                min_d = min(range_vector_distance(c["ranges"], s["ranges"]) for s in selected)
            else:
                min_d = 1.0

            # Disagreement strength score
            strength = (
                0.5 * f["mean_pairwise_score_difference"]
                + 0.3 * f["num_range_ge_2_metrics"]
                + 0.2 * f["num_low_vs_high_metrics"]
            )

            # Subfolder penalty
            sub_penalty = 0.15 * subfolder_counts[c["subfolder"]]

            # JEV contrast bonus
            jev_bonus = 0.05 * f["mean_jev_contrast"]

            score = min_d + strength - sub_penalty + jev_bonus + candidate_jitter[key]
            if score > best_score:
                best_score = score
                best_cand = c

        if not best_cand:
            break

        selected.append(best_cand)
        selected_keys.add((best_cand["rel_path"], best_cand["index"]))
        subfolder_counts[best_cand["subfolder"]] += 1

    return selected, reallocation_notes


def load_selected_records(
    selected_candidates: Sequence[Dict[str, Any]],
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    id_prefix: str = "JD",
) -> List[Dict[str, Any]]:
    """
    Two-pass loader: reads files grouped by path and preserves original sampled order.
    """
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    jev_path = Path(jev_dir)

    file_indices: Dict[str, List[int]] = defaultdict(list)
    for c in selected_candidates:
        file_indices[c["rel_path"]].append(c["index"])

    loaded_cache: Dict[Tuple[str, int], Tuple[Any, Any, Any]] = {}
    for rel_path, indices in file_indices.items():
        with open(data_path / rel_path, "r", encoding="utf-8") as f:
            d_records = json.load(f)
        with open(output_path / rel_path, "r", encoding="utf-8") as f:
            o_records = json.load(f)
        with open(jev_path / rel_path, "r", encoding="utf-8") as f:
            j_records = json.load(f)

        for idx in indices:
            loaded_cache[(rel_path, idx)] = (d_records[idx], o_records[idx], j_records[idx])

    annotations: List[Dict[str, Any]] = []
    pad_width = max(4, len(str(len(selected_candidates))))

    for i, c in enumerate(selected_candidates, start=1):
        rel_path = c["rel_path"]
        idx = c["index"]
        conv, llm_judge, jev = loaded_cache[(rel_path, idx)]

        annotations.append({
            "annotation_id": f"{id_prefix}-{i:0{pad_width}d}",
            "sampling_strategy": "judge_disagreement",
            "disagreement_categories": c["disagreement_categories"],
            "disagreement_summary": c["disagreement_summary"],
            "source": {
                "relative_path": rel_path,
                "index": idx,
            },
            "conversation": conv,
            "llm_judge_output": llm_judge,
            "jev_output": jev,
        })

    return annotations


def generate_disagreement_analysis(
    dataset_stats: Dict[str, Any],
    all_candidates: List[Dict[str, Any]],
    selected_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate in-depth statistical analysis for disagreement_analysis.json.
    """
    # 1. Selected sample disagreement statistics by metric
    sample_metric_stats: Dict[str, Any] = {}
    for m in NUMERIC_METRICS:
        ranges = [c["features"]["metric_ranges"][m] for c in selected_candidates]
        stdevs = [c["features"]["metric_stdevs"][m] for c in selected_candidates]
        unanimous = sum(1 for c in selected_candidates if c["features"]["metric_unanimous"][m])
        ge_2 = sum(1 for c in selected_candidates if c["features"]["metric_range_ge_2"][m])
        low_high = sum(1 for c in selected_candidates if c["features"]["metric_low_vs_high"][m])
        sample_metric_stats[m] = {
            "mean_range": round(statistics.mean(ranges), 3),
            "max_range": max(ranges),
            "mean_stdev": round(statistics.mean(stdevs), 3),
            "unanimous_count": unanimous,
            "range_ge_2_count": ge_2,
            "low_vs_high_count": low_high,
        }

    # 2. Pairwise profile distances in selected sample
    mean_d12 = round(statistics.mean(c["features"]["pairwise_profile_distances"]["judge_1_vs_judge_2"] for c in selected_candidates), 2)
    mean_d13 = round(statistics.mean(c["features"]["pairwise_profile_distances"]["judge_1_vs_judge_3"] for c in selected_candidates), 2)
    mean_d23 = round(statistics.mean(c["features"]["pairwise_profile_distances"]["judge_2_vs_judge_3"] for c in selected_candidates), 2)

    # 3. Outlier judges breakdown in selected sample
    outliers_selected = Counter()
    for c in selected_candidates:
        for j, cnt in c["features"]["judge_outlier_counts"].items():
            outliers_selected[f"judge_{j}"] += cnt

    # 4. Pattern examples (annotation ID, metrics, scores, summary)
    pattern_examples = []
    pad_width = max(4, len(str(len(selected_candidates))))
    for i, c in enumerate(selected_candidates, start=1):
        f = c["features"]
        annot_id = f"JD-{i:0{pad_width}d}"
        pattern_examples.append({
            "annotation_id": annot_id,
            "relative_path": c["rel_path"],
            "index": c["index"],
            "categories": c["disagreement_categories"],
            "summary": c["disagreement_summary"],
            "max_range": f["max_individual_metric_range"],
            "num_disagreed_metrics": f["num_disagreed_metrics"],
            "mean_pairwise_diff": f["mean_pairwise_score_difference"],
        })

    # 5. JEV comparisons
    mean_jev_contrast = round(
        statistics.mean(c["features"]["mean_jev_contrast"] for c in selected_candidates), 3
    )
    metric_jev_contrasts = {}
    for m in NUMERIC_METRICS:
        metric_jev_contrasts[m] = round(
            statistics.mean(c["features"]["jev_contrasts"][m] for c in selected_candidates), 3
        )

    # 6. Comparison between Candidate Pool and Selected Sample
    pool_mean_diff = round(
        statistics.mean(c["features"]["mean_pairwise_score_difference"] for c in all_candidates), 3
    )
    sample_mean_diff = round(
        statistics.mean(c["features"]["mean_pairwise_score_difference"] for c in selected_candidates), 3
    )

    pool_pct_ge_2 = round(
        sum(1 for c in all_candidates if c["features"]["num_range_ge_2_metrics"] >= 1) / float(len(all_candidates)) * 100.0, 1
    )
    sample_pct_ge_2 = round(
        sum(1 for c in selected_candidates if c["features"]["num_range_ge_2_metrics"] >= 1) / float(len(selected_candidates)) * 100.0, 1
    )

    pool_pct_low_high = round(
        sum(1 for c in all_candidates if c["features"]["num_low_vs_high_metrics"] >= 1) / float(len(all_candidates)) * 100.0, 1
    )
    sample_pct_low_high = round(
        sum(1 for c in selected_candidates if c["features"]["num_low_vs_high_metrics"] >= 1) / float(len(selected_candidates)) * 100.0, 1
    )

    return {
        "dataset_wide_disagreement_distribution": {
            "metric_range_distributions": dataset_stats["metric_range_distributions"],
            "disagreed_metrics_distribution": dataset_stats["disagreed_count_distribution"],
            "low_vs_high_distribution": dataset_stats["low_vs_high_count_distribution"],
            "max_range_distribution": dataset_stats["max_range_distribution"],
        },
        "selected_sample_disagreement_statistics": {
            "by_metric": sample_metric_stats,
            "mean_judge_pair_profile_distances": {
                "judge_1_vs_judge_2": mean_d12,
                "judge_1_vs_judge_3": mean_d13,
                "judge_2_vs_judge_3": mean_d23,
            },
            "outlier_judge_counts_across_metrics": dict(outliers_selected),
        },
        "disagreement_pattern_examples": pattern_examples[:10],
        "jev_supplementary_analysis": {
            "sample_mean_jev_contrast": mean_jev_contrast,
            "by_metric_mean_contrast": metric_jev_contrasts,
        },
        "candidate_pool_vs_selected_comparison": {
            "mean_pairwise_score_difference": {
                "candidate_pool": pool_mean_diff,
                "selected_sample": sample_mean_diff,
            },
            "percent_with_range_ge_2": {
                "candidate_pool": pool_pct_ge_2,
                "selected_sample": sample_pct_ge_2,
            },
            "percent_with_low_vs_high": {
                "candidate_pool": pool_pct_low_high,
                "selected_sample": sample_pct_low_high,
            },
        },
    }


def write_annotation_set(
    annotation_dir: Union[str, Path],
    annotations: List[Dict[str, Any]],
    selected_candidates: List[Dict[str, Any]],
    all_candidates: List[Dict[str, Any]],
    dataset_stats: Dict[str, Any],
    sample_size: int,
    seed: int,
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    random_sample_path: Union[str, Path],
    metric_profile_path: Union[str, Path],
    reallocation_notes: List[str],
    overwrite: bool = False,
) -> None:
    """
    Write annotations.json, manifest.json, selection_summary.json, and disagreement_analysis.json.
    Guards against accidental overwriting unless overwrite=True.
    """
    target_dir = Path(annotation_dir)
    if target_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output directory '{target_dir}' already exists. Use --overwrite to overwrite."
            )
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    # 1. annotations.json
    with open(target_dir / "annotations.json", "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)

    # 2. manifest.json
    manifest = {
        "requested_sample_size": sample_size,
        "actual_sample_size": len(annotations),
        "random_seed": seed,
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "configured_input_directories": {
            "data_dir": str(Path(data_dir)),
            "output_dir": str(Path(output_dir)),
            "jev_dir": str(Path(jev_dir)),
            "random_sample_file": str(Path(random_sample_path)),
            "metric_profile_sample_file": str(Path(metric_profile_path)),
        },
        "selection_method": (
            "Multi-pattern priority seeding for rare severe disagreements, followed by "
            "greedy max-min Manhattan distance over 7D disagreement range vectors, "
            "disagreement intensity scoring, subfolder frequency penalty, and JEV contrast bonus."
        ),
        "selected_conversations": [
            {
                "annotation_id": item["annotation_id"],
                "relative_path": item["source"]["relative_path"],
                "index": item["source"]["index"],
                "disagreement_categories": item["disagreement_categories"],
                "disagreement_summary": item.get("disagreement_summary", ""),
            }
            for item in annotations
        ],
    }
    with open(target_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # 3. selection_summary.json
    per_subfolder: Counter = Counter()
    per_file: Counter = Counter()
    cat_counts: Counter = Counter()

    for c in selected_candidates:
        per_subfolder[c["subfolder"]] += 1
        per_file[c["rel_path"]] += 1
        for cat in c["disagreement_categories"]:
            cat_counts[cat] += 1

    mean_pairwise_diff = round(
        statistics.mean(c["features"]["mean_pairwise_score_difference"] for c in selected_candidates), 3
    )
    mean_num_disagreed = round(
        statistics.mean(c["features"]["num_disagreed_metrics"] for c in selected_candidates), 2
    )
    strong_count = sum(1 for c in selected_candidates if c["features"]["max_individual_metric_range"] >= 2)
    low_high_count = sum(1 for c in selected_candidates if c["features"]["num_low_vs_high_metrics"] >= 1)

    summary = {
        "total_conversations_examined": dataset_stats["total_discovered"],
        "excluded_due_to_overlap": dataset_stats["total_excluded"],
        "eligible_candidates_count": dataset_stats["eligible_candidates_count"],
        "number_selected": len(selected_candidates),
        "selected_by_disagreement_category": dict(cat_counts),
        "selected_per_subfolder": dict(sorted(per_subfolder.items())),
        "selected_per_file": dict(sorted(per_file.items())),
        "mean_disagreement_statistics": {
            "mean_pairwise_score_difference": mean_pairwise_diff,
            "mean_metrics_disagreed": mean_num_disagreed,
            "strong_disagreements_count": strong_count,
            "low_vs_high_count": low_high_count,
        },
        "random_seed": seed,
        "shortfall_or_fallback": reallocation_notes if reallocation_notes else "None",
    }
    with open(target_dir / "selection_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # 4. disagreement_analysis.json
    analysis = generate_disagreement_analysis(dataset_stats, all_candidates, selected_candidates)
    with open(target_dir / "disagreement_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select 40 judge-disagreement conversations for human annotation."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path to directory containing source conversations (default: data).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Path to directory containing LLM judge outputs (default: output).",
    )
    parser.add_argument(
        "--jev-dir",
        type=Path,
        default=Path("jev_output"),
        help="Path to directory containing JEV judge outputs (default: jev_output).",
    )
    parser.add_argument(
        "--random-sample",
        type=Path,
        default=Path("annotation_set/random_sample/annotations.json"),
        help="Path to random sample annotations.json (default: annotation_set/random_sample/annotations.json).",
    )
    parser.add_argument(
        "--metric-profile-sample",
        type=Path,
        default=Path("annotation_set/metric_profile_sample/annotations.json"),
        help="Path to metric profile sample annotations.json (default: annotation_set/metric_profile_sample/annotations.json).",
    )
    parser.add_argument(
        "--annotation-dir",
        type=Path,
        default=Path("annotation_set/judge_disagreement_sample"),
        help="Path to output directory (default: annotation_set/judge_disagreement_sample).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=40,
        help="Total sample size (default: 40).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling (default: 42).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output directory if present.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    print("Loading previous sample references to exclude...")
    try:
        excluded_refs = load_previous_sample_references(
            random_sample_path=args.random_sample,
            metric_profile_path=args.metric_profile_sample,
        )
    except Exception as e:
        print(f"Error loading previous samples: {e}", file=sys.stderr)
        return 1

    print(f"Loaded {len(excluded_refs)} previous sample records to exclude.")

    print(f"Examining conversations across '{args.data_dir}', '{args.output_dir}', '{args.jev_dir}'...")
    try:
        candidates, stats = build_disagreement_candidates(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            excluded_refs=excluded_refs,
        )
    except Exception as e:
        print(f"Error calculating disagreement features: {e}", file=sys.stderr)
        return 1

    total_discovered = stats["total_discovered"]
    total_excluded = stats["total_excluded"]
    eligible_count = stats["eligible_candidates_count"]
    print(f"Total conversations examined: {total_discovered}")
    print(f"Excluded due to overlap with previous samples: {total_excluded}")
    print(f"Eligible disagreement candidates: {eligible_count}")

    print(f"Selecting {args.sample_size} diverse judge disagreement cases (seed={args.seed})...")
    selected_cands, reallocation_notes = select_diverse_disagreement_cases(
        candidates=candidates,
        target_count=args.sample_size,
        seed=args.seed,
    )
    print(f"Selected {len(selected_cands)} conversations.")

    print("Loading full conversation and judge records...")
    try:
        annotations = load_selected_records(
            selected_candidates=selected_cands,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            id_prefix="JD",
        )
    except Exception as e:
        print(f"Error loading records: {e}", file=sys.stderr)
        return 1

    print(f"Writing judge-disagreement annotation set to '{args.annotation_dir}'...")
    try:
        write_annotation_set(
            annotation_dir=args.annotation_dir,
            annotations=annotations,
            selected_candidates=selected_cands,
            all_candidates=candidates,
            dataset_stats=stats,
            sample_size=args.sample_size,
            seed=args.seed,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            random_sample_path=args.random_sample,
            metric_profile_path=args.metric_profile_sample,
            reallocation_notes=reallocation_notes,
            overwrite=args.overwrite,
        )
    except FileExistsError as e:
        print(f"Output error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error writing annotation set: {e}", file=sys.stderr)
        return 1

    # Final summary report (Section 9)
    sample_mean_ranges = {}
    sample_strong_counts = {}
    for m in NUMERIC_METRICS:
        sample_mean_ranges[m] = round(
            statistics.mean(c["features"]["metric_ranges"][m] for c in selected_cands), 2
        )
        sample_strong_counts[m] = sum(
            1 for c in selected_cands if c["features"]["metric_ranges"][m] >= 2
        )

    categories_count = Counter()
    for c in selected_cands:
        for cat in c["disagreement_categories"]:
            categories_count[cat] += 1

    print("\n=======================================================")
    print("        JUDGE-DISAGREEMENT SELECTION FINAL REPORT       ")
    print("=======================================================")
    print(f"1. Total conversations examined:           {total_discovered}")
    print(f"2. Excluded due to previous sample overlap:{total_excluded}")
    print(f"3. Eligible disagreement candidates:       {eligible_count}")
    print(f"4. Number selected:                        {len(selected_cands)}")
    print("5. Mean disagreement score (range) per metric in selected sample:")
    for m in NUMERIC_METRICS:
        print(f"   - {m:20s}: {sample_mean_ranges[m]:.2f}")
    print("6. Counts of selected cases with strong disagreement (range>=2):")
    for m in NUMERIC_METRICS:
        print(f"   - {m:20s}: {sample_strong_counts[m]} cases")
    print("7. Variety of disagreement patterns represented:")
    for cat, count in categories_count.most_common(8):
        print(f"   - {cat:32s}: {count} cases")
    target_achieved = (len(selected_cands) == args.sample_size)
    print(f"8. Target ({args.sample_size}) achieved:                 {'YES' if target_achieved else 'NO'}")
    print("9. Generated files:")
    print(f"   - {args.annotation_dir / 'annotations.json'}")
    print(f"   - {args.annotation_dir / 'manifest.json'}")
    print(f"   - {args.annotation_dir / 'selection_summary.json'}")
    print(f"   - {args.annotation_dir / 'disagreement_analysis.json'}")
    print("=======================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
