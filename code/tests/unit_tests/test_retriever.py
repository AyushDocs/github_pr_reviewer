import numpy as np
from unittest.mock import patch, MagicMock
from agent.retriever import retrieve, format_context, _tokenize

SAMPLE_KB = [
    {"id": "CR-001", "title": "Hardcoded secrets", "severity": "CRITICAL", "popularity": 1, "bad_pattern": "API_KEY = 'sk-123'", "good_pattern": "os.getenv('API_KEY')", "description": "test", "keywords": ["api_key"]},
    {"id": "CR-002", "title": "SQL injection", "severity": "CRITICAL", "popularity": 2, "bad_pattern": "f'SELECT *'", "good_pattern": "param query", "description": "test", "keywords": ["execute"]},
    {"id": "CR-003", "title": "Missing error handling", "severity": "MEDIUM", "popularity": 3, "bad_pattern": "except: pass", "good_pattern": "log error", "description": "test", "keywords": ["except"]},
    {"id": "CR-004", "title": "Command injection", "severity": "CRITICAL", "popularity": 4, "bad_pattern": "os.system(cmd)", "good_pattern": "subprocess.run", "description": "test", "keywords": ["shell"]},
]


def _mock_indexes(kb):
    import agent.retriever as r
    r._global_bm25_index = MagicMock()
    r._global_bm25_index.get_scores.return_value = np.array([0.8, 0.6, 0.4, 0.2])
    r._global_kb_embeddings = [np.array([1.0, 0.0]) for _ in kb]
    r._global_kb_texts = ["a"] * len(kb)
    r._global_kb_size = len(kb)


def test_retrieve_returns_matching_entries():
    with patch("agent.retriever._init_indexes"):
        _mock_indexes(SAMPLE_KB)
        with patch("agent.retriever.score_dense", return_value=[0.9, 0.7, 0.5, 0.3]):
            diffs = [{"filename": "app/db.py", "patch": "cursor.execute('SELECT *')"}]
            results = retrieve(diffs, SAMPLE_KB, top_k=2)

    assert len(results) == 2
    assert results[0]["id"] in ("CR-001", "CR-002")
    assert results[1]["id"] in ("CR-001", "CR-002")


def test_retrieve_returns_empty_for_no_diffs():
    assert retrieve([], SAMPLE_KB) == []


def test_retrieve_returns_empty_for_empty_kb():
    diffs = [{"filename": "app/main.py", "patch": "x = 1"}]
    assert retrieve(diffs, []) == []


def test_retrieve_handles_no_patch_in_diff():
    with patch("agent.retriever._init_indexes"):
        _mock_indexes(SAMPLE_KB)
        with patch("agent.retriever.score_dense", return_value=[0.1] * 4):
            diffs = [{"filename": "app/main.py"}]  # no patch key
            results = retrieve(diffs, SAMPLE_KB, top_k=2)

    assert len(results) == 2


def test_format_context_empty():
    assert format_context([]) == ""


def test_format_context_formats_entries():
    entries = [{"id": "CR-001", "severity": "CRITICAL", "title": "Test", "bad_pattern": "bad", "good_pattern": "good"}]
    result = format_context(entries)
    assert "CR-001" in result
    assert "CRITICAL" in result
    assert "Test" in result
    assert "bad" in result
    assert "good" in result


def test_format_context_multiple_entries():
    entries = [
        {"id": "CR-001", "severity": "HIGH", "title": "A", "bad_pattern": "x", "good_pattern": "y"},
        {"id": "CR-002", "severity": "LOW", "title": "B", "bad_pattern": "a", "good_pattern": "b"},
    ]
    result = format_context(entries)
    assert "CR-001" in result
    assert "CR-002" in result


def test_tokenize():
    assert _tokenize("foo.Bar_123 baz!") == ["foo", "bar_123", "baz"]
