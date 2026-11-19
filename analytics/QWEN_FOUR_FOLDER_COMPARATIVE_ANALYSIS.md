# Comparative Study: Evaluation and Scoring of 4 Qwen Model Variants

This report presents the empirical pedagogical evaluation and scoring of the four Qwen model configurations in the Socratic AI pipeline. Each model was evaluated across **20 standardized conversations** ($N=20$) by a dual-judge panel consisting of **Judge 1 (`opencode/beam-free`)** and **Judge 3 (`minimaxai/minimax-m3.1-flash`)**.

Scoring is calculated strictly using the production weights established in [`analytics/scoring_model_weights.json`](scoring_model_weights.json), with classification mapped directly to the density cutoffs defined in [`analytics/SOCRATIC_LEVEL_AND_RANKING_ANALYSIS.md`](SOCRATIC_LEVEL_AND_RANKING_ANALYSIS.md).

---

## 1. Executive Summary & Final Rankings

| Rank | Folder Name | Configuration Description | NNLS (0–10) Mean | NNLS (0–10) Median | NNLS (0–5) Mean | Decision Tree (0–10) | Primary Classification Tier |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **#1** | [`socratic_ft_qwen-ft`] | Fine-Tuned + Socratic Prompt | **7.99** | **8.25** | **3.96** | **8.12** | **High** (55%) |
| **#2** | [`ft_qwen-ft`] | Fine-Tuned (Standard) | **7.48** | **7.87** | **3.68** | **7.71** | **High** (45%) |
| **#3** | [`socratic_qwen-base`] | Base Model + Socratic Prompt | **6.21** | **6.28** | **2.99** | **6.53** | **Low** (70%) |
| **#4** | [`base_qwen-base`] | Base Model (Unprompted) | **3.02** | **3.09** | **1.28** | **4.61** | **Low** (100%) |

> [!NOTE]
> The performance ranking is completely unanimous across **NNLS Regression (10-point & 5-point)**, **Decision Tree (10-point & 5-point)**, and **OLS Linear Regression**:  
> `socratic_ft_qwen-ft` > `ft_qwen-ft` > `socratic_qwen-base` > `base_qwen-base`.

---

## 2. Threshold Classification Analysis

As established in [`SOCRATIC_LEVEL_AND_RANKING_ANALYSIS.md`](SOCRATIC_LEVEL_AND_RANKING_ANALYSIS.md), conversations are partitioned into three pedagogical quality tiers based on empirical density boundaries on the 10-point and 5-point NNLS scales:

| Socratic Level Tier | Score Cutoff (10-Scale) | Score Cutoff (5-Scale) | Pedagogical Interpretation |
| :---: | :---: | :---: | :--- |
| **High** | **`Score > 8.20`** | **`Score > 4.05`** | Sustained question-led guidance, high student agency, minimal nudging. |
| **Medium** | **`7.00 <= Score <= 8.20`** | **`3.40 <= Score <= 4.05`** | Mixed interaction; provides some direct clues but maintains dialogue progress. |
| **Low** | **`Score < 7.00`** | **`Score < 3.40`** | Premature solution disclosure, statement-heavy guidance, low student agency. |

### Tier Distribution by Model Folder ($N = 20$ each)

| Folder Name | High Level (`> 8.20`) | Medium Level (`7.00 – 8.20`) | Low Level (`< 7.00`) | % High + Medium |
| :--- | :---: | :---: | :---: | :---: |
| **`socratic_ft_qwen-ft`** | **11** (55.0%) | **6** (30.0%) | **3** (15.0%) | **85.0%** |
| **`ft_qwen-ft`** | **9** (45.0%) | **6** (30.0%) | **5** (25.0%) | **75.0%** |
| **`socratic_qwen-base`** | **1** (5.0%) | **5** (25.0%) | **14** (70.0%) | **30.0%** |
| **`base_qwen-base`** | **0** (0.0%) | **0** (0.0%) | **20** (100.0%) | **0.0%** |

