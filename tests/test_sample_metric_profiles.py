"""Tests for scripts/sample_metric_profiles.py."""

import json
from pathlib import Path
import pytest

from scripts.sample_metric_profiles import (
    NUMERIC_METRICS,
    compute_median_score,
    is_primary_eligible,
    get_profile_categories,
    load_random_sample_references,
    extract_judge_scores,
    build_metric_profiles,
    select_diverse_primary_candidates,
    select_diverse_secondary_candidates,
    load_selected_records,
    write_annotation_set,
    main,
)


def test_median_score_calculation():
    assert compute_median_score([1, 2, 3]) == 2
    assert compute_median_score([0, 1, 1]) == 1
    assert compute_median_score([3, 3, 2]) == 3
    assert compute_median_score([0, 0, 0]) == 0
    assert compute_median_score([2, 1, 3]) == 2
    assert compute_median_score([0, 3, 1]) == 1


def test_primary_rule_eligibility():
    # Exactly one or two median metric scores == 1; no 0; others 2 or 3
    assert is_primary_eligible([3, 3, 2, 1, 3, 2, 3]) is True   # One 1
    assert is_primary_eligible([2, 1, 3, 2, 1, 3, 2]) is True   # Two 1s
    assert is_primary_eligible([3, 1, 1, 1, 2, 3, 2]) is False  # Three 1s
    assert is_primary_eligible([3, 3, 2, 2, 3, 2, 3]) is False  # No 1
    assert is_primary_eligible([3, 3, 2, 0, 3, 2, 3]) is False  # Contains 0
    assert is_primary_eligible([1, 0, 3, 3, 3, 3, 3]) is False  # Has 0 and 1


def test_profile_categories_tagging():
    # Primary isolated weakness
    cats_1 = get_profile_categories([3, 3, 2, 1, 3, 2, 3])  # diagnosis is index 3
    assert cats_1 == ["isolated_weakness_diagnosis"]

    cats_2 = get_profile_categories([1, 1, 3, 3, 3, 3, 3])  # socratic_guidance and scaffolding
    assert "isolated_weakness_socratic_guidance" in cats_2
    assert "isolated_weakness_scaffolding" in cats_2

    # Uniformly strong
    cats_strong = get_profile_categories([3, 3, 2, 2, 3, 3, 3])
    assert "uniformly_strong" in cats_strong

    # Multiple weaknesses
    cats_mult = get_profile_categories([1, 1, 1, 2, 3, 3, 3])
    assert "multiple_weaknesses" in cats_mult
    assert "mixed_strengths_weaknesses" in cats_mult

    # Mixed with 0
    cats_mixed = get_profile_categories([2, 0, 3, 2, 2, 3, 3])
    assert "mixed_strengths_weaknesses" in cats_mixed


def test_missing_random_sample_error(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match="Random sample file not found"):
        load_random_sample_references(non_existent)


