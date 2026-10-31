"""data_loader.py - Load and index conversation datasets from annotation_set/."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("annotation_ui.data_loader")

SAMPLES_META = {
    "random_sample": {
        "key": "random_sample",
        "display_name": "Random Sample",
        "id_prefix": "RND",
        "expected_count": 240,
        "excel_file": "random_sample_annotator.xlsx",
        "sheet_name": "Random_Sample_Annotator",
        "description": "Unbiased baseline sample (240 conversations)",
    },
    "metric_profile_sample": {
        "key": "metric_profile_sample",
        "display_name": "Metric-Profile Sample",
        "id_prefix": "MP",
        "expected_count": 120,
        "excel_file": "metric_profile_sample_annotator.xlsx",
        "sheet_name": "Metric_Profile_Annotator",
        "description": "Targeted metric strengths & weaknesses (120 conversations)",
    },
    "judge_disagreement_sample": {
        "key": "judge_disagreement_sample",
        "display_name": "Judge-Disagreement Sample",
        "id_prefix": "JD",
        "expected_count": 40,
        "excel_file": "judge_disagreement_sample_annotator.xlsx",
        "sheet_name": "Judge_Disagreement_Annotator",
        "description": "Severely divergent judge evaluations (40 conversations)",
    },
}


class AnnotationDataLoader:
    """Manages loading and indexing of annotation sets."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.annotation_set_dir = self.base_dir / "annotation_set"
        self._samples: Dict[str, List[Dict[str, Any]]] = {}
        self._id_maps: Dict[str, Dict[str, Tuple[int, Dict[str, Any]]]] = {}
        self._id_lists: Dict[str, List[str]] = {}
        self._load_all_samples()

    def _load_all_samples(self) -> None:
        """Load and index JSON files for all sample sets."""
        for key, meta in SAMPLES_META.items():
            json_path = self.annotation_set_dir / key / "annotations.json"
            if not json_path.exists():
                logger.warning("File not found: %s", json_path)
                self._samples[key] = []
                self._id_maps[key] = {}
                self._id_lists[key] = []
                continue

            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    records: List[Dict[str, Any]] = json.load(f)
            except Exception as e:
                logger.error("Failed to load %s: %s", json_path, e)
                records = []

            self._samples[key] = records
            id_map: Dict[str, Tuple[int, Dict[str, Any]]] = {}
            id_list: List[str] = []
            for idx, rec in enumerate(records):
                ann_id = rec.get("annotation_id", "")
                if ann_id:
                    id_map[ann_id] = (idx, rec)
                    id_list.append(ann_id)

            self._id_maps[key] = id_map
            self._id_lists[key] = id_list
            logger.info("Loaded %d records for %s", len(records), key)

    def get_sample_keys(self) -> List[str]:
        return list(SAMPLES_META.keys())

    def get_sample_meta(self, sample_key: str) -> Optional[Dict[str, Any]]:
        return SAMPLES_META.get(sample_key)

    def get_id_list(self, sample_key: str) -> List[str]:
        return self._id_lists.get(sample_key, [])

    def get_conversation_by_id(
        self, sample_key: str, annotation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve conversation record, previous and next IDs, and progress info."""
        id_map = self._id_maps.get(sample_key, {})
        if annotation_id not in id_map:
            return None

        idx, record = id_map[annotation_id]
        id_list = self._id_lists[sample_key]
        total = len(id_list)

        prev_id = id_list[idx - 1] if idx > 0 else None
        next_id = id_list[idx + 1] if idx < total - 1 else None

        return {
            "record": record,
            "index": idx + 1,  # 1-based index for UI
            "total": total,
            "prev_id": prev_id,
            "next_id": next_id,
            "sample_key": sample_key,
        }

    def get_conversation_by_index(
        self, sample_key: str, index_1_based: int
    ) -> Optional[Dict[str, Any]]:
        """Retrieve conversation record by 1-based index."""
        id_list = self._id_lists.get(sample_key, [])
        if not (1 <= index_1_based <= len(id_list)):
            return None
        ann_id = id_list[index_1_based - 1]
        return self.get_conversation_by_id(sample_key, ann_id)
