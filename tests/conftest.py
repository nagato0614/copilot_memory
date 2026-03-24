"""Shared test fixtures for copilot-memory tests."""

import pathlib

import pytest


@pytest.fixture(autouse=True)
def tmp_memory_dir(tmp_path, monkeypatch):
    """Use a temporary directory for each test to isolate DB and model cache."""
    monkeypatch.setenv("COPILOT_MEMORY_DIR", str(tmp_path))

    # Reset singleton connection between tests
    import copilot_memory.db as db_mod
    if db_mod._connection is not None:
        db_mod._connection.close()
    db_mod._connection = None

    # Reset config module to pick up new env var
    import copilot_memory.config as config_mod
    config_mod.MEMORY_DIR = tmp_path
    config_mod.DB_PATH = tmp_path / "memory.db"
    # Keep models in a shared location so we don't re-download each test
    config_mod.MODEL_CACHE_DIR = pathlib.Path.home() / ".copilot-memory" / "models"

    yield tmp_path

    # Cleanup connection after test
    if db_mod._connection is not None:
        db_mod._connection.close()
        db_mod._connection = None
