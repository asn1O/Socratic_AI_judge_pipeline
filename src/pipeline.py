"""Evaluate Socratic conversations with the judge prompt and persist results by model."""

import argparse
import json
import logging
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

try:
    from .model import Model
except ImportError:  # pragma: no cover
    from model import Model

try:
    from .prompt_generator import DatasetPromptGenerator
except ImportError:  # pragma: no cover
    from prompt_generator import DatasetPromptGenerator

MODEL_WAIT_SECONDS = 60
EVALUATION_REQUIRED_FIELDS = [
    "correctness",
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
    "premature_answer",
    "hallucination",
    "evidence",
]
EVALUATION_EVIDENCE_FIELDS = [
    "correctness",
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
    "premature_answer",
    "hallucination",
]
EVALUATION_NUMERIC_FIELDS = [
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
]

logger = logging.getLogger("pipeline")
logger.setLevel(logging.INFO)
logger.propagate = False


def _generator_id() -> str:
    """Return the worker identifier used to distinguish generated files."""
    return os.getenv("DATASET_GENERATOR_ID", "unknown").strip() or "unknown"


def _configure_logging(output_dir: str, model_name: Optional[str] = None) -> None:
    """Configure a shared pipeline logger for the current evaluation run."""
    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if model_name:
        safe_model_name = model_name.replace("/", "_").replace(":", "-")
        log_path = log_dir / f"{_generator_id()}.{safe_model_name}.log"
    else:
        log_path = log_dir / f"{_generator_id()}.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Remove existing FileHandlers so we can reconfigure per-model if needed
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


def _model_output_dir(model: Model, output_dir: str) -> Path:
    """Return the results directory for one model, matching the input layout style."""
    model_name = f"{model.provider}_{model.model_name}".replace("/", "_")
    return Path(output_dir) / model_name


def _relative_data_path(file_path: Path, data_dir: Path) -> str:
    return file_path.relative_to(data_dir).as_posix()


def _load_models(models_path: str) -> List[Model]:
    """Load the configured models directly into an array."""
    path = Path(models_path)
    if not path.is_file():
        raise FileNotFoundError(f"models file not found: {models_path}")

    load_dotenv()
    with path.open("r", encoding="utf-8") as file:
        model_data = json.load(file)

    if not isinstance(model_data, list):
        raise ValueError("models file must contain a JSON array")

    return [Model.from_dict(entry) for entry in model_data]


def _discover_conversation_files(data_dir: Path) -> List[Path]:
    """Return all JSON files under the configured data directory."""
    files: List[Path] = []
    for path in sorted(data_dir.rglob("*.json")):
        if path.name.endswith("_state.json"):
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


def _state_path_for_source_dir(source_dir: Path, judge_number: int = 1) -> Path:
    if judge_number > 1:
        return source_dir / f"evaluation_state_{judge_number}.json"
    return source_dir / "evaluation_state.json"


def _validate_evaluation_payload(payload: Any) -> bool:
    """Ensure the judge result matches the required contract exactly."""
    if not isinstance(payload, dict):
        return False

    if list(payload.keys()) != EVALUATION_REQUIRED_FIELDS:
        return False

    if not isinstance(payload["correctness"], bool):
        return False
    if not isinstance(payload["premature_answer"], bool):
        return False
    if not isinstance(payload["hallucination"], bool):
        return False

    for field in EVALUATION_NUMERIC_FIELDS:
        if not isinstance(payload[field], int) or payload[field] not in (0, 1, 2, 3):
            return False

    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return False
    if list(evidence.keys()) != EVALUATION_EVIDENCE_FIELDS:
        return False
    if any(not isinstance(evidence[field], str) for field in EVALUATION_EVIDENCE_FIELDS):
        return False

    return True


def _load_state(source_dir: Path, judge_number: int = 1) -> Dict[str, Dict[str, Any]]:
    """Load the persisted per-conversation evaluator metadata."""
    state_path = _state_path_for_source_dir(source_dir, judge_number)
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


def _save_state(source_dir: Path, state: Dict[str, Dict[str, Any]], judge_number: int = 1) -> None:
    """Persist evaluator metadata for every evaluated conversation."""
    source_dir.mkdir(parents=True, exist_ok=True)
    state_path = _state_path_for_source_dir(source_dir, judge_number)
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


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """Parse the first complete JSON object in a model response."""
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in response")

    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text, idx=start)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ValueError("response JSON is not a JSON object")
    return payload


def _parse_judge_response(reply: str) -> Dict[str, Any]:
    """Parse a judge model response into the evaluation JSON payload."""
    cleaned = (reply or "").strip()
    if not cleaned:
        raise ValueError("empty response")

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    return _extract_first_json_object(cleaned)


def _build_conversation_key(source_rel_path: str, index: int) -> str:
    return f"{source_rel_path}:{index}"


