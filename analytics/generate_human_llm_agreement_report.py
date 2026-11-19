#!/usr/bin/env python3
"""Generate a concise human-versus-LLM agreement report and dashboard."""

from pathlib import Path
from html import escape
import json

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_DIR = BASE_DIR / "misc" / "annotation_excel_files"
ANALYTICS_DIR = BASE_DIR / "analytics"
CHARTS_DIR = ANALYTICS_DIR / "charts"
REPORT_PATH = ANALYTICS_DIR / "HUMAN_LLM_AGREEMENT_REPORT.md"
CHART_PATH = CHARTS_DIR / "human_llm_agreement_dashboard.svg"
OVERALL_CHART_PATH = CHARTS_DIR / "human_llm_overall_scores.svg"
POOLED_SAMPLE = "Random + Metric Profile (excluding Judge Disagreement)"
HUMAN_OVERALL_5_COLUMN = "Overall Score (out of 5)"
OVERALL_WEIGHTS_PATH = ANALYTICS_DIR / "scoring_model_weights.json"
OVERALL_FEATURE_KEYS = [
    "socratic_guidance",
    "scaffolding",
    "state_adaptation",
    "diagnosis",
    "student_agency",
    "progression",
    "coherence",
]
OVERALL_MODELS = [
    ("OLS", "ols_linear_regression"),
    ("NNLS", "nnls_regression"),
    ("Decision Tree", "decision_tree"),
]

ANNOTATION_SET_KEYS = {
    "Metric Profile": "metric_profile_sample",
    "Random": "random_sample",
    "Judge Disagreement": "judge_disagreement_sample",
}

SAMPLES = [
    (
        "Metric Profile",
        "metric_profile_sample_annotator.xlsx",
        "metric_profile_sample_judges.xlsx",
    ),
    (
        "Random",
        "random_sample_annotator.xlsx",
        "random_sample_judges.xlsx",
    ),
    (
        "Judge Disagreement",
        "judge_disagreement_sample_annotator.xlsx",
        "judge_disagreement_sample_judges.xlsx",
    ),
]

METRICS = [
    ("Socratic Guidance", "Socratic Guidance (0-3)"),
    ("Scaffolding", "Scaffolding (0-3)"),
    ("State Adaptation", "State Adaptation (0-3)"),
    ("Diagnosis", "Diagnosis (0-3)"),
    ("Student Agency", "Student Agency (0-3)"),
    ("Progression", "Progression (0-3)"),
    ("Coherence", "Coherence (0-3)"),
]

JUDGES = ["Judge 1", "Judge 2", "Judge 3", "Judge 4", "Judge 5"]
CONFIGS = ["J1+J3", *JUDGES]
MEASURES = ["MAE", "Exact agreement (%)", "QWK"]


