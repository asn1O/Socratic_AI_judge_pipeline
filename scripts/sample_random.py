#!/usr/bin/env python3
"""
Randomly select conversations for human annotation across parallel data and judge trees.

Aligns records across:
- data/: conversations
- output/: LLM judge outputs
- jev_output/: JEV judge outputs
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def discover_records(data_dir: Union[str, Path]) -> List[Tuple[str, int]]:
    """
    Recursively discover all JSON files under data_dir and enumerate conversations.

    Returns a list of (relative_path, index) tuples, sorted by relative_path
    and index to ensure deterministic ordering before sampling.
    """
    data_path = Path(data_dir)
    if not data_path.exists() or not data_path.is_dir():
        raise FileNotFoundError(f"Data directory '{data_dir}' does not exist or is not a directory.")

    records: List[Tuple[str, int]] = []
    json_paths: List[Path] = []

    for root, _, files in os.walk(data_path):
        for fname in files:
            if fname.endswith(".json"):
                json_paths.append(Path(root) / fname)

    # Sort file paths to ensure deterministic discovery order
    json_paths.sort()

    for file_path in json_paths:
        rel_path = file_path.relative_to(data_path).as_posix()
        with open(file_path, "r", encoding="utf-8") as f:
            file_records = json.load(f)

        if not isinstance(file_records, list):
            raise ValueError(
                f"Expected JSON array in '{file_path}', but found {type(file_records).__name__}."
            )

        for idx in range(len(file_records)):
            records.append((rel_path, idx))

    # Sort record references by relative path and index before sampling
    records.sort(key=lambda r: (r[0], r[1]))
    return records


def sample_random_records(
    records: Sequence[Tuple[str, int]],
    sample_size: int,
    seed: int = 42,
) -> List[Tuple[str, int]]:
    """
    Randomly select unique conversations without replacement.

    Stops with ValueError if total conversations discovered is less than sample_size.
    """
    total_records = len(records)
    if total_records < sample_size:
        raise ValueError(
            f"Cannot select {sample_size} conversations: only {total_records} discovered."
        )

    rng = random.Random(seed)
    return rng.sample(records, k=sample_size)


def load_selected_records(
    selected_refs: Sequence[Tuple[str, int]],
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    sampling_strategy: str = "random",
    id_prefix: str = "RND",
) -> List[Dict[str, Any]]:
    """
    Load conversation and corresponding judge records for selected references.

    Uses a two-pass approach: groups by relative_path so each required file
    is read only once from disk, preserving the exact sampled order in output.
    """
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    jev_path = Path(jev_dir)

    # Group requested indices by relative path
    file_indices: Dict[str, List[int]] = defaultdict(list)
    for rel_path, idx in selected_refs:
        file_indices[rel_path].append(idx)

    # Cache loaded records by (rel_path, idx)
    loaded_cache: Dict[Tuple[str, int], Tuple[Any, Any, Any]] = {}

    for rel_path, indices in file_indices.items():
        d_file = data_path / rel_path
        o_file = output_path / rel_path
        j_file = jev_path / rel_path

        if not d_file.exists():
            raise FileNotFoundError(f"Missing conversation file: '{d_file}'")
        if not o_file.exists():
            raise FileNotFoundError(f"Missing LLM judge file: '{o_file}'")
        if not j_file.exists():
            raise FileNotFoundError(f"Missing JEV judge file: '{j_file}'")

        with open(d_file, "r", encoding="utf-8") as f:
            d_records = json.load(f)
        with open(o_file, "r", encoding="utf-8") as f:
            o_records = json.load(f)
        with open(j_file, "r", encoding="utf-8") as f:
            j_records = json.load(f)

        for idx in indices:
            if idx >= len(d_records):
                raise IndexError(
                    f"Index {idx} out of range in conversation file '{d_file}' (length {len(d_records)})"
                )
            if idx >= len(o_records):
                raise IndexError(
                    f"Index {idx} out of range in LLM judge file '{o_file}' (length {len(o_records)})"
                )
            if idx >= len(j_records):
                raise IndexError(
                    f"Index {idx} out of range in JEV judge file '{j_file}' (length {len(j_records)})"
                )

            loaded_cache[(rel_path, idx)] = (d_records[idx], o_records[idx], j_records[idx])

    # Build annotations in the exact sampled order
    annotations: List[Dict[str, Any]] = []
    pad_width = max(4, len(str(len(selected_refs))))

    for i, (rel_path, idx) in enumerate(selected_refs, start=1):
        conv, llm_judge, jev = loaded_cache[(rel_path, idx)]
        annotations.append({
            "annotation_id": f"{id_prefix}-{i:0{pad_width}d}",
            "sampling_strategy": sampling_strategy,
            "source": {
                "relative_path": rel_path,
                "index": idx,
            },
            "conversation": conv,
            "llm_judge_output": llm_judge,
            "jev_output": jev,
        })

    return annotations


def write_annotation_set(
    annotation_dir: Union[str, Path],
    annotations: List[Dict[str, Any]],
    selected_refs: Sequence[Tuple[str, int]],
    total_discovered: int,
    sample_size: int,
    seed: int,
    data_dir: Union[str, Path],
    output_dir: Union[str, Path],
    jev_dir: Union[str, Path],
    overwrite: bool = False,
) -> None:
    """
    Write annotations.json, manifest.json, and selection_summary.json.

    Safeguards against accidental overwriting unless overwrite=True.
    """
    target_dir = Path(annotation_dir)

    if target_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output directory '{target_dir}' already exists. Use --overwrite to overwrite."
            )
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    # 1. annotations.json
    annotations_file = target_dir / "annotations.json"
    with open(annotations_file, "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)

    # 2. manifest.json
    manifest = {
        "random_seed": seed,
        "requested_sample_size": sample_size,
        "actual_sample_size": len(annotations),
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_directories": {
            "data_dir": str(Path(data_dir)),
            "output_dir": str(Path(output_dir)),
            "jev_dir": str(Path(jev_dir)),
        },
        "selected_conversations": [
            {
                "annotation_id": item["annotation_id"],
                "relative_path": item["source"]["relative_path"],
                "index": item["source"]["index"],
            }
            for item in annotations
        ],
    }
    manifest_file = target_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # 3. selection_summary.json
    per_subfolder: Dict[str, int] = defaultdict(int)
    per_file: Dict[str, int] = defaultdict(int)

    for rel_path, _ in selected_refs:
        subfolder = Path(rel_path).parent.as_posix()
        per_subfolder[subfolder] += 1
        per_file[rel_path] += 1

    summary = {
        "total_conversations_discovered": total_discovered,
        "number_selected": len(annotations),
        "random_seed": seed,
        "selected_per_subfolder": dict(sorted(per_subfolder.items())),
        "selected_per_file": dict(sorted(per_file.items())),
    }
    summary_file = target_dir / "selection_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Randomly select conversations for human annotation."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path to directory containing source conversations (default: data).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Path to directory containing LLM judge outputs (default: output).",
    )
    parser.add_argument(
        "--jev-dir",
        type=Path,
        default=Path("jev_output"),
        help="Path to directory containing JEV judge outputs (default: jev_output).",
    )
    parser.add_argument(
        "--annotation-dir",
        type=Path,
        default=Path("annotation_set/random_sample"),
        help="Path to output annotation directory (default: annotation_set/random_sample).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=240,
        help="Number of conversations to sample (default: 240).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling (default: 42).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output directory if present.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    print(f"Discovering conversations in '{args.data_dir}'...")
    try:
        all_records = discover_records(args.data_dir)
    except Exception as e:
        print(f"Error during record discovery: {e}", file=sys.stderr)
        return 1

    total_discovered = len(all_records)
    print(f"Discovered {total_discovered} conversations across JSON files.")

    try:
        selected_refs = sample_random_records(
            records=all_records,
            sample_size=args.sample_size,
            seed=args.seed,
        )
    except ValueError as e:
        print(f"Sampling error: {e}", file=sys.stderr)
        return 1

    print(
        f"Selected {len(selected_refs)} conversations uniformly without replacement (seed={args.seed})."
    )

    print("Loading conversation and judge records...")
    try:
        annotations = load_selected_records(
            selected_refs=selected_refs,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            sampling_strategy="random",
            id_prefix="RND",
        )
    except Exception as e:
        print(f"Error loading records: {e}", file=sys.stderr)
        return 1

    print(f"Writing annotation set to '{args.annotation_dir}'...")
    try:
        write_annotation_set(
            annotation_dir=args.annotation_dir,
            annotations=annotations,
            selected_refs=selected_refs,
            total_discovered=total_discovered,
            sample_size=args.sample_size,
            seed=args.seed,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            jev_dir=args.jev_dir,
            overwrite=args.overwrite,
        )
    except FileExistsError as e:
        print(f"Output error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error writing annotation set: {e}", file=sys.stderr)
        return 1

    print(f"Successfully generated annotation set in '{args.annotation_dir}':")
    print(f"  - annotations.json ({len(annotations)} records)")
    print("  - manifest.json")
    print("  - selection_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
