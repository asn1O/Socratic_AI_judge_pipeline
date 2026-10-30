import json
from pathlib import Path

from src.pipeline import _validate_evaluation_payload, _state_path_for_source_dir


VALID_PAYLOAD = {
    "correctness": True,
    "socratic_guidance": 3,
    "scaffolding": 3,
    "state_adaptation": 3,
    "diagnosis": 3,
    "student_agency": 3,
    "progression": 3,
    "coherence": 3,
    "premature_answer": False,
    "hallucination": False,
    "evidence": {
        "correctness": "ok",
        "socratic_guidance": "ok",
        "scaffolding": "ok",
        "state_adaptation": "ok",
        "diagnosis": "ok",
        "student_agency": "ok",
        "progression": "ok",
        "coherence": "ok",
        "premature_answer": "ok",
        "hallucination": "ok",
    },
}


def test_validate_evaluation_payload_accepts_required_shape():
    assert _validate_evaluation_payload(VALID_PAYLOAD) is True


def test_validate_evaluation_payload_rejects_missing_fields():
    payload = json.loads(json.dumps(VALID_PAYLOAD))
    payload.pop("hallucination")
    assert _validate_evaluation_payload(payload) is False


# ---------- _state_path_for_source_dir tests ----------

def test_state_path_judge_1_default():
    """Judge 1 (default) uses evaluation_state.json."""
    result = _state_path_for_source_dir(Path("/tmp/output/model_x"))
    assert result == Path("/tmp/output/model_x/evaluation_state.json")


def test_state_path_judge_1_explicit():
    """Explicitly passing judge_number=1 uses evaluation_state.json."""
    result = _state_path_for_source_dir(Path("/tmp/output/model_x"), judge_number=1)
    assert result == Path("/tmp/output/model_x/evaluation_state.json")


def test_state_path_judge_2():
    """Judge 2 uses evaluation_state_2.json."""
    result = _state_path_for_source_dir(Path("/tmp/output/model_x"), judge_number=2)
    assert result == Path("/tmp/output/model_x/evaluation_state_2.json")
