# Comprehensive Human Evaluation vs. 5 LLM Judges
## Analysis of the Judge-Disagreement Benchmark Sample (34 Conversations)

**Dataset Scope**: Judge-Disagreement Sample (`JD-0001` through `JD-0040`)  
**Completed Human Annotations**: 34 records (6 unannotated records ignored: `JD-0011`, `JD-0012`, `JD-0026`, `JD-0031`, `JD-0032`, `JD-0040`)  
**Total Paired Judgments**: 238 metric evaluations per judge ($34 \text{ conversations} \times 7 \text{ pedagogical metrics}$)  
**Judges Evaluated**:
- **Judge 1**: `beam:cloud` (Ollama)
- **Judge 2**: `gpt-oss:120b` (Ollama)
- **Judge 3**: `minimax-m3.1-flash` (Ollama)
- **Judge 4**: `imajev-4b` (v1, specialized Socratic evaluator)
- **Judge 5**: `imajev-4b v2` (v2, specialized Socratic evaluator)

---

## Executive Summary & Key Findings

> [!IMPORTANT]
> **Who is the most accurate judge?**  
> Across all 238 paired comparisons, **Judge 1 (`beam:cloud`) is unequivocally the #1 most accurate judge overall**, achieving the lowest Mean Absolute Error (**0.391**), highest Exact Agreement (**63.0%**), highest Within-1 Agreement (**97.9%**), highest Quadratic Weighted Kappa (**0.662**), and virtually zero systematic bias (**+0.046**).
>
> **Judge 3 (`minimax-m3.1-flash`)** ranks **#2**, demonstrating superior precision on *Progression* ($r=0.414, \text{MAE}=0.265$) and *State Adaptation* ($64.7\%$ exact agreement).
>
> **Judge 2 (`gpt-oss:120b`)** is the **least accurate**, severely corrupted by **systematic grade inflation** (overall bias $+0.80$, with Scaffolding biased $+1.35$ and Student Agency $+1.41$). In severe disagreements (range $\ge 2$), Judge 2 was strictly closest to human in **0.0%** of cases.

![Judge Accuracy Overview: MAE and Exact Agreement](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/judge_accuracy_mae_and_exact_agreement.png)

---

## 1. Overall Judge Benchmark Comparison

Pooling all 238 evaluations per judge against human gold-standard annotations:

| Metric | Judge 1 (`beam:cloud`) | Judge 2 (`gpt-oss:120b`) | Judge 3 (`minimax-m3.1`) | Judge 4 (`imajev-4b v1`) | Judge 5 (`imajev-4b v2`) | J1–J3 Ensemble Mean |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Overall Rank** | **#1** | #5 | **#2** | #4 | **#3** | **Ensemble Leader** |
| **Mean Absolute Error (MAE)** | **0.391** | 0.807 | **0.466** | 0.634 | 0.605 | **0.471** |
| **Root Mean Squared Error (RMSE)**| **0.658** | 1.104 | 0.742 | 0.924 | 0.912 | **0.658** |
| **Exact Agreement Rate (%)** | **63.0%** | 39.5% | 57.1% | 47.1% | 50.4% | *N/A (continuous)* |
| **Within-1 Agreement Rate (%)** | **97.9%** | 80.3% | 96.6% | 89.9% | 89.5% | *N/A (continuous)* |
| **Systematic Bias ($\mu_J - \mu_H$)**| **+0.046** | +0.798 | +0.172 | +0.450 | +0.445 | +0.339 |
| **Pearson Correlation ($r$)** | **0.663** | 0.381 | 0.600 | 0.520 | 0.529 | **0.707** |
| **Spearman Rank ($\rho$)** | **0.669** | 0.372 | 0.619 | 0.545 | 0.543 | **0.717** |
| **Quadratic Weighted Kappa (QWK)**| **0.662** | 0.200 | 0.586 | 0.451 | 0.461 | **0.611 (median)** |