@pytest.fixture
def mock_metric_dataset(tmp_path: Path):
    """
    Creates a mock dataset with 3 parallel directory trees and known score patterns.
    """
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    jev_dir = tmp_path / "jev_output"

    models = ["model_A", "model_B"]
    files_per_model = ["batch_01.json", "batch_02.json"]

    # We will create 2 * 2 * 10 = 40 records
    all_refs = []
    record_idx = 0

    for m in models:
        for f in files_per_model:
            d_p = data_dir / m / f
            o_p = output_dir / m / f
            j_p = jev_dir / m / f

            d_p.parent.mkdir(parents=True, exist_ok=True)
            o_p.parent.mkdir(parents=True, exist_ok=True)
            j_p.parent.mkdir(parents=True, exist_ok=True)

            d_list = []
            o_list = []
            j_list = []

            for i in range(10):
                rel_path = f"{m}/{f}"
                all_refs.append((rel_path, i))

                # Assign distinct score patterns to test various categories
                if record_idx % 4 == 0:
                    # Primary candidate: weak socratic_guidance (med=1)
                    s_tuple = [1, 1, 2]
                    med_rest = 3
                is_sa_weak = (record_idx in (5, 9))
                if record_idx % 4 == 0:
                    # Primary candidate: weak socratic_guidance (med=1)
                    s_tuple = [1, 1, 2]
                    med_rest = 3
                elif is_sa_weak:
                    # Primary candidate: rare weak student_agency (med=1)
                    s_tuple = [3, 3, 3]
                    med_rest = 3
                elif record_idx % 4 == 2:
                    # Multiple weaknesses: 3 metrics scored 1
                    s_tuple = [1, 1, 1]
                    med_rest = 1
                else:
                    # Uniformly strong: all 3s
                    s_tuple = [3, 3, 3]
                    med_rest = 3

                # Judge outputs
                j1_eval = {metric: med_rest for metric in NUMERIC_METRICS}
                j2_eval = {metric: med_rest for metric in NUMERIC_METRICS}
                j3_eval = {metric: med_rest for metric in NUMERIC_METRICS}

                if record_idx % 4 == 0:
                    j1_eval["socratic_guidance"] = s_tuple[0]
                    j2_eval["socratic_guidance"] = s_tuple[1]
                    j3_eval["socratic_guidance"] = s_tuple[2]
                elif is_sa_weak:
                    j1_eval["student_agency"] = 1
                    j2_eval["student_agency"] = 1
                    j3_eval["student_agency"] = 2
                elif record_idx % 4 == 2:
                    j1_eval["socratic_guidance"] = 1
                    j2_eval["socratic_guidance"] = 1
                    j3_eval["socratic_guidance"] = 1
                    j1_eval["scaffolding"] = 1
                    j2_eval["scaffolding"] = 1
                    j3_eval["scaffolding"] = 1
                    j1_eval["student_agency"] = 1
                    j2_eval["student_agency"] = 1
                    j3_eval["student_agency"] = 1

                # JEV outputs
                jev_answers = {}
                for metric in NUMERIC_METRICS:
                    jev_answers[metric] = {
                        "type": "score",
                        "score": 2.2,
                        "probabilities": {"0": 0.05, "1": 0.15, "2": 0.50, "3": 0.30},
                    }

                d_list.append({
                    "id": f"conv_{record_idx}",
                    "text": f"Conversation text {record_idx}",
                })
                o_list.append({
                    "source_file": rel_path,
                    "conversation_index": i,
                    "judge_1": {"evaluation": j1_eval},
                    "judge_2": {"evaluation": j2_eval},
                    "judge_3": {"evaluation": j3_eval},
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

    # Create a mock random sample file excluding 4 records
    rand_sample_path = tmp_path / "mock_random_annotations.json"
    rand_records = [
        {"annotation_id": "RND-0001", "source": {"relative_path": all_refs[0][0], "index": all_refs[0][1]}},
        {"annotation_id": "RND-0002", "source": {"relative_path": all_refs[1][0], "index": all_refs[1][1]}},
    ]
    rand_sample_path.write_text(json.dumps(rand_records), encoding="utf-8")

    return {
        "root": tmp_path,
        "data_dir": data_dir,
        "output_dir": output_dir,
        "jev_dir": jev_dir,
        "rand_sample_path": rand_sample_path,
        "excluded_refs": {all_refs[0], all_refs[1]},
        "total_records": record_idx,
    }


def test_build_profiles_and_exclusion(mock_metric_dataset):
    excluded = load_random_sample_references(mock_metric_dataset["rand_sample_path"])
    assert len(excluded) == 2

    candidates, stats = build_metric_profiles(
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    assert stats["total_discovered"] == 40
    assert stats["total_excluded"] == 2
    assert len(candidates) == 38

    # Ensure none of the excluded references are in candidates
    candidate_refs = set((c["rel_path"], c["index"]) for c in candidates)
    for ref in excluded:
        assert ref not in candidate_refs


def test_uniqueness_and_reproducibility(mock_metric_dataset):
    excluded = load_random_sample_references(mock_metric_dataset["rand_sample_path"])
    candidates, _ = build_metric_profiles(
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    primary = [c for c in candidates if c["is_primary"]]
    selected_1 = select_diverse_primary_candidates(primary, target_count=8, seed=42)
    selected_2 = select_diverse_primary_candidates(primary, target_count=8, seed=42)
    selected_diff = select_diverse_primary_candidates(primary, target_count=8, seed=999)

    # Reproducibility
    assert [(c["rel_path"], c["index"]) for c in selected_1] == [(c["rel_path"], c["index"]) for c in selected_2]
    # Uniqueness
    assert len(set((c["rel_path"], c["index"]) for c in selected_1)) == 8


def test_coverage_maximization(mock_metric_dataset):
    excluded = load_random_sample_references(mock_metric_dataset["rand_sample_path"])
    candidates, _ = build_metric_profiles(
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    primary = [c for c in candidates if c["is_primary"]]
    # In mock data, student_agency is weak in some candidates
    sa_candidates = [c for c in primary if c["medians"][4] == 1]
    assert len(sa_candidates) > 0

    selected = select_diverse_primary_candidates(primary, target_count=10, seed=42)
    # student_agency candidates should all be prioritized and selected
    for sa in sa_candidates:
        assert any(s["rel_path"] == sa["rel_path"] and s["index"] == sa["index"] for s in selected)


def test_positional_alignment(mock_metric_dataset):
    excluded = load_random_sample_references(mock_metric_dataset["rand_sample_path"])
    candidates, _ = build_metric_profiles(
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    selected = candidates[:6]
    annotations = load_selected_records(
        selected_candidates=selected,
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
    )

    assert len(annotations) == 6
    for idx, item in enumerate(annotations):
        assert item["annotation_id"] == f"MP-{idx + 1:04d}"
        rel_path = item["source"]["relative_path"]
        record_idx = item["source"]["index"]

        with open(mock_metric_dataset["data_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_d = json.load(f)[record_idx]
        with open(mock_metric_dataset["output_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_o = json.load(f)[record_idx]
        with open(mock_metric_dataset["jev_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_j = json.load(f)[record_idx]

        assert item["conversation"] == raw_d
        assert item["llm_judge_output"] == raw_o
        assert item["jev_output"] == raw_j


def test_output_directory_protection_and_schemas(mock_metric_dataset):
    excluded = load_random_sample_references(mock_metric_dataset["rand_sample_path"])
    candidates, stats = build_metric_profiles(
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
        excluded_refs=excluded,
    )

    selected = candidates[:10]
    annotations = load_selected_records(
        selected_candidates=selected,
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
    )

    out_dir = mock_metric_dataset["root"] / "metric_out"

    # First write must succeed
    write_annotation_set(
        annotation_dir=out_dir,
        annotations=annotations,
        selected_candidates=selected,
        dataset_stats=stats,
        sample_size=10,
        seed=42,
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
        random_sample_path=mock_metric_dataset["rand_sample_path"],
        reallocation_notes=[],
        overwrite=False,
    )

    # Second write without overwrite must fail
    with pytest.raises(FileExistsError):
        write_annotation_set(
            annotation_dir=out_dir,
            annotations=annotations,
            selected_candidates=selected,
            dataset_stats=stats,
            sample_size=10,
            seed=42,
            data_dir=mock_metric_dataset["data_dir"],
            output_dir=mock_metric_dataset["output_dir"],
            jev_dir=mock_metric_dataset["jev_dir"],
            random_sample_path=mock_metric_dataset["rand_sample_path"],
            reallocation_notes=[],
            overwrite=False,
        )

    # Third write with overwrite=True must succeed
    write_annotation_set(
        annotation_dir=out_dir,
        annotations=annotations,
        selected_candidates=selected,
        dataset_stats=stats,
        sample_size=10,
        seed=42,
        data_dir=mock_metric_dataset["data_dir"],
        output_dir=mock_metric_dataset["output_dir"],
        jev_dir=mock_metric_dataset["jev_dir"],
        random_sample_path=mock_metric_dataset["rand_sample_path"],
        reallocation_notes=[],
        overwrite=True,
    )

    # Verify all 4 files exist and have proper fields
    assert (out_dir / "annotations.json").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "selection_summary.json").exists()
    assert (out_dir / "profile_analysis.json").exists()

    with open(out_dir / "manifest.json") as f:
        manifest = json.load(f)
        assert manifest["requested_sample_size"] == 10
        assert manifest["actual_sample_size"] == 10
        assert "aggregate_score_method" in manifest
        assert "diversity_selection_method" in manifest

    with open(out_dir / "profile_analysis.json") as f:
        analysis = json.load(f)
        assert "dataset_wide_distributions" in analysis
        assert "diversity_statistics" in analysis
        assert "inadequately_covered_categories" in analysis


def test_cli_end_to_end(mock_metric_dataset):
    out_dir = mock_metric_dataset["root"] / "cli_metric_out"
    cmd = [
        "--data-dir", str(mock_metric_dataset["data_dir"]),
        "--output-dir", str(mock_metric_dataset["output_dir"]),
        "--jev-dir", str(mock_metric_dataset["jev_dir"]),
        "--random-sample", str(mock_metric_dataset["rand_sample_path"]),
        "--annotation-dir", str(out_dir),
        "--sample-size", "12",
        "--primary-fraction", "0.70",
        "--seed", "42",
    ]
    exit_code = main(cmd)
    assert exit_code == 0
    assert (out_dir / "annotations.json").exists()

    # Re-running without overwrite returns 1
    assert main(cmd) == 1

    # Re-running with overwrite returns 0
    assert main(cmd + ["--overwrite"]) == 0
