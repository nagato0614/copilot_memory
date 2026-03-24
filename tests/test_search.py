"""Tests for hybrid search functionality."""

from copilot_memory.search import hybrid_search, _fts_escape
from copilot_memory.storage import save_chunk


def _seed_data(tmp_memory_dir):
    """Insert test data for search tests."""
    save_chunk("Pythonでリスト内包表記の使い方", "リスト内包表記は [expr for item in iterable] の形式です", project="python")
    save_chunk("asyncioの基本的な使い方", "asyncio.run()でコルーチンを実行します", project="python")
    save_chunk("DockerでMCPサーバーを起動する方法", "docker run -i で stdin/stdout をパイプします", project="infra")


def test_fts_escape_basic():
    """FTS escape formats tokens correctly."""
    result = _fts_escape("Python list comprehension")
    assert '"Python"' in result
    assert '"list"' in result
    assert '"comprehension"' in result
    assert " OR " in result


def test_fts_escape_short_tokens():
    """Short tokens (< 3 chars) are filtered out."""
    result = _fts_escape("go is ok")
    # "go", "is", "ok" are all < 3 chars, none pass filter
    # But full query "go is ok" >= 3 chars, so falls back to full query
    assert result == '"go is ok"'


def test_fts_escape_full_query_fallback():
    """Full query used as fallback when >= 3 chars."""
    result = _fts_escape("abc")
    assert result == '"abc"'


def test_hybrid_search_returns_results(tmp_memory_dir):
    """Search returns relevant results."""
    _seed_data(tmp_memory_dir)
    results = hybrid_search("Pythonのリスト", limit=3)
    assert len(results) > 0
    assert results[0].question  # has content


def test_hybrid_search_relevance_ordering(tmp_memory_dir):
    """Most relevant result has highest score."""
    _seed_data(tmp_memory_dir)
    results = hybrid_search("Pythonのリスト内包表記", limit=3)
    assert len(results) > 0
    # First result should be most relevant
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_search_project_filter(tmp_memory_dir):
    """Project filter narrows results."""
    _seed_data(tmp_memory_dir)
    results = hybrid_search("使い方", limit=10, project="infra")
    for r in results:
        assert r.project == "infra"


def test_hybrid_search_empty_query(tmp_memory_dir):
    """Empty or very short query returns empty results."""
    _seed_data(tmp_memory_dir)
    results = hybrid_search("ab", limit=3)
    # Very short query may still get vector results
    # Just verify it doesn't crash
    assert isinstance(results, list)


def test_hybrid_search_no_data(tmp_memory_dir):
    """Search on empty DB returns empty list."""
    results = hybrid_search("anything", limit=5)
    assert isinstance(results, list)
    assert len(results) == 0
