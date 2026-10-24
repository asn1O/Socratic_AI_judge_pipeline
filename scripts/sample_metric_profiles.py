#!/usr/bin/env python3
"""
Select 120 metric-profile conversations for human annotation.

Identifies conversations with metric-level strengths and weaknesses based on
the median discrete score across three LLM judges, complemented by JEV scores.
Excludes the 240 conversations previously selected in the random sample.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
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


def load_random_sample_references(random_sample_path: Union[str, Path]) -> Set[Tuple[str, int]]:
    """
    Read the random sample annotations and return a set of (relative_path, index) tuples.
    Raises FileNotFoundError if the file is missing.
    """
    sample_file = Path(random_sample_path)
    if not sample_file.exists():
        raise FileNotFoundError(
            f"Random sample file not found at '{sample_file}'. "
            "Cannot enforce random sample exclusion requirement."
        )

    with open(sample_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list):
        raise ValueError(
            f"Expected JSON array in '{sample_file}', got {type(records).__name__}."
        )

    excluded: Set[Tuple[str, int]] = set()
    for item in records:
        source = item.get("source", {})
        rel_path = source.get("relative_path")
        idx = source.get("index")
        if rel_path is not None and idx is not None:
            excluded.add((rel_path, int(idx)))

    return excluded


def compute_median_score(scores: Sequence[int]) -> int:
    """
    Compute the integer median of discrete judge scores.
    For 3 judges, returns the middle element of the sorted scores.
    """
    if len(scores) == 3:
        return sorted(scores)[1]
    sorted_scores = sorted(scores)
    mid = len(sorted_scores) // 2
    return sorted_scores[mid]


def extract_judge_scores(output_item: Dict[str, Any], jev_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metric scores from 3 LLM judges and JEV for a single conversation.
    """
    medians: List[int] = []
    means: List[float] = []
    judge_scores: Dict[str, List[int]] = {}
    jev_argmax: Dict[str, int] = {}
    jev_expected: Dict[str, float] = {}

    jev_answers = jev_item.get("evaluation", {}).get("answers", {})

    for metric in NUMERIC_METRICS:
        s1 = output_item.get("judge_1", {}).get("evaluation", {}).get(metric)
        s2 = output_item.get("judge_2", {}).get("evaluation", {}).get(metric)
        s3 = output_item.get("judge_3", {}).get("evaluation", {}).get(metric)

        vals = [int(v) for v in (s1, s2, s3) if v is not None]
        if len(vals) < 3:
            raise ValueError(f"Incomplete LLM judge scores for metric '{metric}'")

        judge_scores[metric] = vals
        med = compute_median_score(vals)
        medians.append(med)
        means.append(sum(vals) / float(len(vals)))

        # JEV continuous and discrete scores
        m_ans = jev_answers.get(metric, {})
        c_score = float(m_ans.get("score", 0.0))
        jev_expected[metric] = c_score

        probs = m_ans.get("probabilities", {})
        if probs:
            # Discrete argmax: bucket k in {0,1,2,3} with highest probability
            am = int(max(probs.items(), key=lambda kv: (float(kv[1]), int(kv[0])))[0])
            jev_argmax[metric] = am
        else:
            jev_argmax[metric] = int(round(c_score))

    # JEV boundary closeness: average distance to nearest decision boundary (0.5, 1.5, 2.5)
    # Higher (less negative) means closer to a boundary
    bound_dist = sum(
        min(abs(jev_expected[m] - 0.5), abs(jev_expected[m] - 1.5), abs(jev_expected[m] - 2.5))
        for m in NUMERIC_METRICS
    ) / len(NUMERIC_METRICS)
    boundary_closeness = -bound_dist

    return {
        "medians": medians,
        "means": means,
        "judge_scores": judge_scores,
        "jev_argmax": jev_argmax,
        "jev_expected": jev_expected,
        "jev_boundary_closeness": boundary_closeness,
    }


