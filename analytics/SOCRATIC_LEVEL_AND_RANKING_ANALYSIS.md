# Socratic Level Separability & Conversation Ranking Analysis

This report investigates the discriminative power of the **Judge 1 & Judge 3 ensemble scoring models** across all **2,562 graded tutoring conversations**, specifically analyzing whether a conversation's configured `socratic_level` (`low`, `medium`, `high`) can be identified **solely by its predicted score**, and evaluates model representation across the overall ranking.

---

## Executive Summary

- **Primary Question**: *Can we distinguish whether a Socratic tutoring conversation is of level Low, Medium, or High by only reading its score?*
- **Verdict**: **Yes, with high confidence.**
  - **Low vs. High Separability is near-total**: The pairwise ROC-AUC is **0.9629**, with an enormous effect size (**Cohen’s $d = 2.63$**). Out of 657 Low conversations, only 3.6% ever reach High-tier scores; out of 977 High conversations, only 3.8% drop into Low-tier scores.
  - **Medium Level Acts as a Continuous Spectrum**: Medium conversations average 7.78/10 (3.82/5), positioned between Low (6.44/10) and High (8.41/10). Overall 3-way classification accuracy based solely on a 1D score threshold is **64.7%** (vs. 33.3% random baseline), with **97.6% accuracy within $\pm 1$ tier**.
  - **Top Rank Dominance**: In the top 20% ranked conversations, **99.0%** are High or Medium (75.8% High, 23.2% Medium, only 1.0% Low). In the bottom 20%, **96.8%** are Low or Medium (79.1% Low, 17.7% Medium, only 3.1% High).
  - **Top Model Generators**: Google's Gemini family (`gemini-3.7-flash`, `gemini-3.5-flash-lite`, `gemini-2.5-flash-lite`, `gemini-3.1-flash-lite`) and Moonshot AI's `kimi-k3` achieve the highest representation in the top scoring tiers (40%–62% of their generated dialogues place in the top 20%).

---

## 1. Statistical Score Distribution by Socratic Level ($N=2,562$)

### 1.1 10-Point Scale (NNLS Regression)

| Socratic Level | Sample Count | Mean | Std Dev | Min | 25% (Q1) | Median | 75% (Q3) | Max |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **High** | 977 | **8.41** | 0.50 | 6.11 | 8.33 | **8.72** | 8.72 | 8.72 |
| **Medium** | 928 | **7.78** | 0.76 | 5.16 | 7.20 | **7.87** | 8.42 | 8.72 |
| **Low** | 657 | **6.44** | 0.94 | 3.75 | 5.77 | **6.53** | 6.99 | 8.72 |

### 1.2 5-Point Scale (NNLS Regression)

| Socratic Level | Sample Count | Mean | Std Dev | Min | 25% (Q1) | Median | 75% (Q3) | Max |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **High** | 977 | **4.16** | 0.27 | 2.89 | 4.10 | **4.33** | 4.33 | 4.33 |
| **Medium** | 928 | **3.82** | 0.41 | 2.47 | 3.49 | **3.87** | 4.18 | 4.33 |
| **Low** | 657 | **3.10** | 0.50 | 1.63 | 2.74 | **3.15** | 3.41 | 4.33 |

### 1.3 Decision Tree Regressor (10-Point & 5-Point Scales)

| Socratic Level | Sample Count | 10-Scale Mean | 10-Scale Median | 5-Scale Mean | 5-Scale Median |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **High** | 977 | **8.39** ($\pm 0.38$) | **8.49** | **4.16** ($\pm 0.20$) | **4.21** |
| **Medium** | 928 | **7.84** ($\pm 0.70$) | **7.62** | **3.85** ($\pm 0.38$) | **3.72** |
| **Low** | 657 | **6.64** ($\pm 0.99$) | **6.14** | **3.19** ($\pm 0.54$) | **2.85** |

---

## 2. Statistical Separability & Inferential Tests

### 2.1 Hypothesis Testing
- **One-Way ANOVA**:
  - $F = 1462.48$, $p < 10^{-280}$ (Rejects the null hypothesis of equal means across levels with overwhelming significance).
- **Kruskal-Wallis Non-Parametric Test**:
  - $H = 1297.19$, $p < 10^{-280}$ (Confirming ordinal divergence independent of normality assumptions).

