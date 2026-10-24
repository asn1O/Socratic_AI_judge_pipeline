# Judge-Disagreement Sample Selection (Task 3)

This directory contains the **40 judge-disagreement conversations** selected for human annotation to evaluate judge reliability, inter-judge variance, and model evaluation differences across our ensemble of LLM judges.

## Overview

- **Strategy**: Multi-pattern diversity selection targeted at severe and multi-dimensional LLM judge disagreement.
- **Sample Size**: 40 conversations.
- **Annotation IDs**: `JD-0001` through `JD-0040`.
- **Random Seed**: `42`.
- **Eligible Candidate Pool**: 2,353 conversations (strictly excluding all 360 records from both `random_sample/` and `metric_profile_sample/`).
- **Overlap with Previous Samples**: **0 (100% disjoint)**.

---

## 1. Objective & Disagreement Dynamics

This targeted sample isolates conversations where the three LLM judges (`beam:cloud`, `gpt-oss:120b`, `minimax-m3.1`) exhibit substantial divergence in their evaluations of the seven Socratic tutoring metrics:
1. `socratic_guidance`
2. `scaffolding`
3. `state_adaptation`
4. `diagnosis`
5. `student_agency`
6. `progression`
7. `coherence`

By obtaining human gold-standard ratings on these cases, we can diagnose *why* automated judges disagree and calibrate inter-judge scoring rubrics.

---

## 2. Calculated Disagreement Features

For every conversation across the dataset, the following metrics and features are computed:

### Per-Metric Disagreement
For each of the 7 metrics with judge scores $j_1, j_2, j_3 \in \{0, 1, 2, 3\}$:
- **Range**: $\text{range} = \max(j_1, j_2, j_3) - \min(j_1, j_2, j_3)$
- **Standard Deviation**: Sample standard deviation across the three judges.
- **Unanimous Agreement**: $\text{range} == 0$.
- **Strong Disagreement**: $\text{range} \ge 2$.
- **Low-vs-High Disagreement**: At least one judge rates $\le 1$ while another rates $\ge 2$.
- **Mean & Integer Median**: $\mu = \frac{j_1+j_2+j_3}{3}$ and $\text{median} = \text{sorted}([j_1, j_2, j_3])[1]$.
- **Outlier Judge**: Identifies whether a single judge diverged while the other two agreed.

### Conversation-Level Disagreement Aggregates
- **Mean Absolute Pairwise Score Difference (21 comparisons)**:
  Across the 3 judge pairs and 7 metrics ($3 \times 7 = 21$):
  $$\text{mean\_pairwise\_diff} = \frac{1}{21} \sum_{m=1}^7 \left( |j_{1,m} - j_{2,m}| + |j_{1,m} - j_{3,m}| + |j_{2,m} - j_{3,m}| \right)$$
- **Number of Disagreed Metrics**: Count of metrics where $\text{range} \ge 1$ (out of 7).
- **Number of Range $\ge 2$ Metrics**: Count of metrics with severe disagreement.
- **Number of Low-vs-High Metrics**: Count of metrics spanning the quality divide ($0/1$ vs $2/3$).
- **Pairwise Profile Distances**: Total Manhattan distance across all 7 metrics for each judge pair:
  $$D(j_a, j_b) = \sum_{m=1}^7 |j_{a,m} - j_{b,m}|$$
- **JEV Contrast Score**: Continuous distance between JEV expected scores and the LLM judge mean:
  $$\text{jev\_contrast} = \frac{1}{7} \sum_{m=1}^7 |\text{jev\_expected}_m - \mu_m|$$
- **Disagreement Summary**: Concise automated narrative identifying specific metrics, judges, scores, and outlier patterns.

---

## 3. Multi-Pattern Diversity Selection Strategy

Rather than simply choosing the 40 conversations with the highest raw difference, the algorithm covers a rich variety of disagreement patterns across the entire metric space:

