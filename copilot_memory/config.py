"""Configuration constants for copilot-memory."""

import os
import pathlib

# Paths
MEMORY_DIR = pathlib.Path(
    os.environ.get("COPILOT_MEMORY_DIR", str(pathlib.Path.home() / ".copilot-memory"))
)
DB_PATH = MEMORY_DIR / "memory.db"
MODEL_CACHE_DIR = MEMORY_DIR / "models"

# Embedding
EMBEDDING_MODEL = os.environ.get(
    "COPILOT_MEMORY_MODEL", "intfloat/multilingual-e5-large"
)
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

# Search
RRF_K = 60
FTS_LIMIT = 50
VEC_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 10
TIME_DECAY_HALF_LIFE_DAYS = 30

# Deduplication
DEDUP_SIMILARITY_THRESHOLD = 0.92
DEDUP_L2_THRESHOLD = 0.40
