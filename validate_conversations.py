import argparse
import json
import logging
from collections import Counter
from pathlib import Path

# ── Logging setup ──────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

log = logging.getLogger(__name__)

file_handler = logging.FileHandler(
    Path(__file__).parent / "validator.log", mode="a", encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
log.addHandler(file_handler)

# ── Paths ──────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"


VALID_SPEAKERS = {"student", "tutor"}
VALID_STATES = {"diagnosis", "support", "synthesis", "closing"}


def is_valid_conversation(entry: dict) -> tuple[bool, str, str]:
    """Structurally validate a single conversation entry.

    Returns (True, "", "") if valid,
    or (False, specific_detail, general_category) if not.
    """

    # 1. Must have "problem" and "conversation" fields
    if "problem" not in entry:
        return False, "missing 'problem' field", "missing required field"
    if "conversation" not in entry:
        return False, "missing 'conversation' field", "missing required field"

    turns = entry["conversation"]

    if not isinstance(turns, list) or len(turns) == 0:
        return False, "'conversation' is not a non-empty list", "invalid conversation format"

    # 2. Turn numbering must start at 1 and increment by 1
    for i, turn in enumerate(turns):
        expected_turn = i + 1
        if "turn" not in turn:
            return (
                False,
                f"turn at index {i}: missing 'turn' field",
                "missing turn number",
            )
        if turn["turn"] != expected_turn:
            return (
                False,
                f"turn at index {i}: expected turn number {expected_turn}, "
                f"got {turn['turn']}",
                "incorrect turn numbering",
            )

    # 3. Speaker must be "student" or "tutor" (case-insensitive),
    #    first turn must be student, and they must alternate
    for i, turn in enumerate(turns):
        if "speaker" not in turn:
            return (
                False,
                f"turn {i+1}: missing 'speaker' field",
                "missing speaker field",
            )

        speaker = turn["speaker"].strip().lower()

        if speaker not in VALID_SPEAKERS:
            return (
                False,
                f"turn {i+1}: invalid speaker '{turn['speaker']}'",
                "invalid speaker value",
            )

        expected_speaker = "student" if i % 2 == 0 else "tutor"
        if speaker != expected_speaker:
            return (
                False,
                f"turn {i+1}: expected speaker '{expected_speaker}', "
                f"got '{turn['speaker']}'",
                "speaker alternation broken",
            )

    # 4. Every tutor turn must have a valid "state"
    for i, turn in enumerate(turns):
        if turn["speaker"].strip().lower() != "tutor":
            continue
        if "state" not in turn:
            return (
                False,
                f"turn {i+1} (tutor): missing 'state' field",
                "missing tutor state",
            )
        state = turn["state"].strip().lower()
        if state not in VALID_STATES:
            return (
                False,
                f"turn {i+1} (tutor): invalid state '{turn['state']}'",
                "invalid tutor state value",
            )

    # 5. Last tutor turn must be "Closing",
    #    and the tutor turn before that must be "Synthesis"
    tutor_turns = [
        (i, t) for i, t in enumerate(turns)
        if t["speaker"].strip().lower() == "tutor"
    ]

    if len(tutor_turns) < 2:
        return (
            False,
            "fewer than 2 tutor turns; cannot verify Synthesis→Closing",
            "too few tutor turns",
        )

    last_tutor_idx, last_tutor = tutor_turns[-1]
    if last_tutor["state"].strip().lower() != "closing":
        return (
            False,
            f"turn {last_tutor_idx+1}: last tutor turn state must be "
            f"'Closing', got '{last_tutor['state']}'",
            "last tutor turn not Closing",
        )

    second_last_idx, second_last_tutor = tutor_turns[-2]
    if second_last_tutor["state"].strip().lower() != "synthesis":
        return (
            False,
            f"turn {second_last_idx+1}: second-to-last tutor turn state must "
            f"be 'Synthesis', got '{second_last_tutor['state']}'",
            f"second-to-last tutor turn state must "
            f"be 'Synthesis', got '{second_last_tutor['state']}'",
        )

    return True, "", ""


def validate_file(file_path: Path, error_stats: Counter, delete_invalid: bool) -> int:
    """Validate every conversation in a single JSON file.

    Returns the number of invalid elements found.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        conversations: list[dict] = json.load(f)

    valid = []
    invalid_count = 0

    for index, element in enumerate(conversations):
        is_valid, error_detail, error_category = is_valid_conversation(element)

        if is_valid:
            valid.append(element)
        else:
            invalid_count += 1
            error_stats[error_category] += 1
            if delete_invalid:
                log.warning(
                    "REMOVED  file=%s  index=%d  reason=%s",
                    file_path, index, error_detail,
                )
            else:
                log.warning(
                    "INVALID  file=%s  index=%d  reason=%s",
                    file_path, index, error_detail,
                )
                valid.append(element)

    # Write back only if something was removed
    removed_count = invalid_count if delete_invalid else 0
    if removed_count > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(valid, f, indent=2, ensure_ascii=False)
        log.info("Rewrote %s  (removed %d elements)", file_path, removed_count)

    return invalid_count


def main():
    parser = argparse.ArgumentParser(description="Validate JSON conversations.")
    parser.add_argument(
        "--delete-invalid",
        action="store_true",
        help="Actually remove structurally invalid elements and rewrite the files."
    )
    args = parser.parse_args()

    json_files = sorted(DATA_DIR.rglob("*.json"))
    log.info("Found %d JSON files under %s", len(json_files), DATA_DIR)

    total_invalid = 0
    error_stats = Counter()

    for file_path in json_files:
        total_invalid += validate_file(file_path, error_stats, args.delete_invalid)

    log.info("Done. Total invalid elements found: %d", total_invalid)

    # ── Error stats summary ────────────────────────────────────────────
    if error_stats:
        log.info("── Error Stats ──")
        for error_msg, count in error_stats.most_common():
            log.info("  %4d × %s", count, error_msg)
    else:
        log.info("No errors found. All conversations are valid.")


if __name__ == "__main__":
    main()
