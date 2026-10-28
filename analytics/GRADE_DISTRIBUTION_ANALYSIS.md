# Socratic AI Judge Evaluation: Conversation Grade Tier Distribution

This report provides a comprehensive comparative analysis of conversation-level evaluation tiers across all **3,007 Socratic conversations** (spanning **16 generative AI models**) evaluated by our 3-judge ensemble (`output/`) and the standalone **JEV** (`imajev-4b` under `jev_output/`) on the `asn/data-analysis` branch.

---

## 1. Evaluation Setup & Scoring Dimensions

Each conversation is scored across **7 numerical rubric dimensions** on an integer scale from **0 to 3**:
- `socratic_guidance`: Question-driven vs. statement-based guidance
- `scaffolding`: Granularity and escalation of hints
- `state_adaptation`: Responsiveness to student misunderstandings
- `diagnosis`: Investigating and identifying core misconceptions
- `student_agency`: Degree to which the student performs the intellectual heavy lifting
- `progression`: Systematic advancement through the pedagogical objective
- `coherence`: Contextual and logical continuity across turns

### Rubric Scale
- **3 (Strong):** Exceeds expectations; exemplary pedagogical behavior.
- **2 (Adequate):** Meets standards with minor non-critical omissions.
- **1 (Weak):** Suboptimal; frequent leading prompts or unaddressed slips.
- **0 (Very Poor / Absent):** Total absence of pedagogical behavior or direct answer revelation.

---

## 2. Evaluator Ensemble Overview

| Evaluator Slot | Provider | Model Identifier | Role | Output Source |
|:---|:---|:---|:---|:---|
| **Judge 1** | `Ollama` | `beam:cloud` | Generalist LLM evaluator | `output/*/asn-set[*].json` |
| **Judge 2** | `Ollama` | `gpt-oss:120b` | High-parameter OSS model (more lenient) | `output/*/asn-set[*].json` |
| **Judge 3** | `Ollama` | `minimax-m3.1-flash` | Flash-tier reasoning model (balanced) | `output/*/asn-set[*].json` |
| **JEV** | `imajev` | `imajev-4b` | Specialized 4B evaluation SLM (dialogue turns only) | `jev_output/*/asn-set[*].json` |
| **JEV-2** | `imajev` | `imajev-4b` | Specialized 4B evaluation SLM (dialogues + state & reasoning) | `jev_output2/*/asn-set[*].json` |

---

## 3. Overall Conversation Tier Distribution ($N = 3,007$)

Every conversation is classified into mutually exclusive tiers based on its **lowest score** awarded across the 7 numerical dimensions:

### A. Mutually Exclusive Tiers

| Tier / Condition | Criterion | Judge 1 (`beam:cloud`) | Judge 2 (`gpt-oss:120b`) | Judge 3 (`minimax-m3.1`) | JEV (`imajev-4b` Argmax) | JEV-2 (`imajev-4b` Argmax)* |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **All grades are 3** | $\min = 3, \max = 3$ | **1,132** (37.65%) | **1,947** (64.75%) | **1,048** (34.85%) | **743** (24.71%) | **593** (21.86%) |
| **All grades are 2 or 3** *(not all 3)* | $\min = 2, \max \in \{2, 3\}$ | **1,292** (42.97%) | **694** (23.08%) | **1,372** (45.63%) | **960** (31.93%) | **1,266** (46.66%) |
| **All grades are 1, 2, or 3** *(min = 1, no 0s)* | $\min = 1$ | **527** (17.53%) | **287** (9.54%) | **524** (17.43%) | **1,161** (38.61%) | **786** (28.97%) |
| **Contains at least one 0** | $\min = 0$ | **56** (1.86%) | **79** (2.63%) | **63** (2.10%) | **143** (4.76%) | **68** (2.51%) |
| **Total Conversations** | &mdash; | **3,007** (100.0%) | **3,007** (100.0%) | **3,007** (100.0%) | **3,007** (100.0%) | **2,713** (100.0%)* |

*\*Note: JEV-2 evaluated on the clean dataset of $N=2,713$ post boolean checks.*

---

### B. Cumulative Thresholds

| Threshold | Judge 1 | Judge 2 | Judge 3 | JEV (Argmax) | JEV-2 (Argmax)* |
|:---|:---:|:---:|:---:|:---:|:---:|
| **All dimensions $\ge 3$** *(Flawless conversation)* | 1,132 (37.65%) | 1,947 (64.75%) | 1,048 (34.85%) | 743 (24.71%) | 593 (21.86%) |
| **All dimensions $\ge 2$** *(High quality / acceptable)* | 2,424 (80.61%) | 2,641 (87.83%) | 2,420 (80.48%) | 1,703 (56.63%) | 1,859 (68.52%) |
| **All dimensions $\ge 1$** *(Free of zero-score failures)* | 2,951 (98.14%) | 2,928 (97.37%) | 2,944 (97.90%) | 2,864 (95.24%) | 2,645 (97.49%) |
| **Total Conversations** | 3,007 (100.0%) | 3,007 (100.0%) | 3,007 (100.0%) | 3,007 (100.0%) | 2,713 (100.0%)* |

