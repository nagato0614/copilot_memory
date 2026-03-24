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
        "Use search_memory before answering to recall relevant context. "
        "Use save_memory after answering to store new Q&A pairs."
    ),
)


@mcp.tool()
def search_memory(query: str, limit: int = 10, project: str = "") -> str:
    """Search long-term memory for relevant past Q&A pairs.

    Call this BEFORE answering the user to retrieve relevant context
    from past conversations.

    Args:
        query: The search query (typically the user's current question)
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
            "question": r.question,
            "answer": r.answer,
            "project": r.project,
            "score": round(r.score, 4),
            "created_at": r.created_at,
        })
    return json.dumps({"results": output, "count": len(output)}, ensure_ascii=False)


@mcp.tool()
def save_memory(
    question: str, answer: str, project: str = "", tags: str = ""
) -> str:
    """Save a Q&A pair to long-term memory.

    Call this AFTER answering the user to store the interaction for
    future reference. Automatically deduplicates near-identical entries.

    Args:
        question: The user's question (condensed if very long)
        answer: A concise summary of the response (2-5 sentences)
        project: Optional project/workspace name
        tags: Optional comma-separated topic tags (e.g., "python,debugging")
    """
    result = save_chunk(question, answer, project=project, tags=tags)
    return json.dumps({"id": result.id, "status": result.status})


@mcp.tool()
def save_conversation(conversation: str, project: str = "") -> str:
    """Save a multi-turn conversation, automatically splitting into Q&A pairs.

    Use this for bulk-saving conversation history. The conversation text
    is parsed to extract individual Q&A pairs.

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
