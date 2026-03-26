"""Tests for database initialization and schema."""

from copilot_memory.db import get_connection


def test_connection_creates_db(tmp_memory_dir):
    """DB file is created on first connection."""
    conn = get_connection()
    db_files = list(tmp_memory_dir.glob("memory.db*"))
    assert len(db_files) > 0


def test_schema_tables_exist(tmp_memory_dir):
    """All required tables are created."""
    conn = get_connection()
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'trigger') ORDER BY name"
        )
    ]
    assert "chunks" in tables
    assert "chunks_fts" in tables
    assert "chunks_vec" in tables
    assert "chunks_ai" in tables
    assert "chunks_ad" in tables
    assert "chunks_au" in tables


def test_chunks_table_columns(tmp_memory_dir):
    """chunks table has expected columns."""
    conn = get_connection()
    columns = [row[1] for row in conn.execute("PRAGMA table_info(chunks)")]
    expected = ["id", "content", "project", "tags", "source_path", "created_at", "updated_at", "access_count"]
    for col in expected:
        assert col in columns


def test_connection_is_singleton(tmp_memory_dir):
    """get_connection returns the same connection object."""
    conn1 = get_connection()
    conn2 = get_connection()
    assert conn1 is conn2