#### Key Classification Takeaways:

1. **`base_qwen-base` is 100% Low-Tier**: All 20 conversations scored below 3.80 / 10, characterized by instantaneous answer dumping and absence of scaffolding.
2. **Socratic Prompting Elevates Base Model by 30%**: `socratic_qwen-base` lifts 30% of its dialogues into the Medium and High tiers (25% Medium, 5% High).
3. **Fine-Tuning Achieves 75%+ High/Medium Delivery**: `ft_qwen-ft` places 75% of interactions in the Medium-to-High tiers without requiring specialized system prompting.
4. **Dual Synergism (`socratic_ft_qwen-ft`) Delivers 85% Top-Tier Performance**: Combining fine-tuning with Socratic system prompting achieves the lowest failure rate (only 15% Low) and highest concentration in High tier (55%).

---

## 3. Comprehensive Statistical Scoring Profiles

### 3.1 NNLS Regression Model (Primary Metric)

| Folder Name | 10-Scale Mean | 10-Scale Median | 10-Scale Min | 10-Scale Max | 10-Scale StdDev | 5-Scale Mean | 5-Scale Median |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`socratic_ft_qwen-ft`** | **7.99** | **8.25** | 5.72 | 8.72 | 0.84 | **3.96** | **4.10** |
| **`ft_qwen-ft`** | **7.48** | **7.87** | 2.74 | 8.72 | 1.62 | **3.68** | **3.91** |
| **`socratic_qwen-base`** | **6.21** | **6.28** | 3.80 | 8.72 | 1.32 | **2.99** | **3.01** |
| **`base_qwen-base`** | **3.02** | **3.09** | 2.28 | 3.76 | 0.43 | **1.28** | **1.30** |

### 3.2 Decision Tree Regressor Model

| Folder Name | 10-Scale Mean | 10-Scale Median | 10-Scale Min | 10-Scale Max | 5-Scale Mean | 5-Scale Median |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`socratic_ft_qwen-ft`** | **8.12** | **8.49** | 7.19 | 8.49 | **4.01** | **4.21** |
| **`ft_qwen-ft`** | **7.71** | **8.05** | 4.61 | 8.49 | **3.79** | **3.96** |
| **`socratic_qwen-base`** | **6.53** | **6.14** | 4.61 | 8.49 | **3.13** | **2.85** |
| **`base_qwen-base`** | **4.61** | **4.61** | 4.61 | 4.61 | **2.15** | **2.15** |

---

## 4. Underlying Pedagogical Dimension Profiles (0.0 to 3.0 Scale)

Averaged across Judge 1 and Judge 3 ratings:

| Dimension | `socratic_ft_qwen-ft` | `ft_qwen-ft` | `socratic_qwen-base` | `base_qwen-base` |
| :--- | :---: | :---: | :---: | :---: |
| **Socratic guidance** | **2.70** | 2.38 | 1.73 | 0.03 |
| **Scaffolding** | **2.80** | 2.58 | 1.73 | 0.25 |
| **State adaptation** | **2.60** | 2.52 | 2.38 | 2.10 |
| **Diagnosis** | **2.73** | 2.62 | 2.40 | 1.48 |
| **Student agency** | **2.88** | 2.70 | 2.23 | 1.38 |
| **Progression** | **2.77** | 2.73 | 2.80 | 2.45 |
| **Coherence** | **2.70** | 2.35 | 2.33 | 2.75 |

---

## 5. Granular Conversation-Level Score Table

Full breakdown of all 80 conversation scores ($20 \times 4$):

