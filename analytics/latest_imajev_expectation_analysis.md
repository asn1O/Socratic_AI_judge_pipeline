# JEV (`imajev-4b`) Continuous Expectation & Range Analysis

This report presents the in-depth evaluation analysis for **JEV (`imajev-4b`)** based on the **continuous expected score** ($\mathbb{E}[S] = \sum_{k=0}^3 k \cdot P(k)$) for each metric across the **2,713 cleaned conversations** in `jev_output/`.

---

## 1. Score Range Definitions (Nearest-Integer Rounding Bands)

- **Range 3 ($[2.50, 3.00]$):** Rounds to **3** *(Strong pedagogical behavior)*
- **Range 2 ($[1.50, 2.50)$):** Rounds to **2** *(Adequate pedagogical behavior)*
- **Range 1 ($[0.50, 1.50)$):** Rounds to **1** *(Weak pedagogical behavior)*
- **Range 0 ($[0.00, 0.50)$):** Rounds to **0** *(Very poor / absent)*

---

## 2. Metric-by-Metric Expectation Distribution ($N = 2,713$)

The distribution of JEV continuous expected scores across each of the 7 numerical dimensions:

| Evaluation Dimension | Mean Expected Score | Range 3 ($[2.50, 3.00]$) | Range 2 ($[1.50, 2.50)$) | Range 1 ($[0.50, 1.50)$) | Range 0 ($[0.00, 0.50)$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`progression`** | **2.831** | **2,664** (98.23%) | 49 (1.81%) | 0 (0.00%) | 0 (0.00%) |
| **`coherence`** | **2.800** | **2,636** (97.16%) | 76 (2.80%) | 1 (0.04%) | 0 (0.00%) |
| **`diagnosis`** | **2.778** | **2,651** (97.71%) | 62 (2.29%) | 0 (0.00%) | 0 (0.00%) |
| **`state_adaptation`** | **2.705** | **2,496** (91.97%) | 216 (7.96%) | 1 (0.04%) | 0 (0.00%) |
| **`student_agency`** | **2.542** | **1,710** (63.03%) | 1,002 (36.93%) | 1 (0.04%) | 0 (0.00%) |
| **`socratic_guidance`** | **2.108** | **555** (20.46%) | 1,830 (67.45%) | 316 (11.65%) | 12 (0.44%) |
| **`scaffolding`** | **1.933** | **72** (2.65%) | 2,263 (83.41%) | 378 (13.93%) | 0 (0.00%) |

### Observations:
- **Ceiling Metrics:** Dimensions like `progression` (98.2%), `coherence` (97.2%), `diagnosis` (97.7%), and `state_adaptation` (92.0%) overwhelmingly land in Range 3.
- **Differentiating Metrics:** JEV evaluates **`scaffolding`** (mean 1.933) and **`socratic_guidance`** (mean 2.108) with high stringency, placing 83.4% and 67.5% of dialogues respectively in the Range 2 band.

---

## 3. Conversation-Level Tier Distribution ($N = 2,713$)

Classifying each conversation by its **lowest expected score** across all 7 dimensions:

| Tier / Condition | Expected Score Condition | Conversation Count | Percentage |
|:---|:---|:---:|:---:|
| **All grades are 3** | All 7 metrics $\ge 2.50$ | **30** | **1.11%** |
| **All grades are 2 or 3** *(not all 3)* | All 7 metrics $\ge 1.50$ *(at least one $< 2.50$)* | **2,152** | **79.32%** |
| **All grades are 1, 2, or 3** *(min = 1)* | All 7 metrics $\ge 0.50$ *(at least one $< 1.50$)* | **519** | **19.13%** |
| **Contains at least one 0** | At least one metric $< 0.50$ | **12** | **0.44%** |
| **Total Clean Conversations** | &mdash; | **2,713** | **100.00%** |

---

## 4. Cumulative View on Expected Scores ($N = 2,713$)

| Quality Threshold | Condition Across All 7 Metrics | Count | Percentage |
|:---|:---|:---:|:---:|
| **All Dimensions in Range 3** | All 7 metrics $\ge 2.50$ *(Exemplary execution)* | **30** | **1.11%** |
| **All Dimensions $\ge$ Range 2** | All 7 metrics $\ge 1.50$ *(Solid adequate / strong floor)* | **2,182** | **80.43%** |
| **All Dimensions $\ge$ Range 1** | All 7 metrics $\ge 0.50$ *(No zero-level collapses)* | **2,701** | **99.56%** |

---

## 5. Per-Model Conversation Distribution (Expected Score Ranges)

Cell format: **`All 3 / Min 2 / Min 1 / Min 0`**  
*(where All 3: $\min \ge 2.50$, Min 2: $1.50 \le \min < 2.50$, Min 1: $0.50 \le \min < 1.50$, Min 0: $\min < 0.50$)*

| Model Name | Clean $N$ | All 3 ($\min \ge 2.50$) | Min 2 ($[1.50, 2.50)$) | Min 1 ($[0.50, 1.50)$) | Min 0 ($< 0.50$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`Google_gemini-3.5-flash`** | 327 | 0 (0.0%) | 253 (77.4%) | 73 (22.3%) | 1 (0.3%) |
| **`Google_gemini-3-flash-preview`** | 372 | 5 (1.3%) | 282 (75.8%) | 84 (22.6%) | 1 (0.3%) |
| **`NVIDIA_nemotron-3-super-120b`** | 280 | 3 (1.1%) | 239 (85.4%) | 37 (13.2%) | 1 (0.4%) |
| **`Google_gemini-3.5-flash-lite`** | 236 | 5 (2.1%) | 198 (83.9%) | 33 (14.0%) | 0 (0.0%) |
| **`Google_gemini-3.1-flash-lite`** | 223 | 2 (0.9%) | 193 (86.5%) | 28 (12.6%) | 0 (0.0%) |
| **`OpenRouter_nemotron-3-super-120b`** | 208 | 2 (1.0%) | 180 (86.5%) | 25 (12.0%) | 1 (0.5%) |
| **`OpenRouter_nemotron-3-ultra-550b`** | 244 | 6 (2.5%) | 176 (72.1%) | 59 (24.2%) | 3 (1.2%) |
| **`NVIDIA_nemotron-3-ultra-550b`** | 255 | 3 (1.2%) | 192 (75.3%) | 60 (23.5%) | 0 (0.0%) |
| **`Google_gemma-4-31b-it`** | 228 | 2 (0.9%) | 174 (76.3%) | 51 (22.4%) | 1 (0.4%) |
| **`Google_gemini-3.6-flash`** | 220 | 1 (0.5%) | 165 (75.0%) | 50 (22.7%) | 4 (1.8%) |
| **`Google_gemini-2.5-flash-lite`** | 43 | 1 (2.3%) | 37 (86.0%) | 5 (11.6%) | 0 (0.0%) |
| **`NVIDIA_moonshotai_kimi-k3`** | 48 | 0 (0.0%) | 41 (85.4%) | 7 (14.6%) | 0 (0.0%) |
| **`Google_gemini-3.8-flash`** | 17 | 0 (0.0%) | 13 (76.5%) | 4 (23.5%) | 0 (0.0%) |
| **`Google_gemini-3.7-flash`** | 10 | 0 (0.0%) | 7 (70.0%) | 3 (30.0%) | 0 (0.0%) |
| **`NVIDIA_deepseek-v4-pro-0813`** | 1 | 0 (0.0%) | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| **`NVIDIA_deepseek-v4-flash-0731`** | 1 | 0 (0.0%) | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) |

---

## 6. Summary Takeaways

1. **Why "All 3s" is Rare Under Expected Scores (1.11%):**
   Because expected score is continuous, maintaining $\ge 2.50$ across **all 7 dimensions concurrently** acts as a strict conjunction of 7 high bars. While models achieve $\ge 2.50$ on 5 out of 7 metrics easily, `scaffolding` (mean $1.933$) and `socratic_guidance` (mean $2.108$) naturally center around the 2.0 mark.
2. **Solid Adequate Floor (80.43%):**
   Over **80%** of all clean conversations maintain an expected score $\ge 1.50$ across all 7 dimensions simultaneously, demonstrating strong baseline consistency without any weak interventions.
3. **Near Absence of Zero-Level Failures (0.44%):**
   Only **12 conversations** across the entire 2,713 dataset have any metric falling below $0.50$ (Range 0), indicating that removing the 294 flagged conversations effectively cleansed severe breakdowns from JEV's assessment as well.
