# Metric-Profile Sample Selection (Task 2)

This directory contains the **120 metric-profile conversations** selected for human annotation to evaluate how individual metric strengths and weaknesses align with human-assigned overall quality scores.

## Overview

- **Strategy**: Targeted metric-profile sampling with diversity optimization.
- **Sample Size**: 120 conversations (84 Primary, 36 Secondary).
- **Annotation IDs**: `MP-0001` through `MP-0120`.
- **Random Seed**: `42`.
- **Eligible Candidate Pool**: 2,473 conversations (strictly excluding all 240 records in `random_sample/`).
- **Overlap with Random Sample**: **0 (100% disjoint)**.

---

## 1. Metric System & Discrete Median Rule

The evaluation assesses seven dimensions on a discrete 0–3 integer scale:
1. `socratic_guidance`
2. `scaffolding`
3. `state_adaptation`
4. `diagnosis`
5. `student_agency`
6. `progression`
7. `coherence`

### Why the Discrete Median Score is Used
For each conversation and each metric, three LLM judges (`beam:cloud`, `gpt-oss:120b`, `minimax-m3.1`) provide integer ratings $j_1, j_2, j_3 \in \{0, 1, 2, 3\}$.

The primary score for category eligibility is the **integer median**:
$$\text{median} = \text{sorted}([j_1, j_2, j_3])[1]$$

> [!IMPORTANT]
> **Median vs. Rounded Mean**:
> The selection strictly uses the median discrete score, **not** the rounded mean. Because there are three integer ratings, the median is always an exact integer between 0 and 3. Using rounded means would introduce ambiguity at fractional boundary thresholds (such as 1.5 or 2.5) and distort category boundaries. JEV expected scores are retained as supplementary signals and do not replace the three-judge median.

---

## 2. Primary Category: Isolated Weaknesses (84 Conversations, 70%)

The primary category isolates conversations where a model performs well overall but exhibits specific, identifiable weaknesses on one or two metrics.

### Eligibility Criteria
A conversation qualifies for the primary pool if and only if:
1. **Exactly one or two** of the seven median metric scores equal `1`.
2. **Every other metric** has a median score of `2` or `3`.
3. **No metric** has a median score of `0`.
4. The conversation is not present in `random_sample/annotations.json`.

### Illustrative Examples

| Median Metric Scores Vector $[m_1, m_2, \dots, m_7]$ | Eligible? | Reason |
|---|:---:|---|
| `[3, 3, 2, 1, 3, 2, 3]` | **Yes** | Exactly one metric scored 1; all others $\ge 2$; no 0s |
| `[2, 1, 3, 2, 1, 3, 2]` | **Yes** | Exactly two metrics scored 1; all others $\ge 2$; no 0s |
| `[3, 1, 1, 1, 2, 3, 2]` | **No** | Three metrics scored 1 (multiple weaknesses) |
| `[3, 3, 2, 2, 3, 2, 3]` | **No** | Zero metrics scored 1 (uniformly strong) |
| `[3, 3, 2, 0, 3, 2, 3]` | **No** | A metric scored 0 (severe flaw, ineligible for isolated weakness) |

### Empirical Metric Coverage & Dataset Characteristics
Across the 2,473 eligible non-random conversations, **251 conversations** met the primary isolated-weakness rule.

Their distribution across the seven metrics reveals important empirical characteristics of the dataset:

| Metric | Primary Candidates Available ($N=251$) | Selected in Sample ($N=84$) | Coverage Notes |
|---|:---:|:---:|---|
| **`socratic_guidance`** | 179 | **55** | Balanced against scaffolding |
| **`scaffolding`** | 152 | **55** | Balanced against socratic guidance |
| **`student_agency`** | 11 | **11** | **100% of all available candidates selected** |
| **`state_adaptation`** | 0 | 0 | Dataset-wide minimum median is 2 (2,680 threes, 33 twos) |
| **`diagnosis`** | 0 | 0 | Dataset-wide minimum median is 2 (2,442 threes, 271 twos) |
| **`progression`** | 0 | 0 | Dataset-wide minimum median is 2 (2,647 threes, 66 twos) |
| **`coherence`** | 0 | 0 | Dataset-wide minimum median is 2 (2,707 threes, 6 twos) |

