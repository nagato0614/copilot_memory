"""Pydantic data models for copilot-memory."""

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A stored memory chunk."""

    id: str
    content: str
    project: str = ""
    tags: str = ""
    source_path: str = ""
    created_at: float
    updated_at: float
    access_count: int = 0


class SearchResult(BaseModel):
    """A search result with score."""

    id: str
    content: str
    project: str = ""
    source_path: str = ""
    score: float
    created_at: float


class SaveResult(BaseModel):
    """Result of a save operation."""

    id: str
    status: str = Field(description="'saved' or 'deduplicated'")


class ConversationSaveResult(BaseModel):
    """Result of a conversation save operation."""

    saved_count: int
    deduplicated_count: int