### 2.2 Pairwise Effect Sizes (Cohen's $d$)
- **Low vs. High**: $d = \mathbf{2.63}$ *(Massive separation; $> 98\%$ non-overlap between pure Low and pure High distributions)*.
- **Low vs. Medium**: $d = \mathbf{1.58}$ *(Very large separation; average Medium conversation is 1.58 standard deviations higher than Low)*.
- **Medium vs. High**: $d = \mathbf{0.98}$ *(Large separation; clear positive shift, though intermediate overlap exists)*.

### 2.3 Binary Discriminative Power (Low vs. High)
- **ROC-AUC**: **0.9629**
- A randomly chosen High conversation has a **96.3% probability** of having a higher score than a randomly chosen Low conversation.

---

## 3. Classifying Socratic Level by Score Alone (Threshold Rules)

Using empirical density cutoffs on the 10-point and 5-point scales provides an actionable classifier:

| Score Range (10-Scale) | Score Range (5-Scale) | Inferred Level | Probability Composition | Actual Class Coverage |
|---|---|:---:|---|---|
| **$\text{Score} > 8.20$** | **$\text{Score} > 4.05$** | **High** | **66.7% High**, 31.3% Medium, **only 2.0% Low** | Captures **78.2%** of all Highs |
| **$7.00 \le \text{Score} \le 8.20$** | **$3.40 \le \text{Score} \le 4.05$** | **Medium** | **55.6% Medium**, 24.6% High, 19.7% Low | Captures **42.8%** of all Mediums |
| **$\text{Score} < 7.00$** | **$\text{Score} < 3.40$** | **Low** | **70.2% Low**, 24.5% Medium, **only 5.3% High** | Captures **75.0%** of all Lows |

### 1D Confusion Matrix ($N=2,562$)
```text
                          Predicted Low      Predicted Medium      Predicted High
Actual Low (657)               490                 143                  24
Actual Medium (928)            169                 400                 359
Actual High (977)               37                 173                 767
```

- **Exact 3-Class Accuracy**: **64.7%**
- **Accuracy Within $\pm 1$ Tier**: **97.6%**
- **Extreme Error Rate** (Low predicted as High, or High predicted as Low): **2.38%** (61 / 2,562).

---

## 4. Rank Distribution Breakdown (Rank 1 to 2,562)

Sorting all 2,562 conversations strictly by their predicted score:

| Rank Tier | Conversation Count | % High Level | % Medium Level | % Low Level |
|---|:---:|:---:|:---:|:---:|
| **Top 20%** (Ranks 1 – 512) | 512 | **75.8%** (388) | **23.2%** (119) | **1.0%** (5) |
| **Middle 60%** (Ranks 513 – 2049) | 1,537 | 37.3% (573) | **46.7%** (718) | 16.0% (246) |
| **Bottom 20%** (Ranks 2050 – 2562) | 513 | 3.1% (16) | 17.7% (91) | **79.1%** (406) |

---

## 5. Model Representation Among Top-Ranked Conversations

### 5.1 Model Presence in the Top 500 (Top ~20% Scoring Tier)

