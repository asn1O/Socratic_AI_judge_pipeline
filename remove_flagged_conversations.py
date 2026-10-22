#!/usr/bin/env python3
"""remove_flagged_conversations.py - Remove flawed conversations across data, output, and jev_output.

Identifies conversations where ANY of the 3 LLM judges flagged:
- correctness is not True (False, missing, or null)
- premature_answer is not False (True, missing, or null)
- hallucination is not False (True, missing, or null)

Removes these conversations consistently across:
- data/<model>/<set_file>.json
- output/<model>/<set_file>.json
- jev_output/<model>/<set_file>.json

Logs all removed elements (file location, 0-indexed position, reasons, and problem snippet)
to both a human-readable log file (removed_conversations.log) and a structured JSON file (removed_conversations.json).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"


def setup_logger(log_file_path: Optional[Path] = None) -> Tuple[logging.Logger, Optional[logging.FileHandler]]:
    """Configure logging to stdout and optionally to a log file."""
    logger = logging.getLogger("clean_conversations")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = None
    if log_file_path:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger, file_handler


def is_set_file(path: Path) -> bool:
    """Return True if path is a JSON evaluation set file, ignoring state files."""
    if not path.is_file() or not path.name.endswith(".json"):
        return False
    lower = path.name.lower()
    if "state" in lower or "evaluation_state" in lower:
        return False
    return "set" in lower and ("[" in lower or "set_" in lower or "set-" in lower)


def _is_true(v: Any) -> bool:
    """Check if value is boolean True or string 'true'."""
    return v is True or (isinstance(v, str) and v.strip().lower() == "true")


def _is_false(v: Any) -> bool:
    """Check if value is boolean False or string 'false'."""
    return v is False or (isinstance(v, str) and v.strip().lower() == "false")


def check_conversation_flagged(item: Dict[str, Any]) -> List[str]:
    """Check if any judge in output evaluation flagged correctness, premature answer, or hallucination.

    A conversation is flagged if:
    - correctness is not True
    - premature_answer is not False
    - hallucination is not False
    - any of the 3 judge evaluations is missing
    """
    reasons: List[str] = []
    for j_key in ["judge_1", "judge_2", "judge_3"]:
        judge_data = item.get(j_key)
        if not isinstance(judge_data, dict):
            reasons.append(f"{j_key}: missing judge data")
            continue
        eval_data = judge_data.get("evaluation")
        if not isinstance(eval_data, dict):
            reasons.append(f"{j_key}: missing evaluation dictionary")
            continue

        corr = eval_data.get("correctness")
        prem = eval_data.get("premature_answer")
        hall = eval_data.get("hallucination")

        if not _is_true(corr):
            reasons.append(f"{j_key}: correctness={corr} (expected True)")
        if not _is_false(prem):
            reasons.append(f"{j_key}: premature_answer={prem} (expected False)")
        if not _is_false(hall):
            reasons.append(f"{j_key}: hallucination={hall} (expected False)")

    return reasons


def scan_and_clean_dataset(
    data_dir: Path,
    output_dir: Path,
    jev_dir: Path,
    apply_changes: bool = False,
    reindex: bool = True,
    logger: Optional[logging.Logger] = None,
    file_handler: Optional[logging.FileHandler] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Scan output folder for flagged conversations and optionally remove them across all 3 directories."""
    log = logger or logging.getLogger("clean_conversations")

    output_files = sorted(
        [p for p in output_dir.rglob("*.json") if is_set_file(p)],
        key=lambda p: str(p.relative_to(output_dir)),
    )

    log.info("Found %d evaluation set files in %s", len(output_files), output_dir)

    total_scanned = 0
    total_flagged = 0
    all_removals: List[Dict[str, Any]] = []
    model_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "flagged": 0, "kept": 0})
    files_modified = 0
    skipped_files = 0

    for out_path in output_files:
        rel_path = out_path.relative_to(output_dir)
        model_name = rel_path.parts[0] if len(rel_path.parts) > 1 else out_path.parent.name
        file_name = out_path.name

        data_path = data_dir / rel_path
        jev_path = jev_dir / rel_path

        # 1. Validate file existence
        if not data_path.exists():
            log.error("Missing corresponding data file: %s", data_path)
            skipped_files += 1
            continue
        if not jev_path.exists():
            log.error("Missing corresponding JEV file: %s", jev_path)
            skipped_files += 1
            continue

        # 2. Load JSON contents
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                out_items = json.load(f)
            with open(data_path, "r", encoding="utf-8") as f:
                data_items = json.load(f)
            with open(jev_path, "r", encoding="utf-8") as f:
                jev_items = json.load(f)
        except Exception as exc:
            log.error("Failed to read JSON for %s: %s", rel_path, exc)
            skipped_files += 1
            continue

        if not (isinstance(out_items, list) and isinstance(data_items, list) and isinstance(jev_items, list)):
            log.warning("Skipping %s: non-list JSON structure", rel_path)
            skipped_files += 1
            continue

        # 3. Verify alignment
        n_out, n_data, n_jev = len(out_items), len(data_items), len(jev_items)
        if not (n_out == n_data == n_jev):
            log.error(
                "Length mismatch in %s: data=%d, output=%d, jev=%d. Skipping file for safety.",
                rel_path,
                n_data,
                n_out,
                n_jev,
            )
            skipped_files += 1
            continue

        total_scanned += n_out
        model_stats[model_name]["total"] += n_out

        # 4. Check for flagged conversations
        flagged_indices = set()
        file_removals = []

        for idx, it in enumerate(out_items):
            reasons = check_conversation_flagged(it)
            if reasons:
                flagged_indices.add(idx)
                problem_snippet = ""
                if idx < len(data_items) and isinstance(data_items[idx], dict):
                    prob = data_items[idx].get("problem") or ""
                    problem_snippet = prob[:80] + ("..." if len(prob) > 80 else "")

                record = {
                    "model": model_name,
                    "file_name": file_name,
                    "relative_path": str(rel_path),
                    "original_position": idx,
                    "reasons": reasons,
                    "problem_snippet": problem_snippet,
                    "data_file": str(data_path),
                    "output_file": str(out_path),
                    "jev_file": str(jev_path),
                }
                file_removals.append(record)
                log.info(
                    "REMOVE: %s | Index %d | %s | %s",
                    rel_path,
                    idx,
                    "; ".join(reasons),
                    f"'{problem_snippet}'" if problem_snippet else "",
                )
                if file_handler:
                    file_handler.flush()

        if not flagged_indices:
            model_stats[model_name]["kept"] += n_out
            continue

        total_flagged += len(flagged_indices)
        model_stats[model_name]["flagged"] += len(flagged_indices)
        model_stats[model_name]["kept"] += (n_out - len(flagged_indices))
        all_removals.extend(file_removals)

        # 5. Apply removal if requested
        if apply_changes:
            files_modified += 1
            new_data = [item for idx, item in enumerate(data_items) if idx not in flagged_indices]
            new_out = [item for idx, item in enumerate(out_items) if idx not in flagged_indices]
            new_jev = [item for idx, item in enumerate(jev_items) if idx not in flagged_indices]

            if reindex:
                for new_idx, it in enumerate(new_out):
                    if isinstance(it, dict):
                        it["conversation_index"] = new_idx
                for new_idx, it in enumerate(new_jev):
                    if isinstance(it, dict):
                        it["conversation_index"] = new_idx

            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(new_out, f, indent=2, ensure_ascii=False)
            with open(jev_path, "w", encoding="utf-8") as f:
                json.dump(new_jev, f, indent=2, ensure_ascii=False)

            log.info(
                "APPLIED: Rewrote %s across data, output, jev_output (removed %d, %d remaining)",
                rel_path,
                len(flagged_indices),
                len(new_data),
            )
            if file_handler:
                file_handler.flush()

    summary = {
        "timestamp": datetime.now().isoformat(),
        "mode": "APPLIED" if apply_changes else "DRY_RUN",
        "total_files_inspected": len(output_files),
        "skipped_files_due_to_mismatch": skipped_files,
        "total_conversations_scanned": total_scanned,
        "total_flagged_for_removal": total_flagged,
        "total_retained": total_scanned - total_flagged,
        "files_modified": files_modified if apply_changes else 0,
        "model_statistics": dict(model_stats),
    }

    return all_removals, summary


