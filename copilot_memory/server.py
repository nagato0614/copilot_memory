"""MCP server for copilot-memory: long-term memory for AI coding assistants."""

import asyncio
import json

from mcp.server.fastmcp import FastMCP

from .models import ConversationSaveResult, SaveResult, SearchResult
from .search import hybrid_search
from .storage import save_chunk, save_conversation as _save_conversation

mcp = FastMCP(
    name="copilot-memory",
    instructions=(
        "Long-term memory system for AI coding assistants. "
        "MANDATORY: Call search_memory BEFORE every response to retrieve relevant context. "
        "MANDATORY: Call save_memory AFTER every response — multiple times, one per topic. "
        "Save not just Q&A, but also design decisions, work logs, insights, and discussions."
    ),
)


@mcp.tool()
def search_memory(query: str, limit: int = 10, project: str = "") -> str:
    """MANDATORY: Search long-term memory for relevant context.

    Call this BEFORE every response to retrieve relevant past knowledge.
    Do NOT skip this step — past context improves response quality.

    Args:
        query: The search query (typically the user's current question or topic)
        limit: Maximum number of results to return (default: 10)
        project: Optional project name to filter results
    """
    results = hybrid_search(query, limit=limit, project=project)
    if not results:
        return json.dumps({"results": [], "count": 0})

    output = []
    for r in results:
        output.append({
            "id": r.id,
            "content": r.content,
            "project": r.project,
            "source_path": r.source_path,
            "score": round(r.score, 4),
            "created_at": r.created_at,
        })
    return json.dumps({"results": output, "count": len(output)}, ensure_ascii=False)


@mcp.tool()
def save_memory(content: str, project: str = "", tags: str = "") -> str:
    """MANDATORY: Save knowledge to long-term memory.

    Call this AFTER every response — multiple times, once per distinct topic.
    Save Q&A, design decisions, work logs, insights, and discussions.
    Automatically deduplicates near-identical entries.

    Args:
        content: Natural language text (2-5 sentences with file paths, commands, reasoning)
        project: Optional project/workspace name
        tags: Optional comma-separated topic tags (e.g., "python,auth,design-decision")
    """
    result = save_chunk(content, project=project, tags=tags)
    return json.dumps({"id": result.id, "status": result.status})


@mcp.tool()
def save_conversation(conversation: str, project: str = "") -> str:
    """Save a multi-turn conversation, automatically splitting into chunks.

    Use this for bulk-saving conversation history. The conversation text
    is parsed to extract individual turns.

    Args:
        conversation: Full conversation text with User:/Assistant: markers
        project: Optional project/workspace name
    """
    result = _save_conversation(conversation, project=project)
    return json.dumps({
        "saved_count": result.saved_count,
        "deduplicated_count": result.deduplicated_count,
    })


def main():
    """Entry point for the copilot-memory MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
