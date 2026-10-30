import json
from collections import Counter
from pathlib import Path
import tempfile

from scripts.validate_conversations import is_valid_conversation, validate_file


def test_valid_conversation():
    valid_convo = {
        "problem": "Calculate 2 + 2",
        "conversation": [
            {"turn": 1, "speaker": "student", "text": "What is 2+2?"},
            {"turn": 2, "speaker": "tutor", "state": "Diagnosis", "text": "What do you think?"},
            {"turn": 3, "speaker": "student", "text": "Is it 4?"},
            {"turn": 4, "speaker": "tutor", "state": "Synthesis", "text": "Exactly, because 2 and 2 make 4."},
            {"turn": 5, "speaker": "student", "text": "Thanks!"},
            {"turn": 6, "speaker": "tutor", "state": "Closing", "text": "You did great. Bye!"},
        ],
    }
    valid, msg, cat = is_valid_conversation(valid_convo)
    assert valid is True
    assert msg == ""
    assert cat == ""


def test_invalid_conversation_missing_synthesis():
    invalid_convo = {
        "problem": "Calculate 2 + 2",
        "conversation": [
            {"turn": 1, "speaker": "student", "text": "What is 2+2?"},
            {"turn": 2, "speaker": "tutor", "state": "Diagnosis", "text": "What do you think?"},
            {"turn": 3, "speaker": "student", "text": "Is it 4?"},
            {"turn": 4, "speaker": "tutor", "state": "Support", "text": "Think about it."},
            {"turn": 5, "speaker": "student", "text": "Thanks!"},
            {"turn": 6, "speaker": "tutor", "state": "Closing", "text": "Bye!"},
        ],
    }
    valid, msg, cat = is_valid_conversation(invalid_convo)
    assert valid is False
    assert "Synthesis" in msg


def test_validate_file_counts():
    valid_convo = {
        "problem": "Calculate 2 + 2",
        "conversation": [
            {"turn": 1, "speaker": "student", "text": "What is 2+2?"},
            {"turn": 2, "speaker": "tutor", "state": "Diagnosis", "text": "What do you think?"},
            {"turn": 3, "speaker": "student", "text": "Is it 4?"},
            {"turn": 4, "speaker": "tutor", "state": "Synthesis", "text": "2 and 2 make 4."},
            {"turn": 5, "speaker": "student", "text": "Thanks!"},
            {"turn": 6, "speaker": "tutor", "state": "Closing", "text": "Bye!"},
        ],
    }
    invalid_convo = {
        "problem": "Bad",
        "conversation": [
            {"turn": 1, "speaker": "student", "text": "Hi"},
            {"turn": 2, "speaker": "tutor", "state": "Support", "text": "Hello"},
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([valid_convo, invalid_convo], f)

        error_stats = Counter()
        total_count, invalid_count = validate_file(
            file_path=file_path,
            error_stats=error_stats,
            delete_invalid=False,
        )

        assert total_count == 2
        assert invalid_count == 1
        assert len(error_stats) == 1


def test_validate_dataset_folder_stats():
    valid_convo = {
        "problem": "Calculate 2 + 2",
        "conversation": [
            {"turn": 1, "speaker": "student", "text": "What is 2+2?"},
            {"turn": 2, "speaker": "tutor", "state": "Diagnosis", "text": "What do you think?"},
            {"turn": 3, "speaker": "student", "text": "Is it 4?"},
            {"turn": 4, "speaker": "tutor", "state": "Synthesis", "text": "2 and 2 make 4."},
            {"turn": 5, "speaker": "student", "text": "Thanks!"},
            {"turn": 6, "speaker": "tutor", "state": "Closing", "text": "Bye!"},
        ],
    }
    invalid_convo = {
        "problem": "Bad",
        "conversation": [
            {"turn": 1, "speaker": "student", "text": "Hi"},
            {"turn": 2, "speaker": "tutor", "state": "Support", "text": "Hello"},
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        folder_a = base_dir / "Model_A"
        folder_b = base_dir / "Model_B"
        folder_empty = base_dir / "Model_Empty"
        folder_a.mkdir()
        folder_b.mkdir()
        folder_empty.mkdir()

        with open(folder_a / "file1.json", "w", encoding="utf-8") as f:
            json.dump([valid_convo, invalid_convo], f)

        with open(folder_b / "file2.json", "w", encoding="utf-8") as f:
            json.dump([valid_convo, valid_convo], f)

        from scripts.validate_conversations import validate_dataset

        total, total_invalid, folder_stats, errors, file_count = validate_dataset(
            data_dir=base_dir,
            delete_invalid=False,
        )

        assert total == 4
        assert total_invalid == 1
        assert file_count == 2

        assert "Model_A" in folder_stats
        assert folder_stats["Model_A"]["total"] == 2
        assert folder_stats["Model_A"]["invalid"] == 1

        assert "Model_B" in folder_stats
        assert folder_stats["Model_B"]["total"] == 2
        assert folder_stats["Model_B"]["invalid"] == 0

        assert "Model_Empty" in folder_stats
        assert folder_stats["Model_Empty"]["total"] == 0
        assert folder_stats["Model_Empty"]["invalid"] == 0

