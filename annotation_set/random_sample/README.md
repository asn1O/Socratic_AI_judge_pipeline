# Random Sample Selection (Task 1)

This directory contains the randomly sampled benchmark set of **240 conversations** selected for human annotation.

## Overview

- **Strategy**: Unbiased uniform random sampling without replacement across the entire dataset.
- **Sample Size**: 240 conversations.
- **Annotation IDs**: `RND-0001` through `RND-0240`.
- **Random Seed**: `42` (default).
- **Candidate Pool**: 2,713 total conversations across 249 source JSON files.

## Selection Methodology

1. **Deterministic Discovery & Sorting**:
   - Recursively discovers all `.json` files under `data/`.
   - Enumerates every conversation by its relative file path (POSIX format) and 0-based array index `(relative_path, index)`.
   - Sorts all record references lexicographically by `(relative_path, index)` prior to sampling. This eliminates operating system and filesystem traversal non-determinism, ensuring exact reproducibility with the same random seed.

2. **Uniform Sampling**:
   - Samples exactly 240 unique references using Python's standard `random.Random(seed).sample(...)`.
   - Sampling is performed globally across the dataset rather than per file or per subfolder, reflecting the natural distribution of the dataset.

3. **Two-Pass Record Alignment**:
   - Groups selected references by source file so each required file is read from disk only once.
   - Extracts corresponding records at the exact same relative path and array index from all three directory trees:
     - `data/`: original conversation text, domain, topic, and problem config.
     - `output/`: outputs from Judge 1 (`beam:cloud`), Judge 2 (`gpt-oss:120b`), and Judge 3 (`minimax-m3.1`).
     - `jev_output/`: outputs from JEV (`imajev-4b`).
   - Preserves original sample ordering and assigns sequential annotation IDs `RND-0001` to `RND-0240`.

4. **Directory Protection**:
   - The sampling script protects existing outputs and will refuse to overwrite this folder unless `--overwrite` is explicitly provided.

## Directory Structure

```text
annotation_set/random_sample/
├── annotations.json          # 240 aligned records with conversation and all judge outputs
├── manifest.json             # Seed, requested/actual size, timestamp, source paths, and index map
├── selection_summary.json    # Record counts and distribution across source subfolders and files
└── README.md                 # This documentation
```

### Record Structure in `annotations.json`

```json
{
  "annotation_id": "RND-0001",
  "sampling_strategy": "random",
  "source": {
    "relative_path": "OpenRouter_nvidia_nemotron-3-ultra-550b-a55b_free/edw-set[4].json",
    "index": 8
  },
  "conversation": { ... },
  "llm_judge_output": { ... },
  "jev_output": { ... }
}
```

## Reproduction Command

```bash
python scripts/sample_random.py \
    --data-dir data \
    --output-dir output \
    --jev-dir jev_output \
    --annotation-dir annotation_set/random_sample \
    --sample-size 240 \
    --seed 42 \
    --overwrite
```