### Step 1: Priority Seeding of Rare Disagreements
Certain metrics exhibit severe disagreements only very rarely in the dataset. To ensure complete representation across all 7 dimensions, the selection algorithm prioritizes:
- **`progression` range $\ge 2$**: **1 conversation** (the only conversation in the entire 2,353 candidate pool with a 2-point progression split).
- **`diagnosis` range $\ge 2$**: **3 conversations** (100% of all available cases in the pool).
- **`coherence` range $\ge 2$**: **2 conversations** (selected from the 4 available cases).
- **`state_adaptation` range $\ge 1$**: **2 conversations** with multi-metric divergence (state adaptation's maximum range in the dataset is 1).

### Step 2: Greedy Max-Min Vector Diversity
Fills the remaining slots up to 40 by maximizing the distance between 7D range vectors:
$$D_{\text{range}}(u, v) = \frac{1}{7} \sum_{m=1}^7 |u_m - v_m|$$
combined with:
- **Disagreement Intensity**: Rewards conversations with higher pairwise difference, range $\ge 2$ metrics, and low-vs-high splits.
- **Subfolder Frequency Penalty**: Prevents excessive concentration in any single AI model family.
- **JEV Contrast Bonus**: Breaks ties in favor of conversations with greater divergence between JEV and the LLM judges.
- **Deterministic Seeded Jitter**: Guarantees reproducible tie-breaking with seed `42`.

---

## 4. Disagreement Statistics: Candidate Pool vs. Selected Sample

The selection algorithm dramatically enriches the sample with high-value diagnostic disagreements:

| Disagreement Metric | Eligible Candidate Pool ($N=2,353$) | Selected Sample ($N=40$) | Enrichment Factor |
|---|:---:|:---:|:---:|
| **Mean Pairwise Score Difference** | 0.186 | **0.636** | **3.42× higher** |
| **Cases with Range $\ge 2$** | 9.2% (217 cases) | **97.5% (39 cases)** | **10.6× higher** |
| **Cases with Low-vs-High Disagreement** | 16.2% (382 cases) | **100.0% (40 cases)** | **6.17× higher** |
| **Mean Disagreed Metrics per Convo** | 1.84 / 7 | **4.72 / 7** | **2.57× higher** |
| **Max Pairwise Profile Distance** | 1.95 | **5.33** | **2.73× higher** |

### Per-Metric Strong Disagreement (Range $\ge 2$) Representation

| Metric | Candidate Pool Range $\ge 2$ | Selected Sample Range $\ge 2$ | Mean Range in Sample |
|---|:---:|:---:|:---:|
| `socratic_guidance` | 29 | **9** | 1.02 |
| `scaffolding` | 182 | **33** | 1.88 |
| `state_adaptation` | 0 (max range = 1) | 0 (11 with range 1) | 0.28 |
| `diagnosis` | 3 | **3 (100% selected)** | 0.95 |
| `student_agency` | 52 | **27** | 1.62 |
| `progression` | 1 | **1 (100% selected)** | 0.68 |
| `coherence` | 4 | **3** | 0.25 |

---

## 5. Disagreement Categories Represented

Each selected record in `annotations.json` includes all applicable category tags:
- `strong_metric_disagreement`: 39 cases (range $\ge 2$ on at least one metric).
- `low_vs_high_disagreement`: 40 cases (at least one metric spanning $\le 1$ vs $\ge 2$).
- `multi_metric_disagreement`: 39 cases (disagreement on $\ge 3$ metrics).
- `profile_level_disagreement`: 40 cases (max pairwise profile distance $\ge 4$).
- `severe_disagreement_scaffolding`: 33 cases.
- `severe_disagreement_student_agency`: 27 cases.
- `disagreement_diagnosis`: 32 cases (including 3 severe).
- `mixed_outliers`: 28 cases (different judges serve as the outlier on different metrics).
- `judge_1_outlier`: 23 cases; `judge_2_outlier`: 23 cases; `judge_3_outlier`: 10 cases.
- `jev_contrast`: 24 cases (meaningful contrast between JEV and the LLM judges).

---

## 6. Directory Artifacts

```text
annotation_set/judge_disagreement_sample/
├── annotations.json          # 40 records (JD-0001 .. JD-0040) with categories and disagreement_summary
├── manifest.json             # Seed, requested/actual size, timestamp, methods, and record category mapping
├── selection_summary.json    # Candidate pool counts, selected counts per category, and subfolder distribution
├── disagreement_analysis.json# Statistical comparison, range tables, judge pair distances, and pattern examples
└── README.md                 # This documentation
```

### Record Structure in `annotations.json`

```json
{
  "annotation_id": "JD-0001",
  "sampling_strategy": "judge_disagreement",
  "disagreement_categories": [
    "strong_metric_disagreement",
    "low_vs_high_disagreement",
    "multi_metric_disagreement",
    "broad_multi_metric_disagreement",
    "profile_level_disagreement",
    "severe_disagreement_scaffolding",
    "severe_disagreement_student_agency",
    "severe_disagreement_progression",
    "judge_1_outlier",
    "mixed_outliers",
    "jev_contrast"
  ],
  "disagreement_summary": "Strong disagreements (range>=2): scaffolding (J1=1, J2=3, J3=1), student_agency (J1=1, J2=3, J3=2), progression (J1=1, J2=3, J3=3); 5/7 metrics disagreed (mean pairwise diff=0.76); Outlier counts: Judge 1: 3, Judge 2: 1; JEV contrast on student_agency",
  "source": {
    "relative_path": "Google_gemini-3.5-flash/asn-set[11].json",
    "index": 1
  },
  "conversation": { ... },
  "llm_judge_output": { ... },
  "jev_output": { ... }
}
```

---

## Reproduction Command

```bash
python scripts/sample_judge_disagreement.py \
    --data-dir data \
    --output-dir output \
    --jev-dir jev_output \
    --random-sample annotation_set/random_sample/annotations.json \
    --metric-profile-sample annotation_set/metric_profile_sample/annotations.json \
    --annotation-dir annotation_set/judge_disagreement_sample \
    --sample-size 40 \
    --seed 42 \
    --overwrite
```
