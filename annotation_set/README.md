# AI Tutoring Conversation Annotation Sets

This directory contains the complete human annotation dataset comprising **400 unique, disjoint conversations** across three targeted sampling strategies.

## Overview & Directory Map

```text
annotation_set/
├── random_sample/                   # 240 conversations (Task 1: Unbiased baseline)
│   ├── annotations.json
│   ├── manifest.json
│   ├── selection_summary.json
│   └── README.md
├── metric_profile_sample/           # 120 conversations (Task 2: Strengths & weaknesses)
│   ├── annotations.json
│   ├── manifest.json
│   ├── selection_summary.json
│   ├── profile_analysis.json
│   └── README.md
└── judge_disagreement_sample/       # 40 conversations (Task 3: Judge evaluation variance)
    ├── annotations.json
    ├── manifest.json
    ├── selection_summary.json
    ├── disagreement_analysis.json
    └── README.md
```

## Summary Table

| Sample Strategy | Size | ID Prefix | Primary Objective | Detailed Documentation |
|---|:---:|:---:|---|---|
| **Random Sample** | 240 | `RND-0001` .. `RND-0240` | Unbiased baseline for overall performance estimation | [`random_sample/README.md`](random_sample/README.md) |
| **Metric-Profile Sample** | 120 | `MP-0001` .. `MP-0120` | Isolates specific metric strengths and weaknesses (discrete median = 1) | [`metric_profile_sample/README.md`](metric_profile_sample/README.md) |
| **Judge-Disagreement Sample** | 40 | `JD-0001` .. `JD-0040` | Captures severe and multi-dimensional divergence between LLM judges | [`judge_disagreement_sample/README.md`](judge_disagreement_sample/README.md) |
| **Total Human Annotation Pool** | **400** | — | **Zero overlap across all three sets (100% disjoint)** | — |

---

## Key Methodological Principles

1. **Exact Positional Alignment**:
   Every selected record across all three sets maintains exact alignment across `data/`, `output/`, and `jev_output/`.
2. **Discrete Integer Median**:
   In `metric_profile_sample/`, category definitions strictly utilize the median discrete score $\text{sorted}([j_1, j_2, j_3])[1]$ to eliminate fractional boundary ambiguities.
3. **Disagreement Diagnostics**:
   In `judge_disagreement_sample/`, selection is enriched 3.4× in pairwise disagreement, covering severe range splits ($\ge 2$) across all dimensions including rare metrics like progression, diagnosis, and coherence.
4. **Reproducibility**:
   All samples use deterministic sorting prior to sampling and a default random seed of `42`.