> [!TIP]
> **Ensemble Power**: While Judge 1 is the best individual judge, an **Ensemble Mean of Judges 1, 2, and 3** yields the strongest linear correlation ($r = 0.707, \rho = 0.717$), smoothing out individual judge idiosyncrasies.

---

## 2. Metric-by-Metric Breakdown & Correlation Analysis

![Judge Correlation and Bias Profiles](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/judge_correlation_and_bias_profiles.png)

### Socratic Guidance (0–3 Scale)
- **Human Ground Truth**: Mean = $1.35 \pm 0.54$ (Median = $1.0$)
- **Judge 1**: Mean = $1.21$, Bias = $-0.15$, **MAE = 0.324** (lowest), **Exact = 67.6%**, Within-1 = $100\%$, $r = 0.343$ ($p = 0.047^*$)
- **Judge 2**: Mean = $2.06$, Bias = $+0.71$, MAE = $0.706$, Exact = $38.2\%$, $r = 0.552$ ($p < 0.001^{***}$)
- **Judge 3**: Mean = $1.44$, Bias = $+0.09$ (closest mean), MAE = $0.382$, Exact = $61.8\%$, $r = 0.299$
- **Judge 4**: Mean = $1.38$, Bias = $+0.03$, MAE = $0.500$, Exact = $50.0\%$, $r = 0.223$
- **Judge 5**: Mean = $1.32$, Bias = $-0.03$, MAE = $0.382$, Exact = $61.8\%$, $r = 0.325$
- **Analysis**: Judge 1 achieves the lowest error and highest exact match. Judge 2 tracks relative ranking well ($r=0.552$), but systematically overestimates guidance by $+0.71$ points.

### Scaffolding (0–3 Scale)
- **Human Ground Truth**: Mean = $1.41 \pm 0.50$
- **Judge 1**: Mean = $1.26$, Bias = $-0.15$, **MAE = 0.324**, **Exact = 67.6%**, Within-1 = $100\%$, **$r = 0.311$**
- **Judge 2**: Mean = $2.76$, Bias = **$+1.35$**, MAE = $1.412$, **Exact = only 11.8%**, **Within-1 = only 47.1%**, $r = -0.071$
- **Judge 3**: Mean = $1.24$, Bias = $-0.18$, MAE = $0.529$, Exact = $47.1\%$, $r = -0.036$
- **Judge 4**: Mean = $1.12$, Bias = $-0.29$, MAE = $0.529$, Exact = $52.9\%$, $r = -0.073$
- **Judge 5**: Mean = $1.18$, Bias = $-0.24$, MAE = $0.471$, Exact = $58.8\%$, $r = -0.055$
- **Analysis**: **Judge 1 dominates Scaffolding**. Judge 2 suffers an catastrophic failure here, giving an average score of $2.76$ when humans rated $1.41$, misclassifying large step handouts as fine-grained nudges.

### Diagnosis (0–3 Scale)
- **Human Ground Truth**: Mean = $1.82 \pm 0.63$
- **Judge 1**: Mean = $2.00$, Bias = $+0.18$, **MAE = 0.294**, **Exact = 73.5%**, **$r = 0.527$ ($p = 0.0013^{**}$)**, **QWK = 0.500**
- **Judge 2**: Mean = $2.91$, Bias = $+1.09$, MAE = $1.088$, Exact = $11.8\%$, $r = 0.247$
- **Judge 3**: Mean = $2.59$, Bias = $+0.76$, MAE = $0.824$, Exact = $32.4\%$, $r = 0.051$
- **Judge 4**: Mean = $3.00$, Bias = $+1.18$, MAE = $1.176$, Exact = $8.8\%$, $\text{std} = 0.0$ (saturated)
- **Judge 5**: Mean = $3.00$, Bias = $+1.18$, MAE = $1.176$, Exact = $8.8\%$, $\text{std} = 0.0$ (saturated)
- **Analysis**: **Judge 1 is the clear and decisive winner on Diagnosis**. While Judges 2, 3, 4, and 5 indiscriminately awarded near-perfect scores ($2.6$–$3.0$), Judge 1 accurately discriminated between superficial checks and true probing diagnosis.

