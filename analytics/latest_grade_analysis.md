# Socratic AI Judge Evaluation: Clean Dataset Grade Tier Analysis

This report presents the complete conversation-level grade tier distribution across the **2,713 pristine conversations** currently residing in `data/`, `output/`, and `jev_output/` after removing the 294 conversations that failed the strict boolean checks (`correctness=False`, `premature_answer=True`, or `hallucination=True`).

Evaluations are presented for all four judges:
- **Judge 1:** `Ollama` &middot; `beam:cloud`
- **Judge 2:** `Ollama` &middot; `gpt-oss:120b`
- **Judge 3:** `Ollama` &middot; `minimax-m3.1-flash`
- **JEV:** `imajev` &middot; `imajev-4b` (Argmax discrete classification)

---

## 1. Overall Conversation Tier Distribution ($N = 2,713$)

Every conversation is classified based on its **lowest score** awarded across the 7 numerical dimensions (`socratic_guidance`, `scaffolding`, `state_adaptation`, `diagnosis`, `student_agency`, `progression`, `coherence`):

### Mutually Exclusive Tiers

| Tier / Condition | Lowest Score Criterion | Judge 1 (`beam:cloud`) | Judge 2 (`gpt-oss:120b`) | Judge 3 (`minimax-m3.1`) | JEV (`imajev-4b` Argmax) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **All grades are 3** | $\min = 3, \max = 3$ | **1,091** (40.21%) | **1,837** (67.71%) | **1,038** (38.26%) | **717** (26.43%) |
| **All grades are 2 or 3** *(not all 3)* | $\min = 2, \max \in \{2, 3\}$ | **1,198** (44.16%) | **619** (22.82%) | **1,279** (47.14%) | **885** (32.62%) |
| **All grades are 1, 2, or 3** *(min = 1, no 0s)* | $\min = 1$ | **412** (15.19%) | **220** (8.11%) | **380** (14.01%) | **1,022** (37.67%) |
| **Contains at least one 0** | $\min = 0$ | **12** (0.44%) | **37** (1.36%) | **16** (0.59%) | **89** (3.28%) |
| **Total Clean Conversations** | &mdash; | **2,713** (100.0%) | **2,713** (100.0%) | **2,713** (100.0%) | **2,713** (100.0%) |

---

## 2. Cumulative Quality Thresholds ($N = 2,713$)

| Threshold | Judge 1 (`beam:cloud`) | Judge 2 (`gpt-oss:120b`) | Judge 3 (`minimax-m3.1`) | JEV (`imajev-4b` Argmax) |
|:---|:---:|:---:|:---:|:---:|
| **All dimensions $\ge 3$** *(Flawless Pedagogical Execution)* | 1,091 (40.21%) | 1,837 (67.71%) | 1,038 (38.26%) | 717 (26.43%) |
| **All dimensions $\ge 2$** *(High / Acceptable Quality Across All 7)* | 2,289 (84.37%) | 2,456 (90.53%) | 2,317 (85.40%) | 1,602 (59.05%) |
| **All dimensions $\ge 1$** *(Completely Free of Severe Failures)* | 2,701 (99.56%) | 2,676 (98.64%) | 2,697 (99.41%) | 2,624 (96.72%) |
| **Total Clean Conversations** | 2,713 (100.0%) | 2,713 (100.0%) | 2,713 (100.0%) | 2,713 (100.0%) |

---

## 3. Multi-Judge Consensus on the Cleaned Set ($N = 2,713$)

Analyzing agreement across the 3 LLM judges (`beam:cloud`, `gpt-oss:120b`, `minimax-m3.1-flash`):

- **Unanimous "All 3s" (All 3 Judges):** **813 conversations** (29.97%) received straight 3s across the board from all three independent judges simultaneously.
- **Majority "All 3s" ($\ge 2$ Judges):** **1,257 conversations** (46.33%).
- **At least 1 Judge gave "All 3s":** **1,896 conversations** (69.89%).
- **Unanimous "All $\ge 2$" (All 3 Judges):** **2,142 conversations** (78.95%) have no dimension scored below 2 by any judge.
- **Majority "All $\ge 2$" ($\ge 2$ Judges):** **2,376 conversations** (87.58%).

---

## 4. JEV (`imajev-4b`) Dual-Interpretation Summary

Because JEV outputs both class probability distributions and continuous expected values ($\mathbb{E}[S] = \sum_{k=0}^3 k \cdot P(k)$):

### A. Discrete Class Prediction via Argmax ($\text{argmax}_k P(k)$)
- **All 7 grades are 3:** **717** (26.43%)
- **All grades are 2 or 3 (min = 2):** **885** (32.62%)
- **All grades are 1, 2, or 3 (min = 1):** **1,022** (37.67%)
- **Contains at least one 0 (min = 0):** **89** (3.28%)

