# JEV (`imajev-4b`) Continuous Expectation & Range Analysis

This report presents the in-depth evaluation analysis for **JEV (`imajev-4b`)** based on the **continuous expected score** ($\mathbb{E}[S] = \sum_{k=0}^3 k \cdot P(k)$) for each metric across the **2,713 cleaned conversations** in `jev_output/` (Run 1: Dialogues only) and `jev_output2/` (Run 2: Dialogues + Conversation State & Reasoning).

---

## 1. Score Range Definitions (Nearest-Integer Rounding Bands)

- **Range 3 ($[2.50, 3.00]$):** Rounds to **3** *(Strong pedagogical behavior)*
- **Range 2 ($[1.50, 2.50)$):** Rounds to **2** *(Adequate pedagogical behavior)*
- **Range 1 ($[0.50, 1.50)$):** Rounds to **1** *(Weak pedagogical behavior)*
- **Range 0 ($[0.00, 0.50)$):** Rounds to **0** *(Very poor / absent)*

---

## 2. JEV-1: Metric-by-Metric Expectation Distribution (`jev_output/`, $N = 2,713$)

The distribution of JEV-1 continuous expected scores across each of the 7 numerical dimensions (evaluated using dialogue turns only):

| Evaluation Dimension | Mean Expected Score | Range 3 ($[2.50, 3.00]$) | Range 2 ($[1.50, 2.50)$) | Range 1 ($[0.50, 1.50)$) | Range 0 ($[0.00, 0.50)$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`progression`** | **2.831** | **2,664** (98.23%) | 49 (1.81%) | 0 (0.00%) | 0 (0.00%) |
| **`coherence`** | **2.800** | **2,636** (97.16%) | 76 (2.80%) | 1 (0.04%) | 0 (0.00%) |
| **`diagnosis`** | **2.778** | **2,651** (97.71%) | 62 (2.29%) | 0 (0.00%) | 0 (0.00%) |
| **`state_adaptation`** | **2.705** | **2,496** (91.97%) | 216 (7.96%) | 1 (0.04%) | 0 (0.00%) |
| **`student_agency`** | **2.542** | **1,710** (63.03%) | 1,002 (36.93%) | 1 (0.04%) | 0 (0.00%) |
| **`socratic_guidance`** | **2.108** | **555** (20.46%) | 1,830 (67.45%) | 316 (11.65%) | 12 (0.44%) |
| **`scaffolding`** | **1.933** | **72** (2.65%) | 2,263 (83.41%) | 378 (13.93%) | 0 (0.00%) |

---

## 3. JEV-2: Metric-by-Metric Expectation Distribution (`jev_output2/`, $N = 2,713$)

The distribution of JEV-2 continuous expected scores across each of the 7 numerical dimensions (evaluated with conversation state and reasoning provided):

| Evaluation Dimension | Mean Expected Score | Range 3 ($[2.50, 3.00]$) | Range 2 ($[1.50, 2.50)$) | Range 1 ($[0.50, 1.50)$) | Range 0 ($[0.00, 0.50)$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`state_adaptation`** | **2.881** | **2,712** (99.96%) | 1 (0.04%) | 0 (0.00%) | 0 (0.00%) |
| **`progression`** | **2.877** | **2,706** (99.74%) | 7 (0.26%) | 0 (0.00%) | 0 (0.00%) |
| **`diagnosis`** | **2.872** | **2,688** (99.08%) | 25 (0.92%) | 0 (0.00%) | 0 (0.00%) |
| **`coherence`** | **2.841** | **2,686** (99.00%) | 27 (1.00%) | 0 (0.00%) | 0 (0.00%) |
| **`student_agency`** | **2.479** | **1,358** (50.06%) | 1,352 (49.83%) | 3 (0.11%) | 0 (0.00%) |
| **`scaffolding`** | **2.044** | **139** (5.12%) | 2,335 (86.07%) | 239 (8.81%) | 0 (0.00%) |
| **`socratic_guidance`** | **2.040** | **379** (13.97%) | 1,914 (70.55%) | 402 (14.82%) | 18 (0.66%) |

### Observations & Comparative Delta:
- **Major Gain in State Adaptation (+0.176):** With the conversation state explicitly provided in `jev_output2`, JEV increased its rating from 2.705 to **2.881**, with 99.96% of dialogues landing in Range 3.
- **Scaffolding Lift (+0.111):** Access to tutor reasoning clarified subtle escalating hints, pushing mean scaffolding from 1.933 to **2.044** and doubling Range 3 dialogues from 72 to 139.
- **Consistent Disciplinary Stringency:** Both runs maintain rigorous standards on `socratic_guidance` (2.108 vs 2.040) and `scaffolding`, keeping them distinctly separated from ceiling-level dimensions.

---

## 4. Conversation-Level Tier Distribution ($N = 2,713$)

Classifying each conversation by its **lowest expected score** across all 7 dimensions:

| Tier / Condition | Expected Score Condition | JEV-1 Count (`jev_output/`) | JEV-1 % | JEV-2 Count (`jev_output2/`) | JEV-2 % |
|:---|:---|:---:|:---:|:---:|:---:|
| **All grades are 3** | All 7 metrics $\ge 2.50$ | **30** | **1.11%** | **48** | **1.77%** |
| **All grades are 2 or 3** *(not all 3)* | All 7 metrics $\ge 1.50$ *(at least one $< 2.50$)* | **2,152** | **79.32%** | **2,181** | **80.39%** |
| **All grades are 1, 2, or 3** *(min = 1)* | All 7 metrics $\ge 0.50$ *(at least one $< 1.50$)* | **519** | **19.13%** | **466** | **17.18%** |
| **Contains at least one 0** | At least one metric $< 0.50$ | **12** | **0.44%** | **18** | **0.66%** |
| **Total Clean Conversations** | &mdash; | **2,713** | **100.00%** | **2,713** | **100.00%** |

---

## 5. Cumulative Quality View on Expected Scores ($N = 2,713$)

| Quality Threshold | Condition Across All 7 Metrics | JEV-1 Count | JEV-1 % | JEV-2 Count | JEV-2 % |
|:---|:---|:---:|:---:|:---:|:---:|
| **All Dimensions in Range 3** | All 7 metrics $\ge 2.50$ *(Exemplary execution)* | 30 | 1.11% | **48** | **1.77%** |
| **All Dimensions $\ge$ Range 2** | All 7 metrics $\ge 1.50$ *(Solid adequate / strong floor)* | 2,182 | 80.43% | **2,229** | **82.16%** |
| **All Dimensions $\ge$ Range 1** | All 7 metrics $\ge 0.50$ *(No zero-level collapses)* | 2,701 | 99.56% | **2,695** | **99.34%** |

---

## 6. Per-Model Conversation Distribution (Expected Score Ranges)

Cell format: **`All 3 / Min 2 / Min 1 / Min 0`**  
*(where All 3: $\min \ge 2.50$, Min 2: $1.50 \le \min < 2.50$, Min 1: $0.50 \le \min < 1.50$, Min 0: $\min < 0.50$)*

| Model Name | Clean $N$ | JEV-1 (`jev_output/`) | JEV-2 (`jev_output2/`) |
|:---|:---:|:---:|:---:|
| **`Google_gemini-3.5-flash`** | 327 | 0 / 253 / 73 / 1 | 2 (0.6%) / 256 (78.3%) / 68 (20.8%) / 1 (0.3%) |
| **`Google_gemini-3-flash-preview`** | 372 | 5 / 282 / 84 / 1 | 4 (1.1%) / 289 (77.7%) / 77 (20.7%) / 2 (0.5%) |
| **`NVIDIA_nemotron-3-super-120b`** | 280 | 3 / 239 / 37 / 1 | 10 (3.6%) / 230 (82.1%) / 39 (13.9%) / 1 (0.4%) |
| **`Google_gemini-3.5-flash-lite`** | 236 | 5 / 198 / 33 / 0 | 5 (2.1%) / 199 (84.3%) / 32 (13.6%) / 0 (0.0%) |
| **`Google_gemini-3.1-flash-lite`** | 223 | 2 / 193 / 28 / 0 | 1 (0.4%) / 211 (94.6%) / 11 (4.9%) / 0 (0.0%) |
| **`OpenRouter_nemotron-3-super-120b`** | 208 | 2 / 180 / 25 / 1 | 5 (2.4%) / 181 (87.0%) / 18 (8.7%) / 4 (1.9%) |
| **`OpenRouter_nemotron-3-ultra-550b`** | 244 | 6 / 176 / 59 / 3 | 9 (3.7%) / 183 (75.0%) / 49 (20.1%) / 3 (1.2%) |
| **`NVIDIA_nemotron-3-ultra-550b`** | 255 | 3 / 192 / 60 / 0 | 7 (2.7%) / 195 (76.5%) / 52 (20.4%) / 1 (0.4%) |
| **`Google_gemma-4-31b-it`** | 228 | 2 / 174 / 51 / 1 | 2 (0.9%) / 171 (75.0%) / 54 (23.7%) / 1 (0.4%) |
| **`Google_gemini-3.6-flash`** | 220 | 1 / 165 / 50 / 4 | 1 (0.5%) / 164 (74.5%) / 50 (22.7%) / 5 (2.3%) |
| **`Google_gemini-2.5-flash-lite`** | 43 | 1 / 37 / 5 / 0 | 2 (4.7%) / 38 (88.4%) / 3 (7.0%) / 0 (0.0%) |
| **`NVIDIA_moonshotai_kimi-k3`** | 48 | 0 / 41 / 7 / 0 | 0 (0.0%) / 43 (89.6%) / 5 (10.4%) / 0 (0.0%) |
| **`Google_gemini-3.8-flash`** | 17 | 0 / 13 / 4 / 0 | 0 (0.0%) / 12 (70.6%) / 5 (29.4%) / 0 (0.0%) |
| **`Google_gemini-3.7-flash`** | 10 | 0 / 7 / 3 / 0 | 0 (0.0%) / 7 (70.0%) / 3 (30.0%) / 0 (0.0%) |
| **`NVIDIA_deepseek-v4-pro-0813`** | 1 | 0 / 1 / 0 / 0 | 0 (0.0%) / 1 (100.0%) / 0 (0.0%) / 0 (0.0%) |
| **`NVIDIA_deepseek-v4-flash-0731`** | 1 | 0 / 1 / 0 / 0 | 0 (0.0%) / 1 (100.0%) / 0 (0.0%) / 0 (0.0%) |

---

## 7. Summary Takeaways

1. **Why "All 3s" is Rare Under Expected Scores (1.11% in JEV-1, 1.77% in JEV-2):**
   Because expected score is continuous, maintaining $\ge 2.50$ across **all 7 dimensions concurrently** acts as a strict conjunction of 7 high bars. While models achieve $\ge 2.50$ on 5 out of 7 metrics easily, `scaffolding` and `socratic_guidance` naturally center around the 2.0 mark.
2. **Elevated Adequate Floor in JEV-2 (82.16%):**
   Over **82%** of all clean conversations maintain an expected score $\ge 1.50$ across all 7 dimensions simultaneously in JEV-2 (up from 80.43% in JEV-1), confirming that supplying tutor reasoning eliminates ambiguity about whether guidance was pedagogically calibrated.
3. **State Adaptation Reaches Virtual Ceiling:**
   Explicit awareness of the conversational state allows JEV-2 to recognize adaptation in **99.96%** of cases, up from 91.97% in JEV-1.
4. **Near Absence of Zero-Level Failures (0.44% - 0.66%):**
   Under 1% of conversations across the entire 2,713 dataset have any metric falling below $0.50$ (Range 0), demonstrating robust pedagogical stability across the curated corpus.

