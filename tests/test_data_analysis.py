import json
from pathlib import Path

from analytics.data_analysis import (
    is_set_file,
    natural_sort_key,
    process_model_folder,
    compute_inter_judge_agreement,
    NUMERIC_METRICS,
    BOOLEAN_METRICS,
)


def test_natural_sort_key():
    files = ["asn-set[10].json", "asn-set[2].json", "asn-set[0].json"]
    sorted_files = sorted(files, key=natural_sort_key)
    assert sorted_files == ["asn-set[0].json", "asn-set[2].json", "asn-set[10].json"]


def test_is_set_file():
    assert is_set_file("asn-set[0].json") is True
    assert is_set_file("edw-set[12].json") is True
    assert is_set_file("son-set[5].json") is True
    assert is_set_file("evaluation_state.json") is False
    assert is_set_file("evaluation_state_2.json") is False
    assert is_set_file("analysis.csv") is False
    assert is_set_file("other.txt") is False


def test_process_model_folder(tmp_path: Path):
    model_dir = tmp_path / "Test_Model"
    model_dir.mkdir()

    sample_eval = {
        "correctness": True,
        "socratic_guidance": 3,
        "scaffolding": 2,
        "state_adaptation": 3,
        "diagnosis": 3,
        "student_agency": 3,
        "progression": 3,
        "coherence": 3,
        "premature_answer": False,
        "hallucination": False,
    }

    item = {
        "source_file": "Test_Model/asn-set[0].json",
        "conversation_index": 0,
        "judge_1": {
            "model": {"provider": "Ollama", "model_name": "beam:cloud"},
            "total_tokens": 1000,
            "evaluation": sample_eval,
        },
        "judge_2": {
            "model": {"provider": "Ollama", "model_name": "gpt-oss:120b"},
            "total_tokens": 1200,
            "evaluation": sample_eval,
        },
    }

    set_file = model_dir / "asn-set[0].json"
    with open(set_file, "w") as fp:
        json.dump([item], fp)

    # Add a state file to ensure it gets ignored
    state_file = model_dir / "evaluation_state.json"
    with open(state_file, "w") as fp:
        json.dump({"completed": True}, fp)

    rows, summary = process_model_folder(model_dir)

    assert len(rows) == 1
    assert rows[0]["conversation_id"] == "asn-set[0].json:0"
    assert rows[0]["file_name"] == "asn-set[0].json"
    assert rows[0]["conversation_index"] == 0
    assert rows[0]["socratic_guidance"] == 3.0
    assert rows[0]["scaffolding"] == 2.0
    assert rows[0]["correctness"] is True
    assert rows[0]["premature_answer"] is False
    assert rows[0]["hallucination"] is False
    assert rows[0]["judge_1_tokens"] == 1000
    assert rows[0]["judge_2_tokens"] == 1200
    assert rows[0]["total_tokens"] == 2200

    assert summary["total_conversations"] == 1
    assert summary["total_files"] == 1
    assert summary["metrics"]["socratic_guidance"]["mean"] == 3.0
