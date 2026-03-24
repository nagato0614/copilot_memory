FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY copilot_memory/ ./copilot_memory/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Pre-download embedding model
RUN python -c "\
from copilot_memory.config import EMBEDDING_MODEL, MODEL_CACHE_DIR; \
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True); \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer(EMBEDDING_MODEL, cache_folder=str(MODEL_CACHE_DIR))"

# Default data directory (mount a volume here for persistence)
ENV COPILOT_MEMORY_DIR=/data
VOLUME /data

# Run MCP server via stdio
ENTRYPOINT ["python", "-m", "copilot_memory.server"]