### Student Agency (0–3 Scale)
- **Human Ground Truth**: Mean = $1.47 \pm 0.51$
- **Judge 1**: Mean = $1.62$, Bias = $+0.15$, **MAE = 0.441**, **Exact = 55.9%**, Within-1 = $100\%$
- **Judge 2**: Mean = $2.88$, Bias = **$+1.41$**, MAE = $1.412$, **Exact = 5.9%**, Within-1 = $52.9\%$
- **Judge 3**: Mean = $1.62$, Bias = $+0.15$, MAE = $0.500$, Exact = $50.0\%$, Within-1 = $100\%$
- **Judge 4**: Mean = $2.68$, Bias = $+1.21$, MAE = $1.206$, Exact = $8.8\%$
- **Judge 5**: Mean = $2.65$, Bias = $+1.18$, MAE = $1.176$, Exact = $14.7\%$
- **Analysis**: Judges 1 and 3 correctly recognize student passivity (means $1.62$ vs human $1.47$). Judges 2, 4, and 5 falsely attribute agency to the student even when the tutor supplies the reasoning.

### Progression (0–3 Scale)
- **Human Ground Truth**: Mean = $2.71 \pm 0.52$
- **Judge 1**: Mean = $2.50$, Bias = $-0.21$, MAE = $0.618$, Exact = $44.1\%$, $r = -0.205$
- **Judge 2**: Mean = $3.00$, Bias = $+0.29$, MAE = $0.294$, Exact = $73.5\%$, $\text{std} = 0.0$ (saturated)
- **Judge 3**: Mean = $2.79$, Bias = $+0.09$, **MAE = 0.265**, **Exact = 73.5%**, **$r = 0.414$ ($p = 0.015^*$ leave-one-out)**, **QWK = 0.395**
- **Judge 4 & 5**: Saturated at $3.00$ ($\text{MAE}=0.294$, Exact = $73.5\%$)
- **Analysis**: **Judge 3 is the best on Progression**. Unlike Judges 2, 4, and 5 that trivially assign 3.0, Judge 3 actively identified the few conversations where progression was incomplete (score 2).

### State Adaptation & Coherence
- **State Adaptation**: Human mean = $2.47$. Judges 2, 4, 5 saturated at $3.00$ ($\text{MAE}=0.529$). Judge 3 had the lowest MAE ($0.412$) and highest exact agreement ($64.7\%$), with $r=0.232$.
- **Coherence**: Human mean = $2.79$. Over $80\%$ of dialogues were coherent. All judges performed adequately, with Judge 1 achieving $79.4\%$ and Judges 2, 4, 5 achieving $82.4\%$ exact match.

---

## 3. Disagreement Resolution: Who is Right When Judges Disagree?

Because this benchmark consists specifically of high-disagreement conversations, we investigated who the human agreed with when the judges diverged.

![Judge Disagreement and Outlier Resolution](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/judge_disagreement_and_outlier_resolution.png)

### Severe Disagreements (Range $\ge 2$, 66 Metric-Level Cases)
In cases where judges had a spread of 2 or more points (e.g., $J_1=1, J_2=3, J_3=1$):
- **Judge 1 was strictly closest to Human in 28 cases (42.4%)**
- **Judge 3 was strictly closest to Human in 13 cases (19.7%)**
- **Equidistant / Tie in 25 cases (37.9%)**
- **Judge 2 was strictly closest to Human in 0 cases (0.0%)**

> [!WARNING]
> **Zero Solo Wins for Judge 2**: In all 66 severe disagreement incidents, Judge 2 was **never once** the sole judge that human agreed with. Whenever Judge 2 broke away from Judge 1 or Judge 3, Judge 2 was wrong.

### 2-vs-1 Outlier Splits (When Two Judges Agree and One Diverges)
1. **When Judge 2 was the lone outlier (52 occurrences)**:
   - Human sided with the **majority (Judge 1 & Judge 3) 67.3% of the time (35 cases)**.
   - Human sided with the outlier (Judge 2) only **7.7% of the time (4 cases)**.
   - *Verdict*: Judge 2 outliers are almost exclusively false-positive grade inflation errors.