---

## 4. Multi-Judge Consensus Analysis

Analyzing agreement across Judge 1, Judge 2, and Judge 3 on reaching top-tier ratings:

- **Unanimous "All 3s" (3 / 3 Judges):** **819 conversations** (27.24%) received straight 3s from all three independent judges.
- **Majority "All 3s" ($\ge 2$ Judges):** **1,300 conversations** (43.23%) reached top-tier consensus.
- **At least one Judge gave "All 3s":** **2,008 conversations** (66.78%).
- **Unanimous "All $\ge 2$" (3 / 3 Judges):** **2,215 conversations** (73.66%) demonstrated consistent quality with zero ratings below 2 from any judge.

---

## 5. Detailed Breakdown of JEV & JEV-2 (`imajev-4b`)

Because JEV outputs continuous expected scores $\mathbb{E}[S] = \sum_{k=0}^3 k \cdot P(k)$ in addition to class probability distributions, both standard interpretations are reported below:

### 5.1 JEV-1 (`jev_output/` &mdash; Dialogue Turns Only, $N = 3,007$)

#### Interpretation 1: Discrete Argmax Classification ($\text{argmax}_{k} P(k)$)
- **All 7 grades are 3:** **743** (24.71%)
- **All grades are 2 or 3 (min = 2):** **960** (31.93%)
- **All grades are 1, 2, or 3 (min = 1):** **1,161** (38.61%)
- **Contains at least one 0 (min = 0):** **143** (4.76%)

#### Interpretation 2: Rounded Expected Score ($\text{round}(\mathbb{E}[S])$)
- **All 7 metrics $\ge 2.50$ (All 3s):** **30** (1.00%)
- **All 7 metrics $\ge 1.50$, at least one $< 2.50$ (All 2 or 3):** **2,304** (76.62%)
- **All 7 metrics $\ge 0.50$, at least one $< 1.50$ (All 1, 2, or 3):** **649** (21.58%)
- **At least one metric $< 0.50$ (Contains 0):** **24** (0.80%)

### 5.2 JEV-2 (`jev_output2/` &mdash; Dialogues + State & Reasoning, $N = 2,713$)

#### Interpretation 1: Discrete Argmax Classification ($\text{argmax}_{k} P(k)$)
- **All 7 grades are 3:** **593** (21.86%)
- **All grades are 2 or 3 (min = 2):** **1,266** (46.66%)
- **All grades are 1, 2, or 3 (min = 1):** **786** (28.97%)
- **Contains at least one 0 (min = 0):** **68** (2.51%)

#### Interpretation 2: Continuous Rounded Expected Score ($\text{round}(\mathbb{E}[S])$)
- **All 7 metrics $\ge 2.50$ (All 3s):** **48** (1.77%)
- **All 7 metrics $\ge 1.50$, at least one $< 2.50$ (All 2 or 3):** **2,181** (80.39%)
- **All 7 metrics $\ge 0.50$, at least one $< 1.50$ (All 1, 2, or 3):** **466** (17.18%)
- **At least one metric $< 0.50$ (Contains 0):** **18** (0.66%)

---

## 6. Per-Model Distribution Table Across All 16 Models

Format for each cell: **`All 3 / Min 2 / Min 1 / Min 0`**