| Folder | Set & Index | NNLS (0–10) | NNLS (0–5) | Decision Tree (10) | OLS (10) | Socratic Level Tier |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #0 | 6.59 | 3.23 | 7.19 | 6.47 | **Low** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #1 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #2 | 8.15 | 4.06 | 7.62 | 8.59 | **Medium** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #3 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #4 | 7.96 | 3.91 | 8.49 | 8.00 | **Medium** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #5 | 8.35 | 4.14 | 8.49 | 8.30 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #6 | 7.72 | 3.83 | 7.62 | 7.77 | **Medium** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #7 | 7.50 | 3.68 | 8.49 | 7.66 | **Medium** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #8 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #9 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #10 | 6.74 | 3.34 | 7.62 | 6.92 | **Low** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #11 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #12 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #13 | 8.63 | 4.29 | 8.49 | 8.49 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[0].json` #14 | 7.32 | 3.61 | 7.62 | 7.46 | **Medium** |
| `socratic_ft_qwen-ft` | `asn-set[1].json` #0 | 8.42 | 4.18 | 7.62 | 8.40 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[1].json` #1 | 8.26 | 4.10 | 8.49 | 8.09 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[1].json` #2 | 5.72 | 2.81 | 7.62 | 5.75 | **Low** |
| `socratic_ft_qwen-ft` | `asn-set[1].json` #3 | 8.24 | 4.10 | 7.62 | 8.25 | **High** |
| `socratic_ft_qwen-ft` | `asn-set[1].json` #4 | 7.96 | 3.91 | 8.49 | 7.83 | **Medium** |
| `ft_qwen-ft` | `asn-set[0].json` #0 | 2.74 | 1.22 | 4.61 | 3.08 | **Low** |
| `ft_qwen-ft` | `asn-set[0].json` #1 | 7.26 | 3.60 | 7.62 | 7.99 | **Medium** |
| `ft_qwen-ft` | `asn-set[0].json` #2 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `ft_qwen-ft` | `asn-set[0].json` #3 | 8.35 | 4.14 | 8.49 | 8.30 | **High** |
| `ft_qwen-ft` | `asn-set[0].json` #4 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `ft_qwen-ft` | `asn-set[0].json` #5 | 8.26 | 4.10 | 8.49 | 8.37 | **High** |
| `ft_qwen-ft` | `asn-set[0].json` #6 | 7.87 | 3.91 | 7.62 | 7.85 | **Medium** |
| `ft_qwen-ft` | `asn-set[0].json` #7 | 6.81 | 3.30 | 7.19 | 6.88 | **Low** |
| `ft_qwen-ft` | `asn-set[0].json` #8 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `ft_qwen-ft` | `asn-set[0].json` #9 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `ft_qwen-ft` | `asn-set[0].json` #10 | 7.57 | 3.72 | 7.62 | 8.04 | **Medium** |
| `ft_qwen-ft` | `asn-set[0].json` #11 | 7.59 | 3.72 | 8.49 | 7.60 | **Medium** |
| `ft_qwen-ft` | `asn-set[0].json` #12 | 7.87 | 3.91 | 7.62 | 8.41 | **Medium** |
| `ft_qwen-ft` | `asn-set[0].json` #13 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `ft_qwen-ft` | `asn-set[0].json` #14 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `ft_qwen-ft` | `asn-set[1].json` #0 | 4.01 | 1.82 | 4.61 | 4.55 | **Low** |
| `ft_qwen-ft` | `asn-set[1].json` #1 | 6.08 | 3.00 | 7.62 | 6.67 | **Low** |
| `ft_qwen-ft` | `asn-set[1].json` #2 | 6.96 | 3.45 | 7.62 | 7.41 | **Low** |
| `ft_qwen-ft` | `asn-set[1].json` #3 | 7.20 | 3.49 | 7.19 | 7.29 | **Medium** |
| `ft_qwen-ft` | `asn-set[1].json` #4 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_qwen-base` | `asn-set[0].json` #0 | 5.56 | 2.65 | 6.14 | 6.28 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #1 | 6.71 | 3.26 | 7.19 | 6.66 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #2 | 8.72 | 4.33 | 8.49 | 8.70 | **High** |
| `socratic_qwen-base` | `asn-set[0].json` #3 | 4.64 | 2.13 | 4.61 | 4.52 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #4 | 6.53 | 3.15 | 6.14 | 6.59 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #5 | 5.67 | 2.69 | 5.56 | 5.49 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #6 | 5.28 | 2.46 | 4.61 | 5.30 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #7 | 6.51 | 3.15 | 7.19 | 7.31 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #8 | 7.57 | 3.72 | 7.62 | 7.59 | **Medium** |
| `socratic_qwen-base` | `asn-set[0].json` #9 | 7.59 | 3.72 | 8.49 | 7.60 | **Medium** |
| `socratic_qwen-base` | `asn-set[0].json` #10 | 5.95 | 2.88 | 6.14 | 6.47 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #11 | 7.59 | 3.72 | 8.49 | 7.43 | **Medium** |
| `socratic_qwen-base` | `asn-set[0].json` #12 | 7.57 | 3.75 | 7.62 | 8.11 | **Medium** |
| `socratic_qwen-base` | `asn-set[0].json` #13 | 4.34 | 1.97 | 4.61 | 4.22 | **Low** |
| `socratic_qwen-base` | `asn-set[0].json` #14 | 6.81 | 3.30 | 7.19 | 7.05 | **Low** |
| `socratic_qwen-base` | `asn-set[1].json` #0 | 4.28 | 1.98 | 5.50 | 4.73 | **Low** |
| `socratic_qwen-base` | `asn-set[1].json` #1 | 5.74 | 2.73 | 6.14 | 5.59 | **Low** |
| `socratic_qwen-base` | `asn-set[1].json` #2 | 6.04 | 2.88 | 6.14 | 6.17 | **Low** |
| `socratic_qwen-base` | `asn-set[1].json` #3 | 7.20 | 3.49 | 7.19 | 7.12 | **Medium** |
| `socratic_qwen-base` | `asn-set[1].json` #4 | 3.80 | 1.75 | 5.50 | 4.19 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #0 | 2.73 | 1.13 | 4.61 | 2.77 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #1 | 3.25 | 1.41 | 4.61 | 2.88 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #2 | 3.26 | 1.43 | 4.61 | 2.79 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #3 | 3.12 | 1.32 | 4.61 | 2.90 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #4 | 2.49 | 1.02 | 4.61 | 2.13 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #5 | 2.91 | 1.21 | 4.61 | 2.53 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #6 | 3.07 | 1.28 | 4.61 | 2.45 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #7 | 3.16 | 1.36 | 4.61 | 2.90 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #8 | 3.51 | 1.55 | 4.61 | 3.09 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #9 | 2.76 | 1.14 | 4.61 | 2.62 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #10 | 3.37 | 1.47 | 4.61 | 3.27 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #11 | 3.22 | 1.40 | 4.61 | 3.13 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #12 | 3.70 | 1.66 | 4.61 | 3.60 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #13 | 2.58 | 1.06 | 4.61 | 2.18 | **Low** |
| `base_qwen-base` | `asn-set[0].json` #14 | 2.28 | 0.91 | 4.61 | 2.05 | **Low** |
| `base_qwen-base` | `asn-set[1].json` #0 | 2.67 | 1.10 | 4.61 | 2.23 | **Low** |
| `base_qwen-base` | `asn-set[1].json` #1 | 3.76 | 1.66 | 4.61 | 3.22 | **Low** |
| `base_qwen-base` | `asn-set[1].json` #2 | 3.31 | 1.44 | 4.61 | 2.84 | **Low** |
| `base_qwen-base` | `asn-set[1].json` #3 | 2.91 | 1.21 | 4.61 | 3.26 | **Low** |
| `base_qwen-base` | `asn-set[1].json` #4 | 2.28 | 0.91 | 4.61 | 2.22 | **Low** |
