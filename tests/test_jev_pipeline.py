import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from code.jev_model import FIXED_QUESTIONS, call_jev, format_conversation_state
from code.jev_pipeline import _state_path_for_source_dir, run_pipeline


def test_format_conversation_state():
    raw_record = {
        "config": {"difficulty": "easy"},
        "domain": "physics",
        "topic": "Newton's laws",
        "problem": "Calculate force on 2kg object accelerating at 3 m/s²",
        "conversation": [
            {
                "turn": 1,
                "speaker": "student",
                "text": "F = ma, right?",
            },
            {
                "turn": 2,
                "speaker": "tutor",
                "reasoning": "Student correctly remembered Newton's 2nd law.",
                "state": "Diagnosis",
                "response": "Yes, exactly! Now what are the values of m and a?",
            },
            {
                "turn": 3,
                "speaker": "student",
                "text": "m = 2 and a = 3.",
            },
            {
                "turn": 4,
                "speaker": "tutor",
                "reasoning": "Guide student to final calculation.",
                "state": "Support",
                "text": "So what is 2 times 3?",
            },
        ],
    }

    state = format_conversation_state(raw_record)
    assert state["domain"] == "physics"
    assert state["topic"] == "Newton's laws"
    assert state["problem"] == "Calculate force on 2kg object accelerating at 3 m/s²"
    assert len(state["conversation"]) == 4

    # Student turn 1
    assert state["conversation"][0] == {
        "turn": 1,
        "speaker": "student",
        "text": "F = ma, right?",
    }
    # Tutor turn 2: 'response' mapped to 'text'
    assert state["conversation"][1] == {
        "turn": 2,
        "speaker": "tutor",
        "text": "Yes, exactly! Now what are the values of m and a?",
    }
    # Student turn 3
    assert state["conversation"][2] == {
        "turn": 3,
        "speaker": "student",
        "text": "m = 2 and a = 3.",
    }
    # Tutor turn 4: direct 'text' retained
    assert state["conversation"][3] == {
        "turn": 4,
        "speaker": "tutor",
        "text": "So what is 2 times 3?",
    }


def test_call_jev_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "imajev-2b",
        "answers": {
            "socratic_guidance": {"score": 2.5},
        },
        "usage": {
            "input_tokens": 512,
            "total_ms": 100.0,
        },
    }

    with patch("requests.post", return_value=mock_response):
        success, data, total_tokens, error_code = call_jev(
            state={"domain": "math", "conversation": []}
        )

    assert success is True
    assert data["model"] == "imajev-2b"
    assert total_tokens == 512
    assert error_code is None


def test_call_jev_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("requests.post", return_value=mock_response):
        success, data, total_tokens, error_code = call_jev(
            state={"domain": "math", "conversation": []}
        )

    assert success is False
    assert data is None
    assert total_tokens == 0
    assert error_code == "HTTP_500"


def test_call_jev_connection_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        success, data, total_tokens, error_code = call_jev(
            state={"domain": "math", "conversation": []}
        )

    assert success is False
    assert data is None
    assert total_tokens == 0
    assert error_code == "CONNECTION_ERROR"


def test_state_path():
    p = _state_path_for_source_dir(Path("/tmp/jev_output/test_model"))
    assert p == Path("/tmp/jev_output/test_model/evaluation_state.json")


def test_run_pipeline_end_to_end(monkeypatch):
    sample_records = [
        {
            "domain": "biology",
            "topic": "cells",
            "problem": "What is the powerhouse of the cell?",
            "conversation": [
                {"turn": 1, "speaker": "student", "text": "Is it mitochondria?"},
                {"turn": 2, "speaker": "tutor", "response": "Why do you think so?"},
            ],
        },
        {
            "domain": "biology",
            "topic": "cells",
            "problem": "What does chlorophyll do?",
            "conversation": [
                {"turn": 1, "speaker": "student", "text": "It absorbs light."},
                {"turn": 2, "speaker": "tutor", "response": "Correct, for what process?"},
            ],
        },
    ]

    mock_jev_eval = {
        "model": "imajev-2b",
        "answers": {
            "socratic_guidance": {"score": 3.0},
        },
        "usage": {
            "input_tokens": 120,
        },
    }

    def fake_call_jev(state, questions=None, url=None, timeout=None):
        return True, mock_jev_eval, 120, None

    monkeypatch.setattr("code.jev_pipeline.call_jev", fake_call_jev)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        data_dir = tmp_path / "data"
        output_dir = tmp_path / "jev_output"

        model_dir = data_dir / "TestModel"
        model_dir.mkdir(parents=True, exist_ok=True)
        data_file = model_dir / "sample.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(sample_records, f)

        # Run pipeline evaluating 1 conversation
        count = run_pipeline(
            max_conversations=1,
            source_model_dir="TestModel",
            data_dir=str(data_dir),
            output_dir=str(output_dir),
        )
        assert count == 1

        # Check logs directory exists in output_dir
        assert (output_dir / "logs").exists()

        # Check state file
        state_file = output_dir / "TestModel" / "evaluation_state.json"
        assert state_file.exists()
        with open(state_file, encoding="utf-8") as f:
            state_data = json.load(f)
        assert "TestModel/sample.json:0" in state_data

        # Check evaluated output file
        out_file = output_dir / "TestModel" / "sample.json"
        assert out_file.exists()
        with open(out_file, encoding="utf-8") as f:
            saved_records = json.load(f)
        assert len(saved_records) == 1
        record0 = saved_records[0]
        assert record0["source_file"] == "TestModel/sample.json"
        assert record0["conversation_index"] == 0
        assert record0["model"]["provider"] == "imajev"
        assert record0["model"]["model_name"] == "imajev-2b"
        assert record0["total_tokens"] == 120
        assert record0["evaluation"] == mock_jev_eval

        # Re-running with max_conversations=2 should only evaluate the remaining 1 conversation
        count2 = run_pipeline(
            max_conversations=2,
            source_model_dir="TestModel",
            data_dir=str(data_dir),
            output_dir=str(output_dir),
        )
        assert count2 == 1

        with open(out_file, encoding="utf-8") as f:
            saved_records2 = json.load(f)
        assert len(saved_records2) == 2