def _format_run_summary(stats: Dict[str, Any], duration_seconds: float) -> str:
    """Build the plain-text end-of-run report."""
    attempts = stats["attempts"]
    saved = stats["saved"]
    failed = stats["failed"]
    accept_rate = (saved / attempts * 100.0) if attempts else 0.0
    lines = [
        "\n=== Evaluation Summary ===",
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


MAX_CONSECUTIVE_HTTP_ERRORS = 3


def _is_http_error(error_code: Optional[str]) -> bool:
    """Return True if error_code represents a 4xx or 5xx HTTP response."""
    if not error_code or not error_code.startswith("HTTP_"):
        return False
    try:
        status = int(error_code[5:])
        return 400 <= status <= 599
    except ValueError:
        return False


def _maybe_evaluate_model(
    model: Model,
    data_dir: Path,
    output_dir: Path,
    source_model_dir: str,
    max_conversations: int,
    judge_number: int = 1,
    state: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Evaluate up to max_conversations from one source model folder and return statistics."""
    source_root = data_dir / source_model_dir
    if not source_root.exists():
        raise FileNotFoundError(f"Input model folder not found: {source_root}")

    output_model_dir = output_dir / source_model_dir
    output_model_dir.mkdir(parents=True, exist_ok=True)
    state = state if state is not None else _load_state(output_model_dir, judge_number)
    model_key = f"{model.provider} / {model.model_name}"
    stats = _new_stats()
    stats["models"][model_key]["model"] = model

    conversation_files = _discover_conversation_files(source_root)
    if not conversation_files:
        logger.warning("No conversation files found under %s", source_root)
        return stats

    generator = DatasetPromptGenerator()
    evaluated_for_model = 0
    consecutive_http_errors = 0

    for file_path in conversation_files:
        if evaluated_for_model >= max_conversations:
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
            if evaluated_for_model >= max_conversations:
                break

            payload = record if isinstance(record, dict) else {"conversation": record}
            if "conversation" not in payload or not isinstance(payload["conversation"], list):
                logger.warning("Skipping record %s in %s because it has no conversation list", idx, file_path)
                continue

            conversation_key = _build_conversation_key(relative_path, idx)
            if conversation_key in state:
                continue

            attempt = 0
            while True:
                attempt += 1
                prompt, _ = generator.generate_prompt(payload["conversation"])
                stats["attempts"] += 1
                stats["models"][model_key]["attempts"] += 1

                _call_failed = False
                try:
                    success, reply, total_tokens, error_code = model.call_model(prompt)
                except Exception as exc:  # pragma: no cover - defensive guard
                    stats["failed"] += 1
                    stats["models"][model_key]["failed"] += 1
                    logger.error(
                        "MODEL_FAILURE provider=%s model=%s file=%s index=%s retry=%s reason=%s",
                        model.provider,
                        model.model_name,
                        relative_path,
                        idx,
                        attempt,
                        exc,
                    )
                    _call_failed = True
                finally:
                    if _call_failed:
                        # time.sleep(MODEL_WAIT_SECONDS)
                        continue

                if not success or reply is None:
                    stats["failed"] += 1
                    stats["models"][model_key]["failed"] += 1
                    logger.error(
                        "MODEL_FAILURE provider=%s model=%s file=%s index=%s retry=%s error_code=%s",
                        model.provider,
                        model.model_name,
                        relative_path,
                        idx,
                        attempt,
                        error_code or "UNKNOWN_ERROR",
                    )
                    if _is_http_error(error_code):
                        consecutive_http_errors += 1
                        logger.warning(
                            "Consecutive HTTP errors: %s/%s (error_code=%s)",
                            consecutive_http_errors,
                            MAX_CONSECUTIVE_HTTP_ERRORS,
                            error_code,
                        )
                        if consecutive_http_errors >= MAX_CONSECUTIVE_HTTP_ERRORS:
                            logger.error(
                                "ABORT: %s consecutive HTTP errors (%s). Stopping pipeline.",
                                consecutive_http_errors,
                                error_code,
                            )
                            # time.sleep(MODEL_WAIT_SECONDS)
                            return stats
                    else:
                        consecutive_http_errors = 0
                    # time.sleep(MODEL_WAIT_SECONDS)
                    continue

                try:
                    evaluation = _parse_judge_response(reply)
                    if not _validate_evaluation_payload(evaluation):
                        raise ValueError("judge output does not match required schema")
                except (TypeError, ValueError) as exc:
                    stats["failed"] += 1
                    stats["models"][model_key]["failed"] += 1
                    logger.error(
                        "JUDGE_PARSE_FAILURE provider=%s model=%s file=%s index=%s retry=%s reason=%s",
                        model.provider,
                        model.model_name,
                        relative_path,
                        idx,
                        attempt,
                        exc,
                    )
                    # time.sleep(MODEL_WAIT_SECONDS)
                    continue

                consecutive_http_errors = 0
                break

            judge_key = f"judge_{judge_number}"
            judge_result = {
                "model": {"provider": model.provider, "model_name": model.model_name},
                "total_tokens": total_tokens,
                "evaluation": evaluation,
            }

            # Merge into existing record if the other judge already evaluated this conversation
            existing_record = None
            for row in existing_rows:
                if row.get("source_file") == relative_path and row.get("conversation_index") == idx:
                    existing_record = row
                    break

            if existing_record is not None:
                existing_record[judge_key] = judge_result
            else:
                result_record = {
                    "source_file": relative_path,
                    "conversation_index": idx,
                    judge_key: judge_result,
                }
                existing_rows.append(result_record)

            _write_output_entries(output_file, existing_rows)

            state[conversation_key] = {
                "provider": model.provider,
                "model_name": model.model_name,
                "status": "evaluated",
            }
            _save_state(output_model_dir, state, judge_number)

            stats["saved"] += 1
            stats["models"][model_key]["saved"] += 1
            evaluated_for_model += 1

            logger.info(
                "EVALUATED provider=%s model=%s file=%s index=%s total_tokens=%s output=%s",
                model.provider,
                model.model_name,
                relative_path,
                idx,
                total_tokens,
                output_file,
            )

            # time.sleep(MODEL_WAIT_SECONDS)

    return stats


def run_pipeline(
    max_conversations: Optional[int] = None,
    models_path: Optional[str] = None,
    data_dir: str = "data",
    output_dir: str = "output",
    source_model_dir: Optional[str] = None,
    judge_index: Optional[int] = None,
    judge_number: Optional[int] = None,
) -> int:
    """Evaluate up to max_conversations from a single input model folder."""
    load_dotenv()
    _configure_logging(output_dir)

    if max_conversations is None or max_conversations < 0:
        raise ValueError("max_conversations is required and must be non-negative")
    if source_model_dir is None or not source_model_dir.strip():
        raise ValueError("source_model_dir is required")
    if judge_index is None:
        raise ValueError("judge_index is required")
    if judge_number is None or judge_number not in (1, 2, 3):
        raise ValueError("judge_number is required and must be 1, 2, or 3")

    if models_path is None:
        models_path = str(Path(__file__).resolve().parent.parent / "models" / "model.json")

    models = _load_models(models_path)
    if not models:
        logger.error("No models found in %s.", models_path)
        return 0

    if judge_index < 0 or judge_index >= len(models):
        logger.error("Invalid judge index %s for models array of length %s.", judge_index, len(models))
        return 0
    models = [models[judge_index]]

    data_root = Path(data_dir)
    if not data_root.exists():
        raise FileNotFoundError(f"Data directory not found: {data_root}")

    source_root = data_root / source_model_dir
    if not source_root.exists():
        raise FileNotFoundError(f"Input model folder not found: {source_root}")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    started_at = time.monotonic()
    combined_stats = _new_stats()

    for model in models:
        _configure_logging(output_dir, model.model_name)
        model_state = _load_state(output_root / source_model_dir, judge_number)
        model_stats = _maybe_evaluate_model(
            model=model,
            data_dir=data_root,
            output_dir=output_root,
            source_model_dir=source_model_dir,
            max_conversations=max_conversations,
            judge_number=judge_number,
            state=model_state,
        )

        for model_key, stats in model_stats["models"].items():
            combined_stats["models"][model_key]["attempts"] += stats.get("attempts", 0)
            combined_stats["models"][model_key]["saved"] += stats.get("saved", 0)
            combined_stats["models"][model_key]["failed"] += stats.get("failed", 0)

        combined_stats["attempts"] += model_stats["attempts"]
        combined_stats["saved"] += model_stats["saved"]
        combined_stats["failed"] += model_stats["failed"]

    summary = _format_run_summary(combined_stats, time.monotonic() - started_at)
    print(summary)
    logger.info(summary)
    return combined_stats["saved"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Socratic conversations with configured models.")
    parser.add_argument(
        "--models-path",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "models" / "model.json"),
        help="Path to the JSON file that lists the models.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Directory containing input conversation JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory where evaluated results are stored.",
    )
    parser.add_argument(
        "--source-model-dir",
        type=str,
        required=True,
        help="Input model folder under data to evaluate, such as Google_gemini-3.6-flash.",
    )
    parser.add_argument(
        "--max-conversations",
        type=int,
        required=True,
        help="Maximum number of conversations to evaluate from the given source model folder in this run.",
    )
    parser.add_argument(
        "--judge-index",
        type=int,
        required=True,
        help="Zero-based index of the judge model to use from the model.json file.",
    )
    parser.add_argument(
        "--judge-number",
        type=int,
        required=True,
        choices=[1, 2, 3],
        help="Which judge slot this run fills (1, 2, or 3). Controls the state file and output field used.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    count = run_pipeline(
        max_conversations=args.max_conversations,
        models_path=args.models_path,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        source_model_dir=args.source_model_dir,
        judge_index=args.judge_index,
        judge_number=args.judge_number,
    )
    print(f"Evaluated {count} conversation(s).")
