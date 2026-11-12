import argparse
import json
import logging
from pathlib import Path
from typing import Any

# python3 scripts/convert_for_finetuning.py --input-dir data --output-dir fine_tuning_data

LOG_FORMAT = "%(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger(__name__)

DEFAULT_INPUT_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "fine_tuning_data"
OUTPUT_FILENAME = "fine_tuning_data.jsonl"

SYSTEM_PROMPT = (
    "You are a Socratic tutor. Guide the student toward the answer without giving it away.\n"
    "For every reply, output <reasoning>...</reasoning>, <state>...</state>, and "
    "<response>...</response>."
)


def _required_string(value: Any, field: str, source: Path, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{source}: conversation {index} must have a non-empty {field!r}"
        )
    return value


def convert_conversation(entry: dict[str, Any], source: Path, index: int) -> dict[str, Any]:
    """Convert one source conversation into a chat fine-tuning record."""
    problem = _required_string(entry.get("problem"), "problem", source, index)
    turns = entry.get("conversation")
    if not isinstance(turns, list) or not turns:
        raise ValueError(
            f"{source}: conversation {index} must have a non-empty 'conversation' list"
        )

    messages = [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nProblem: {problem}",
        }
    ]

    for turn_index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            raise ValueError(
                f"{source}: conversation {index}, turn {turn_index} must be an object"
            )

        speaker = turn.get("speaker")
        if not isinstance(speaker, str):
            raise ValueError(
                f"{source}: conversation {index}, turn {turn_index} has no valid speaker"
            )
        speaker = speaker.strip().lower()

        if speaker == "student":
            messages.append({
                "role": "user",
                "content": _required_string(turn.get("text"), "text", source, index),
            })
        elif speaker == "tutor":
            reasoning = _required_string(turn.get("reasoning"), "reasoning", source, index)
            state = _required_string(turn.get("state"), "state", source, index)
            response = _required_string(turn.get("response"), "response", source, index)
            messages.append({
                "role": "assistant",
                "content": (
                    f"<reasoning>{reasoning}</reasoning>\n"
                    f"<state>{state}</state>\n"
                    f"<response>{response}</response>"
                ),
            })
        else:
            raise ValueError(
                f"{source}: conversation {index}, turn {turn_index} "
                f"has unsupported speaker {turn.get('speaker')!r}"
            )

    return {"messages": messages}


def convert_file(source: Path) -> tuple[list[dict[str, Any]], bool]:
    """Convert one source JSON file; return (records, was skipped)."""
    try:
        entries = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source}: invalid JSON: {exc}") from exc

    if not isinstance(entries, list):
        log.warning("Skipping %s: top-level JSON value is not a conversation list", source)
        return [], True

    if not any(isinstance(entry, dict) and "conversation" in entry for entry in entries):
        log.warning("Skipping %s: no conversation entries found", source)
        return [], True

    records = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "conversation" not in entry:
            raise ValueError(
                f"{source}: entry {index} is not a conversation object"
            )
        records.append(convert_conversation(entry, source, index))

    return records, False


def convert_dataset(input_dir: Path, output_dir: Path) -> tuple[int, int, int]:
    """Convert all conversation JSON files recursively under input_dir."""
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    try:
        output_dir.relative_to(input_dir)
    except ValueError:
        pass
    else:
        raise ValueError("Output directory must not be inside the input directory")

    files = sorted(input_dir.rglob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found under {input_dir}")

    converted_files = skipped_files = 0
    records: list[dict[str, Any]] = []
    for source in files:
        file_records, skipped = convert_file(source)
        if skipped:
            skipped_files += 1
        else:
            converted_files += 1
            records.extend(file_records)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / OUTPUT_FILENAME
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )

    return converted_files, skipped_files, len(records)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert nested Socratic conversations into a fine-tuning JSONL file."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Dataset directory to scan recursively (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Destination directory for {OUTPUT_FILENAME} "
        f"(default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    converted_files, skipped_files, conversation_count = convert_dataset(
        args.input_dir, args.output_dir
    )
    log.info(
        "Converted %d conversations from %d files; skipped %d unrelated files. Output: %s",
        conversation_count,
        converted_files,
        skipped_files,
        args.output_dir.resolve() / OUTPUT_FILENAME,
    )


if __name__ == "__main__":
    main()