def is_primary_eligible(medians: Sequence[int]) -> bool:
    """
    Check if a median score vector satisfies the primary isolated-weakness rule:
    - Exactly one or two of the 7 median metric scores equal 1.
    - Every other metric has a median score of 2 or 3.
    - No metric has a median score of 0.
    """
    c0 = medians.count(0)
    c1 = medians.count(1)
    return (c0 == 0) and (c1 in (1, 2)) and all(x in (1, 2, 3) for x in medians)


def get_profile_categories(medians: Sequence[int]) -> List[str]:
    """
    Assign all applicable profile categories for a conversation based on its median scores.
    """
    categories: List[str] = []
    c0 = medians.count(0)
    c1 = medians.count(1)
    c_low = c0 + c1
    c_high = sum(1 for x in medians if x in (2, 3))

    # Check primary isolated weaknesses
    if is_primary_eligible(medians):
        for idx, metric in enumerate(NUMERIC_METRICS):
            if medians[idx] == 1:
                categories.append(f"isolated_weakness_{metric}")
    elif min(medians) >= 2:
        categories.append("uniformly_strong")
    elif c_low >= 3:
        categories.append("multiple_weaknesses")
        if c_high > 0:
            categories.append("mixed_strengths_weaknesses")
    elif c_low > 0 and c_high > 0:
        categories.append("mixed_strengths_weaknesses")
    else:
        categories.append("other_diverse_profile")

    return categories


