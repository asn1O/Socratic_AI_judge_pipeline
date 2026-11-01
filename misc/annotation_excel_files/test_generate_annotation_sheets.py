import openpyxl
from pathlib import Path
from scripts.generate_annotation_sheets import (
    NUMERIC_METRICS,
    BOOLEAN_METRIC,
    ALL_METRICS,
    SAMPLE_CONFIGS,
    create_annotation_workbook,
)


def test_generate_annotation_sheets_structure(tmp_path):
    output_excel = tmp_path / "test_sheets.xlsx"
    split_dir = tmp_path / "split_files"
    base_dir = Path(__file__).resolve().parent.parent

    stats = create_annotation_workbook(
        base_dir=base_dir,
        output_excel_path=output_excel,
        output_dir=base_dir / "output",
        jev_dir=base_dir / "jev_output",
        jev2_dir=base_dir / "jev_output2",
        annotation_set_dir=base_dir / "annotation_set",
        split_dir=split_dir,
    )

    assert output_excel.exists()
    assert stats["total_records"] == 400

    wb = openpyxl.load_workbook(output_excel)
    expected_tabs = [
        "Random_Sample_Annotator",
        "Random_Sample_Judges",
        "Metric_Profile_Annotator",
        "Metric_Profile_Judges",
        "Judge_Disagreement_Annotator",
        "Judge_Disagreement_Judges",
    ]
    assert wb.sheetnames == expected_tabs

    # 1. Test Annotator Sheet (e.g. Judge Disagreement)
    ws_ann = wb["Judge_Disagreement_Annotator"]
    assert ws_ann.max_row == 41  # 1 header row + 40 records
    assert ws_ann.max_column == 11
    assert ws_ann.cell(1, 1).value == "Annotation ID"
    assert ws_ann.cell(1, 9).value == "Correctness (Boolean)"
    assert ws_ann.cell(1, 10).value == "Overall Score (out of 5)"
    assert ws_ann.cell(1, 11).value == "Overall Score (out of 10)"
    assert ws_ann.cell(2, 1).value == "JD-0001"
    assert ws_ann.cell(41, 1).value == "JD-0040"

    # Verify that cells for annotator entry are empty
    for c in range(2, 12):
        assert ws_ann.cell(2, c).value is None

    # 2. Test Judge Sheet
    ws_jdg = wb["Judge_Disagreement_Judges"]
    assert ws_jdg.max_row == 42  # 2 header rows + 40 records
    assert ws_jdg.max_column == 41  # 1 ID col + 8 metrics * 5 judges = 41
    assert ws_jdg.cell(1, 1).value == "Annotation ID"
    assert ws_jdg.cell(3, 1).value == "JD-0001"

    # Verify judge sub-headers in row 2
    for j_i in range(5):
        assert ws_jdg.cell(2, 2 + j_i).value == f"Judge {j_i + 1}"

    # Verify Judge 1..3 values are populated for JD-0001
    for j_i in range(3):
        col = 2 + j_i
        val = ws_jdg.cell(3, col).value
        assert val is not None
        assert isinstance(val, int)

    # Verify Judge 4 (JEV) is populated
    assert ws_jdg.cell(3, 5).value is not None  # Col 5 is Judge 4

    # Verify JD-0008 has Judge 5 populated (since it exists in jev_output2)
    # Find JD-0008 row
    jd8_row = None
    for r in range(3, ws_jdg.max_row + 1):
        if ws_jdg.cell(r, 1).value == "JD-0008":
            jd8_row = r
            break
    assert jd8_row is not None
    # Col 6 is Socratic Guidance Judge 5
    assert ws_jdg.cell(jd8_row, 6).value is not None

    # Verify split files generated
    assert (split_dir / "random_sample_annotator.xlsx").exists()
    assert (split_dir / "random_sample_judges.xlsx").exists()
    assert (split_dir / "judge_disagreement_sample_annotator.xlsx").exists()
    assert (split_dir / "judge_disagreement_sample_judges.xlsx").exists()
