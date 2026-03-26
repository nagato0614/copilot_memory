"""Claude Code hook handlers.

- Stop hook: saves the latest Q&A pair to memory after each response
- UserPromptSubmit hook: searches memory and injects context before each response
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Log to ~/.copilot-memory/hook.log for debugging."""
    from .config import MEMORY_DIR

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    log_path = MEMORY_DIR / "hook.log"
    handler = logging.FileHandler(str(log_path), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _read_transcript(transcript_path: str) -> list[dict]:
    """Read a JSONL transcript file and return parsed messages."""
    messages = []
    path = Path(transcript_path)
    if not path.exists():
        return messages
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return messages


def _get_role(message: dict) -> str:
    """Extract the role from a transcript message, handling nested formats."""
    role = message.get("role", "")
    if not role and "message" in message and isinstance(message["message"], dict):
        role = message["message"].get("role", "")
    return role


def _extract_text(message: dict) -> str:
    """Extract human-readable text from a transcript message.

    Handles Claude API response format where content is a list of blocks:
    - {"type": "text", "text": "..."} → extract text
    - {"type": "tool_use", ...} → skip (not human-readable)
    - {"type": "tool_result", ...} → skip
    Also handles simple string content and nested message formats.
    """
    # Some transcript formats wrap the actual message
    if "message" in message and isinstance(message["message"], dict):
        return _extract_text(message["message"])

    content = message.get("content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                block_type = block.get("type", "")
                # Only extract actual text blocks
                if block_type == "text":
                    text = block.get("text", "")
                    if text:
                        parts.append(text)
                # Skip tool_use, tool_result, etc. — not human-readable
        return "\n".join(parts)

    return ""


def _extract_last_turn(messages: list[dict]) -> tuple[str, str] | None:
    """Extract the last meaningful user→assistant pair from transcript.

    Tracks pairs: when a user message arrives, record it; when the next
    assistant message with text arrives, form a pair. This ensures the
    question and answer always correspond to the same turn.
    """
    current_user = ""
    last_pair: tuple[str, str] | None = None

    for msg in messages:
        role = _get_role(msg)
        text = _extract_text(msg)
        if not text.strip():
            continue

        if role in ("human", "user"):
            current_user = text.strip()
        elif role == "assistant" and current_user:
            last_pair = (current_user, text.strip())

    return last_pair


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, adding ellipsis if needed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def _is_trivial(user_text: str, assistant_text: str) -> bool:
    """Check if the conversation is too trivial to save."""
    # Skip very short interactions
    if len(user_text) < 5 or len(assistant_text) < 20:
        return True
    # Skip greetings
    greetings = {"hi", "hello", "hey", "thanks", "thank you", "bye", "ok", "yes", "no"}
    if user_text.strip().lower().rstrip("!.") in greetings:
        return True
    return False


def handle_stop_hook() -> None:
    """Handler for Claude Code Stop hook.

    Reads JSON from stdin, extracts the latest Q&A from the transcript,
    and saves it to the memory database.
    Always exits 0 to avoid blocking the user.
    """
    try:
        _setup_logging()
        raw = sys.stdin.read()
        if not raw:
            logger.info("No input received")
            return

        event = json.loads(raw)
        logger.info("Received Stop event: session=%s", event.get("session_id", "?"))

        transcript_path = event.get("transcript_path", "")
        if not transcript_path:
            logger.info("No transcript_path in event")
            return

        messages = _read_transcript(transcript_path)
        if not messages:
            logger.info("Empty transcript")
            return

        turn = _extract_last_turn(messages)
        if turn is None:
            logger.info("Could not extract Q&A turn (no text content found)")
            return

        user_text, assistant_text = turn

        if _is_trivial(user_text, assistant_text):
            logger.info("Skipping trivial interaction")
            return

        # Derive project name from cwd
        cwd = event.get("cwd", "")
        project = Path(cwd).name if cwd else ""

        content = _truncate(user_text, 500) + "\n" + _truncate(assistant_text, 2000)

        logger.info("Saving: content=%s...", content[:120])

        from .storage import save_chunk

        result = save_chunk(content=content, project=project)
        logger.info("Saved memory: id=%s status=%s project=%s", result.id, result.status, project)

    except Exception as e:
        logger.exception("Hook error: %s", e)
    # Always exit 0 — never block the user


def handle_prompt_hook() -> None:
    """Handler for Claude Code UserPromptSubmit hook.

    Reads the user's prompt from stdin, searches memory for relevant context,
    and prints results to stdout. Claude Code injects stdout content into
    the conversation as additional context.
    Always exits 0 to avoid blocking the user.
    """
    try:
        _setup_logging()
        raw = sys.stdin.read()
        if not raw:
            return

        event = json.loads(raw)
        query = event.get("user_prompt", "")
        logger.info("Received UserPromptSubmit: query=%s...", query[:80] if query else "")

        # Skip very short or empty queries
        if len(query.strip()) < 5:
            logger.info("Query too short, skipping search")
            return

        from .search import hybrid_search

        results = hybrid_search(query, limit=5)
        if not results:
            logger.info("No memory results found")
            return

        logger.info("Found %d memory results", len(results))

        # Output to stdout — Claude Code injects this as context
        lines = ["[copilot-memory] 関連する過去の記憶:"]
        for r in results:
            lines.append(f"- [{r.project or 'general'}] {r.content}")
        print("\n".join(lines))

    except Exception as e:
        logger.exception("Prompt hook error: %s", e)
    # Always exit 0 — never block the user
