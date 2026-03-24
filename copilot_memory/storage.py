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
    question: str, answer: str, project: str = "", tags: str = ""
) -> SaveResult:
    """Save a Q&A pair, deduplicating against existing chunks."""
    conn = get_connection()
    text = question + "\n" + answer
    embedding = embed_passage(text)
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
        "INSERT INTO chunks (id, question, answer, project, tags, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (chunk_id, question, answer, project, tags, now, now),
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


def split_conversation(text: str) -> list[tuple[str, str]]:
    """Split conversation text into (question, answer) pairs."""
    user_pattern = r"(?:^|\n)\s*(?:User|Human|Q)\s*[:\-]\s*"
    assistant_pattern = r"(?:^|\n)\s*(?:Assistant|AI|A|Copilot|Claude)\s*[:\-]\s*"

    parts = re.split(user_pattern, text, flags=re.IGNORECASE)

    pairs = []
    for part in parts:
        if not part.strip():
            continue
        answer_split = re.split(assistant_pattern, part, maxsplit=1, flags=re.IGNORECASE)
        if len(answer_split) == 2:
            pairs.append((answer_split[0].strip(), answer_split[1].strip()))
        elif part.strip():
            pairs.append((part.strip(), ""))

    return [(q, a) for q, a in pairs if q]


def save_conversation(conversation: str, project: str = "") -> ConversationSaveResult:
    """Parse and save a multi-turn conversation."""
    pairs = split_conversation(conversation)
    saved = 0
    deduped = 0

    for question, answer in pairs:
        result = save_chunk(question, answer, project=project)
        if result.status == "saved":
            saved += 1
        else:
            deduped += 1

    return ConversationSaveResult(saved_count=saved, deduplicated_count=deduped)
