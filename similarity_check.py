import os
import json
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Logging setup ──────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s  %(levelname)s  %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIRECTORY = os.path.join(SCRIPT_DIR, "data")
SIMILARITY_THRESHOLD = 0.90

file_handler = logging.FileHandler(
    os.path.join(SCRIPT_DIR, "similarity.log"), mode="a", encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
log.addHandler(file_handler)


def extract_text_from_convo(convo):
    """Helper to extract text from a conversation array."""
    texts = []
    for turn in convo:
        if 'text' in turn:
            texts.append(turn['text'])
        if 'response' in turn:
            texts.append(turn['response'])
    return " ".join(texts)


def get_all_json_files(data_dir):
    """Retrieve all JSON files while excluding specific folders."""
    json_files = []
    for root, dirs, files in os.walk(data_dir):
        dirs[:] = [d for d in dirs if d not in ['logs', 'rejected_responses']]

        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    return json_files


def run_fast_similarity(data_dir, threshold=0.90):
    all_files = get_all_json_files(data_dir)
    log.info("Found %d files. Loading conversations into memory...", len(all_files))

    entries = []

    # 1. Open files exactly once and load texts into memory
    for file_path in all_files:
        folder_name = os.path.basename(os.path.dirname(file_path))
        filename = os.path.basename(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for idx, item in enumerate(data):
                        if 'conversation' in item:
                            text = extract_text_from_convo(item['conversation'])
                            if text.strip():  # Only keep non-empty conversations
                                entries.append({
                                    'folder': folder_name,
                                    'filename': filename,
                                    'index': idx,
                                    'text': text
                                })
        except Exception:
            log.warning("Skipping unreadable file: %s", file_path)

    num_entries = len(entries)
    log.info("Loaded %d conversation entries.", num_entries)

    if num_entries < 2:
        log.info("Not enough entries to compare.")
        return

    log.info("Vector embedding all conversations simultaneously...")
    texts = [entry['text'] for entry in entries]
    vectorizer = TfidfVectorizer(stop_words='english')
    # 2. Fit TF-IDF on all documents at once
    tfidf_matrix = vectorizer.fit_transform(texts)

    log.info("Calculating full cosine similarity matrix...")
    # 3. Calculate all pairwise similarities mathematically at once
    similarity_matrix = cosine_similarity(tfidf_matrix)

    log.info("Finding pairs with similarity >= %s", threshold)
    found_pairs = 0

    # 4. Iterate over the upper triangle of the matrix to extract results
    for i in range(num_entries):
        for j in range(i + 1, num_entries):
            sim = similarity_matrix[i, j]
            if sim >= threshold:
                loc1 = f"{entries[i]['folder']}/{entries[i]['filename']} (index {entries[i]['index']})"
                loc2 = f"{entries[j]['folder']}/{entries[j]['filename']} (index {entries[j]['index']})"

                log.warning(
                    "Similarity: %.4f  Pair 1: %s  Pair 2: %s",
                    sim, loc1, loc2,
                )
                found_pairs += 1

    log.info("Total similar pairs found: %d", found_pairs)


if __name__ == "__main__":
    run_fast_similarity(DATA_DIRECTORY, SIMILARITY_THRESHOLD)