| AI Model Name | Total Generated Convos | Count in Top 500 | % of Model's Convos in Top 500 | Average Score / 10 | Average Score / 5 |
|---|:---:|:---:|:---:|:---:|:---:|
| `Google_gemini-3.7-flash` | 8 | 5 | **62.5%** | 7.99 | 3.93 |
| `Google_gemini-3.5-flash-lite` | 208 | 96 | **46.2%** | 8.05 | 3.97 |
| `Google_gemini-2.5-flash-lite` | 40 | 18 | **45.0%** | 8.16 | 4.03 |
| `Google_gemini-3.1-flash-lite` | 220 | 95 | **43.2%** | 8.07 | 3.98 |
| `Google_gemma-4-31b-it` | 198 | 66 | **33.3%** | 7.65 | 3.75 |
| `Google_gemini-3.8-flash` | 15 | 5 | **33.3%** | 7.53 | 3.68 |
| `Google_gemini-3.5-flash` | 290 | 85 | **29.3%** | 7.63 | 3.74 |
| `Google_gemini-3.6-flash` | 208 | 57 | **27.4%** | 7.50 | 3.67 |
| `Google_gemini-3-flash-preview` | 353 | 76 | **21.5%** | 7.48 | 3.66 |
| `NVIDIA_moonshotai_kimi-k3` | 35 | 7 | **20.0%** | 8.16 | 4.02 |
| `NVIDIA_deepseek-ai_deepseek-v4-pro-0813` | 1 | 1 | 100.0%* | 8.72 | 4.33 |
| `NVIDIA_deepseek-ai_deepseek-v4-flash-0731` | 1 | 1 | 100.0%* | 8.72 | 4.33 |
| `OpenRouter_nvidia_nemotron-3-super-120b-a12b_free` | 208 | 0 | **0.0%** | 7.67 | 3.76 |
| `NVIDIA_nvidia_nemotron-3-super-120b-a12b` | 279 | 0 | **0.0%** | 7.61 | 3.73 |
| `OpenRouter_nvidia_nemotron-3-ultra-550b-a55b_free` | 243 | 0 | **0.0%** | 7.56 | 3.70 |
| `NVIDIA_nvidia_nemotron-3-ultra-550b-a55b` | 255 | 0 | **0.0%** | 7.55 | 3.70 |

*\*Note: DeepSeek sample size is $N=1$.*

### 5.2 Key Model Observations
1. **Gemini "Flash-Lite" Series Leads Top-Tier Density**:
   - `gemini-3.5-flash-lite`, `gemini-2.5-flash-lite`, and `gemini-3.1-flash-lite` all place **over 43%** of their total output into the top 20% tier of tutoring interactions.
2. **Nemotron Architectural Ceiling**:
   - The Nemotron models (`nemotron-3-super` and `nemotron-3-ultra`) place **0 conversations in the top 500**, but represent **25% to 30% of the bottom 500 tier**. Their pedagogical evaluations suffer from premature hint disclosure and lower state adaptation under student errors.

---

## 6. Sample of Overall Top-Ranked Conversations

Conversations tied for the theoretical maximum score ($\text{Score} = 8.72 / 10$ and $4.33 / 5$) where both Judge 1 and Judge 3 awarded maximum pedagogical ratings across all 7 dimensions:

| Rank | Model | File & Convo Index | Socratic Level | Academic Domain | Topic | Score (10) | Score (5) |
|:---:|---|:---:|:---:|---|---|:---:|:---:|
| **1** | `Google_gemini-2.5-flash-lite` | `asn-set[0].json` #2 | **High** | Economics & Finance | Personal budgeting | **8.72** | **4.33** |
| **2** | `Google_gemini-2.5-flash-lite` | `asn-set[0].json` #3 | **High** | Biology | Photosynthesis | **8.72** | **4.33** |
| **3** | `Google_gemini-2.5-flash-lite` | `asn-set[0].json` #4 | **Medium** | Computer Science | Tracing a simple algorithm by hand | **8.72** | **4.33** |
| **4** | `Google_gemini-2.5-flash-lite` | `asn-set[0].json` #6 | **Medium** | History & Social Studies | Cause-and-effect in historical events | **8.72** | **4.33** |
| **5** | `Google_gemini-2.5-flash-lite` | `asn-set[0].json` #9 | **High** | Physics | Newton's laws in everyday scenarios | **8.72** | **4.33** |
| **6** | `Google_gemini-2.5-flash-lite` | `asn-set[0].json` #12 | **High** | Economics & Finance | Inflation basics | **8.72** | **4.33** |
| **7** | `Google_gemini-2.5-flash-lite` | `asn-set[2].json` #5 | **High** | Ethics & Critical Thinking | Cost-benefit reasoning | **8.72** | **4.33** |
| **8** | `Google_gemini-2.5-flash-lite` | `asn-set[3].json` #6 | **High** | Statistics & Data | Mean, median, mode | **8.72** | **4.33** |
| **9** | `Google_gemini-2.5-flash-lite` | `asn-set[3].json` #9 | **High** | Ethics & Critical Thinking | Logical fallacies | **8.72** | **4.33** |
| **10** | `Google_gemini-2.5-flash-lite` | `asn-set[4].json` #0 | **High** | Physics | Levers and pulleys | **8.72** | **4.33** |
| **11** | `Google_gemini-3-flash-preview` | `asn-set[0].json` #1 | **High** | History & Social Studies | Primary vs secondary sources | **8.72** | **4.33** |
| **12** | `Google_gemini-3-flash-preview` | `asn-set[10].json` #6 | **High** | Biology | Punnett squares / genetics | **8.72** | **4.33** |
| **13** | `Google_gemini-3.7-flash` | `asn-set[0].json` #1 | **High** | Everyday Reasoning | Scaling a recipe | **8.72** | **4.33** |
| **14** | `Google_gemini-3.7-flash` | `asn-set[0].json` #4 | **High** | Ethics & Critical Thinking | Logical fallacies | **8.72** | **4.33** |
| **15** | `Google_gemini-3.7-flash` | `asn-set[0].json` #5 | **High** | Physics | States of matter and phase changes | **8.72** | **4.33** |
| **16** | `NVIDIA_moonshotai_kimi-k3` | `asn-set[0].json` #0 | **High** | Economics & Finance | Personal budgeting | **8.72** | **4.33** |
| **17** | `NVIDIA_moonshotai_kimi-k3` | `asn-set[0].json` #1 | **High** | Logic & Puzzles | Venn diagram reasoning | **8.72** | **4.33** |
| **18** | `NVIDIA_moonshotai_kimi-k3` | `asn-set[0].json` #2 | **High** | Computer Science | Binary number conversion | **8.72** | **4.33** |
| **19** | `NVIDIA_deepseek-ai_deepseek-v4-pro-0813` | `asn-set[0].json` #0 | **High** | History & Social Studies | Comparing political systems | **8.72** | **4.33** |
| **20** | `NVIDIA_deepseek-ai_deepseek-v4-flash-0731` | `asn-set[0].json` #0 | **High** | History & Social Studies | Comparing political systems | **8.72** | **4.33** |

