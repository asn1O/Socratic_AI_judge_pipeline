"""Tests for scripts/sample_judge_disagreement.py."""

import json
from pathlib import Path
import pytest

from scripts.sample_judge_disagreement import (
    NUMERIC_METRICS,
    load_previous_sample_references,
    calculate_disagreement_features,
    assign_disagreement_categories,
    build_disagreement_candidates,
    select_diverse_disagreement_cases,
    load_selected_records,
    write_annotation_set,
    main,
)


def test_feature_calculations_unanimous():
    output_item = {
        "judge_1": {"evaluation": {m: 3 for m in NUMERIC_METRICS}},
        "judge_2": {"evaluation": {m: 3 for m in NUMERIC_METRICS}},
        "judge_3": {"evaluation": {m: 3 for m in NUMERIC_METRICS}},
    }
    jev_item = {
        "evaluation": {
            "answers": {
                m: {"score": 3.0, "probabilities": {"3": 1.0}}
                for m in NUMERIC_METRICS
            }
        }
    }

    feats = calculate_disagreement_features(output_item, jev_item)

    for m in NUMERIC_METRICS:
        assert feats["metric_ranges"][m] == 0
        assert feats["metric_stdevs"][m] == 0.0
        assert feats["metric_unanimous"][m] is True
        assert feats["metric_range_ge_2"][m] is False
        assert feats["metric_low_vs_high"][m] is False
        assert feats["metric_means"][m] == 3.0
        assert feats["metric_medians"][m] == 3

    assert feats["mean_pairwise_score_difference"] == 0.0
    assert feats["num_disagreed_metrics"] == 0
    assert feats["num_range_ge_2_metrics"] == 0
    assert feats["max_individual_metric_range"] == 0
    assert feats["pairwise_profile_distances"]["judge_1_vs_judge_2"] == 0


def test_feature_calculations_severe_disagreement():
    output_item = {
        "judge_1": {"evaluation": {m: 3 for m in NUMERIC_METRICS}},
        "judge_2": {"evaluation": {m: 1 for m in NUMERIC_METRICS}},
        "judge_3": {"evaluation": {m: 3 for m in NUMERIC_METRICS}},
    }
    # Modify one metric to have range 3 (0 vs 3)
    output_item["judge_2"]["evaluation"]["scaffolding"] = 0

    jev_item = {
        "evaluation": {
            "answers": {
                m: {"score": 2.5, "probabilities": {"2": 0.5, "3": 0.5}}
                for m in NUMERIC_METRICS
            }
        }
    }

    feats = calculate_disagreement_features(output_item, jev_item)

    # Scaffolding: J1=3, J2=0, J3=3 -> range=3, diff_ge_2=True, low_vs_high=True
    assert feats["metric_ranges"]["scaffolding"] == 3
    assert feats["metric_range_ge_2"]["scaffolding"] is True
    assert feats["metric_low_vs_high"]["scaffolding"] is True

    # Other metrics: J1=3, J2=1, J3=3 -> range=2, diff_ge_2=True, low_vs_high=True
    assert feats["metric_ranges"]["socratic_guidance"] == 2
    assert feats["metric_range_ge_2"]["socratic_guidance"] is True

    # Total pairwise differences:
    # scaffolding: |3-0| + |3-3| + |0-3| = 3 + 0 + 3 = 6
    # 6 other metrics: |3-1| + |3-3| + |1-3| = 2 + 0 + 2 = 4 each -> 24
    # total = 6 + 24 = 30 across 21 comparisons -> 30/21 = 1.4286
    assert abs(feats["mean_pairwise_score_difference"] - (30.0 / 21.0)) < 0.001

    assert feats["num_disagreed_metrics"] == 7
    assert feats["num_range_ge_2_metrics"] == 7
    assert feats["max_individual_metric_range"] == 3

    # Outlier: Judge 2 is the outlier on all 7 metrics
    assert feats["judge_outlier_counts"][2] == 7

    categories = assign_disagreement_categories(feats)
    assert "strong_metric_disagreement" in categories
    assert "extreme_metric_disagreement" in categories
    assert "low_vs_high_disagreement" in categories
    assert "multi_metric_disagreement" in categories
    assert "judge_2_outlier" in categories
    assert "severe_disagreement_scaffolding" in categories


