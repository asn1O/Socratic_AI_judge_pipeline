"""Tests for scripts/sample_random.py."""

import json
from pathlib import Path
import pytest

from scripts.sample_random import (
    discover_records,
    sample_random_records,
    load_selected_records,
    write_annotation_set,
    main,
)


@pytest.fixture
def mock_dataset(tmp_path: Path):
    """
    Creates a small 3-tree mock dataset:
    data/, output/, and jev_output/ with 2 subfolders and multiple files.
    """
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    jev_dir = tmp_path / "jev_output"

    subfolders = ["folder_A", "folder_B"]
    files_per_subfolder = ["file_1.json", "file_2.json"]

    record_count = 0
    for sub in subfolders:
        for f in files_per_subfolder:
            d_p = data_dir / sub / f
            o_p = output_dir / sub / f
            j_p = jev_dir / sub / f

            d_p.parent.mkdir(parents=True, exist_ok=True)
            o_p.parent.mkdir(parents=True, exist_ok=True)
            j_p.parent.mkdir(parents=True, exist_ok=True)

            d_list = []
            o_list = []
            j_list = []

            # 5 records per file
            for i in range(5):
                d_list.append({
                    "id": f"{sub}_{f}_{i}",
                    "conversation": f"Conversation text {record_count}",
                })
                o_list.append({
                    "id": f"{sub}_{f}_{i}",
                    "llm_eval": f"LLM judge score {record_count}",
                })
                j_list.append({
                    "id": f"{sub}_{f}_{i}",
                    "jev_eval": f"JEV judge score {record_count}",
                })
                record_count += 1

            d_p.write_text(json.dumps(d_list), encoding="utf-8")
            o_p.write_text(json.dumps(o_list), encoding="utf-8")
            j_p.write_text(json.dumps(j_list), encoding="utf-8")

    return {
        "root": tmp_path,
        "data_dir": data_dir,
        "output_dir": output_dir,
        "jev_dir": jev_dir,
        "total_records": record_count,  # 2 * 2 * 5 = 20
    }


def test_discover_records(mock_dataset):
    records = discover_records(mock_dataset["data_dir"])
    assert len(records) == mock_dataset["total_records"]
    # Verify deterministic sorting: sorted by relative_path, then index
    for i in range(len(records) - 1):
        curr_path, curr_idx = records[i]
        next_path, next_idx = records[i + 1]
        assert (curr_path, curr_idx) < (next_path, next_idx)


def test_reproducibility():
    population = [("file_a.json", i) for i in range(50)]
    sample_1 = sample_random_records(population, sample_size=10, seed=42)
    sample_2 = sample_random_records(population, sample_size=10, seed=42)
    sample_diff = sample_random_records(population, sample_size=10, seed=123)

    assert sample_1 == sample_2
    assert sample_1 != sample_diff


def test_sampling_without_replacement():
    population = [("file_a.json", i) for i in range(100)]
    sample = sample_random_records(population, sample_size=40, seed=42)

    assert len(sample) == 40
    # Every sampled tuple should be unique
    assert len(set(sample)) == 40


