"""Tests for hybrid search functionality."""

from copilot_memory.search import hybrid_search, _fts_escape
from copilot_memory.storage import save_chunk


def _seed_data(tmp_memory_dir):
    """Insert test data for search tests."""
    save_chunk("Pythonでリスト内包表記を使う方法: [expr for item in iterable] の形式で新しいリストを生成する。", project="python")
    save_chunk("asyncioの基本的な使い方: asyncio.run()でコルーチンを実行し、awaitでI/O待ちを非同期化する。", project="python")
    save_chunk("DockerでMCPサーバーを起動する方法: docker run -i でstdin/stdoutをパイプしてstdio transportで接続する。", project="infra")


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
    assert results[0].content


def test_hybrid_search_relevance_ordering(tmp_memory_dir):
    """Most relevant result has highest score."""
    _seed_data(tmp_memory_dir)
    results = hybrid_search("Pythonのリスト内包表記", limit=3)
    assert len(results) > 0
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_search_project_filter(tmp_memory_dir):
    """Project filter narrows results."""
    _seed_data(tmp_memory_dir)
    results = hybrid_search("使い方", limit=10, project="infra")
    for r in results:
        assert r.project == "infra"


def test_hybrid_search_empty_query(tmp_memory_dir):
    """Empty or very short query doesn't crash."""
    _seed_data(tmp_memory_dir)
    results = hybrid_search("ab", limit=3)
    assert isinstance(results, list)


def test_hybrid_search_no_data(tmp_memory_dir):
    """Search on empty DB returns empty list."""
    results = hybrid_search("anything", limit=5)
    assert isinstance(results, list)
    assert len(results) == 0


def test_hybrid_search_returns_source_path(tmp_memory_dir):
    """Search results include source_path field."""
    save_chunk("[ファイル: /tmp/test.py]\ndef hello(): pass", source_path="/tmp/test.py", project="test")
    results = hybrid_search("hello function", limit=3)
    assert len(results) > 0
    assert results[0].source_path == "/tmp/test.py"
