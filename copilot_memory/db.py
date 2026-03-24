"""SQLite database connection and schema management using apsw."""

import apsw
import sqlite_vec

from . import config
from .embedding import get_embedding_dim

_connection: apsw.Connection | None = None


def get_connection() -> apsw.Connection:
    """Get or create the singleton database connection."""
    global _connection
    if _connection is None:
        config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        _connection = apsw.Connection(str(config.DB_PATH))
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.enable_load_extension(True)
        _connection.load_extension(sqlite_vec.loadable_path())
        _connection.enable_load_extension(False)
        _init_schema(_connection)
    return _connection


def _init_schema(conn: apsw.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          TEXT PRIMARY KEY,
            question    TEXT NOT NULL,
            answer      TEXT NOT NULL,
            project     TEXT DEFAULT '',
            tags        TEXT DEFAULT '',
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL,
            access_count INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            question,
            answer,
            tags,
            content='chunks',
            content_rowid='rowid',
            tokenize='trigram'
        )
    """)

    # FTS sync triggers
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, question, answer, tags)
            VALUES (new.rowid, new.question, new.answer, new.tags);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, question, answer, tags)
            VALUES ('delete', old.rowid, old.question, old.answer, old.tags);
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, question, answer, tags)
            VALUES ('delete', old.rowid, old.question, old.answer, old.tags);
            INSERT INTO chunks_fts(rowid, question, answer, tags)
            VALUES (new.rowid, new.question, new.answer, new.tags);
        END
    """)

    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec "
        f"USING vec0(embedding float[{get_embedding_dim()}])"
    )


def close_connection() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