def test_positional_alignment(mock_dataset):
    all_records = discover_records(mock_dataset["data_dir"])
    selected_refs = sample_random_records(all_records, sample_size=8, seed=42)

    annotations = load_selected_records(
        selected_refs=selected_refs,
        data_dir=mock_dataset["data_dir"],
        output_dir=mock_dataset["output_dir"],
        jev_dir=mock_dataset["jev_dir"],
    )

    assert len(annotations) == 8

    # Verify positional alignment for every single sampled record
    for item in annotations:
        rel_path = item["source"]["relative_path"]
        idx = item["source"]["index"]

        # Read directly from raw files to verify identity
        with open(mock_dataset["data_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_conv = json.load(f)[idx]
        with open(mock_dataset["output_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_llm = json.load(f)[idx]
        with open(mock_dataset["jev_dir"] / rel_path, "r", encoding="utf-8") as f:
            raw_jev = json.load(f)[idx]

        assert item["conversation"] == raw_conv
        assert item["llm_judge_output"] == raw_llm
        assert item["jev_output"] == raw_jev


def test_output_directory_protection(mock_dataset):
    all_records = discover_records(mock_dataset["data_dir"])
    selected_refs = sample_random_records(all_records, sample_size=5, seed=42)
    annotations = load_selected_records(
        selected_refs=selected_refs,
        data_dir=mock_dataset["data_dir"],
        output_dir=mock_dataset["output_dir"],
        jev_dir=mock_dataset["jev_dir"],
    )

    out_dir = mock_dataset["root"] / "annotation_set" / "random_sample"

    # First write should succeed
    write_annotation_set(
        annotation_dir=out_dir,
        annotations=annotations,
        selected_refs=selected_refs,
        total_discovered=len(all_records),
        sample_size=5,
        seed=42,
        data_dir=mock_dataset["data_dir"],
        output_dir=mock_dataset["output_dir"],
        jev_dir=mock_dataset["jev_dir"],
        overwrite=False,
    )

    # Second write without overwrite=True must raise FileExistsError
    with pytest.raises(FileExistsError):
        write_annotation_set(
            annotation_dir=out_dir,
            annotations=annotations,
            selected_refs=selected_refs,
            total_discovered=len(all_records),
            sample_size=5,
            seed=42,
            data_dir=mock_dataset["data_dir"],
            output_dir=mock_dataset["output_dir"],
            jev_dir=mock_dataset["jev_dir"],
            overwrite=False,
        )

    # Third write with overwrite=True must succeed
    write_annotation_set(
        annotation_dir=out_dir,
        annotations=annotations,
        selected_refs=selected_refs,
        total_discovered=len(all_records),
        sample_size=5,
        seed=42,
        data_dir=mock_dataset["data_dir"],
        output_dir=mock_dataset["output_dir"],
        jev_dir=mock_dataset["jev_dir"],
        overwrite=True,
    )


def test_insufficient_records_error():
    records = [("file_1.json", i) for i in range(10)]
    with pytest.raises(ValueError, match="only 10 discovered"):
        sample_random_records(records, sample_size=20, seed=42)


def test_output_schema_and_types(mock_dataset):
    all_records = discover_records(mock_dataset["data_dir"])
    selected_refs = sample_random_records(all_records, sample_size=6, seed=42)
    annotations = load_selected_records(
        selected_refs=selected_refs,
        data_dir=mock_dataset["data_dir"],
        output_dir=mock_dataset["output_dir"],
        jev_dir=mock_dataset["jev_dir"],
    )

    out_dir = mock_dataset["root"] / "schema_check"
    write_annotation_set(
        annotation_dir=out_dir,
        annotations=annotations,
        selected_refs=selected_refs,
        total_discovered=len(all_records),
        sample_size=6,
        seed=42,
        data_dir=mock_dataset["data_dir"],
        output_dir=mock_dataset["output_dir"],
        jev_dir=mock_dataset["jev_dir"],
    )

    # Check annotations.json
    with open(out_dir / "annotations.json", "r", encoding="utf-8") as f:
        annot_data = json.load(f)
    assert len(annot_data) == 6
    for idx, item in enumerate(annot_data, start=1):
        assert item["annotation_id"] == f"RND-{idx:04d}"
        assert item["sampling_strategy"] == "random"
        assert "relative_path" in item["source"]
        assert "index" in item["source"]
        assert "conversation" in item
        assert "llm_judge_output" in item
        assert "jev_output" in item

    # Check manifest.json
    with open(out_dir / "manifest.json", "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    assert manifest_data["random_seed"] == 42
    assert manifest_data["requested_sample_size"] == 6
    assert manifest_data["actual_sample_size"] == 6
    assert "generation_timestamp" in manifest_data
    assert "source_directories" in manifest_data
    assert len(manifest_data["selected_conversations"]) == 6
    assert manifest_data["selected_conversations"][0]["annotation_id"] == "RND-0001"

    # Check selection_summary.json
    with open(out_dir / "selection_summary.json", "r", encoding="utf-8") as f:
        summary_data = json.load(f)
    assert summary_data["total_conversations_discovered"] == 20
    assert summary_data["number_selected"] == 6
    assert summary_data["random_seed"] == 42
    assert "selected_per_subfolder" in summary_data
    assert "selected_per_file" in summary_data
    assert sum(summary_data["selected_per_subfolder"].values()) == 6
    assert sum(summary_data["selected_per_file"].values()) == 6


def test_cli_end_to_end(mock_dataset):
    out_dir = mock_dataset["root"] / "cli_test"
    cmd = [
        "--data-dir", str(mock_dataset["data_dir"]),
        "--output-dir", str(mock_dataset["output_dir"]),
        "--jev-dir", str(mock_dataset["jev_dir"]),
        "--annotation-dir", str(out_dir),
        "--sample-size", "5",
        "--seed", "100",
    ]
    exit_code = main(cmd)
    assert exit_code == 0
    assert (out_dir / "annotations.json").exists()

    # Re-running without overwrite should return code 1
    exit_code_dup = main(cmd)
    assert exit_code_dup == 1

    # Running with --overwrite should return code 0
    exit_code_over = main(cmd + ["--overwrite"])
    assert exit_code_over == 0
