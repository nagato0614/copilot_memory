"""Hybrid search: FTS5 keyword + vector search + RRF fusion + time decay."""

import time

from .config import (
    DEFAULT_SEARCH_LIMIT,
    FTS_LIMIT,
    RRF_K,
    TIME_DECAY_HALF_LIFE_DAYS,
    VEC_LIMIT,
)
from .db import get_connection
from .embedding import embed_query, serialize_float32
from .models import SearchResult


def _fts_escape(query: str) -> str:
    """Escape and format query for FTS5 trigram tokenizer."""
    tokens = query.split()
    valid = [f'"{t}"' for t in tokens if len(t) >= 3]
    if not valid:
        if len(query) >= 3:
            return f'"{query}"'
        return ""
    return " OR ".join(valid)


def hybrid_search(
    query: str, limit: int = DEFAULT_SEARCH_LIMIT, project: str = ""
) -> list[SearchResult]:
    """Run hybrid search combining FTS5 keyword and vector similarity."""
    conn = get_connection()

    # 1. FTS5 keyword search
    fts_query = _fts_escape(query)
    fts_results: list[tuple[int, float]] = []
    if fts_query:
        fts_results = list(conn.execute(
            "SELECT rowid, rank FROM chunks_fts WHERE chunks_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (fts_query, FTS_LIMIT),
        ))

    # 2. Vector search
    embedding = embed_query(query)
    embedding_bytes = serialize_float32(embedding)
    vec_results = list(conn.execute(
        "SELECT rowid, distance FROM chunks_vec "
        "WHERE embedding MATCH ? AND k = ?",
        (embedding_bytes, VEC_LIMIT),
    ))

    # 3. RRF fusion
    scores: dict[int, float] = {}
    for rank_pos, (rowid, _) in enumerate(fts_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (RRF_K + rank_pos + 1)
    for rank_pos, (rowid, _) in enumerate(vec_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (RRF_K + rank_pos + 1)

    if not scores:
        return []

    # 4. Time decay + fetch metadata
    now = time.time()
    half_life_seconds = TIME_DECAY_HALF_LIFE_DAYS * 86400
    rowids = list(scores.keys())

    placeholders = ",".join("?" for _ in rowids)
    rows = list(conn.execute(
        f"SELECT rowid, id, question, answer, project, created_at "
        f"FROM chunks WHERE rowid IN ({placeholders})",
        rowids,
    ))

    chunk_map = {}
    for row in rows:
        rowid, chunk_id, question, answer, proj, created_at = row
        age = now - created_at
        decay = 0.5 ** (age / half_life_seconds)
        scores[rowid] *= decay
        chunk_map[rowid] = (chunk_id, question, answer, proj, created_at)

    # 5. Filter by project
    if project:
        scored_rowids = [
            (rid, s)
            for rid, s in scores.items()
            if rid in chunk_map and chunk_map[rid][3] == project
        ]
    else:
        scored_rowids = [
            (rid, s) for rid, s in scores.items() if rid in chunk_map
        ]

    # 6. Sort and limit
    scored_rowids.sort(key=lambda x: x[1], reverse=True)
    results = []
    for rid, score in scored_rowids[:limit]:
        chunk_id, question, answer, proj, created_at = chunk_map[rid]
        results.append(
            SearchResult(
                id=chunk_id,
                question=question,
                answer=answer,
                project=proj,
                score=score,
                created_at=created_at,
            )
        )

    return results