def test_missing_sample_references_error(tmp_path: Path):
    non_existent = tmp_path / "non_existent.json"
    real_file = tmp_path / "real.json"
    real_file.write_text("[]", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Random sample file not found"):
        load_previous_sample_references(non_existent, real_file)

    with pytest.raises(FileNotFoundError, match="Metric profile sample file not found"):
        load_previous_sample_references(real_file, non_existent)


@pytest.fixture
def mock_disagreement_dataset(tmp_path: Path):
    """
    Creates a mock 3-tree dataset with 50 conversations and mock previous annotation sets.
    """
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    jev_dir = tmp_path / "jev_output"

    models = ["model_X", "model_Y"]
    files = ["set_1.json", "set_2.json"]

    all_refs = []
    record_idx = 0

    for m in models:
        for f in files:
            d_p = data_dir / m / f
            o_p = output_dir / m / f
            j_p = jev_dir / m / f

            d_p.parent.mkdir(parents=True, exist_ok=True)
            o_p.parent.mkdir(parents=True, exist_ok=True)
            j_p.parent.mkdir(parents=True, exist_ok=True)

            d_list = []
            o_list = []
            j_list = []

            for i in range(12):
                rel_path = f"{m}/{f}"
                all_refs.append((rel_path, i))

                # Create varying levels of disagreement
                j1_scores = {metric: 3 for metric in NUMERIC_METRICS}
                j2_scores = {metric: 3 for metric in NUMERIC_METRICS}
                j3_scores = {metric: 3 for metric in NUMERIC_METRICS}

                if record_idx % 5 == 0:
                    # Strong disagreement on scaffolding (range 2)
                    j2_scores["scaffolding"] = 1
                elif record_idx % 5 == 1:
                    # Strong disagreement on diagnosis (range 2)
                    j1_scores["diagnosis"] = 1
                elif record_idx % 5 == 2:
                    # Multi-metric minor disagreement (range 1 on 4 metrics)
                    j2_scores["socratic_guidance"] = 2
                    j3_scores["scaffolding"] = 2
                    j1_scores["student_agency"] = 2
                    j2_scores["progression"] = 2
                elif record_idx % 5 == 3:
                    # Strong disagreement on progression (range 2)
                    j3_scores["progression"] = 1
                else:
                    # Unanimous agreement
                    pass

                jev_answers = {
                    metric: {
                        "type": "score",
                        "score": 2.5,
                        "probabilities": {"2": 0.5, "3": 0.5},
                    }
                    for metric in NUMERIC_METRICS
                }

                d_list.append({"id": f"conv_{record_idx}", "text": f"Text {record_idx}"})
                o_list.append({
                    "source_file": rel_path,
                    "conversation_index": i,
                    "judge_1": {"evaluation": j1_scores},
                    "judge_2": {"evaluation": j2_scores},
                    "judge_3": {"evaluation": j3_scores},
                })
                j_list.append({
                    "source_file": rel_path,
                    "conversation_index": i,
                    "evaluation": {"answers": jev_answers},
                })

                record_idx += 1

            d_p.write_text(json.dumps(d_list), encoding="utf-8")
            o_p.write_text(json.dumps(o_list), encoding="utf-8")
            j_p.write_text(json.dumps(j_list), encoding="utf-8")

    # Mock previous samples
    rand_sample_path = tmp_path / "mock_random.json"
    mp_sample_path = tmp_path / "mock_mp.json"

    # Exclude 3 records in random, 2 in metric profile
    rand_sample_path.write_text(
        json.dumps([
            {"annotation_id": "RND-0001", "source": {"relative_path": all_refs[0][0], "index": all_refs[0][1]}},
            {"annotation_id": "RND-0002", "source": {"relative_path": all_refs[1][0], "index": all_refs[1][1]}},
            {"annotation_id": "RND-0003", "source": {"relative_path": all_refs[2][0], "index": all_refs[2][1]}},
        ]),
        encoding="utf-8",
    )
    mp_sample_path.write_text(
        json.dumps([
            {"annotation_id": "MP-0001", "source": {"relative_path": all_refs[3][0], "index": all_refs[3][1]}},
            {"annotation_id": "MP-0002", "source": {"relative_path": all_refs[4][0], "index": all_refs[4][1]}},
        ]),
        encoding="utf-8",
    )

    return {
        "root": tmp_path,
        "data_dir": data_dir,
        "output_dir": output_dir,
        "jev_dir": jev_dir,
        "rand_path": rand_sample_path,
        "mp_path": mp_sample_path,
        "total_records": record_idx,
        "excluded_refs": set(all_refs[:5]),
    }


def test_build_candidates_and_exclusion(mock_disagreement_dataset):
    excluded = load_previous_sample_references(
        mock_disagreement_dataset["rand_path"],
        mock_disagreement_dataset["mp_path"],
    )
    assert len(excluded) == 5

    candidates, stats = build_disagreement_candidates(
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    assert stats["total_discovered"] == mock_disagreement_dataset["total_records"]
    assert stats["total_excluded"] == 5
    assert len(candidates) == mock_disagreement_dataset["total_records"] - 5

    candidate_keys = set((c["rel_path"], c["index"]) for c in candidates)
    for ref in excluded:
        assert ref not in candidate_keys


def test_selection_uniqueness_and_reproducibility(mock_disagreement_dataset):
    excluded = load_previous_sample_references(
        mock_disagreement_dataset["rand_path"],
        mock_disagreement_dataset["mp_path"],
    )
    candidates, _ = build_disagreement_candidates(
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    selected_1, _ = select_diverse_disagreement_cases(candidates, target_count=10, seed=42)
    selected_2, _ = select_diverse_disagreement_cases(candidates, target_count=10, seed=42)
    selected_diff, _ = select_diverse_disagreement_cases(candidates, target_count=10, seed=1234)

    assert len(selected_1) == 10
    # Uniqueness
    assert len(set((c["rel_path"], c["index"]) for c in selected_1)) == 10
    # Reproducibility
    assert [(c["rel_path"], c["index"]) for c in selected_1] == [(c["rel_path"], c["index"]) for c in selected_2]


def test_positional_alignment_and_annotation_fields(mock_disagreement_dataset):
    excluded = load_previous_sample_references(
        mock_disagreement_dataset["rand_path"],
        mock_disagreement_dataset["mp_path"],
    )
    candidates, _ = build_disagreement_candidates(
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    selected = candidates[:5]
    annotations = load_selected_records(
        selected_candidates=selected,
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
        id_prefix="JD",
    )

    assert len(annotations) == 5
    for idx, item in enumerate(annotations):
        assert item["annotation_id"] == f"JD-{idx + 1:04d}"
        assert item["sampling_strategy"] == "judge_disagreement"
        assert "disagreement_categories" in item
        assert "disagreement_summary" in item
        rel_path = item["source"]["relative_path"]
        record_idx = item["source"]["index"]

        with open(mock_disagreement_dataset["data_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_d = json.load(f)[record_idx]
        with open(mock_disagreement_dataset["output_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_o = json.load(f)[record_idx]
        with open(mock_disagreement_dataset["jev_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_j = json.load(f)[record_idx]

        assert item["conversation"] == raw_d
        assert item["llm_judge_output"] == raw_o
        assert item["jev_output"] == raw_j


def test_output_directory_protection_and_artifacts(mock_disagreement_dataset):
    excluded = load_previous_sample_references(
        mock_disagreement_dataset["rand_path"],
        mock_disagreement_dataset["mp_path"],
    )
    candidates, stats = build_disagreement_candidates(
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    selected = candidates[:6]
    annotations = load_selected_records(
        selected_candidates=selected,
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
    )

    out_dir = mock_disagreement_dataset["root"] / "jd_output"

    # First write succeeds
    write_annotation_set(
        annotation_dir=out_dir,
        annotations=annotations,
        selected_candidates=selected,
        all_candidates=candidates,
        dataset_stats=stats,
        sample_size=6,
        seed=42,
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
        random_sample_path=mock_disagreement_dataset["rand_path"],
        metric_profile_path=mock_disagreement_dataset["mp_path"],
        reallocation_notes=[],
        overwrite=False,
    )

    # Second write fails
    with pytest.raises(FileExistsError):
        write_annotation_set(
            annotation_dir=out_dir,
            annotations=annotations,
            selected_candidates=selected,
            all_candidates=candidates,
            dataset_stats=stats,
            sample_size=6,
            seed=42,
            data_dir=mock_disagreement_dataset["data_dir"],
            output_dir=mock_disagreement_dataset["output_dir"],
            jev_dir=mock_disagreement_dataset["jev_dir"],
            random_sample_path=mock_disagreement_dataset["rand_path"],
            metric_profile_path=mock_disagreement_dataset["mp_path"],
            reallocation_notes=[],
            overwrite=False,
        )

    # Third write with overwrite succeeds
    write_annotation_set(
        annotation_dir=out_dir,
        annotations=annotations,
        selected_candidates=selected,
        all_candidates=candidates,
        dataset_stats=stats,
        sample_size=6,
        seed=42,
        data_dir=mock_disagreement_dataset["data_dir"],
        output_dir=mock_disagreement_dataset["output_dir"],
        jev_dir=mock_disagreement_dataset["jev_dir"],
        random_sample_path=mock_disagreement_dataset["rand_path"],
        metric_profile_path=mock_disagreement_dataset["mp_path"],
        reallocation_notes=[],
        overwrite=True,
    )

    assert (out_dir / "annotations.json").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "selection_summary.json").exists()
    assert (out_dir / "disagreement_analysis.json").exists()

    with open(out_dir / "manifest.json") as f:
        m = json.load(f)
        assert m["requested_sample_size"] == 6
        assert m["actual_sample_size"] == 6

    with open(out_dir / "disagreement_analysis.json") as f:
        a = json.load(f)
        assert "dataset_wide_disagreement_distribution" in a
        assert "selected_sample_disagreement_statistics" in a
        assert "candidate_pool_vs_selected_comparison" in a


def test_cli_end_to_end(mock_disagreement_dataset):
    out_dir = mock_disagreement_dataset["root"] / "cli_jd_test"
    cmd = [
        "--data-dir", str(mock_disagreement_dataset["data_dir"]),
        "--output-dir", str(mock_disagreement_dataset["output_dir"]),
        "--jev-dir", str(mock_disagreement_dataset["jev_dir"]),
        "--random-sample", str(mock_disagreement_dataset["rand_path"]),
        "--metric-profile-sample", str(mock_disagreement_dataset["mp_path"]),
        "--annotation-dir", str(out_dir),
        "--sample-size", "8",
        "--seed", "42",
    ]

    exit_code = main(cmd)
    assert exit_code == 0
    assert (out_dir / "annotations.json").exists()

    # Re-running without overwrite fails
    assert main(cmd) == 1

    # Re-running with overwrite succeeds
    assert main(cmd + ["--overwrite"]) == 0
