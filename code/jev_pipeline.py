"""Evaluate Socratic conversations using the direct JEV endpoint and persist results."""

import argparse
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

try:
    from .jev_model import (
        DEFAULT_JEV_URL,
        DEFAULT_MODEL_NAME,
        DEFAULT_PROVIDER,
        FIXED_QUESTIONS,
        call_jev,
        format_conversation_state,
    )
except ImportError:  # pragma: no cover
    from jev_model import (
        DEFAULT_JEV_URL,
        DEFAULT_MODEL_NAME,
        DEFAULT_PROVIDER,
        FIXED_QUESTIONS,
        call_jev,
        format_conversation_state,
    )

MAX_CONSECUTIVE_ERRORS = 3
RETRY_WAIT_SECONDS = 2.0

logger = logging.getLogger("jev_pipeline")
logger.setLevel(logging.INFO)
logger.propagate = False


def _generator_id() -> str:
    """Return the worker identifier used to distinguish generated files."""
    return os.getenv("DATASET_GENERATOR_ID", "unknown").strip() or "unknown"


def _configure_logging(output_dir: str, model_name: Optional[str] = None) -> None:
    """Configure a shared pipeline logger for the current evaluation run inside output_dir/logs."""
    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if model_name:
        safe_model_name = model_name.replace("/", "_").replace(":", "-")
        log_path = log_dir / f"{_generator_id()}.{safe_model_name}.log"
    else:
        log_path = log_dir / f"{_generator_id()}.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if not any(type(handler) is logging.StreamHandler for handler in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)


def _relative_data_path(file_path: Path, data_dir: Path) -> str:
    return file_path.relative_to(data_dir).as_posix()


def _discover_conversation_files(data_dir: Path) -> List[Path]:
    """Return all conversation JSON files under the configured data directory."""
    files: List[Path] = []
    for path in sorted(data_dir.rglob("*.json")):
        if path.name.endswith("_state.json") or path.name.startswith("evaluation_state"):
            continue
        if path.name == "model.json":
            continue
        files.append(path)
    return files


def _load_json_array(path: Path) -> List[Any]:
    """Load a JSON file and accept either a list or a single record object with a conversation array."""
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        conversation = payload.get("conversation")
        if isinstance(conversation, list):
            return [payload]
        raise ValueError(f"JSON record at {path} does not contain a conversation list")

    raise ValueError(f"JSON record at {path} is not a list or conversation object")


def _state_path_for_source_dir(source_dir: Path) -> Path:
    return source_dir / "evaluation_state.json"