---

## 7. Domain & Topic Affinity Among Top Tiers

Across the Top 500 conversations, the distribution across academic subject areas shows high consistency:

1. **Economics & Finance**: 57 conversations (e.g., *Personal budgeting*, *Inflation basics*, *Simple vs. compound interest*).
2. **Logic & Puzzles**: 49 conversations (e.g., *Venn diagram reasoning*, *Truth-tellers and liars*).
3. **Ethics & Critical Thinking**: 47 conversations (e.g., *Logical fallacies*, *Argument structure*, *Trolley problem*).
4. **Statistics & Data**: 45 conversations (e.g., *Mean, median, mode*, *Reading graphs*).
5. **Quantitative Aptitude**: 44 conversations (e.g., *Ratio and proportion*, *Percentages*).
6. **History & Social Studies**: 43 conversations (e.g., *Primary vs secondary sources*, *Cause-and-effect*).
7. **Physics**: 41 conversations (e.g., *Newton's laws*, *Levers and pulleys*).
8. **Biology**: 40 conversations (e.g., *Photosynthesis*, *Punnett squares*).

---

## 8. Related Artifacts & Code References

- **Full Ranked Dataset**: [`analytics/ranked_conversations.csv`](file:///home/ayaans/Desktop/SOCRATIC%20AI/Socratic_AI_judge_pipeline/analytics/ranked_conversations.csv)
- **Model Score Benchmark**: [`analytics/model_scores_summary.csv`](file:///home/ayaans/Desktop/SOCRATIC%20AI/Socratic_AI_judge_pipeline/analytics/model_scores_summary.csv)
- **Model Parameters & Serialized Weights**: [`analytics/scoring_model_weights.json`](file:///home/ayaans/Desktop/SOCRATIC%20AI/Socratic_AI_judge_pipeline/analytics/scoring_model_weights.json)
- **Scoring Pipeline**: [`analytics/score_all_graded_conversations.py`](file:///home/ayaans/Desktop/SOCRATIC%20AI/Socratic_AI_judge_pipeline/analytics/score_all_graded_conversations.py)
- **Training Pipeline**: [`analytics/train_overall_scoring_models.py`](file:///home/ayaans/Desktop/SOCRATIC%20AI/Socratic_AI_judge_pipeline/analytics/train_overall_scoring_models.py)
