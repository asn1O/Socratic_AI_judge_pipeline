# Comprehensive Human Evaluation vs. 5 LLM Judges
## Analysis of the Metric-Profile Benchmark Sample (100 Conversations)

**Dataset Scope**: Metric-Profile Sample (`MP-0001` through `MP-0120`)  
**Completed Human Annotations**: 100 records (20 empty unannotated rows ignored; 100% ID-matched)  
**Total Paired Judgments**: 700 metric evaluations per judge ($100 \text{ conversations} \times 7 \text{ pedagogical metrics}$)  
**Judges Evaluated**:
- **Judge 1**: `beam:cloud` (Ollama)
- **Judge 2**: `gpt-oss:120b` (Ollama)
- **Judge 3**: `minimax-m3.1-flash` (Ollama)
- **Judge 4**: `imajev-4b` (v1, specialized Socratic evaluator)
- **Judge 5**: `imajev-4b v2` (v2, specialized Socratic evaluator)

---

## Executive Summary & Key Findings

> [!IMPORTANT]
> **Who is the most accurate judge on the Metric-Profile benchmark?**  
> Across all 700 paired evaluations, **Judge 1 (`beam:cloud`) is once again the #1 most accurate judge**, achieving:
> - **Lowest Mean Absolute Error**: **0.300** (vs 0.534 for Judge 2)
> - **Highest Exact Agreement Rate**: **70.6%**
> - **Near-Perfect Within-1 Point Agreement**: **99.4%**
> - **Highest Inter-Rater Reliability (QWK)**: **0.742** (Substantial Agreement)
> - **Strongest Correlation with Human Ratings**: Pearson **$r = 0.749$** ($p < 10^{-100}$)
> - **Minimal Systematic Bias**: Only **$+0.106$** on a 0–3 scale.
>
> **Judge 3 (`minimax-m3.1-flash`)** firmly holds **#2** (QWK **0.692**, MAE **0.360**, Exact **65.6%**, $98.4\%$ within-1 point), beating Judge 1 on *Student Agency* ($r=0.639$, MAE=0.33) and *Progression* ($r=0.393$, MAE=0.27).
>
> **Judge 2 (`gpt-oss:120b`)** is the **least accurate (#5)** (QWK **0.514**, MAE **0.534**, Bias **$+0.429$**), suffering from grade inflation on *Scaffolding* (MAE $0.87$, bias $+0.51$) and *Student Agency* (MAE $0.91$, bias $+0.89$).
>
> **Judges 4 & 5 (`imajev-4b`)** tie for **#3 & #4** (QWK $\approx 0.540$–$0.546$, MAE $\approx 0.547$–$0.550$).

![Metric Profile Accuracy Overview: MAE and Exact Agreement](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/mp_judge_accuracy_mae_and_exact_agreement.png)

---

## 1. Overall Judge Benchmark Comparison (700 Pairs per Judge)

Pooling all 700 judgments per judge against human gold-standard annotations:

| Metric | Judge 1 (`beam:cloud`) | Judge 2 (`gpt-oss:120b`) | Judge 3 (`minimax-m3.1`) | Judge 4 (`imajev-4b v1`) | Judge 5 (`imajev-4b v2`) | J1–J3 Ensemble Mean |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Overall Rank** | **#1** | #5 | **#2** | #4 | **#3** | **Ensemble Leader** |
| **Mean Absolute Error (MAE)** | **0.300** | 0.534 | **0.360** | 0.550 | 0.547 | **0.378** |
| **Root Mean Squared Error (RMSE)**| **0.558** | 0.811 | 0.626 | 0.812 | 0.806 | **0.555** |
| **Exact Agreement Rate (%)** | **70.6%** | 52.7% | 65.6% | 50.4% | 50.4% | *Continuous* |
| **Within-1 Point Agreement (%)** | **99.4%** | 93.9% | 98.4% | 94.6% | 94.9% | *Continuous* |
| **Systematic Bias ($\mu_J - \mu_H$)**| **+0.106** | +0.429 | +0.183 | +0.361 | +0.367 | +0.239 |
| **Pearson Correlation ($r$)** | **0.749** | 0.595 | 0.713 | 0.599 | 0.608 | **0.768** |
| **Spearman Rank ($\rho$)** | **0.747** | 0.596 | 0.708 | 0.597 | 0.594 | **0.769** |
| **Quadratic Weighted Kappa (QWK)**| **0.742** | 0.514 | 0.692 | 0.540 | 0.546 | **0.732 (median)** |

> [!TIP]
> **Ensemble Performance**: The J1–J3 Ensemble Mean achieves the highest linear correlation across the benchmark (**$r = 0.768$, $\rho = 0.769$**), slightly edging out Judge 1 alone in tracking continuous quality gradients.

---

## 2. Metric-by-Metric Breakdown & Correlation Analysis

![Metric Profile Correlation and Bias Profiles](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/mp_judge_correlation_and_bias_profiles.png)

### Socratic Guidance (0–3 Scale)
- **Human Ground Truth**: Mean = $1.53 \pm 0.73$
- **Judge 1**: Mean = $1.48$, Bias = $-0.05$, **MAE = 0.270**, **Exact = 74.0%**, **Within-1 = 99.0%**, **$r = 0.713$ ($p = 8.2 \times 10^{-17}$)**, **QWK = 0.710**
- **Judge 2**: Mean = $1.62$, Bias = $+0.09$, MAE = $0.450$, Exact = $58.0\%$, $r = 0.580$, QWK = $0.572$
- **Judge 3**: Mean = $1.54$, Bias = $+0.01$ (closest mean), MAE = $0.330$, Exact = $70.0\%$, $r = 0.589$, QWK = $0.584$
- **Judge 4**: Mean = $1.43$, Bias = $-0.10$, MAE = $0.480$, Exact = $55.0\%$, $r = 0.568$, QWK = $0.559$
- **Judge 5**: Mean = $1.33$, Bias = $-0.20$, MAE = $0.460$, Exact = $54.0\%$, Within-1 = $100.0\%$, $r = 0.644$, QWK = $0.620$
- **Analysis**: Judge 1 is the undisputed leader on Socratic Guidance, explaining over $50\%$ of human score variance ($R^2 = 0.51$). Judge 5 shows marked correlation improvements over Judge 4 ($r = 0.644$ vs $0.568$).

### Scaffolding (0–3 Scale)
- **Human Ground Truth**: Mean = $1.55 \pm 0.70$
- **Judge 1**: Mean = $1.49$, Bias = $-0.06$, **MAE = 0.340**, **Exact = 67.0%**, Within-1 = $99.0\%$, **$r = 0.650$ ($p = 2.5 \times 10^{-13}$)**, **QWK = 0.647**
- **Judge 2**: Mean = $2.06$, Bias = **$+0.51$**, MAE = $0.870$, **Exact = only 34.0%**, Within-1 = $79.0\%$, $r = 0.369$, QWK = $0.293$
- **Judge 3**: Mean = $1.49$, Bias = $-0.06$, MAE = $0.400$, Exact = $65.0\%$, Within-1 = $95.0\%$, $r = 0.604$, QWK = $0.591$
- **Judge 4**: Mean = $1.41$, Bias = $-0.14$, MAE = $0.540$, Exact = $57.0\%$, $r = 0.418$, QWK = $0.401$
- **Judge 5**: Mean = $1.52$, Bias = $-0.03$, MAE = $0.530$, Exact = $58.0\%$, $r = 0.457$, QWK = $0.439$
- **Analysis**: Judge 1 and Judge 3 perform strongly. Judge 2 exhibits severe leniency bias ($+0.51$), with more than $20\%$ of evaluations missing by 2 or more points.

### Diagnosis (0–3 Scale)
- **Human Ground Truth**: Mean = $2.16 \pm 0.39$
- **Judge 1**: Mean = $2.26$, Bias = $+0.10$, **MAE = 0.220** (lowest), **Exact = 78.0%** (highest), **Within-1 = 100.0%**, **$r = 0.433$ ($p = 7.0 \times 10^{-6}$)**, **QWK = 0.416**
- **Judge 2**: Mean = $2.71$, Bias = $+0.55$, MAE = $0.550$, Exact = $45.0\%$, $r = 0.316$
- **Judge 3**: Mean = $2.62$, Bias = $+0.46$, MAE = $0.540$, Exact = $47.0\%$, $r = 0.155$
- **Judge 4**: Mean = $2.98$, Bias = $+0.82$, MAE = $0.820$, Exact = $19.0\%$, $r = 0.058$
- **Judge 5**: Mean = $3.00$, Bias = $+0.84$, MAE = $0.840$, Exact = $17.0\%$, $\text{std} = 0.0$ (saturated)
- **Analysis**: Judge 1 stands alone in successfully diagnosing intermediate understanding levels ($78\%$ exact agreement). Judges 2, 3, 4, and 5 heavily over-rate diagnostic probing.

### Student Agency (0–3 Scale)
- **Human Ground Truth**: Mean = $1.69 \pm 0.63$
- **Judge 1**: Mean = $1.89$, Bias = $+0.20$, MAE = $0.340$, Exact = $66.0\%$, Within-1 = $100.0\%$, $r = 0.602$, QWK = $0.571$
- **Judge 3**: Mean = $1.90$, Bias = $+0.21$, **MAE = 0.330**, **Exact = 68.0%**, Within-1 = $99.0\%$, **$r = 0.639$ ($p = 8.5 \times 10^{-13}$)**, **QWK = 0.606**
- **Judge 2**: Mean = $2.58$, Bias = $+0.89$, MAE = $0.910$, Exact = $27.0\%$, Within-1 = $82.0\%$, $r = 0.471$
- **Judge 4**: Mean = $2.65$, Bias = $+0.96$, MAE = $0.980$, Exact = $23.0\%$, Within-1 = $79.0\%$, $r = 0.302$
- **Judge 5**: Mean = $2.64$, Bias = $+0.95$, MAE = $0.990$, Exact = $24.0\%$, Within-1 = $77.0\%$, $r = 0.154$
- **Analysis**: **Judge 3 edges out Judge 1** as the top performer on Student Agency. Judges 2, 4, and 5 fail significantly, over-crediting student agency by nearly a full point ($+0.9$ bias).

### Progression (0–3 Scale)
- **Human Ground Truth**: Mean = $2.63 \pm 0.48$
- **Judge 1**: Mean = $2.67$, Bias = $+0.04$, MAE = $0.300$, Exact = $70.0\%$, Within-1 = $100.0\%$, $r = 0.371$, QWK = $0.369$
- **Judge 3**: Mean = $2.78$, Bias = $+0.15$, **MAE = 0.270**, **Exact = 73.0%**, Within-1 = $100.0\%$, **$r = 0.393$ ($p = 5.2 \times 10^{-5}$)**, **QWK = 0.368**
- **Judge 2**: Mean = $2.95$, Bias = $+0.32$, MAE = $0.320$, Exact = $68.0\%$, $r = 0.299$
- **Judges 4 & 5**: Saturated at $3.00$ ($\text{MAE} = 0.370$, Exact = $63.0\%$)
- **Analysis**: Judge 3 is once again the strongest evaluator for Progression, accurately flagging partial progress cases.

### State Adaptation & Coherence
- **State Adaptation**: Human mean = $2.39$. All automated judges display ceiling tendencies (means $2.91$–$3.00$). Judge 1 has the lowest MAE ($0.560$) and highest exact match ($45.0\%$).
- **Coherence**: Human mean = $2.97$. 97 out of 100 dialogues scored a perfect 3. All judges perform with near-zero error (MAE $0.03$–$0.08$, exact match $92\%$–$97\%$).

---

## 3. Disagreement Resolution & Outlier Analysis

![Metric Profile Disagreement and Outliers](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/mp_judge_disagreement_and_outlier_resolution.png)

Out of 700 judgments, judges disagreed ($\text{range} \ge 1$) in **303 instances (43.3%)**.

### Exact Match Rate on Disagreed Items
- **Judge 1**: Matched Human in **206 out of 303 cases (68.0%)**
- **Judge 3**: Matched Human in **171 out of 303 cases (56.4%)**
- **Judge 2**: Matched Human in **only 81 out of 303 cases (26.7%)**

### Severe Disagreements (Range $\ge 2$, 54 Cases)
- Judge 3 was strictly closest in **12 cases (22.2%)**
- Judge 1 was strictly closest in **6 cases (11.1%)**
- Judge 2 was strictly closest in **5 cases (9.3%)**
- Equidistant / Tie in **31 cases (57.4%)**

### 2-vs-1 Outlier Splits (When One Judge Breaks Away from Consensus)
1. **Judge 1 as the Lone Outlier (79 occurrences)**:
   - Human sided with the **outlier (Judge 1) 62.0% of the time (49 cases)**!
   - Human sided with the majority (Judge 2 & 3) only **34.2% of the time (27 cases)**.
   - *Key Finding*: When Judge 1 stands alone against both Judge 2 and Judge 3, **Judge 1 is right almost twice as often as the 2-judge majority combined**.
2. **Judge 2 as the Lone Outlier (154 occurrences)**:
   - Human sided with the **majority (Judge 1 & 3) 77.9% of the time (120 cases)**.
   - Human sided with Judge 2 only **11.7% of the time (18 cases)**.
   - *Key Finding*: Judge 2 breaks away from consensus 154 times, and in nearly $80\%$ of cases it is wrong.
3. **Judge 3 as the Lone Outlier (45 occurrences)**:
   - Human sided with majority $68.9\%$, and with Judge 3 $26.7\%$.

---

## 4. Correctness (Boolean Verification)

- **Human Annotations**: 100 True, 0 False (100% True).
- **Judges 1, 2, 3**: All predicted True for all 100 records (100% Accuracy).
- **Judges 4 & 5 (JEV)**: Do not evaluate boolean correctness.

---

## 5. Overall Holistic Score Calibration

![Metric Profile Overall Score Calibration](/home/ayaans/.gemini/antigravity/brain/bd6029a1-9e89-4c61-b3de-1c68c74c5535/mp_human_overall_score_calibration.png)

How well do automated judges predict the human holistic rating (out of 10)?

| Evaluator / Composite | Pearson $r$ with Human Overall (10) | p-value | Spearman $\rho$ |
| :--- | :---: | :---: | :---: |
| **Judge 1 Average Score** | **0.7033** | $3.4 \times 10^{-16}$ | 0.5820 |
| **Judge 3 Average Score** | 0.6604 | $7.8 \times 10^{-14}$ | 0.6102 |
| **Judge 2 Average Score** | 0.5992 | $4.5 \times 10^{-11}$ | 0.6031 |
| **Judge 5 Average Score** | 0.5717 | $5.2 \times 10^{-10}$ | 0.5101 |
| **Judge 4 Average Score** | 0.5645 | $9.5 \times 10^{-10}$ | 0.5154 |
| **Ensemble (All 5 Judges)** | **0.7525** | $1.8 \times 10^{-19}$ | 0.6729 |
| **Ensemble (Judges 1, 2, 3)** | **0.7630** | $2.8 \times 10^{-20}$ | **0.6893** |

### Which Metrics Drive Human Overall Quality?
1. **Socratic Guidance**: $r = 0.8174$ ($p < 10^{-24}$) — The dominant driver of overall quality.
2. **Scaffolding**: $r = 0.7950$ ($p < 10^{-22}$) — Granularity and appropriateness of assistance.
3. **Diagnosis**: $r = 0.6521$ ($p < 10^{-12}$) — Uncovering the root cause of misunderstanding.
4. **Student Agency**: $r = 0.6394$ ($p < 10^{-12}$) — Who does the intellectual work.
5. **Progression**: $r = 0.5102$ ($p < 10^{-7}$)
6. **State Adaptation**: $r = 0.5080$ ($p < 10^{-7}$)
7. **Coherence**: $r = 0.0708$ ($p = 0.48$, uninformative as nearly all are coherent).

---

## 6. Synthesis Across Both Evaluation Benchmarks

Comparing results between the **Judge-Disagreement Sample** ($N=34$) and the **Metric-Profile Sample** ($N=100$):

| Benchmark Condition | Top Judge | Judge 1 QWK | Judge 3 QWK | Judge 2 QWK | J1–J3 Ensemble $r$ |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Judge Disagreement ($N=34$, High Divergence)** | **Judge 1** | **0.662** | 0.586 | 0.200 | **0.505** (Overall 10) |
| **Metric Profile ($N=100$, Profile Diversity)** | **Judge 1** | **0.742** | 0.692 | 0.514 | **0.763** (Overall 10) |

**Key Takeaways**:
1. **Consistency**: Judge 1 (`beam:cloud`) is consistently the most accurate judge across both challenging datasets.
2. **Reliability Scales with Sample Quality**: When evaluating diverse metric profiles (rather than adversarial disagreements), Judge 1 reaches **$\kappa = 0.742$** and the ensemble reaches **$r = 0.763$**, establishing production-grade reliability for AI-assisted pedagogical scoring.
3. **Complementary Team**: Combining **Judge 1** (primary anchor for Guidance, Scaffolding, Diagnosis) and **Judge 3** (anchor for Agency and Progression) provides the optimal configuration.