def load_sample(title: str, annotation_file: str, judge_file: str) -> pd.DataFrame:
    annotations = pd.read_excel(EXCEL_DIR / annotation_file)
    annotations = annotations.dropna(subset=["Annotation ID"]).copy()
    annotations["Annotation ID"] = annotations["Annotation ID"].astype(str).str.strip()
    annotations = annotations.dropna(subset=[column for _, column in METRICS]).copy()

    judges = pd.read_excel(EXCEL_DIR / judge_file, header=[0, 1])
    judges.columns = [
        f"{column[0]}|{column[1]}" if "Unnamed" not in str(column[1]) else column[0]
        for column in judges.columns
    ]
    judges = judges.dropna(subset=["Annotation ID"]).copy()
    judges["Annotation ID"] = judges["Annotation ID"].astype(str).str.strip()

    if annotations["Annotation ID"].duplicated().any() or judges["Annotation ID"].duplicated().any():
        raise ValueError(f"{title}: duplicate Annotation ID values found")

    paired = annotations.merge(
        judges,
        on="Annotation ID",
        how="inner",
        validate="one_to_one",
    )
    if paired.empty:
        raise ValueError(f"{title}: no paired annotations and judge scores found")

    annotation_records_path = (
        BASE_DIR / "annotation_set" / ANNOTATION_SET_KEYS[title] / "annotations.json"
    )
    annotation_records = json.loads(annotation_records_path.read_text(encoding="utf-8"))
    source_by_id = {
        record["annotation_id"]: record["source"]
        for record in annotation_records
        if "annotation_id" in record and "source" in record
    }
    paired["source_relative_path"] = paired["Annotation ID"].map(
        lambda annotation_id: source_by_id.get(annotation_id, {}).get("relative_path")
    )
    paired["source_index"] = paired["Annotation ID"].map(
        lambda annotation_id: source_by_id.get(annotation_id, {}).get("index")
    )
    if paired["source_relative_path"].isna().any() or paired["source_index"].isna().any():
        raise ValueError(f"{title}: missing source mapping for annotated conversation")

    for _, human_column in METRICS:
        paired[human_column] = pd.to_numeric(paired[human_column], errors="raise")
        if not paired[human_column].between(0, 3).all():
            raise ValueError(f"{title}: human scores outside the expected 0-3 range")
        if not np.equal(paired[human_column], np.floor(paired[human_column])).all():
            raise ValueError(f"{title}: human scores must be integers on the 0-3 scale")
        for judge in JUDGES:
            judge_column = f"{human_column}|{judge}"
            paired[judge_column] = pd.to_numeric(paired[judge_column], errors="raise")
            if not paired[judge_column].between(0, 3).all():
                raise ValueError(f"{title}: {judge} scores outside the expected 0-3 range")
            if not np.equal(paired[judge_column], np.floor(paired[judge_column])).all():
                raise ValueError(f"{title}: {judge} scores must be integers on the 0-3 scale")

    paired[HUMAN_OVERALL_5_COLUMN] = pd.to_numeric(
        paired[HUMAN_OVERALL_5_COLUMN], errors="raise"
    )
    if not paired[HUMAN_OVERALL_5_COLUMN].between(0, 5).all():
        raise ValueError(f"{title}: human overall scores outside the expected 0-5 range")
    paired["sample"] = title
    return paired


def score_pair(
    human: np.ndarray,
    prediction: np.ndarray,
    scale_max: int,
) -> dict:
    human_categories = np.clip(np.rint(human), 0, scale_max).astype(int)
    predicted_categories = np.clip(np.rint(prediction), 0, scale_max).astype(int)
    observed = np.zeros((scale_max + 1, scale_max + 1), dtype=float)
    for human_score, judge_score in zip(human_categories, predicted_categories):
        observed[human_score, judge_score] += 1
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / len(human)
    weights = (np.subtract.outer(np.arange(scale_max + 1), np.arange(scale_max + 1)) / scale_max) ** 2
    expected_disagreement = np.sum(weights * expected)
    qwk = (
        1 - np.sum(weights * observed) / expected_disagreement
        if expected_disagreement > 0
        else np.nan
    )
    return {
        "MAE": float(np.mean(np.abs(prediction - human))),
        "Exact agreement (%)": float(np.mean(predicted_categories == human_categories) * 100),
        "QWK": float(qwk) if pd.notna(qwk) else np.nan,
    }