| Model Name | Sample ($N$) | Judge 1 (`beam:cloud`) | Judge 2 (`gpt-oss:120b`) | Judge 3 (`minimax-m3.1`) | JEV (`imajev-4b` Argmax) | JEV-2 (`imajev-4b` Argmax) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`Google_gemini-3.1-flash-lite`** | 246 | 119 / 113 / 14 / 0 | 193 / 42 / 8 / 3 | 126 / 108 / 11 / 1 | 46 / 113 / 83 / 4 | 50 / 133 / 40 / 0 |
| **`Google_gemini-3.5-flash-lite`** | 267 | 130 / 101 / 35 / 1 | 185 / 54 / 26 / 2 | 126 / 109 / 32 / 0 | 86 / 85 / 92 / 4 | 72 / 102 / 60 / 2 |
| **`Google_gemini-3.5-flash`** | 343 | 131 / 149 / 60 / 3 | 241 / 75 / 23 / 4 | 108 / 175 / 55 / 5 | 58 / 119 / 151 / 15 | 40 / 179 / 102 / 6 |
| **`Google_gemini-3-flash-preview`** | 408 | 121 / 195 / 89 / 3 | 257 / 111 / 32 / 8 | 107 / 213 / 84 / 4 | 65 / 132 / 189 / 22 | 32 / 202 / 128 / 10 |
| **`Google_gemini-3.6-flash`** | 245 | 84 / 112 / 43 / 6 | 153 / 62 / 21 / 9 | 72 / 115 / 51 / 7 | 48 / 83 / 97 / 17 | 37 / 102 / 68 / 13 |
| **`Google_gemma-4-31b-it`** | 240 | 81 / 100 / 54 / 5 | 150 / 57 / 27 / 6 | 87 / 96 / 49 / 8 | 66 / 66 / 98 / 10 | 46 / 98 / 70 / 14 |
| **`NVIDIA_nemotron-3-super-120b`** | 309 | 116 / 137 / 53 / 3 | 203 / 66 / 34 / 6 | 103 / 145 / 59 / 2 | 113 / 81 / 106 / 9 | 97 / 106 / 71 / 6 |
| **`OpenRouter_nemotron-3-super-120b`** | 222 | 84 / 102 / 34 / 2 | 157 / 42 / 21 / 2 | 81 / 99 / 42 / 0 | 78 / 66 / 72 / 6 | 71 / 81 / 51 / 5 |
| **`NVIDIA_nemotron-3-ultra-550b`** | 299 | 100 / 120 / 66 / 13 | 162 / 77 / 40 / 20 | 92 / 134 / 58 / 15 | 83 / 82 / 111 / 23 | 62 / 109 / 79 / 5 |
| **`OpenRouter_nemotron-3-ultra-550b`** | 289 | 100 / 106 / 64 / 19 | 158 / 69 / 45 / 17 | 92 / 115 / 63 / 19 | 70 / 76 / 115 / 28 | 55 / 100 / 85 / 4 |
| **`Google_gemini-2.5-flash-lite`** | 61 | 28 / 29 / 4 / 0 | 42 / 15 / 3 / 1 | 22 / 25 / 13 / 1 | 11 / 36 / 11 / 3 | 10 / 23 / 9 / 1 |
| **`NVIDIA_moonshotai_kimi-k3`** | 48 | 25 / 19 / 4 / 0 | 28 / 18 / 1 / 1 | 19 / 27 / 2 / 0 | 12 / 14 / 22 / 0 | 14 / 19 / 14 / 1 |
| **`Google_gemini-3.8-flash`** | 18 | 6 / 6 / 5 / 1 | 10 / 3 / 5 / 0 | 6 / 9 / 3 / 0 | 5 / 5 / 6 / 2 | 3 / 9 / 4 / 1 |
| **`Google_gemini-3.7-flash`** | 10 | 5 / 3 / 2 / 0 | 6 / 3 / 1 / 0 | 5 / 2 / 2 / 1 | 1 / 2 / 7 / 0 | 3 / 3 / 4 / 0 |
| **`NVIDIA_deepseek-v4-pro-0813`** | 1 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 |
| **`NVIDIA_deepseek-v4-flash-0731`** | 1 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 | 0 / 0 / 1 / 0 | 0 / 0 / 1 / 0 |

---

## 7. Key Findings & Evaluator Profiles

1. **Judge 2 (`gpt-oss:120b`) is the most lenient evaluator:**
   - Classified **64.75%** of all conversations as straight-3s.
   - Shows high tolerance for minor guidance slips.

2. **Judge 1 (`beam:cloud`) and Judge 3 (`minimax-m3.1-flash`) demonstrate strong calibration:**
   - Straight-3 rates of **37.65%** and **34.85%** respectively.
   - The majority of conversations fall into the solid "All 2 or 3" band (~43–46%).

3. **JEV (`imajev-4b` Run 1) is the most stringent evaluator:**
   - Only **24.71%** achieve straight-3s under discrete argmax, and only **1.00%** maintain $\ge 2.5$ expected score across all 7 dimensions simultaneously.
   - Diagnoses weak interventions (min grade 1 or 0) in **43.37%** of conversations, making it particularly effective at detecting edge-case pedagogical degradation.

4. **Zero-score failures are rare across all judges:**
   - Severe pedagogical breakdowns (grade 0 in any category) occur in fewer than **5%** of conversations across all evaluators.

5. **JEV-2 (`imajev-4b` Run 2 with State & Reasoning Context):**
   - Incorporating internal state and pedagogical reasoning provides the SLM with richer context on tutor intent, shifting **46.66%** of conversations into the solid "All 2 or 3" band (up from 31.93% in JEV-1).
   - Zero-score failures dropped from 4.76% to **2.51%**, aligning closer with human-like tolerance for pedagogical exploration when tutor rationale is visible.
