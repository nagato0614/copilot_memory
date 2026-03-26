"""Chunk storage: insert, update, deduplication, and conversation parsing."""

import re
import time
import uuid

from .config import DEDUP_L2_THRESHOLD
from .db import get_connection
from .embedding import embed_passage, serialize_float32
from .models import ConversationSaveResult, SaveResult


def _fetchone(conn, sql, params=()):
    """Fetch one row from apsw cursor (returns None if empty)."""
    for row in conn.execute(sql, params):
        return row
    return None


def save_chunk(
    content: str, project: str = "", tags: str = "", source_path: str = ""
) -> SaveResult:
    """Save a content chunk, deduplicating against existing chunks."""
    conn = get_connection()
    embedding = embed_passage(content)
    embedding_bytes = serialize_float32(embedding)

    # Dedup: find nearest neighbor
    row = _fetchone(
        conn,
        "SELECT rowid, distance FROM chunks_vec WHERE embedding MATCH ? AND k = 1",
        (embedding_bytes,),
    )

    if row and row[1] < DEDUP_L2_THRESHOLD:
        # Update existing chunk
        existing_rowid = row[0]
        now = time.time()
        conn.execute(
            "UPDATE chunks SET updated_at = ?, access_count = access_count + 1 "
            "WHERE rowid = ?",
            (now, existing_rowid),
        )
        chunk_row = _fetchone(
            conn, "SELECT id FROM chunks WHERE rowid = ?", (existing_rowid,)
        )
        return SaveResult(id=chunk_row[0], status="deduplicated")

    # Insert new chunk
    chunk_id = uuid.uuid4().hex
    now = time.time()
    conn.execute(
        "INSERT INTO chunks (id, content, project, tags, source_path, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (chunk_id, content, project, tags, source_path, now, now),
    )

    # Get the rowid of the newly inserted chunk
    rowid_row = _fetchone(
        conn, "SELECT rowid FROM chunks WHERE id = ?", (chunk_id,)
    )

    # Insert vector
    conn.execute(
        "INSERT INTO chunks_vec (rowid, embedding) VALUES (?, ?)",
        (rowid_row[0], embedding_bytes),
    )
    return SaveResult(id=chunk_id, status="saved")


def delete_by_source_path(source_path: str) -> int:
    """Delete all chunks with the given source_path. Returns count deleted."""
    conn = get_connection()
    rows = list(conn.execute(
        "SELECT rowid FROM chunks WHERE source_path = ?", (source_path,)
    ))
    if not rows:
        return 0
    rowids = [r[0] for r in rows]
    placeholders = ",".join("?" for _ in rowids)
    # Delete from vec index first
    conn.execute(
        f"DELETE FROM chunks_vec WHERE rowid IN ({placeholders})", rowids
    )
    # Delete from chunks (FTS triggers handle chunks_fts cleanup)
    conn.execute(
        f"DELETE FROM chunks WHERE rowid IN ({placeholders})", rowids
    )
    return len(rowids)


def split_conversation(text: str) -> list[str]:
    """Split conversation text into content chunks (one per turn)."""
    user_pattern = r"(?:^|\n)\s*(?:User|Human|Q)\s*[:\-]\s*"
    assistant_pattern = r"(?:^|\n)\s*(?:Assistant|AI|A|Copilot|Claude)\s*[:\-]\s*"

    parts = re.split(user_pattern, text, flags=re.IGNORECASE)

    chunks = []
    for part in parts:
        if not part.strip():
            continue
        answer_split = re.split(assistant_pattern, part, maxsplit=1, flags=re.IGNORECASE)
        if len(answer_split) == 2:
            q = answer_split[0].strip()
            a = answer_split[1].strip()
            if q and a:
                chunks.append(f"{q}\n{a}")
            elif q:
                chunks.append(q)
        elif part.strip():
            chunks.append(part.strip())

    return [c for c in chunks if c]


def save_conversation(conversation: str, project: str = "") -> ConversationSaveResult:
    """Parse and save a multi-turn conversation."""
    chunks = split_conversation(conversation)
    saved = 0
    deduped = 0

    for content in chunks:
        result = save_chunk(content, project=project)
        if result.status == "saved":
            saved += 1
        else:
            deduped += 1

    return ConversationSaveResult(saved_count=saved, deduplicated_count=deduped)
