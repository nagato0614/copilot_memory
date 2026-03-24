"""Local embedding model management."""

import struct

from .config import EMBEDDING_MODEL, MODEL_CACHE_DIR, PASSAGE_PREFIX, QUERY_PREFIX

_model = None
_embedding_dim: int | None = None


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model, _embedding_dim
    if _model is None:
        from sentence_transformers import SentenceTransformer

        MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=str(MODEL_CACHE_DIR))
        _embedding_dim = _model.get_sentence_embedding_dimension()
    return _model


def get_embedding_dim() -> int:
    """Get the embedding dimension for the current model."""
    if _embedding_dim is None:
        _get_model()
    return _embedding_dim  # type: ignore


def embed_query(text: str) -> list[float]:
    """Embed a search query. Adds 'query: ' prefix for E5 models."""
    model = _get_model()
    vec = model.encode(QUERY_PREFIX + text, normalize_embeddings=True)
    return vec.tolist()


def embed_passage(text: str) -> list[float]:
    """Embed a passage for storage. Adds 'passage: ' prefix for E5 models."""
    model = _get_model()
    vec = model.encode(PASSAGE_PREFIX + text, normalize_embeddings=True)
    return vec.tolist()


def serialize_float32(vec: list[float]) -> bytes:
    """Serialize a float vector to bytes for sqlite-vec."""
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_float32(data: bytes) -> list[float]:
    """Deserialize bytes to a float vector."""
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))
