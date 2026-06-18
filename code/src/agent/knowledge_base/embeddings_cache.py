import json
import os
import hashlib
import numpy as np
from langsmith import traceable
from agent.config import embeddings as embed_model
from agent.utils.logger import get_logger

log = get_logger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), ".kb_embeddings.json")
CACHE_VERSION = 1


def _entry_text(entry: dict) -> str:
    parts = [
        entry.get("title", ""),
        entry.get("description", ""),
        entry.get("bad_pattern", ""),
        entry.get("good_pattern", ""),
        " ".join(entry.get("keywords", [])),
    ]
    return " ".join(p for p in parts if p)


def _kb_hash(kb: list) -> str:
    raw = json.dumps([{k: e[k] for k in ("id", "title", "bad_pattern", "good_pattern", "keywords", "description")} for e in kb], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def load_or_compute_embeddings(kb: list) -> tuple:
    kb_hash = _kb_hash(kb)
    cached = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cached = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if cached and cached.get("version") == CACHE_VERSION and cached.get("kb_hash") == kb_hash:
        log.info("Using cached KB embeddings (%s entries)", len(cached["embeddings"]))
        embeddings_list = [np.array(e) for e in cached["embeddings"]]
        texts = cached["texts"]
        return embeddings_list, texts

    log.info("Computing KB embeddings for %s entries...", len(kb))
    texts = [_entry_text(e) for e in kb]
    raw_embeddings = embed_model.embed_documents(texts)
    embeddings_list = [np.array(e) for e in raw_embeddings]

    cache_data = {
        "version": CACHE_VERSION,
        "kb_hash": kb_hash,
        "texts": texts,
        "embeddings": raw_embeddings,
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
        log.info("KB embeddings cached to %s", CACHE_FILE)
    except OSError as e:
        log.warning("Failed to cache embeddings: %s", e)

    return embeddings_list, texts


def score_dense(diff_text: str, kb_embeddings: list) -> list:
    diff_emb = np.array(embed_model.embed_query(diff_text))
    scores = [_cosine_similarity(diff_emb, kb_e) for kb_e in kb_embeddings]
    return scores
