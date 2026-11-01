"""excel_manager.py - Read and update human annotation scores in Excel files."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

logger = logging.getLogger("annotation_ui.excel_manager")

METRIC_COLUMNS = [
    ("socratic_guidance", 2, "int", (0, 3)),
    ("scaffolding", 3, "int", (0, 3)),
    ("state_adaptation", 4, "int", (0, 3)),
    ("diagnosis", 5, "int", (0, 3)),
    ("student_agency", 6, "int", (0, 3)),
    ("progression", 7, "int", (0, 3)),
    ("coherence", 8, "int", (0, 3)),
    ("correctness", 9, "bool", None),
    ("overall_score_out_of_5", 10, "float", (0.0, 5.0)),
    ("overall_score_out_of_10", 11, "float", (0.0, 10.0)),
]

SAMPLE_EXCEL_MAP = {
    "random_sample": {
        "file_name": "random_sample_annotator.xlsx",
        "tab_name": "Random_Sample_Annotator",
    },
    "metric_profile_sample": {
        "file_name": "metric_profile_sample_annotator.xlsx",
        "tab_name": "Metric_Profile_Annotator",
    },
    "judge_disagreement_sample": {
        "file_name": "judge_disagreement_sample_annotator.xlsx",
        "tab_name": "Judge_Disagreement_Annotator",
    },
}

UNIFIED_WORKBOOK = "annotation_evaluation_sheets.xlsx"


class ExcelAnnotationManager:
    """Thread-safe manager for reading and writing annotator Excel sheets."""

    def __init__(self, excel_dir: Path):
        self.excel_dir = excel_dir.resolve()
        self._lock = threading.Lock()

    def _get_file_path(self, sample_key: str) -> Path:
        info = SAMPLE_EXCEL_MAP.get(sample_key)
        if not info:
            raise ValueError(f"Unknown sample key: {sample_key}")
        return self.excel_dir / info["file_name"]

    def _get_unified_path(self) -> Path:
        return self.excel_dir / UNIFIED_WORKBOOK

    def get_scores(self, sample_key: str, annotation_id: str) -> Optional[Dict[str, Any]]:
        """Read saved scores for an annotation ID from the sample's Excel file."""
        file_path = self._get_file_path(sample_key)
        if not file_path.exists():
            logger.warning("Excel file %s does not exist", file_path)
            return None

        with self._lock:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active

            target_row = None
            for row_idx in range(2, ws.max_row + 1):
                cell_id = str(ws.cell(row=row_idx, column=1).value or "").strip()
                if cell_id == annotation_id:
                    target_row = row_idx
                    break

            if target_row is None:
                return None

            scores: Dict[str, Any] = {}
            has_data = False
            for key, col_idx, dtype, _ in METRIC_COLUMNS:
                raw_val = ws.cell(row=target_row, column=col_idx).value
                if raw_val is not None:
                    has_data = True
                    if dtype == "bool":
                        if isinstance(raw_val, bool):
                            scores[key] = raw_val
                        elif str(raw_val).strip().upper() in ("TRUE", "1"):
                            scores[key] = True
                        elif str(raw_val).strip().upper() in ("FALSE", "0"):
                            scores[key] = False
                        else:
                            scores[key] = None
                    elif dtype == "int":
                        try:
                            scores[key] = int(raw_val)
                        except (ValueError, TypeError):
                            scores[key] = None
                    elif dtype == "float":
                        try:
                            scores[key] = round(float(raw_val), 2)
                        except (ValueError, TypeError):
                            scores[key] = None
                else:
                    scores[key] = None

            return scores if has_data else None

    def get_all_status(self, sample_key: str) -> Dict[str, bool]:
        """Return a mapping of annotation_id -> is_graded (True if any score exists)."""
        file_path = self._get_file_path(sample_key)
        if not file_path.exists():
            return {}

        status_map: Dict[str, bool] = {}
        with self._lock:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
            for row_idx in range(2, ws.max_row + 1):
                cell_id = str(ws.cell(row=row_idx, column=1).value or "").strip()
                if not cell_id:
                    continue
                # Graded if any metric column is non-empty
                is_graded = any(
                    ws.cell(row=row_idx, column=col_idx).value is not None
                    for _, col_idx, _, _ in METRIC_COLUMNS
                )
                status_map[cell_id] = is_graded
        return status_map

    def get_sample_summary(self, sample_key: str, valid_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Return total rows and graded count for a sample."""
        status_map = self.get_all_status(sample_key)
        if valid_ids is not None:
            valid_set = set(valid_ids)
            status_map = {k: v for k, v in status_map.items() if k in valid_set}
            total = len(valid_ids)
        else:
            total = len(status_map)
        graded = sum(1 for v in status_map.values() if v)
        return {
            "sample_key": sample_key,
            "total": total,
            "graded": graded,
            "pending": total - graded,
            "pct_completed": round((graded / max(1, total)) * 100, 1),
        }

    def save_scores(
        self,
        sample_key: str,
        annotation_id: str,
        scores: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Save scores into the individual sample workbook and the unified workbook.

        Returns:
            (success: bool, message: str)
        """
        file_path = self._get_file_path(sample_key)
        if not file_path.exists():
            return False, f"Target Excel file does not exist: {file_path.name}"

        # Clean and validate inputs
        cleaned_scores: Dict[str, Any] = {}
        for key, col_idx, dtype, bounds in METRIC_COLUMNS:
            val = scores.get(key)
            if val is None or val == "":
                cleaned_scores[key] = None
                continue

            if dtype == "bool":
                if isinstance(val, bool):
                    cleaned_scores[key] = val
                elif str(val).strip().upper() in ("TRUE", "1", "YES"):
                    cleaned_scores[key] = True
                elif str(val).strip().upper() in ("FALSE", "0", "NO"):
                    cleaned_scores[key] = False
                else:
                    return False, f"Invalid boolean for {key}: {val}"
            elif dtype == "int":
                try:
                    int_val = int(val)
                    if bounds and not (bounds[0] <= int_val <= bounds[1]):
                        return False, f"{key} must be between {bounds[0]} and {bounds[1]}"
                    cleaned_scores[key] = int_val
                except (ValueError, TypeError):
                    return False, f"Invalid integer for {key}: {val}"
            elif dtype == "float":
                try:
                    float_val = float(val)
                    if bounds and not (bounds[0] <= float_val <= bounds[1]):
                        return False, f"{key} must be between {bounds[0]} and {bounds[1]}"
                    cleaned_scores[key] = round(float_val, 2)
                except (ValueError, TypeError):
                    return False, f"Invalid decimal for {key}: {val}"

        with self._lock:
            # 1. Update Split File
            try:
                wb = openpyxl.load_workbook(file_path)
                ws = wb.active

                target_row = None
                for row_idx in range(2, ws.max_row + 1):
                    cell_id = str(ws.cell(row=row_idx, column=1).value or "").strip()
                    if cell_id == annotation_id:
                        target_row = row_idx
                        break

                if target_row is None:
                    return False, f"Annotation ID '{annotation_id}' not found in {file_path.name}"

                for key, col_idx, _, _ in METRIC_COLUMNS:
                    cell = ws.cell(row=target_row, column=col_idx)
                    cell.value = cleaned_scores[key]

                wb.save(file_path)
                logger.info("Saved scores for %s in %s (row %d)", annotation_id, file_path.name, target_row)
            except Exception as e:
                logger.exception("Failed to save to %s", file_path)
                return False, f"Error writing to {file_path.name}: {e}"

            # 2. Update Unified Workbook if present
            unified_path = self._get_unified_path()
            if unified_path.exists():
                try:
                    wb_uni = openpyxl.load_workbook(unified_path)
                    tab_name = SAMPLE_EXCEL_MAP[sample_key]["tab_name"]
                    if tab_name in wb_uni.sheetnames:
                        ws_uni = wb_uni[tab_name]
                        uni_target_row = None
                        for row_idx in range(2, ws_uni.max_row + 1):
                            cell_id = str(ws_uni.cell(row=row_idx, column=1).value or "").strip()
                            if cell_id == annotation_id:
                                uni_target_row = row_idx
                                break

                        if uni_target_row:
                            for key, col_idx, _, _ in METRIC_COLUMNS:
                                cell_uni = ws_uni.cell(row=uni_target_row, column=col_idx)
                                cell_uni.value = cleaned_scores[key]
                            wb_uni.save(unified_path)
                            logger.info("Synchronized scores to unified workbook tab %s (row %d)", tab_name, uni_target_row)
                except Exception as e:
                    logger.warning("Failed to sync unified workbook: %s", e)

        has_any_score = any(cleaned_scores[k] is not None for k, _, _, _ in METRIC_COLUMNS)
        msg = (
            f"Successfully saved scores for {annotation_id} to Excel."
            if has_any_score
            else f"Emptied/cleared scores for {annotation_id} in Excel (row {target_row})."
        )
        return True, msg