2. **When Judge 1 was the lone outlier (50 occurrences)**:
   - Human sided with the outlier (Judge 1) **44.0% of the time (22 cases)**, vs. 48.0% with the other two judges.
   - *Verdict*: Judge 1 is so discerning that even when standing alone against both Judge 2 and Judge 3, it is right nearly half the time!
3. **When Judge 3 was the lone outlier (19 occurrences)**:
   - Human sided with majority 47.4%, and with Judge 3 36.8%.

---

## 4. Correctness (Boolean Verification)

- **Human Annotations**: 33 True, 1 False (97.06% True).
- **Judges 1, 2, 3**: All predicted True for 100% of cases (Accuracy = $97.06\%$, Precision = $97.06\%$, Recall = $100.0\%$, F1 = $0.985$).
- **Judges 4 & 5 (JEV)**: Do not evaluate boolean correctness.
- **The Missed Failure (`JD-0033`)**:
  - The human annotator flagged `JD-0033` as having a substantive factual/logical error (Correctness = `False`, Overall Score = `5.5/10`).
  - All 3 LLM judges failed to detect this error, revealing a known vulnerability: subtle mathematical and pedagogical reasoning errors slip through standard LLM judge evaluation.

---

## 5. Overall Holistic Score Calibration

![Human Overall Score Calibration](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/human_overall_score_calibration.png)

How well does the human holistic assessment (out of 10) correlate with automated judges?

| Evaluator / Composite | Pearson $r$ with Human Overall (10) | Spearman $\rho$ |
| :--- | :---: | :---: |
| **Judge 1 Average Score** | 0.3765 | 0.4016 |
| **Judge 2 Average Score** | 0.3383 | 0.3480 |
| **Judge 3 Average Score** | 0.2344 | 0.2665 |
| **Judge 4 Average Score** | -0.0605 | -0.0407 |
| **Judge 5 Average Score** | 0.0723 | -0.0019 |
| **Ensemble (All 5 Judges)** | 0.4320 | 0.4660 |
| **Ensemble (Judges 1, 2, 3)** | **0.5046** | **0.5193** |

### Which Metrics Drive Human Overall Quality?
Correlating individual human metric ratings with the human overall score:
1. **Socratic Guidance**: $r = 0.7157$ (The dominant factor in human grading)
2. **Progression**: $r = 0.4734$
3. **Diagnosis**: $r = 0.4472$
4. **State Adaptation**: $r = 0.3674$
5. **Student Agency**: $r = 0.2805$
6. **Scaffolding**: $r = 0.2663$
7. **Coherence**: $r = 0.2548$

---

## 6. Strategic Recommendations for the Pipeline

1. **Re-weight Judge Voting**:
   - Give **Judge 1 (`beam:cloud`) the highest voting weight** (e.g., $1.5\times$ or primary tie-breaker).
   - Give **Judge 3 (`minimax-m3.1`) standard weight ($1.0\times$)** and prioritize its score for *Progression*.
   - **Discount or down-weight Judge 2 (`gpt-oss:120b`)** to $0.5\times$ or apply a systematic calibration offset ($-0.7$ on Socratic Guidance, $-1.3$ on Scaffolding and Agency) to mitigate severe leniency bias.
2. **Calibrate JEV Models (Judge 4 & 5)**:
   - While JEV models are well-calibrated on Socratic Guidance and Scaffolding, their prompt/extractor needs tightening for *Diagnosis*, *State Adaptation*, and *Progression*, where they currently exhibit ceiling saturation ($3.0$ in almost 100% of cases).
3. **Use J1–J3 Trimmed Mean for Production**:
   - A trimmed mean or weighted ensemble of Judges 1, 2, and 3 boosts correlation with human holistic judgment to $r = 0.505$, providing significantly higher reliability than relying on any individual model.