> [!NOTE]
> For `state_adaptation`, `diagnosis`, `progression`, and `coherence`, the three LLM judges never produced a consensus median rating of `1` without also assigning a `0` or other disqualifying scores. To prevent false coverage claims, the report and analysis explicitly document this empirical property rather than relaxing criteria.

To balance coverage:
- All **11 available conversations** with `student_agency == 1` were selected via priority seeding.
- The remaining primary slots (84 - 11 = 73) were divided in a round-robin balance between `socratic_guidance` (55 total) and `scaffolding` (55 total). Conversations with two weak metrics count toward both metrics.

---

## 3. Secondary Categories (36 Conversations, 30%)

The remaining 36 slots capture informative profiles outside the isolated-weakness rule:

| Category | Definition | Selected ($N=36$) | Description |
|---|---|:---:|---|
| **`uniformly_strong`** | All 7 medians $\ge 2$ | **18** | Diverse high-scoring profiles (straight 3s, straight 2s, mixed 2s/3s) |
| **`multiple_weaknesses`** | $\ge 3$ medians in $\{0, 1\}$ | **17** | Broadly struggling conversations (e.g. `[1, 1, 3, 2, 1, 2, 3]`) |
| **`mixed_strengths_weaknesses`** | Contains $\{0, 1\}$ and $\{2, 3\}$, with a $0$ | **1** | Only 1 non-primary mixed candidate exists with a 0 (`[2, 0, 3, 2, 2, 3, 3]`) |

---

## 4. Diversity-Oriented Selection Algorithm

To prevent selecting nearly identical conversations from the same model:
1. **Max-Min Distance**:
   Calculates normalized Manhattan distance between 7D median score vectors:
   $$D(u, v) = \frac{1}{7} \sum_{m=1}^7 |u_m - v_m|$$
   Greedily maximizes the minimum distance to already selected conversations.
2. **Subfolder Balancing Penalty**:
   Applies a penalty proportional to the number of conversations already selected from that subfolder, ensuring even spread across all 16 AI model families.
3. **JEV Continuous Decision-Boundary Bonus**:
   Scores candidate proximity to discrete decision boundaries ($0.5, 1.5, 2.5$) using JEV's continuous expected scores. Boundary cases provide greater discriminatory signal when LLM profile distances are tied.
4. **Deterministic Seeded Tie-Breaking**:
   Applies pseudo-random jitter derived from candidate source path and index with seed `42` to guarantee complete reproducibility.

---

## 5. Directory Artifacts

```text
annotation_set/metric_profile_sample/
├── annotations.json          # 120 records (MP-0001 .. MP-0120) with conversation, outputs, and profile_categories
├── manifest.json             # Seed, requested/actual size, timestamp, methods, and per-record category mapping
├── selection_summary.json    # Candidate pool counts, selected counts per category, and subfolder distribution
├── profile_analysis.json     # Empirical distributions, diversity stats, means/medians, and coverage limitations
└── README.md                 # This documentation
```

### Record Structure in `annotations.json`

```json
{
  "annotation_id": "MP-0001",
  "sampling_strategy": "metric_profile",
  "profile_categories": [
    "isolated_weakness_socratic_guidance",
    "isolated_weakness_scaffolding"
  ],
  "source": {
    "relative_path": "Google_gemma-4-31b-it/asn-set[1].json",
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
python scripts/sample_metric_profiles.py \
    --data-dir data \
    --output-dir output \
    --jev-dir jev_output \
    --random-sample annotation_set/random_sample/annotations.json \
    --annotation-dir annotation_set/metric_profile_sample \
    --sample-size 120 \
    --primary-fraction 0.70 \
    --seed 42 \
    --overwrite
```