def _load_state(source_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load the persisted per-conversation evaluator metadata."""
    state_path = _state_path_for_source_dir(source_dir)
    if not state_path.exists():
        return {}

    try:
        with state_path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt evaluation state in %s; resetting it.", state_path)
        return {}

    if not isinstance(loaded, dict):
        return {}

    normalized: Dict[str, Dict[str, Any]] = {}
    for key, value in loaded.items():
        if isinstance(value, dict):
            normalized[str(key)] = value
        elif isinstance(value, bool):
            normalized[str(key)] = {"evaluated": bool(value)}
    return normalized


def _save_state(source_dir: Path, state: Dict[str, Dict[str, Any]]) -> None:
    """Persist evaluator metadata for evaluated conversations."""
    source_dir.mkdir(parents=True, exist_ok=True)
    state_path = _state_path_for_source_dir(source_dir)
    with state_path.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, ensure_ascii=False)
        file.write("\n")


def _read_output_entries(output_file: Path) -> List[Dict[str, Any]]:
    if not output_file.exists():
        return []
    try:
        with output_file.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return []


def _write_output_entries(output_file: Path, entries: List[Dict[str, Any]]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2, ensure_ascii=False)
        file.write("\n")


def _build_conversation_key(source_rel_path: str, index: int) -> str:
    return f"{source_rel_path}:{index}"


def _format_run_summary(stats: Dict[str, Any], duration_seconds: float) -> str:
    """Build the plain-text end-of-run report."""
    attempts = stats["attempts"]
    saved = stats["saved"]
    failed = stats["failed"]
    accept_rate = (saved / attempts * 100.0) if attempts else 0.0
    lines = [
        "\n=== JEV Evaluation Summary ===",
        "Overall totals",
        f"  Attempts: {attempts}",
        f"  Saved: {saved}",
        f"  Failed: {failed}",
        f"  Accept rate: {accept_rate:.2f}%",
        f"  Duration (h:m:s): {int(duration_seconds // 3600):02d}:{int(duration_seconds % 3600 // 60):02d}:{int(duration_seconds % 60):02d}",
        "",
        "Per-model results",
    ]
    for model_key, model_stats in stats["models"].items():
        lines.append(
            f"  {model_key}: attempts={model_stats['attempts']} saved={model_stats['saved']} failed={model_stats['failed']}"
        )
    return "\n".join(lines)


def _new_stats() -> Dict[str, Any]:
    return {
        "attempts": 0,
        "saved": 0,
        "failed": 0,
        "models": defaultdict(lambda: {"attempts": 0, "saved": 0, "failed": 0}),
    }


def _is_fatal_error(error_code: Optional[str]) -> bool:
    """Return True if error_code represents a failure that should count toward aborting."""
    if not error_code:
        return True
    if error_code in ("CONNECTION_ERROR", "TIMEOUT", "REQUEST_ERROR"):
        return True
    if error_code.startswith("HTTP_"):
        try:
            status = int(error_code[5:])
            return 400 <= status <= 599
        except ValueError:
            return True
    return False


def _evaluate_source_folder(
    data_dir: Path,
    output_dir: Path,
    source_model_dir: str,
    max_conversations: int,
    jev_url: str = DEFAULT_JEV_URL,
    provider: str = DEFAULT_PROVIDER,
    wait_seconds: float = 0.0,
    state: Optional[Dict[str, Dict[str, Any]]] = None,
    include_state: bool = False,
    include_reasoning: bool = False,
    include_state_reasoning: bool = False,
) -> Dict[str, Any]:
    """Evaluate up to max_conversations from one source model folder using the direct JEV endpoint."""
    include_state = include_state or include_state_reasoning
    include_reasoning = include_reasoning or include_state_reasoning

    source_root = data_dir / source_model_dir
    if not source_root.exists():
        raise FileNotFoundError(f"Input model folder not found: {source_root}")

    output_model_dir = output_dir / source_model_dir
    output_model_dir.mkdir(parents=True, exist_ok=True)
    state = state if state is not None else _load_state(output_model_dir)

    model_key = f"{provider} / {DEFAULT_MODEL_NAME}"
    stats = _new_stats()

    conversation_files = _discover_conversation_files(source_root)
    if not conversation_files:
        logger.warning("No conversation files found under %s", source_root)
        return stats

    evaluated_count = 0
    consecutive_errors = 0

    for file_path in conversation_files:
        if evaluated_count >= max_conversations:
            break

        try:
            records = _load_json_array(file_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable conversation file %s: %s", file_path, exc)
            continue

        relative_path = _relative_data_path(file_path, data_dir)
        output_file = output_dir / relative_path
        existing_rows = _read_output_entries(output_file)

        for idx, record in enumerate(records):
            if evaluated_count >= max_conversations:
                break

            payload = record if isinstance(record, dict) else {"conversation": record}
            if "conversation" not in payload or not isinstance(payload["conversation"], list):
                logger.warning("Skipping record %s in %s because it has no conversation list", idx, file_path)
                continue

            conversation_key = _build_conversation_key(relative_path, idx)
            if conversation_key in state:
                continue

            # Format state payload for JEV endpoint
            eval_state = format_conversation_state(
                payload,
                include_state=include_state,
                include_reasoning=include_reasoning,
            )

            attempt = 0
            call_succeeded = False
            evaluation_result: Optional[Dict[str, Any]] = None
            total_tokens = 0
            model_name = DEFAULT_MODEL_NAME

            while not call_succeeded:
                attempt += 1
                stats["attempts"] += 1
                stats["models"][model_key]["attempts"] += 1

                try:
                    success, reply_data, total_tokens, error_code = call_jev(
                        state=eval_state,
                        url=jev_url,
                    )
                except Exception as exc:  # pragma: no cover - defensive guard
                    success = False
                    reply_data = None
                    total_tokens = 0
                    error_code = "UNEXPECTED_ERROR"
                    logger.error(
                        "MODEL_FAILURE provider=%s model=%s file=%s index=%s retry=%s reason=%s",
                        provider,
                        model_name,
                        relative_path,
                        idx,
                        attempt,
                        exc,
                    )

                if not success or reply_data is None:
                    stats["failed"] += 1
                    stats["models"][model_key]["failed"] += 1
                    logger.error(
                        "MODEL_FAILURE provider=%s model=%s file=%s index=%s retry=%s error_code=%s",
                        provider,
                        model_name,
                        relative_path,
                        idx,
                        attempt,
                        error_code or "UNKNOWN_ERROR",
                    )

                    if _is_fatal_error(error_code):
                        consecutive_errors += 1
                        logger.warning(
                            "Consecutive errors: %s/%s (error_code=%s)",
                            consecutive_errors,
                            MAX_CONSECUTIVE_ERRORS,
                            error_code,
                        )
                        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            logger.error(
                                "ABORT: %s consecutive errors (%s). Stopping pipeline.",
                                consecutive_errors,
                                error_code,
                            )
                            return stats
                    else:
                        consecutive_errors = 0

                    if RETRY_WAIT_SECONDS > 0:
                        time.sleep(RETRY_WAIT_SECONDS)
                    continue

                # Successful call
                consecutive_errors = 0
                evaluation_result = reply_data
                model_name = reply_data.get("model", model_name)
                call_succeeded = True

            # Prepare output record without judge_1 / judge_2 wrappers
            # Direct embedding of JEV JSON evaluation response
            output_model_info = {
                "provider": provider,
                "model_name": model_name,
            }

            existing_record = None
            for row in existing_rows:
                if row.get("source_file") == relative_path and row.get("conversation_index") == idx:
                    existing_record = row
                    break

            if existing_record is not None:
                existing_record["model"] = output_model_info
                existing_record["total_tokens"] = total_tokens
                existing_record["evaluation"] = evaluation_result
            else:
                result_record = {
                    "source_file": relative_path,
                    "conversation_index": idx,
                    "model": output_model_info,
                    "total_tokens": total_tokens,
                    "evaluation": evaluation_result,
                }
                existing_rows.append(result_record)

            _write_output_entries(output_file, existing_rows)

            state[conversation_key] = {
                "provider": provider,
                "model_name": model_name,
                "status": "evaluated",
            }
            _save_state(output_model_dir, state)

            stats["saved"] += 1
            stats["models"][model_key]["saved"] += 1
            evaluated_count += 1

            logger.info(
                "EVALUATED provider=%s model=%s file=%s index=%s total_tokens=%s output=%s",
                provider,
                model_name,
                relative_path,
                idx,
                total_tokens,
                output_file,
            )

            if wait_seconds > 0:
                time.sleep(wait_seconds)

    return stats


def run_pipeline(
    max_conversations: Optional[int] = None,
    source_model_dir: Optional[str] = None,
    data_dir: str = "data",
    output_dir: str = "jev_output",
    jev_url: Optional[str] = None,
    provider: str = DEFAULT_PROVIDER,
    wait_seconds: float = 0.0,
    include_state: bool = False,
    include_reasoning: bool = False,
    include_state_reasoning: bool = False,
) -> int:
    """Evaluate up to max_conversations from a single input model folder using the JEV endpoint."""
    load_dotenv()
    _configure_logging(output_dir)

    if max_conversations is None or max_conversations < 0:
        raise ValueError("max_conversations is required and must be non-negative")
    if source_model_dir is None or not source_model_dir.strip():
        raise ValueError("source_model_dir is required")

    resolved_jev_url = jev_url or os.getenv("JEV_URL") or DEFAULT_JEV_URL

    data_root = Path(data_dir)
    if not data_root.exists():
        raise FileNotFoundError(f"Data directory not found: {data_root}")

    source_root = data_root / source_model_dir
    if not source_root.exists():
        raise FileNotFoundError(f"Input model folder not found: {source_root}")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = time.monotonic()
    model_state = _load_state(output_root / source_model_dir)

    stats = _evaluate_source_folder(
        data_dir=data_root,
        output_dir=output_root,
        source_model_dir=source_model_dir,
        max_conversations=max_conversations,
        jev_url=resolved_jev_url,
        provider=provider,
        wait_seconds=wait_seconds,
        state=model_state,
        include_state=include_state,
        include_reasoning=include_reasoning,
        include_state_reasoning=include_state_reasoning,
    )

    summary = _format_run_summary(stats, time.monotonic() - started_at)
    print(summary)
    logger.info(summary)
    return stats["saved"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Socratic conversations directly with JEV model.")
    parser.add_argument(
        "--source-model-dir",
        type=str,
        required=True,
        help="Input model folder under data to evaluate, such as Google_gemini-2.5-flash-lite.",
    )
    parser.add_argument(
        "--max-conversations",
        type=int,
        required=True,
        help="Maximum number of conversations to evaluate from the given source model folder in this run.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Directory containing input conversation JSON files (default: data).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="jev_output",
        help="Directory where evaluated results are stored (default: jev_output).",
    )
    parser.add_argument(
        "--jev-url",
        type=str,
        default=DEFAULT_JEV_URL,
        help=f"URL of the JEV systemone endpoint (default: {DEFAULT_JEV_URL}).",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=DEFAULT_PROVIDER,
        help=f"Provider name to record in output metadata (default: {DEFAULT_PROVIDER}).",
    )
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=0.0,
        help="Optional delay in seconds between conversation evaluations (default: 0.0).",
    )
    parser.add_argument(
        "--include-state",
        action="store_true",
        default=False,
        help="Include tutor state in conversation turns sent to JEV.",
    )
    parser.add_argument(
        "--include-reasoning",
        action="store_true",
        default=False,
        help="Include tutor reasoning in conversation turns sent to JEV.",
    )
    parser.add_argument(
        "--include-state-reasoning",
        "--include-state-and-reasoning",
        dest="include_state_reasoning",
        action="store_true",
        default=False,
        help="Include both tutor state and reasoning in conversation turns sent to JEV.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    count = run_pipeline(
        max_conversations=args.max_conversations,
        source_model_dir=args.source_model_dir,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        jev_url=args.jev_url,
        provider=args.provider,
        wait_seconds=args.wait_seconds,
        include_state=args.include_state,
        include_reasoning=args.include_reasoning,
        include_state_reasoning=args.include_state_reasoning,
    )
    print(f"Evaluated {count} conversation(s).")


if __name__ == "__main__":
    main()