def calculate_results(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    results = []
    for sample, paired in data.items():
        for metric, human_column in METRICS:
            human = paired[human_column].to_numpy(dtype=float)
            for config in CONFIGS:
                if config == "J1+J3":
                    judge1 = paired[f"{human_column}|Judge 1"].to_numpy(dtype=float)
                    judge3 = paired[f"{human_column}|Judge 3"].to_numpy(dtype=float)
                    prediction = (judge1 + judge3) / 2
                else:
                    prediction = paired[f"{human_column}|{config}"].to_numpy(dtype=float)

                results.append({
                    "sample": sample,
                    "metric": metric,
                    "config": config,
                    "n": len(paired),
                    **score_pair(human, prediction, 3),
                })
    return pd.DataFrame(results)


def calculate_overall_scores(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Apply the existing human-fitted overall-score models to each judge's rubric scores."""
    weights = json.loads(OVERALL_WEIGHTS_PATH.read_text(encoding="utf-8"))
    models = weights["models"]["out_of_5"]
    records = []
    for sample, paired in data.items():
        human = paired[HUMAN_OVERALL_5_COLUMN].to_numpy(dtype=float)
        for config in CONFIGS:
            if config == "J1+J3":
                features = np.column_stack([
                    (
                        paired[f"{column}|Judge 1"].to_numpy(dtype=float)
                        + paired[f"{column}|Judge 3"].to_numpy(dtype=float)
                    ) / 2
                    for _, column in METRICS
                ])
            else:
                features = np.column_stack([
                    paired[f"{column}|{config}"].to_numpy(dtype=float)
                    for _, column in METRICS
                ])
            if not np.isfinite(features).all() or not np.isfinite(human).all():
                raise ValueError(f"{sample}: non-finite rubric or human overall scores")

            for name, model_key in OVERALL_MODELS:
                model = models[model_key]
                if name == "Decision Tree":
                    prediction = np.asarray([
                        evaluate_tree(model["production_tree"], dict(zip(OVERALL_FEATURE_KEYS, row)))
                        for row in features
                    ])
                else:
                    production_weights = model["production_weights"]
                    coefficients = production_weights["coefficients"]
                    prediction = production_weights["intercept"] + sum(
                        coefficients[key] * features[:, index]
                        for index, key in enumerate(OVERALL_FEATURE_KEYS)
                    )
                    prediction = np.clip(prediction, 0, 5)
                prediction = np.round(prediction, 2)
                records.append({
                    "sample": sample,
                    "config": f"{config} | {name}",
                    "evaluator": config,
                    "model": name,
                    "n": len(paired),
                    **score_pair(human, prediction, 5),
                })
    return pd.DataFrame(records)


def evaluate_tree(node: dict, features: dict[str, float]) -> float:
    current = node
    while current["type"] == "split":
        current = (
            current["left"]
            if features[current["feature"]] <= current["threshold"]
            else current["right"]
        )
    return float(current["value"])


def color_for_value(value: float, measure: str) -> str:
    if pd.isna(value):
        return "#e5e7eb"
    if measure == "MAE":
        position = 1 - min(max(value / 1.5, 0), 1)
    elif measure == "Exact agreement (%)":
        position = min(max(value / 100, 0), 1)
    else:
        position = min(max((value + 0.5) / 1.5, 0), 1)
    red, yellow, green = (239, 106, 96), (255, 226, 130), (120, 196, 132)
    start, end, amount = (
        (red, yellow, position * 2)
        if position < 0.5
        else (yellow, green, (position - 0.5) * 2)
    )
    rgb = tuple(round(a + (b - a) * amount) for a, b in zip(start, end))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def svg_text(x: int, y: int, text: str, size: int = 12, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="#202938">{escape(text)}</text>'
    )


def make_dashboard(results: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    samples = [
        "Metric Profile",
        "Random",
        POOLED_SAMPLE,
        "Judge Disagreement",
        "Combined",
    ]
    width, section_height = 1600, 260
    height, cell_width, cell_height = 80 + len(samples) * section_height, 56, 25
    metric_label_width = 145
    panel_xs = [20, 545, 1070]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(20, 34, "Human–LLM Agreement by Sample and Rubric Dimension", 22, "bold"),
        svg_text(20, 58, "Green indicates stronger agreement; MAE is reversed (lower is better). J1+J3 is rounded half-to-even for exact agreement and QWK.", 13),
    ]

    for row, sample in enumerate(samples):
        subset = results[results["sample"] == sample]
        n = len(data[sample])
        top = 80 + row * section_height
        parts.append(svg_text(20, top + 18, f"{sample} sample  |  N = {n} conversations", 16, "bold"))
        for panel, measure in enumerate(MEASURES):
            left = panel_xs[panel]
            parts.append(svg_text(left, top + 42, measure, 13, "bold"))
            matrix = subset.pivot(index="metric", columns="config", values=measure)
            for col, config in enumerate(CONFIGS):
                x = left + metric_label_width + col * cell_width
                label = "J1+J3" if config == "J1+J3" else config.replace("Judge ", "J")
                parts.append(svg_text(x + 2, top + 61, label, 10, "bold"))

            for metric_index, (metric, _) in enumerate(METRICS):
                y = top + 70 + metric_index * cell_height
                parts.append(svg_text(left, y + 16, metric, 10))
                for col, config in enumerate(CONFIGS):
                    value = matrix.loc[metric, config]
                    x = left + metric_label_width + col * cell_width
                    parts.append(
                        f'<rect x="{x}" y="{y}" width="{cell_width - 2}" height="{cell_height - 2}" '
                        f'rx="3" fill="{color_for_value(value, measure)}"/>'
                    )
                    shown = "N/A" if pd.isna(value) else (
                        f"{value:.0f}" if measure == "Exact agreement (%)" else f"{value:.2f}"
                    )
                    parts.append(svg_text(x + 5, y + 15, shown, 9))
    parts.append("</svg>")
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    CHART_PATH.write_text("\n".join(parts), encoding="utf-8")


def make_overall_dashboard(overall: pd.DataFrame) -> None:
    samples = [
        "Metric Profile",
        "Random",
        POOLED_SAMPLE,
        "Judge Disagreement",
        "Combined",
    ]
    width, section_height = 700, 365
    top_margin = 82
    height = top_margin + len(samples) * section_height + 20
    cell_height = 15
    row_height = 15
    metric_xs = [250, 400, 550]
    measures = ["MAE", "Exact agreement (%)", "QWK"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(15, 29, "Human–LLM Overall-Score Agreement", 21, "bold"),
        svg_text(15, 51, "Human overall ratings vs. model-estimated scores on the original 0–5 scale.", 12),
        svg_text(15, 68, "J1+J3 is shown in its own section; individual judges are grouped separately below.", 11),
    ]
    for row, sample in enumerate(samples):
        sample_data = overall[overall["sample"] == sample]
        top = top_margin + row * section_height
        n = int(sample_data["n"].iloc[0])
        parts.append(svg_text(18, top + 17, f"{sample}  |  N = {n} conversations", 14, "bold"))
        parts.extend(
            svg_text(metric_x, top + 39, measure, 11, "bold")
            for metric_x, measure in zip(metric_xs, measures)
        )
        ensemble_top = top + 47
        parts.append(
            f'<rect x="14" y="{ensemble_top}" width="670" height="62" rx="4" fill="#eef4fb"/>'
        )
        parts.append(svg_text(18, ensemble_top + 12, "J1+J3 ensemble", 10, "bold"))
        for model_index, (model, _) in enumerate(OVERALL_MODELS):
            y = ensemble_top + 16 + model_index * row_height
            label = f"J1+J3 / {model}"
            parts.append(svg_text(18, y + 11, label, 9))
            summary = sample_data[sample_data["config"] == f"J1+J3 | {model}"]
            if summary.empty:
                raise ValueError(f"{sample}: missing overall-score results for J1+J3 / {model}")
            for metric_x, measure in zip(metric_xs, measures):
                value = float(summary[measure].iloc[0])
                parts.append(
                    f'<rect x="{metric_x}" y="{y}" width="105" height="{cell_height}" '
                    f'rx="2" fill="{color_for_value(value, measure)}"/>'
                )
                shown = f"{value:.0f}" if measure == "Exact agreement (%)" else f"{value:.2f}"
                parts.append(svg_text(metric_x + 4, y + 11, shown, 9))

        individual_top = ensemble_top + 68
        parts.append(
            f'<line x1="15" y1="{individual_top}" x2="684" y2="{individual_top}" '
            'stroke="#9ca3af" stroke-width="1"/>'
        )
        parts.append(svg_text(18, individual_top + 13, "Individual judges", 10, "bold"))
        for config_index, config in enumerate(JUDGES):
            for model_index, (model, _) in enumerate(OVERALL_MODELS):
                result_index = config_index * len(OVERALL_MODELS) + model_index
                y = individual_top + 18 + result_index * row_height
                label = f"{config.replace('Judge ', 'J')} / {model}"
                parts.append(svg_text(18, y + 11, label, 9))
                summary = sample_data[sample_data["config"] == f"{config} | {model}"]
                if summary.empty:
                    raise ValueError(f"{sample}: missing overall-score results for {config} / {model}")
                for metric_x, measure in zip(metric_xs, measures):
                    value = float(summary[measure].iloc[0])
                    parts.append(
                        f'<rect x="{metric_x}" y="{y}" width="105" height="{cell_height}" '
                        f'rx="2" fill="{color_for_value(value, measure)}"/>'
                    )
                    shown = (
                        f"{value:.0f}" if measure == "Exact agreement (%)"
                        else f"{value:.2f}"
                    )
                    parts.append(svg_text(metric_x + 4, y + 11, shown, 9))

    parts.append("</svg>")
    OVERALL_CHART_PATH.write_text("\n".join(parts), encoding="utf-8")


def macro_summary(results: pd.DataFrame, sample: str) -> pd.DataFrame:
    subset = results[results["sample"] == sample]
    return (
        subset.groupby("config", sort=False)[MEASURES]
        .mean()
        .reindex(CONFIGS)
    )


def format_table(summary: pd.DataFrame) -> list[str]:
    lines = [
        "| Evaluator | MAE (lower is better) | Exact agreement (higher is better) | QWK (higher is better) |",
        "|---|---:|---:|---:|",
    ]
    for config, row in summary.iterrows():
        qwk = "N/A" if pd.isna(row["QWK"]) else f'{row["QWK"]:.3f}'
        label = "J1 + J3 ensemble" if config == "J1+J3" else config
        lines.append(
            f'| {label} | {row["MAE"]:.3f} | {row["Exact agreement (%)"]:.1f}% | {qwk} |'
        )
    return lines


def write_report(data: dict[str, pd.DataFrame], results: pd.DataFrame) -> None:
    samples = [
        "Metric Profile",
        "Random",
        POOLED_SAMPLE,
        "Judge Disagreement",
        "Combined",
    ]
    combined_summary = macro_summary(results, "Combined")
    combined_overall = data["overall_scores"]
    best_overall = {}
    for measure, ascending in [
        ("MAE", True),
        ("Exact agreement (%)", False),
        ("QWK", False),
    ]:
        ordered = combined_overall.sort_values(measure, ascending=ascending)
        best_overall[measure] = ordered.iloc[0]["config"]
    lines = [
        "# Human–LLM Agreement Report",
        "",
        "Human ratings are compared with the J1+J3 ensemble and Judges 1–5. The report shows each sample separately, Random + Metric Profile pooled, and all samples combined.",
        "",
        "## Formulas",
        "",
        "- **MAE:** `mean(|LLM score − human score|)` on the original score scale; lower is better.",
        "- **Exact agreement:** `matching whole-score categories ÷ number of ratings × 100%`; higher is better.",
        "- **QWK:** `1 − Σ(wᵢⱼOᵢⱼ) / Σ(wᵢⱼEᵢⱼ)`, where `wᵢⱼ = ((i − j)/K)²` and `K` is the scale maximum (3 for rubric ratings; 5 for overall scores). QWK is chance-adjusted; 1 is perfect agreement.",
        "- Exact agreement and QWK use scores rounded to the nearest whole number (half ties to the nearest even integer). MAE uses unrounded scores.",
        "",
        "## Rubric-score agreement",
        "",
        "Tables show the macro-average across the seven rubric dimensions; each dimension has equal weight. Scores are on the original 0–3 scale.",
        "",
    ]

    for sample in samples:
        sample_data = data[sample]
        summary = macro_summary(results, sample)
        lines.extend([
            f"### {sample} (N = {len(sample_data)} conversations)",
            "",
            *format_table(summary),
            "",
        ])

    lines.extend([
        "### Rubric dashboard",
        "",
        f"![MAE, exact agreement, and QWK by sample, rubric dimension, and evaluator](./charts/{CHART_PATH.name})",
        "",
        "## Overall-score agreement",
        "",
        "Overall estimates are calculated by applying the existing OLS, NNLS, and Decision Tree models to the J1+J3 average or to each individual judge's seven rubric scores. The models and metric weights were fitted using human overall annotations, with J1+J3 rubric scores as training features. Scores are on the original 0–5 scale; exact agreement and QWK use rounded whole scores. The dashboard keeps J1+J3 separate from the individual judges for clarity.",
        "",
        f"![Human overall scores compared with model-estimated scores for J1+J3 and each individual judge](./charts/{OVERALL_CHART_PATH.name})",
        "",
        "## Critic / Key Findings",
        "",
        f"- On the combined rubric sample, J1 is stronger than J1+J3 on all three measures: MAE {combined_summary.loc['Judge 1', 'MAE']:.3f} vs. {combined_summary.loc['J1+J3', 'MAE']:.3f}; exact agreement {combined_summary.loc['Judge 1', 'Exact agreement (%)']:.1f}% vs. {combined_summary.loc['J1+J3', 'Exact agreement (%)']:.1f}%; QWK {combined_summary.loc['Judge 1', 'QWK']:.3f} vs. {combined_summary.loc['J1+J3', 'QWK']:.3f}. The ensemble is not shown to outperform J1 on these data.",
        f"- J1 and J3 are the strongest individual judges overall; J2, J4, and J5 have weaker combined results (MAE {combined_summary.loc['Judge 2', 'MAE']:.3f}, {combined_summary.loc['Judge 4', 'MAE']:.3f}, and {combined_summary.loc['Judge 5', 'MAE']:.3f}).",
        f"- On the combined overall-score comparison, the strongest configuration is {best_overall['MAE']} for MAE, {best_overall['Exact agreement (%)']} for exact agreement, and {best_overall['QWK']} for QWK.",
        "- Individual-judge overall scores are model estimates, not holistic scores assigned by those judges. The weights were trained using J1+J3 features and human overall annotations, then applied to each judge's scores; this is a cross-evaluator application of the same scoring rule.",
        "- The scoring models were fitted using these same 362 human-rated conversations, so the overall comparisons are in-sample, not independent validation. There is only one human rating set per conversation; Random is the most representative sample, while the other samples are selected.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    sample_data = {
        title: load_sample(title, annotation_file, judge_file)
        for title, annotation_file, judge_file in SAMPLES
    }
    random_metric = pd.concat(
        [sample_data["Random"], sample_data["Metric Profile"]],
        ignore_index=True,
    )
    random_metric["sample"] = POOLED_SAMPLE
    data = {
        **sample_data,
        POOLED_SAMPLE: random_metric,
        "Combined": pd.concat(sample_data.values(), ignore_index=True),
    }
    results = calculate_results(data)
    overall_scores = calculate_overall_scores(data)
    data["overall_scores"] = overall_scores
    make_dashboard(results, data)
    make_overall_dashboard(overall_scores)
    write_report(data, results)
    print(f"Generated {REPORT_PATH}")
    print(f"Generated {CHART_PATH}")
    print(f"Generated {OVERALL_CHART_PATH}")
    for sample in [
        "Metric Profile",
        "Random",
        POOLED_SAMPLE,
        "Judge Disagreement",
        "Combined",
    ]:
        print(f"\n{sample} (macro-average across seven dimensions)")
        print(macro_summary(results, sample).round(3).to_string())


if __name__ == "__main__":
    main()
