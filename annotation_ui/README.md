# Socratic AI Conversation Annotation UI

A dedicated, fast, lightweight web interface for human evaluation and grading of AI tutoring conversations from `annotation_set/` directly into the evaluation Excel workbooks in `misc/annotation_excel_files/`.

---

## Quick Start

Run the following command from the repository root:

```bash
python3 annotation_ui/app.py
```

By default, the server starts at:
👉 **`http://localhost:8080`** (or `http://127.0.0.1:8080`)

To specify a custom port or host:
```bash
python3 annotation_ui/app.py --port 8000
```

---

## Features & Capabilities

1. **Three Annotation Datasets**:
   - **Random Sample**: 228 conversations (`RND-0001` .. `RND-0240`)
   - **Metric-Profile Sample**: 100 conversations (`MP-0001` .. `MP-0120`)
   - **Judge-Disagreement Sample**: 34 conversations (`JD-0001` .. `JD-0039`)

2. **Clean Two-Pane Reading & Grading Layout**:
   - **Left Pane (Conversation Viewer)**:
     - Clear problem description, domain, and simulation configuration tags.
     - Formatted student vs. tutor turns in distinct chat cards.
     - Displays the tutor's pedagogical state (`Diagnosis`, `Support`, `Synthesis`, etc.) and expandable **Tutor Reasoning**.
     - Special diagnostic notes (judge disagreement summary / isolated profile weaknesses).
     - Collapsible **LLM Judge Evaluation Reference** (Judge 1 to 4 scores and evidence).
     - Text zoom controls (`A-` / `A+`).
   - **Right Pane (Grading Panel)**:
     - 7 Core Pedagogical Metrics (0–3 buttons with instant rubric tooltips).
     - Correctness (Boolean `TRUE` / `FALSE`).
     - Holistic Overall Score out of 5 and out of 10.
     - Auto-sync toggle ($2 \times \text{5-score} = \text{10-score}$).

3. **Automated Excel Synchronization**:
   - Saves directly to the corresponding row in:
     - `misc/annotation_excel_files/random_sample_annotator.xlsx`
     - `misc/annotation_excel_files/metric_profile_sample_annotator.xlsx`
     - `misc/annotation_excel_files/judge_disagreement_sample_annotator.xlsx`
     - Also syncs with `misc/annotation_excel_files/annotation_evaluation_sheets.xlsx`.
   - When you visit any conversation ID, previously entered scores are automatically loaded from the Excel sheet into the form.

4. **Speed & Navigation Helpers**:
   - **"Save & Next"**: Saves marks to Excel and instantly moves to ID + 1.
   - **"Next Ungraded" Button**: Automatically skips ahead to the next unannotated conversation in the set.
   - **Quick Jump Input**: Type an index (e.g. `12`) or an ID (e.g. `RND-0012`) and press Enter to jump immediately.
   - **Progress Tracker**: Displays live progress and completion percentage (`12 / 240 (5.0%)`).

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Alt + Enter` or `Ctrl + S` | **Save & Next** (Save marks to Excel and advance to next conversation) |
| `Alt + Left Arrow` | **Previous Conversation** |
| `Alt + Right Arrow` | **Next Conversation** |
| `Enter` (in Jump input) | **Jump to specified conversation # or ID** |

---

## Directory Structure

```text
annotation_ui/
├── app.py              # HTTP Server & REST API endpoints
├── data_loader.py      # Conversation indexer and loader
├── excel_manager.py    # Thread-safe Excel reader and writer
├── static/
│   ├── index.html      # UI Layout
│   ├── style.css       # Clean styling, responsive layout & dark mode
│   └── app.js          # Interactive frontend logic & keyboard shortcuts
├── test_ui.py          # Automated verification test suite
└── README.md           # Documentation
```
