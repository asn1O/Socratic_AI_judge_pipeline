import json
from pathlib import Path

import pytest

from scripts.convert_for_finetuning import (
    SYSTEM_PROMPT,
    OUTPUT_FILENAME,
    convert_conversation,
    convert_dataset,
)


def _conversation(problem: str = "Find the answer") -> dict:
    return {
        "problem": problem,
        "conversation": [
            {"turn": 1, "speaker": "student", "text": "I think it is 4."},
            {
                "turn": 2,
                "speaker": "tutor",
                "reasoning": "Check the student's reasoning.",
                "state": "Diagnosis",
                "response": "How did you get that?",
            },
        ],
    }


def test_convert_conversation_formats_chat_messages():
    converted = convert_conversation(_conversation(), Path("sample.json"), 1)

    assert converted["messages"] == [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nProblem: Find the answer",
        },
        {"role": "user", "content": "I think it is 4."},
        {
            "role": "assistant",
            "content": (
                "<reasoning>Check the student's reasoning.</reasoning>\n"
                "<state>Diagnosis</state>\n"
                "<response>How did you get that?</response>"
            ),
        },
    ]


def test_convert_dataset_writes_all_conversations_to_one_jsonl_file(tmp_path):
    input_dir = tmp_path / "source"
    source_file = input_dir / "model" / "nested" / "a.json"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        json.dumps([_conversation("First"), _conversation("Second")]),
        encoding="utf-8",
    )
    second_source = input_dir / "model" / "z" / "set.json"
    second_source.parent.mkdir(parents=True)
    second_source.write_text(json.dumps([_conversation("Third")]), encoding="utf-8")
    (input_dir / "unrelated.json").write_text(json.dumps({"report": []}), encoding="utf-8")
    output_dir = tmp_path / "custom-output"

    assert convert_dataset(input_dir, output_dir) == (2, 1, 3)

    output_file = output_dir / OUTPUT_FILENAME
    lines = output_file.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert len(records) == 3
    assert [
        record["messages"][0]["content"].split("Problem: ", maxsplit=1)[1]
        for record in records
    ] == ["First", "Second", "Third"]
    assert list(output_dir.iterdir()) == [output_file]


def test_convert_conversation_reports_missing_tutor_fields():
    conversation = _conversation()
    del conversation["conversation"][1]["reasoning"]

    with pytest.raises(ValueError, match="reasoning"):
        convert_conversation(conversation, Path("sample.json"), 1)


def test_output_directory_cannot_be_inside_input(tmp_path):
    input_dir = tmp_path / "source"
    input_dir.mkdir()
    (input_dir / "sample.json").write_text(json.dumps([_conversation()]), encoding="utf-8")

    with pytest.raises(ValueError, match="inside the input directory"):
        convert_dataset(input_dir, input_dir / "output")


def test_convert_dataset_rejects_mixed_conversation_and_nonconversation_entries(tmp_path):
    input_dir = tmp_path / "source"
    input_dir.mkdir()
    (input_dir / "sample.json").write_text(
        json.dumps([_conversation(), {"not": "a conversation"}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="entry 2 is not a conversation object"):
        convert_dataset(input_dir, tmp_path / "output")
