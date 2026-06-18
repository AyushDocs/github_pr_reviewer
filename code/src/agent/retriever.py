import re
import numpy as np
from rank_bm25 import BM25Okapi
from langsmith import traceable
from agent.knowledge_base.embeddings_cache import load_or_compute_embeddings, score_dense
from agent.utils.logger import get_logger

log = get_logger(__name__)

_global_bm25_index = None
_global_kb_texts = None
_global_kb_embeddings = None
_global_kb_id = None

HYBRID_WEIGHT_BM25 = 0.3
HYBRID_WEIGHT_DENSE = 0.7


def _tokenize(text: str) -> list:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def _init_indexes(kb: list):
    global _global_bm25_index, _global_kb_texts, _global_kb_embeddings, _global_kb_id
    kb_id = id(kb)
    if _global_kb_id == kb_id and _global_kb_id is not None:
        return

    _global_kb_embeddings, _global_kb_texts = load_or_compute_embeddings(kb)
    tokenized = [_tokenize(t) for t in _global_kb_texts]
    _global_bm25_index = BM25Okapi(tokenized)
    _global_kb_id = kb_id
    log.info("Indexes built for %s KB entries", len(kb))


@traceable(name="retrieve_kb", run_type="retriever")
def retrieve(diffs: list, kb: list, top_k: int = 5) -> list:
    if not diffs or not kb:
        return []

    _init_indexes(kb)
    diff_text = "\n".join(d.get("patch", "") for d in diffs)
    diff_tokens = _tokenize(diff_text)

    bm25_scores = np.array(_global_bm25_index.get_scores(diff_tokens))
    bm25_norm = bm25_scores / (bm25_scores.max() + 1e-10)

    dense_scores = np.array(score_dense(diff_text, _global_kb_embeddings))
    dense_norm = dense_scores / (dense_scores.max() + 1e-10)

    hybrid = HYBRID_WEIGHT_BM25 * bm25_norm + HYBRID_WEIGHT_DENSE * dense_norm
    top_indices = np.argsort(hybrid)[-top_k:][::-1]

    results = [kb[i] for i in top_indices]
    log.info("Retrieved %s entries via hybrid search", len(results))
    return results


def format_context(entries: list) -> str:
    if not entries:
        return ""
    lines = ["## Relevant known bad practices:\n"]
    for entry in entries:
        lines.append(
            f"- [{entry['id']}] ({entry['severity']}) {entry['title']}\n"
            f"  Pattern: {entry['bad_pattern']}\n"
            f"  Fix: {entry['good_pattern']}\n"
        )
    return "\n".join(lines)
