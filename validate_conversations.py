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


def is_valid_conversation(conversation: dict) -> bool:
    """
    TODO: Implement the actual validation logic here.
    Return True if the conversation element is structurally valid,
    False otherwise.
    """
    return True  # placeholder – replace with real checks


def validate_file(file_path: Path) -> int:
    """Validate every conversation in a single JSON file.

    Returns the number of elements removed.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        conversations: list[dict] = json.load(f)

    valid = []
    removed_count = 0

    for index, element in enumerate(conversations):
        # ── Call the validator here ──────────────────────────────
        if is_valid_conversation(element):
            valid.append(element)
        else:
            log.warning("REMOVED  file=%s  index=%d", file_path, index)
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