def build_metric_profiles(
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    excluded_refs: Set[Tuple[str, int]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Discover all conversations, exclude random sample records, and compute metric profiles.
    Returns:
    - List of candidate profile dicts (sorted deterministically)
    - Dataset-wide statistics dictionary
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

    dataset_distributions: Dict[str, Counter] = {m: Counter() for m in NUMERIC_METRICS}
    dataset_primary_count = 0
    dataset_1_weak_count = 0
    dataset_2_weak_count = 0
    dataset_weak_counts: Counter = Counter()

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
            scores_data = extract_judge_scores(o_records[idx], j_records[idx])
            medians = scores_data["medians"]

            # Record dataset-wide distribution
            for m_idx, m_name in enumerate(NUMERIC_METRICS):
                dataset_distributions[m_name][medians[m_idx]] += 1

            if is_primary_eligible(medians):
                dataset_primary_count += 1
                c1 = medians.count(1)
                if c1 == 1:
                    dataset_1_weak_count += 1
                else:
                    dataset_2_weak_count += 1
                for m_idx, m_name in enumerate(NUMERIC_METRICS):
                    if medians[m_idx] == 1:
                        dataset_weak_counts[m_name] += 1

            if (rel_path, idx) in excluded_refs:
                total_excluded += 1
                continue

            categories = get_profile_categories(medians)
            candidates.append({
                "rel_path": rel_path,
                "index": idx,
                "subfolder": Path(rel_path).parent.as_posix(),
                "medians": medians,
                "means": scores_data["means"],
                "judge_scores": scores_data["judge_scores"],
                "jev_argmax": scores_data["jev_argmax"],
                "jev_expected": scores_data["jev_expected"],
                "jev_boundary_closeness": scores_data["jev_boundary_closeness"],
                "is_primary": is_primary_eligible(medians),
                "profile_categories": categories,
            })

    # Sort candidates deterministically before any sampling
    candidates.sort(key=lambda c: (c["rel_path"], c["index"]))

    stats = {
        "total_discovered": total_discovered,
        "total_excluded": total_excluded,
        "dataset_distributions": {
            m: {str(s): dataset_distributions[m][s] for s in [0, 1, 2, 3]}
            for m in NUMERIC_METRICS
        },
        "dataset_primary_count": dataset_primary_count,
        "dataset_1_weak_count": dataset_1_weak_count,
        "dataset_2_weak_count": dataset_2_weak_count,
        "dataset_weak_counts": dict(dataset_weak_counts),
    }

    return candidates, stats


def vector_distance(v1: Sequence[int], v2: Sequence[int]) -> float:
    """Normalized Manhattan distance between two 7D score vectors (range [0, 3])."""
    return sum(abs(a - b) for a, b in zip(v1, v2)) / float(len(v1))


def select_diverse_primary_candidates(
    primary_candidates: List[Dict[str, Any]],
    target_count: int,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Select primary isolated-weakness candidates with diversity and balanced coverage:
    1. Rounds through eligible weak metrics in order of current coverage (prioritizing
       under-covered metrics like student_agency, and balancing frequent ones).
    2. For the target metric, greedily selects the candidate maximizing vector distance
       to already selected items, applying subfolder penalties and JEV boundary signals.
    """
    if len(primary_candidates) <= target_count:
        return list(primary_candidates)

    selected: List[Dict[str, Any]] = []
    selected_keys: Set[Tuple[str, int]] = set()
    subfolder_counts: Counter = Counter()
    weak_metric_counts: Counter = Counter()

    metric_to_cands: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in primary_candidates:
        for idx, m in enumerate(NUMERIC_METRICS):
            if c["medians"][idx] == 1:
                metric_to_cands[m].append(c)

    candidate_jitter = {
        (c["rel_path"], c["index"]): (hash((c["rel_path"], c["index"], seed)) % 1000) / 10000.0
        for c in primary_candidates
    }

    while len(selected) < target_count:
        # Eligible metrics that still have unselected candidates
        eligible_metrics = [
            m for m in metric_to_cands
            if any((c["rel_path"], c["index"]) not in selected_keys for c in metric_to_cands[m])
        ]
        if not eligible_metrics:
            break

        # Pick the metric with the lowest coverage count so far
        eligible_metrics.sort(key=lambda m: (weak_metric_counts[m], m))
        target_metric = eligible_metrics[0]

        best_candidate = None
        best_score = -float("inf")

        for c in metric_to_cands[target_metric]:
            key = (c["rel_path"], c["index"])
            if key in selected_keys:
                continue

            if selected:
                min_d = min(vector_distance(c["medians"], s["medians"]) for s in selected)
            else:
                min_d = 1.0

            sub_penalty = 0.15 * subfolder_counts[c["subfolder"]]
            jev_bonus = 0.05 * c["jev_boundary_closeness"]
            score = min_d - sub_penalty + jev_bonus + candidate_jitter[key]

            if score > best_score:
                best_score = score
                best_candidate = c

        if not best_candidate:
            break

        selected.append(best_candidate)
        selected_keys.add((best_candidate["rel_path"], best_candidate["index"]))
        subfolder_counts[best_candidate["subfolder"]] += 1
        for idx, m in enumerate(NUMERIC_METRICS):
            if best_candidate["medians"][idx] == 1:
                weak_metric_counts[m] += 1

    return selected


def select_diverse_secondary_candidates(
    candidates_by_category: Dict[str, List[Dict[str, Any]]],
    target_count: int,
    existing_selected: List[Dict[str, Any]],
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], Dict[str, int], List[str]]:
    """
    Select secondary profiles across uniformly_strong, mixed_strengths_weaknesses,
    and multiple_weaknesses, allocating slots based on candidate availability.
    Returns:
    - List of selected secondary candidate dicts
    - Dict of selected counts by secondary category
    - List of reallocation log messages
    """
    reallocation_notes: List[str] = []
    selected: List[Dict[str, Any]] = []
    selected_keys: Set[Tuple[str, int]] = set((c["rel_path"], c["index"]) for c in existing_selected)
    counts_by_cat: Dict[str, int] = defaultdict(int)

    subfolder_counts: Counter = Counter(c["subfolder"] for c in existing_selected)

    mult_pool = [c for c in candidates_by_category.get("multiple_weaknesses", [])
                 if (c["rel_path"], c["index"]) not in selected_keys]
    mixed_pool = [c for c in candidates_by_category.get("mixed_strengths_weaknesses", [])
                  if (c["rel_path"], c["index"]) not in selected_keys]
    strong_pool = [c for c in candidates_by_category.get("uniformly_strong", [])
                   if (c["rel_path"], c["index"]) not in selected_keys]

    # Target allocations:
    # 1 mixed candidate (if available)
    # ~half of remainder to multiple_weaknesses
    # remainder to uniformly_strong
    rem_target = target_count

    # 1. Mixed strengths and weaknesses (e.g. contains 0)
    for c in mixed_pool:
        if rem_target > 0:
            selected.append(c)
            selected_keys.add((c["rel_path"], c["index"]))
            counts_by_cat["mixed_strengths_weaknesses"] += 1
            subfolder_counts[c["subfolder"]] += 1
            rem_target -= 1

    if len(mixed_pool) == 0:
        reallocation_notes.append(
            "Mixed strengths and weaknesses category had 0 non-primary candidates; quota reallocated."
        )

    # 2. Multiple weaknesses
    mult_target = min(len(mult_pool), max(1, rem_target // 2))
    # Select diverse multiple weakness candidates using greedy max-min distance
    selected_mult: List[Dict[str, Any]] = []
    while len(selected_mult) < mult_target:
        best_cand = None
        best_score = -float("inf")
        for c in mult_pool:
            key = (c["rel_path"], c["index"])
            if key in selected_keys:
                continue
            all_curr = existing_selected + selected
            min_d = min(vector_distance(c["medians"], s["medians"]) for s in all_curr) if all_curr else 1.0
            sub_pen = 0.15 * subfolder_counts[c["subfolder"]]
            jev_b = 0.05 * c["jev_boundary_closeness"]
            jitter = (hash((c["rel_path"], c["index"], seed)) % 1000) / 10000.0
            score = min_d - sub_pen + jev_b + jitter
            if score > best_score:
                best_score = score
                best_cand = c
        if not best_cand:
            break
        selected.append(best_cand)
        selected_mult.append(best_cand)
        selected_keys.add((best_cand["rel_path"], best_cand["index"]))
        counts_by_cat["multiple_weaknesses"] += 1
        subfolder_counts[best_cand["subfolder"]] += 1
        rem_target -= 1

    # 3. Uniformly strong
    while rem_target > 0 and strong_pool:
        best_cand = None
        best_score = -float("inf")
        for c in strong_pool:
            key = (c["rel_path"], c["index"])
            if key in selected_keys:
                continue
            all_curr = existing_selected + selected
            min_d = min(vector_distance(c["medians"], s["medians"]) for s in all_curr) if all_curr else 1.0
            sub_pen = 0.15 * subfolder_counts[c["subfolder"]]
            jev_b = 0.05 * c["jev_boundary_closeness"]
            jitter = (hash((c["rel_path"], c["index"], seed)) % 1000) / 10000.0
            score = min_d - sub_pen + jev_b + jitter
            if score > best_score:
                best_score = score
                best_cand = c
        if not best_cand:
            break
        selected.append(best_cand)
        selected_keys.add((best_cand["rel_path"], best_cand["index"]))
        counts_by_cat["uniformly_strong"] += 1
        subfolder_counts[best_cand["subfolder"]] += 1
        rem_target -= 1

    # If still slots left, pull any remaining multiple_weakness candidates
    while rem_target > 0 and mult_pool:
        remaining_pool = [c for c in mult_pool if (c["rel_path"], c["index"]) not in selected_keys]
        if not remaining_pool:
            break
        cand = remaining_pool[0]
        selected.append(cand)
        selected_keys.add((cand["rel_path"], cand["index"]))
        counts_by_cat["multiple_weaknesses"] += 1
        rem_target -= 1

    return selected, dict(counts_by_cat), reallocation_notes


def load_selected_records(
    selected_candidates: Sequence[Dict[str, Any]],
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    id_prefix: str = "MP",
) -> List[Dict[str, Any]]:
    """
    Load raw conversation and judge records for all selected candidates,
    grouping by file for efficient two-pass reading.
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
            "sampling_strategy": "metric_profile",
            "profile_categories": c["profile_categories"],
            "source": {
                "relative_path": rel_path,
                "index": idx,
            },
            "conversation": conv,
            "llm_judge_output": llm_judge,
            "jev_output": jev,
        })

    return annotations


def generate_profile_analysis(
    dataset_stats: Dict[str, Any],
    all_candidates: List[Dict[str, Any]],
    selected_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate detailed profile analysis report for profile_analysis.json.
    """
    # Sample score means and medians
    sample_means: Dict[str, float] = {}
    sample_medians: Dict[str, int] = {}

    for idx, metric in enumerate(NUMERIC_METRICS):
        metric_medians = [c["medians"][idx] for c in selected_candidates]
        sample_means[metric] = round(sum(metric_medians) / float(len(metric_medians)), 3)
        sample_medians[metric] = compute_median_score(metric_medians)

    # Categories count in selected sample
    selected_by_category: Counter = Counter()
    for c in selected_candidates:
        for cat in c["profile_categories"]:
            selected_by_category[cat] += 1

    # Available secondary candidates
    available_secondary: Counter = Counter()
    for c in all_candidates:
        if not c["is_primary"]:
            for cat in c["profile_categories"]:
                available_secondary[cat] += 1

    # Profile diversity statistics: unique vectors, pairwise distance
    unique_vectors = set(tuple(c["medians"]) for c in selected_candidates)
    pairwise_dists = []
    for i in range(len(selected_candidates)):
        for j in range(i + 1, len(selected_candidates)):
            pairwise_dists.append(
                vector_distance(selected_candidates[i]["medians"], selected_candidates[j]["medians"])
            )

    mean_pairwise_d = round(sum(pairwise_dists) / float(len(pairwise_dists)), 3) if pairwise_dists else 0.0
    min_pairwise_d = round(min(pairwise_dists), 3) if pairwise_dists else 0.0

    # Inadequately covered categories (due to dataset limitations)
    uncovered_categories = []
    for m in NUMERIC_METRICS:
        cat_name = f"isolated_weakness_{m}"
        if dataset_stats["dataset_weak_counts"].get(m, 0) == 0:
            uncovered_categories.append({
                "category": cat_name,
                "reason": (
                    f"Zero conversations in the dataset have a median score of 1 for '{m}' "
                    "without containing a 0 score or failing the primary isolated-weakness rule."
                ),
            })

    return {
        "dataset_wide_distributions": dataset_stats["dataset_distributions"],
        "primary_eligibility": {
            "total_primary_eligible": dataset_stats["dataset_primary_count"],
            "one_weak_metric": dataset_stats["dataset_1_weak_count"],
            "two_weak_metrics": dataset_stats["dataset_2_weak_count"],
            "counts_by_weak_metric": dataset_stats["dataset_weak_counts"],
        },
        "available_secondary_profiles": dict(available_secondary),
        "selected_by_profile_category": dict(selected_by_category),
        "selected_sample_metric_summary": {
            "mean_scores": sample_means,
            "median_scores": sample_medians,
        },
        "diversity_statistics": {
            "unique_score_vectors": len(unique_vectors),
            "total_selected": len(selected_candidates),
            "mean_pairwise_distance": mean_pairwise_d,
            "min_pairwise_distance": min_pairwise_d,
        },
        "inadequately_covered_categories": uncovered_categories,
    }


def write_annotation_set(
    annotation_dir: Union[str, Path],
    annotations: List[Dict[str, Any]],
    selected_candidates: List[Dict[str, Any]],
    dataset_stats: Dict[str, Any],
    sample_size: int,
    seed: int,
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    random_sample_path: Union[str, Path],
    reallocation_notes: List[str],
    overwrite: bool = False,
) -> None:
    """
    Write annotations.json, manifest.json, selection_summary.json, and profile_analysis.json.
    Enforces directory protection.
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
        },
        "aggregate_score_method": (
            "Integer median of discrete scores from Judge 1, Judge 2, and Judge 3 per metric."
        ),
        "diversity_selection_method": (
            "Greedy max-min Manhattan distance on normalized 7D median score vectors, "
            "with subfolder balance penalty and JEV continuous boundary informativeness."
        ),
        "selected_conversations": [
            {
                "annotation_id": item["annotation_id"],
                "relative_path": item["source"]["relative_path"],
                "index": item["source"]["index"],
                "profile_categories": item["profile_categories"],
                "is_primary": any(c.startswith("isolated_weakness_") for c in item["profile_categories"]),
            }
            for item in annotations
        ],
    }
    with open(target_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # 3. selection_summary.json
    per_subfolder: Counter = Counter()
    per_file: Counter = Counter()
    primary_selected_count = sum(1 for c in selected_candidates if c["is_primary"])
    secondary_selected_count = len(selected_candidates) - primary_selected_count

    cat_counts: Counter = Counter()
    for c in selected_candidates:
        for cat in c["profile_categories"]:
            cat_counts[cat] += 1

    for c in selected_candidates:
        per_subfolder[c["subfolder"]] += 1
        per_file[c["rel_path"]] += 1

    summary = {
        "total_conversations_examined": dataset_stats["total_discovered"],
        "excluded_due_to_random_sample": dataset_stats["total_excluded"],
        "primary_category_candidates_available": dataset_stats["dataset_primary_count"],
        "secondary_category_candidates_available": (
            dataset_stats["total_discovered"]
            - dataset_stats["total_excluded"]
            - dataset_stats["dataset_primary_count"]
        ),
        "requested_sample_size": sample_size,
        "actual_sample_size": len(selected_candidates),
        "random_seed": seed,
        "selected_by_group": {
            "primary": primary_selected_count,
            "secondary": secondary_selected_count,
        },
        "selected_by_profile_category": dict(cat_counts),
        "selected_per_subfolder": dict(sorted(per_subfolder.items())),
        "selected_per_file": dict(sorted(per_file.items())),
        "quota_shortfalls_and_reallocations": reallocation_notes if reallocation_notes else "None",
    }
    with open(target_dir / "selection_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # 4. profile_analysis.json
    analysis = generate_profile_analysis(dataset_stats, selected_candidates, selected_candidates)
    with open(target_dir / "profile_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select 120 metric-profile conversations for human annotation."
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
        "--annotation-dir",
        type=Path,
        default=Path("annotation_set/metric_profile_sample"),
        help="Path to output directory (default: annotation_set/metric_profile_sample).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=120,
        help="Total sample size (default: 120).",
    )
    parser.add_argument(
        "--primary-fraction",
        type=float,
        default=0.70,
        help="Fraction of sample for primary isolated-weakness category (default: 0.70).",
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

    print(f"Loading random sample references to exclude from '{args.random_sample}'...")
    try:
        excluded_refs = load_random_sample_references(args.random_sample)
    except Exception as e:
        print(f"Error loading random sample: {e}", file=sys.stderr)
        return 1

    print(f"Loaded {len(excluded_refs)} random sample records to exclude.")

    print(f"Examining conversations across '{args.data_dir}', '{args.output_dir}', '{args.jev_dir}'...")
    try:
        candidates, stats = build_metric_profiles(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            excluded_refs=excluded_refs,
        )
    except Exception as e:
        print(f"Error building metric profiles: {e}", file=sys.stderr)
        return 1

    total_discovered = stats["total_discovered"]
    total_excluded = stats["total_excluded"]
    print(f"Total conversations examined: {total_discovered}")
    print(f"Excluded due to random-sample overlap: {total_excluded}")
    print(f"Candidate pool available for metric-profile selection: {len(candidates)}")

    # Partition candidates
    primary_candidates = [c for c in candidates if c["is_primary"]]
    secondary_candidates = [c for c in candidates if not c["is_primary"]]

    primary_target = int(round(args.sample_size * args.primary_fraction))
    secondary_target = args.sample_size - primary_target

    print(f"Primary category candidates available: {len(primary_candidates)} (target: {primary_target})")
    print(f"Secondary category candidates available: {len(secondary_candidates)} (target: {secondary_target})")

    reallocation_notes: List[str] = []

    # Select Primary candidates
    if len(primary_candidates) < primary_target:
        shortfall = primary_target - len(primary_candidates)
        reallocation_notes.append(
            f"Primary candidate pool had {len(primary_candidates)} candidates; "
            f"shortfall of {shortfall} slots reallocated to secondary categories."
        )
        selected_primary = list(primary_candidates)
        secondary_target += shortfall
    else:
        selected_primary = select_diverse_primary_candidates(
            primary_candidates=primary_candidates,
            target_count=primary_target,
            seed=args.seed,
        )

    # Categorize secondary candidates into distinct pools for quota allocation
    sec_by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in secondary_candidates:
        meds = c["medians"]
        c_low = meds.count(0) + meds.count(1)
        if min(meds) >= 2:
            sec_by_cat["uniformly_strong"].append(c)
        elif c_low >= 3:
            sec_by_cat["multiple_weaknesses"].append(c)
        elif any(x in (0, 1) for x in meds) and any(x in (2, 3) for x in meds):
            sec_by_cat["mixed_strengths_weaknesses"].append(c)
        else:
            sec_by_cat["other_diverse_profile"].append(c)

    selected_secondary, sec_counts, sec_notes = select_diverse_secondary_candidates(
        candidates_by_category=sec_by_cat,
        target_count=secondary_target,
        existing_selected=selected_primary,
        seed=args.seed,
    )
    reallocation_notes.extend(sec_notes)

    selected_all = selected_primary + selected_secondary
    print(f"Selected total: {len(selected_all)} (Primary: {len(selected_primary)}, Secondary: {len(selected_secondary)})")

    if len(selected_all) < args.sample_size:
        print(
            f"Warning: could only select {len(selected_all)} of requested {args.sample_size} conversations.",
            file=sys.stderr,
        )

    print("Loading full conversation and judge records...")
    try:
        annotations = load_selected_records(
            selected_candidates=selected_all,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            id_prefix="MP",
        )
    except Exception as e:
        print(f"Error loading records: {e}", file=sys.stderr)
        return 1

    print(f"Writing metric-profile annotation set to '{args.annotation_dir}'...")
    try:
        write_annotation_set(
            annotation_dir=args.annotation_dir,
            annotations=annotations,
            selected_candidates=selected_all,
            dataset_stats=stats,
            sample_size=args.sample_size,
            seed=args.seed,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            random_sample_path=args.random_sample,
            reallocation_notes=reallocation_notes,
            overwrite=args.overwrite,
        )
    except FileExistsError as e:
        print(f"Output error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error writing annotation set: {e}", file=sys.stderr)
        return 1

    # Final summary report (Section 12)
    weak_counts: Counter = Counter()
    for c in selected_primary:
        for idx, m in enumerate(NUMERIC_METRICS):
            if c["medians"][idx] == 1:
                weak_counts[m] += 1

    sample_means: Dict[str, float] = {}
    for idx, m in enumerate(NUMERIC_METRICS):
        sample_means[m] = round(
            sum(c["medians"][idx] for c in selected_all) / float(len(selected_all)), 2
        )

    print("\n=======================================================")
    print("        METRIC-PROFILE SELECTION FINAL REPORT          ")
    print("=======================================================")
    print(f"1. Total conversations examined:           {total_discovered}")
    print(f"2. Excluded due to random-sample overlap:  {total_excluded}")
    print(f"3. Primary candidates available:           {len(primary_candidates)}")
    print(f"   Secondary candidates available:         {len(secondary_candidates)}")
    print(f"4. Selected from Primary (70% target):     {len(selected_primary)}")
    print(f"   Selected from Secondary (30% target):   {len(selected_secondary)}")
    print(f"   Total selected:                         {len(selected_all)}")
    print("5. Coverage counts for 7 weakness metrics (Primary Rule):")
    for m in NUMERIC_METRICS:
        covered_status = f"{weak_counts[m]} selected" if weak_counts[m] > 0 else "0 (no dataset candidates)"
        print(f"   - {m:20s}: {covered_status}")
    print("6. Mean score of each metric in selected sample:")
    for m in NUMERIC_METRICS:
        print(f"   - {m:20s}: {sample_means[m]:.2f}")
    target_achieved = (len(selected_all) == args.sample_size)
    print(f"7. Target ({args.sample_size}) achieved:                 {'YES' if target_achieved else 'NO'}")
    print(f"8. Shortfalls / Reallocations:             {reallocation_notes if reallocation_notes else 'None'}")
    print("9. Generated files:")
    print(f"   - {args.annotation_dir / 'annotations.json'}")
    print(f"   - {args.annotation_dir / 'manifest.json'}")
    print(f"   - {args.annotation_dir / 'selection_summary.json'}")
    print(f"   - {args.annotation_dir / 'profile_analysis.json'}")
    print("=======================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