def main():
    parser = argparse.ArgumentParser(
        description="Identify and remove flawed conversations (correctness=False, premature=True, hallucination=True) across data, output, and jev_output."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually remove the flagged elements and rewrite data, output, and jev_output files. (Defaults to dry-run if omitted).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path to data directory (default: data).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Path to output directory (default: output).",
    )
    parser.add_argument(
        "--jev-dir",
        type=Path,
        default=Path("jev_output"),
        help="Path to jev_output directory (default: jev_output).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("removed_conversations.log"),
        help="Path to write the human-readable log (default: removed_conversations.log).",
    )
    parser.add_argument(
        "--json-log",
        type=Path,
        default=Path("removed_conversations.json"),
        help="Path to save the structured JSON list of removed elements (default: removed_conversations.json).",
    )
    parser.add_argument(
        "--no-reindex",
        action="store_true",
        help="Do not re-index conversation_index in output and jev_output files after removal.",
    )

    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    jev_dir = args.jev_dir.resolve()
    log_file = args.log_file.resolve()
    json_log = args.json_log.resolve()

    logger, file_handler = setup_logger(log_file)

    logger.info("=" * 70)
    logger.info("Starting conversation cleanup run")
    logger.info("Mode: %s", "APPLY (PERMANENTLY WRITING CHANGES)" if args.apply else "DRY-RUN (INSPECTION ONLY - NO FILES MODIFIED)")
    logger.info("Data directory:       %s", data_dir)
    logger.info("Output directory:     %s", output_dir)
    logger.info("JEV Output directory: %s", jev_dir)
    logger.info("Log file:             %s", log_file)
    logger.info("JSON log file:        %s", json_log)
    logger.info("=" * 70)

    removals, summary = scan_and_clean_dataset(
        data_dir=data_dir,
        output_dir=output_dir,
        jev_dir=jev_dir,
        apply_changes=args.apply,
        reindex=not args.no_reindex,
        logger=logger,
        file_handler=file_handler,
    )

    # Save structured JSON
    try:
        output_payload = {
            "summary": summary,
            "removals_count": len(removals),
            "removed_conversations": removals,
        }
        with open(json_log, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=2, ensure_ascii=False)
        logger.info("Saved structured removal log to %s", json_log)
    except Exception as exc:
        logger.error("Failed to write JSON log: %s", exc)

    logger.info("-" * 70)
    logger.info("CLEANUP SUMMARY (%s)", summary["mode"])
    logger.info("Total Files Inspected:       %d", summary["total_files_inspected"])
    if summary["skipped_files_due_to_mismatch"] > 0:
        logger.warning("Files Skipped Due Mismatch: %d (SAFETY CHECK)", summary["skipped_files_due_to_mismatch"])
    logger.info("Total Conversations Scanned: %d", summary["total_conversations_scanned"])
    logger.info("Flagged for Removal:         %d", summary["total_flagged_for_removal"])
    logger.info("Remaining Clean Set:         %d", summary["total_retained"])
    if args.apply:
        logger.info("Files Modified:              %d across each folder (data, output, jev_output)", summary["files_modified"])
    else:
        logger.info("-" * 70)
        logger.info("[DRY-RUN COMPLETE] No files have been modified.")
        logger.info("To permanently apply these removals, run:")
        logger.info("  python3 remove_flagged_conversations.py --apply")
    logger.info("=" * 70)

    if file_handler:
        file_handler.flush()
        file_handler.close()


if __name__ == "__main__":
    main()