### B. Continuous Rounded Expected Score ($\text{round}(\mathbb{E}[S])$)
- **All 7 metrics $\ge 2.50$ (All 3s):** **30** (1.11%)
- **All 7 metrics $\ge 1.50$, at least one $< 2.50$ (All 2 or 3):** **2,152** (79.32%)
- **All 7 metrics $\ge 0.50$, at least one $< 1.50$ (All 1, 2, or 3):** **519** (19.13%)
- **At least one metric $< 0.50$ (Contains 0):** **12** (0.44%)

---

## 5. Per-Model Distribution Table Across All 16 Models ($N = 2,713$)

Format in each cell: **`All 3 / Min 2 / Min 1 / Min 0`**

| Model Name | Clean $N$ | Judge 1 (`beam:cloud`) | Judge 2 (`gpt-oss:120b`) | Judge 3 (`minimax-m3.1`) | JEV (`imajev-4b` Argmax) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`Google_gemini-3.5-flash`** | 327 | 129 / 143 / 54 / 1 | 232 / 72 / 21 / 2 | 107 / 168 / 51 / 1 | 57 / 117 / 142 / 11 |
| **`Google_gemini-3-flash-preview`** | 372 | 118 / 183 / 71 / 0 | 245 / 101 / 23 / 3 | 105 / 203 / 62 / 2 | 62 / 124 / 172 / 14 |
| **`NVIDIA_nemotron-3-super-120b`** | 280 | 111 / 125 / 43 / 1 | 192 / 55 / 29 / 4 | 102 / 135 / 42 / 1 | 108 / 74 / 92 / 6 |
| **`Google_gemini-3.5-flash-lite`** | 236 | 124 / 89 / 23 / 0 | 169 / 48 / 18 / 1 | 124 / 99 / 13 / 0 | 81 / 75 / 77 / 3 |
| **`Google_gemini-3.1-flash-lite`** | 223 | 110 / 105 / 8 / 0 | 177 / 39 / 7 / 0 | 124 / 96 / 3 / 0 | 42 / 103 / 76 / 2 |
| **`OpenRouter_nemotron-3-super-120b`** | 208 | 84 / 95 / 28 / 1 | 151 / 37 / 18 / 2 | 81 / 94 / 33 / 0 | 75 / 64 / 63 / 6 |
| **`OpenRouter_nemotron-3-ultra-550b`** | 244 | 98 / 97 / 48 / 1 | 152 / 62 / 23 / 7 | 91 / 107 / 44 / 2 | 68 / 71 / 92 / 13 |
| **`NVIDIA_nemotron-3-ultra-550b`** | 255 | 95 / 114 / 44 / 2 | 153 / 67 / 28 / 7 | 92 / 121 / 41 / 1 | 81 / 72 / 94 / 8 |
| **`Google_gemma-4-31b-it`** | 228 | 80 / 99 / 46 / 3 | 148 / 50 / 25 / 5 | 87 / 94 / 43 / 4 | 65 / 66 / 88 / 9 |
| **`Google_gemini-3.6-flash`** | 220 | 82 / 100 / 35 / 3 | 142 / 53 / 20 / 5 | 72 / 105 / 39 / 4 | 48 / 76 / 82 / 14 |
| **`Google_gemini-2.5-flash-lite`** | 43 | 22 / 20 / 1 / 0 | 30 / 11 / 2 / 0 | 21 / 19 / 3 / 0 | 11 / 22 / 8 / 2 |
| **`NVIDIA_moonshotai_kimi-k3`** | 48 | 25 / 19 / 4 / 0 | 28 / 18 / 1 / 1 | 19 / 27 / 2 / 0 | 12 / 14 / 22 / 0 |
| **`Google_gemini-3.8-flash`** | 17 | 6 / 6 / 5 / 0 | 10 / 3 / 4 / 0 | 6 / 9 / 2 / 0 | 5 / 5 / 6 / 1 |
| **`Google_gemini-3.7-flash`** | 10 | 5 / 3 / 2 / 0 | 6 / 3 / 1 / 0 | 5 / 2 / 2 / 1 | 1 / 2 / 7 / 0 |
| **`NVIDIA_deepseek-v4-pro-0813`** | 1 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 |
| **`NVIDIA_deepseek-v4-flash-0731`** | 1 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 0 / 0 / 1 / 0 |

---

## 6. Key Takeaways

1. **Purged Zero-Score Pedagogical Failures:**
   In the raw dataset, Judge 1 had 56 zero-score conversations; on this clean dataset it has only **12** (0.44%). Judge 3 dropped from 63 down to **16** (0.59%). Removing the 294 conversations that failed boolean checks virtually eliminated all severe failures.
2. **High-Quality Baseline Floor:**
   **84.4%** (Judge 1), **90.5%** (Judge 2), and **85.4%** (Judge 3) of conversations now satisfy the $\ge 2$ standard across all 7 dimensions.
3. **Multi-Judge Consensus:**
   **78.95%** of all remaining conversations (2,142) achieved unanimous $\ge 2$ ratings across all 3 LLM judges, confirming that this cleaned 2,713-conversation dataset is a curated, high-integrity pedagogical corpus.
