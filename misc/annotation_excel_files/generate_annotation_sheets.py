#!/usr/bin/env python3
"""generate_annotation_sheets.py - Generate Excel annotation workbooks for Socratic AI evaluation.

Creates a unified 6-tab Excel workbook (and optional 6 separate files) covering the 3 annotation sets:
1. Random Sample (240 convos)
2. Metric-Profile Sample (120 convos)
3. Judge-Disagreement Sample (40 convos)

Each set has 2 tabs:
- Annotator Tab: annotation_id, 7 metrics (0-3), boolean correctness, overall out of 5, overall out of 10.
- Judge Tab: annotation_id, and for each metric 5 grouped columns (Judge 1, Judge 2, Judge 3, Judge 4, Judge 5).

Judge Ensemble:
- Judge 1: beam:cloud (from output/)
- Judge 2: gpt-oss:120b (from output/)
- Judge 3: minimax-m3.1-flash (from output/)
- Judge 4: imajev-4b (from jev_output/)
- Judge 5: imajev-4b v2 (from jev_output2/ or output/judge_5; filled as evaluation completes)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("generate_annotation_sheets")

NUMERIC_METRICS = [
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
]

METRIC_LABELS = {
    "socratic_guidance": "Socratic Guidance",
    "scaffolding": "Scaffolding",
    "state_adaptation": "State Adaptation",
    "diagnosis": "Diagnosis",
    "student_agency": "Student Agency",
    "progression": "Progression",
    "coherence": "Coherence",
    "correctness": "Correctness",
}

BOOLEAN_METRIC = "correctness"
ALL_METRICS = NUMERIC_METRICS + [BOOLEAN_METRIC]

SAMPLE_CONFIGS = [
    {
        "key": "random_sample",
        "name": "Random Sample",
        "annotator_tab": "Random_Sample_Annotator",
        "judge_tab": "Random_Sample_Judges",
        "id_prefix": "RND",
        "count": 240,
    },
    {
        "key": "metric_profile_sample",
        "name": "Metric-Profile Sample",
        "annotator_tab": "Metric_Profile_Annotator",
        "judge_tab": "Metric_Profile_Judges",
        "id_prefix": "MP",
        "count": 120,
    },
    {
        "key": "judge_disagreement_sample",
        "name": "Judge-Disagreement Sample",
        "annotator_tab": "Judge_Disagreement_Annotator",
        "judge_tab": "Judge_Disagreement_Judges",
        "id_prefix": "JD",
        "count": 40,
    },
]

# Color Palette for Excel Styling
NAVY_HEADER = "1F4E78"        # Main dark navy header
WHITE_TEXT = "FFFFFF"
LIGHT_GRAY_FILL = "F9FBFD"    # Very subtle alternating data row fill
BORDER_GRAY = "D9D9D9"

# Metric group header colors in Judge tabs (subtle distinct pastels for visual grouping)
METRIC_GROUP_COLORS = [
    "D9E1F2",  # Soft Blue (socratic_guidance)
    "E2EFDA",  # Soft Green (scaffolding)
    "FFF2CC",  # Soft Yellow (state_adaptation)
    "FCE4D6",  # Soft Peach (diagnosis)
    "EDEDED",  # Soft Slate (student_agency)
    "DDEBF7",  # Ice Blue (progression)
    "EAD1DC",  # Soft Lavender (coherence)
    "F4CCCC",  # Soft Rose (correctness)
]


def _extract_jev_metric_score(answers: Dict[str, Any], metric: str) -> Optional[int]:
    """Extract discrete argmax score (0-3) for a given metric from JEV answers."""
    m_ans = answers.get(metric, {})
    if not m_ans:
        return None
    probs = m_ans.get("probabilities", {})
    if probs:
        try:
            return int(max(probs, key=probs.get))
        except (ValueError, TypeError):
            pass
    score = m_ans.get("score")
    if score is not None:
        try:
            return int(round(float(score)))
        except (ValueError, TypeError):
            pass
    return None


def extract_judge_scores(
    record: Dict[str, Any],
    base_dir: Path,
    output_dir: Path,
    jev_dir: Path,
    jev2_dir: Path,
) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    """Extract scores for Judge 1 through Judge 5 for all metrics.
    
    Returns:
        (scores_by_judge, judge_5_found)
    """
    rel_path = record.get("source", {}).get("relative_path", "")
    idx = record.get("source", {}).get("index", 0)

    # 1. LLM Judges (1, 2, 3, or optional 4, 5)
    llm = record.get("llm_judge_output")
    if not llm and rel_path:
        out_p = output_dir / rel_path
        if out_p.exists():
            try:
                with open(out_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if idx < len(data):
                    llm = data[idx]
            except Exception as e:
                logger.debug("Failed to read output file %s: %s", out_p, e)
    llm = llm or {}

    # 2. Judge 4 (JEV 1 from annotations.json or jev_output/)
    jev1 = record.get("jev_output")
    if not jev1 and rel_path:
        j1_p = jev_dir / rel_path
        if j1_p.exists():
            try:
                with open(j1_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if idx < len(data):
                    jev1 = data[idx]
            except Exception as e:
                logger.debug("Failed to read JEV1 file %s: %s", j1_p, e)
    jev1 = jev1 or {}

    # 3. Judge 5 (JEV 2 from jev_output2/ or check output/ for judge_5)
    jev2 = None
    if rel_path:
        j2_p = jev2_dir / rel_path
        if j2_p.exists():
            try:
                with open(j2_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if idx < len(data) and "evaluation" in data[idx]:
                    jev2 = data[idx]
            except Exception as e:
                logger.debug("Failed to read JEV2 file %s: %s", j2_p, e)

    scores: Dict[str, Dict[str, Any]] = {}

    # Judge 1..3
    for j_num in [1, 2, 3]:
        j_key = f"judge_{j_num}"
        j_eval = llm.get(j_key, {}).get("evaluation", {})
        scores[f"Judge {j_num}"] = {
            m: j_eval.get(m) for m in NUMERIC_METRICS + [BOOLEAN_METRIC]
        }

    # Judge 4: first check if llm has judge_4, otherwise JEV1
    if "judge_4" in llm and "evaluation" in llm["judge_4"]:
        j4_eval = llm["judge_4"]["evaluation"]
        scores["Judge 4"] = {m: j4_eval.get(m) for m in NUMERIC_METRICS + [BOOLEAN_METRIC]}
    else:
        j4_answers = jev1.get("evaluation", {}).get("answers", {}) if jev1 else {}
        scores["Judge 4"] = {
            m: _extract_jev_metric_score(j4_answers, m) for m in NUMERIC_METRICS
        }
        scores["Judge 4"][BOOLEAN_METRIC] = None  # JEV does not evaluate booleans

    # Judge 5: check if llm has judge_5, otherwise JEV2
    judge_5_found = False
    if "judge_5" in llm and "evaluation" in llm["judge_5"]:
        j5_eval = llm["judge_5"]["evaluation"]
        scores["Judge 5"] = {m: j5_eval.get(m) for m in NUMERIC_METRICS + [BOOLEAN_METRIC]}
        judge_5_found = True
    elif jev2:
        j5_answers = jev2.get("evaluation", {}).get("answers", {})
        scores["Judge 5"] = {
            m: _extract_jev_metric_score(j5_answers, m) for m in NUMERIC_METRICS
        }
        scores["Judge 5"][BOOLEAN_METRIC] = None
        judge_5_found = any(scores["Judge 5"][m] is not None for m in NUMERIC_METRICS)
    else:
        scores["Judge 5"] = {m: None for m in ALL_METRICS}

    return scores, judge_5_found


def _apply_border(cell: Any, thin: Side) -> None:
    cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)


def build_annotator_sheet(
    ws: Any,
    records: List[Dict[str, Any]],
    sample_name: str,
) -> None:
    """Populate the human annotator tab with annotation IDs and clean entry columns."""
    thin = Side(border_style="thin", color=BORDER_GRAY)
    header_fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color=WHITE_TEXT)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers = [
        ("annotation_id", "Annotation ID", 16),
        ("socratic_guidance", "Socratic Guidance (0-3)", 18),
        ("scaffolding", "Scaffolding (0-3)", 16),
        ("state_adaptation", "State Adaptation (0-3)", 18),
        ("diagnosis", "Diagnosis (0-3)", 16),
        ("student_agency", "Student Agency (0-3)", 16),
        ("progression", "Progression (0-3)", 16),
        ("coherence", "Coherence (0-3)", 16),
        ("correctness", "Correctness (Boolean)", 18),
        ("overall_score_out_of_5", "Overall Score (out of 5)", 18),
        ("overall_score_out_of_10", "Overall Score (out of 10)", 18),
    ]

    # Header Row
    ws.row_dimensions[1].height = 28
    for col_idx, (_, label, width) in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        _apply_border(cell, thin)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Data Validation Rules
    # 1. 0 to 3 for metrics
    dv_0_to_3 = DataValidation(
        type="whole",
        operator="between",
        formula1=0,
        formula2=3,
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid Score",
        error="Please enter an integer between 0 and 3.",
    )
    ws.add_data_validation(dv_0_to_3)

    # 2. Boolean TRUE/FALSE
    dv_bool = DataValidation(
        type="list",
        formula1='"TRUE,FALSE"',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid Boolean",
        error="Please select TRUE or FALSE.",
    )
    ws.add_data_validation(dv_bool)

    # 3. Overall out of 5
    dv_5 = DataValidation(
        type="decimal",
        operator="between",
        formula1=0,
        formula2=5,
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid Score",
        error="Please enter a score between 0 and 5.",
    )
    ws.add_data_validation(dv_5)

    # 4. Overall out of 10
    dv_10 = DataValidation(
        type="decimal",
        operator="between",
        formula1=0,
        formula2=10,
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid Score",
        error="Please enter a score between 0 and 10.",
    )
    ws.add_data_validation(dv_10)

    zebra_fill = PatternFill(start_color=LIGHT_GRAY_FILL, end_color=LIGHT_GRAY_FILL, fill_type="solid")
    id_font = Font(name="Calibri", size=11, bold=True)
    body_font = Font(name="Calibri", size=11)

    for row_idx, rec in enumerate(records, start=2):
        ws.row_dimensions[row_idx].height = 20
        is_zebra = (row_idx % 2 == 1)

        # Col 1: ID
        id_cell = ws.cell(row=row_idx, column=1, value=rec.get("annotation_id", ""))
        id_cell.font = id_font
        id_cell.alignment = center_align
        _apply_border(id_cell, thin)
        if is_zebra:
            id_cell.fill = zebra_fill

        # Cols 2 to 11: Empty cells ready for entry
        for col_idx in range(2, 12):
            cell = ws.cell(row=row_idx, column=col_idx, value=None)
            cell.font = body_font
            cell.alignment = center_align
            _apply_border(cell, thin)
            if is_zebra:
                cell.fill = zebra_fill

    # Apply validation ranges
    max_row = len(records) + 1
    if max_row >= 2:
        # cols 2-8 (B to H) for 0-3
        dv_0_to_3.add(f"B2:H{max_row}")
        # col 9 (I) for bool
        dv_bool.add(f"I2:I{max_row}")
        # col 10 (J) for out of 5
        dv_5.add(f"J2:J{max_row}")
        # col 11 (K) for out of 10
        dv_10.add(f"K2:K{max_row}")

    # Freeze top row and Column A
    ws.freeze_panes = "B2"


def build_judge_sheet(
    ws: Any,
    records: List[Dict[str, Any]],
    scores_list: List[Dict[str, Dict[str, Any]]],
    sample_name: str,
) -> None:
    """Populate the judge evaluation scores tab with 5 columns grouped under each metric."""
    thin = Side(border_style="thin", color=BORDER_GRAY)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    header_font_l1 = Font(name="Calibri", size=11, bold=True, color="1F4E78")
    header_font_l2 = Font(name="Calibri", size=9, bold=True, color="333333")
    id_header_fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
    id_header_font = Font(name="Calibri", size=11, bold=True, color=WHITE_TEXT)

    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 24

    # Column A: Annotation ID spanning row 1 and 2
    ws.merge_cells("A1:A2")
    a1_cell = ws.cell(row=1, column=1, value="Annotation ID")
    a1_cell.fill = id_header_fill
    a1_cell.font = id_header_font
    a1_cell.alignment = center_align
    _apply_border(a1_cell, thin)
    _apply_border(ws.cell(row=2, column=1), thin)
    ws.column_dimensions["A"].width = 16

    col_idx = 2
    metric_ranges: List[Tuple[int, int]] = []

    judges = ["Judge 1", "Judge 2", "Judge 3", "Judge 4", "Judge 5"]

    for m_i, metric in enumerate(ALL_METRICS):
        start_col = col_idx
        end_col = col_idx + 4
        metric_ranges.append((start_col, end_col))

        color_hex = METRIC_GROUP_COLORS[m_i % len(METRIC_GROUP_COLORS)]
        group_fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")

        # Row 1: Merged metric group title
        ws.merge_cells(start_row=1, start_column=start_col, end_row=1, end_column=end_col)
        m_label = METRIC_LABELS.get(metric, metric)
        if metric == BOOLEAN_METRIC:
            m_label += " (Boolean)"
        else:
            m_label += " (0-3)"

        m_cell = ws.cell(row=1, column=start_col, value=m_label)
        m_cell.fill = group_fill
        m_cell.font = header_font_l1
        m_cell.alignment = center_align
        for c in range(start_col, end_col + 1):
            _apply_border(ws.cell(row=1, column=c), thin)

        # Row 2: Sub-headers for Judge 1 through Judge 5
        for j_offset, j_name in enumerate(judges):
            curr_c = start_col + j_offset
            sub_cell = ws.cell(row=2, column=curr_c, value=j_name)
            sub_cell.fill = group_fill
            sub_cell.font = header_font_l2
            sub_cell.alignment = center_align
            _apply_border(sub_cell, thin)
            ws.column_dimensions[get_column_letter(curr_c)].width = 11

        col_idx = end_col + 1

    # Data Rows
    zebra_fill = PatternFill(start_color=LIGHT_GRAY_FILL, end_color=LIGHT_GRAY_FILL, fill_type="solid")
    id_font = Font(name="Calibri", size=11, bold=True)
    body_font = Font(name="Calibri", size=10)
    missing_j5_font = Font(name="Calibri", size=10, italic=True, color="888888")

    for row_offset, (rec, rec_scores) in enumerate(zip(records, scores_list)):
        row_idx = row_offset + 3
        ws.row_dimensions[row_idx].height = 19
        is_zebra = (row_offset % 2 == 1)

        # Col 1: ID
        id_cell = ws.cell(row=row_idx, column=1, value=rec.get("annotation_id", ""))
        id_cell.font = id_font
        id_cell.alignment = center_align
        _apply_border(id_cell, thin)
        if is_zebra:
            id_cell.fill = zebra_fill

        # Data for each metric and judge
        c_pointer = 2
        for metric in ALL_METRICS:
            for j_name in judges:
                val = rec_scores.get(j_name, {}).get(metric)
                cell = ws.cell(row=row_idx, column=c_pointer)
                cell.alignment = center_align
                _apply_border(cell, thin)

                if val is not None:
                    cell.value = val
                    cell.font = body_font
                else:
                    cell.value = None
                    cell.font = missing_j5_font

                if is_zebra:
                    cell.fill = zebra_fill

                c_pointer += 1

    # Freeze panes at B3 (keeps Row 1, 2 and Column A locked)
    ws.freeze_panes = "B3"


def create_annotation_workbook(
    base_dir: Path,
    output_excel_path: Path,
    output_dir: Path,
    jev_dir: Path,
    jev2_dir: Path,
    annotation_set_dir: Path,
    split_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the consolidated 6-tab Excel workbook and optionally individual files."""
    wb = openpyxl.Workbook()
    # Remove default empty sheet
    wb.remove(wb.active)

    stats = {
        "total_records": 0,
        "sets": {},
        "judge_5_total_filled": 0,
    }

    if split_dir:
        split_dir.mkdir(parents=True, exist_ok=True)

    for cfg in SAMPLE_CONFIGS:
        sample_key = cfg["key"]
        sample_path = annotation_set_dir / sample_key / "annotations.json"
        if not sample_path.exists():
            logger.warning("Annotations file not found for %s at %s", sample_key, sample_path)
            continue

        with open(sample_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        logger.info("Loaded %d records for %s", len(records), cfg["name"])

        # Extract judge scores
        scores_list: List[Dict[str, Dict[str, Any]]] = []
        j5_filled_count = 0
        for rec in records:
            s_dict, has_j5 = extract_judge_scores(rec, base_dir, output_dir, jev_dir, jev2_dir)
            scores_list.append(s_dict)
            if has_j5:
                j5_filled_count += 1

        stats["total_records"] += len(records)
        stats["judge_5_total_filled"] += j5_filled_count
        stats["sets"][sample_key] = {
            "count": len(records),
            "j5_filled": j5_filled_count,
            "j5_pending": len(records) - j5_filled_count,
        }

        # 1. Annotator Sheet (in unified workbook)
        ws_annotator = wb.create_sheet(title=cfg["annotator_tab"])
        build_annotator_sheet(ws_annotator, records, cfg["name"])

        # 2. Judge Sheet (in unified workbook)
        ws_judge = wb.create_sheet(title=cfg["judge_tab"])
        build_judge_sheet(ws_judge, records, scores_list, cfg["name"])

        # Optional separate workbooks
        if split_dir:
            # Individual file for annotator
            wb_ann = openpyxl.Workbook()
            ws_ann_single = wb_ann.active
            ws_ann_single.title = cfg["annotator_tab"]
            build_annotator_sheet(ws_ann_single, records, cfg["name"])
            ann_file = split_dir / f"{sample_key}_annotator.xlsx"
            wb_ann.save(ann_file)

            # Individual file for judges
            wb_jdg = openpyxl.Workbook()
            ws_jdg_single = wb_jdg.active
            ws_jdg_single.title = cfg["judge_tab"]
            build_judge_sheet(ws_jdg_single, records, scores_list, cfg["name"])
            jdg_file = split_dir / f"{sample_key}_judges.xlsx"
            wb_jdg.save(jdg_file)

    output_excel_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_excel_path)
    logger.info("Saved unified 6-tab Excel workbook to %s", output_excel_path)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate 6-tab Excel workbook for human annotation and multi-judge comparison."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("annotation_evaluation_sheets.xlsx"),
        help="Target output path for the unified Excel file.",
    )
    parser.add_argument(
        "--split-dir",
        type=Path,
        default=Path("annotation_excel_files"),
        help="Directory to save individual Excel files (set to empty string to disable).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path to raw conversation data directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Path to LLM judge outputs directory.",
    )
    parser.add_argument(
        "--jev-dir",
        type=Path,
        default=Path("jev_output"),
        help="Path to standard JEV evaluations directory (Judge 4).",
    )
    parser.add_argument(
        "--jev2-dir",
        type=Path,
        default=Path("jev_output2"),
        help="Path to JEV v2 evaluations directory (Judge 5).",
    )
    parser.add_argument(
        "--annotation-set-dir",
        type=Path,
        default=Path("annotation_set"),
        help="Path to human annotation sets directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(__file__).resolve().parent.parent

    split_dir = args.split_dir if str(args.split_dir).strip() else None

    logger.info("=== Socratic AI Annotation Excel Generator ===")
    logger.info("Unified Output: %s", args.output)
    if split_dir:
        logger.info("Split Files Dir: %s", split_dir)
    logger.info("Judge 4 Source: %s", args.jev_dir)
    logger.info("Judge 5 Source: %s", args.jev2_dir)

    stats = create_annotation_workbook(
        base_dir=base_dir,
        output_excel_path=args.output,
        output_dir=args.output_dir,
        jev_dir=args.jev_dir,
        jev2_dir=args.jev2_dir,
        annotation_set_dir=args.annotation_set_dir,
        split_dir=split_dir,
    )

    print("\n" + "=" * 60)
    print("           ANNOTATION EXCEL GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total Evaluated Conversations: {stats['total_records']}")
    print(f"Judge 5 (JEV2) Filled: {stats['judge_5_total_filled']} / {stats['total_records']} ({stats['judge_5_total_filled']/max(1, stats['total_records'])*100:.1f}%)")
    print("-" * 60)
    for k, info in stats["sets"].items():
        pct = (info["j5_filled"] / max(1, info["count"])) * 100
        print(f"• {k:<26}: {info['count']:>3} rows | Judge 5 filled: {info['j5_filled']:>3}/{info['count']} ({pct:.1f}%) | Pending: {info['j5_pending']}")
    print("=" * 60)
    print(f"Unified File: {args.output.resolve()}")
    if split_dir:
        print(f"Individual Files: {split_dir.resolve()}/*.xlsx")
    print("\nNote: When the 5th judge evaluation completes, simply re-run this script:")
    print("      python3 scripts/generate_annotation_sheets.py")
    print("and the remaining Judge 5 columns will automatically be filled.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
