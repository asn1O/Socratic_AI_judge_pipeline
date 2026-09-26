import json
import logging
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


def is_valid_conversation(entry: dict) -> tuple[bool, str]:
    """Structurally validate a single conversation entry.

    Returns (True, "") if valid, or (False, reason) if not.
    """

    # 1. Must have "problem" and "conversation" fields
    if "problem" not in entry:
        return False, "missing 'problem' field"
    if "conversation" not in entry:
        return False, "missing 'conversation' field"

    turns = entry["conversation"]

    if not isinstance(turns, list) or len(turns) == 0:
        return False, "'conversation' is not a non-empty list"

    # 2. Turn numbering must start at 1 and increment by 1
    for i, turn in enumerate(turns):
        expected_turn = i + 1
        if "turn" not in turn:
            return False, f"turn at index {i}: missing 'turn' field"
        if turn["turn"] != expected_turn:
            return False, (
                f"turn at index {i}: expected turn number {expected_turn}, "
                f"got {turn['turn']}"
            )

    # 3. Speaker must be "student" or "tutor" (case-insensitive),
    #    first turn must be student, and they must alternate
    for i, turn in enumerate(turns):
        if "speaker" not in turn:
            return False, f"turn {i+1}: missing 'speaker' field"

        speaker = turn["speaker"].strip().lower()

        if speaker not in VALID_SPEAKERS:
            return False, f"turn {i+1}: invalid speaker '{turn['speaker']}'"

        expected_speaker = "student" if i % 2 == 0 else "tutor"
        if speaker != expected_speaker:
            return False, (
                f"turn {i+1}: expected speaker '{expected_speaker}', "
                f"got '{turn['speaker']}'"
            )

    # 4. Every tutor turn must have a valid "state"
    for i, turn in enumerate(turns):
        if turn["speaker"].strip().lower() != "tutor":
            continue
        if "state" not in turn:
            return False, f"turn {i+1} (tutor): missing 'state' field"
        state = turn["state"].strip().lower()
        if state not in VALID_STATES:
            return False, (
                f"turn {i+1} (tutor): invalid state '{turn['state']}'"
            )

    # 5. Last tutor turn must be "Closing",
    #    and the tutor turn before that must be "Synthesis"
    tutor_turns = [
        (i, t) for i, t in enumerate(turns)
        if t["speaker"].strip().lower() == "tutor"
    ]

    if len(tutor_turns) < 2:
        return False, "fewer than 2 tutor turns; cannot verify Synthesis→Closing"

    last_tutor_idx, last_tutor = tutor_turns[-1]
    if last_tutor["state"].strip().lower() != "closing":
        return False, (
            f"turn {last_tutor_idx+1}: last tutor turn state must be "
            f"'Closing', got '{last_tutor['state']}'"
        )

    second_last_idx, second_last_tutor = tutor_turns[-2]
    if second_last_tutor["state"].strip().lower() != "synthesis":
        return False, (
            f"turn {second_last_idx+1}: second-to-last tutor turn state must "
            f"be 'Synthesis', got '{second_last_tutor['state']}'"
        )

    return True, ""


def validate_file(file_path: Path) -> int:
    """Validate every conversation in a single JSON file.

    Returns the number of elements removed.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        conversations: list[dict] = json.load(f)

    valid = []
    removed_count = 0

    for index, element in enumerate(conversations):
        is_valid, error_msg = is_valid_conversation(element)

        if is_valid:
            valid.append(element)
        else:
            log.warning(
                "REMOVED  file=%s  index=%d  reason=%s",
                file_path, index, error_msg,
            )
            removed_count += 1

    # Write back only if something was removed
    if removed_count > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(valid, f, indent=2, ensure_ascii=False)
        log.info("Rewrote %s  (removed %d elements)", file_path, removed_count)

    return removed_count


def main():
    json_files = sorted(DATA_DIR.rglob("*.json"))
    log.info("Found %d JSON files under %s", len(json_files), DATA_DIR)

    total_removed = 0

    for file_path in json_files:
        total_removed += validate_file(file_path)

    log.info("Done. Total elements removed: %d", total_removed)


if __name__ == "__main__":
    main()
