"""Claude Code Stop hook handler.

Reads the transcript from a Claude Code Stop event and saves the latest
Q&A pair to the memory database.
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
    """Extract the last meaningful user/assistant turn from transcript.

    Iterates through all messages and keeps the last user text and
    last assistant text that contain actual readable content.
    """
    last_user = ""
    last_assistant = ""

    for msg in messages:
        role = msg.get("role", "")
        # Also check nested message format
        if not role and "message" in msg and isinstance(msg["message"], dict):
            role = msg["message"].get("role", "")
        # Some formats use "type" instead of "role"
        if not role:
            role = msg.get("type", "")

        text = _extract_text(msg)
        if not text.strip():
            continue

        if role in ("human", "user"):
            last_user = text.strip()
        elif role == "assistant":
            last_assistant = text.strip()

    if not last_user or not last_assistant:
        return None

    return last_user, last_assistant


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
    """Main handler for Claude Code Stop hook.

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

        question = _truncate(user_text, 500)
        answer = _truncate(assistant_text, 1000)

        logger.info("Saving: question=%s answer=%s...", question[:80], answer[:80])

        from .storage import save_chunk

        result = save_chunk(question=question, answer=answer, project=project)
        logger.info("Saved memory: id=%s status=%s project=%s", result.id, result.status, project)

    except Exception as e:
        logger.exception("Hook error: %s", e)
    # Always exit 0 — never block the user
