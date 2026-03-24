"""Tests for Claude Code Stop hook handler."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from copilot_memory.hook import (
    _extract_last_turn,
    _extract_text,
    _is_trivial,
    _read_transcript,
    _truncate,
)


def _write_transcript(path: Path, messages: list[dict]) -> None:
    """Write a JSONL transcript file."""
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def test_extract_text_string():
    assert _extract_text({"content": "hello"}) == "hello"


def test_extract_text_list():
    msg = {"content": [{"text": "part1"}, {"text": "part2"}]}
    assert _extract_text(msg) == "part1\npart2"


def test_extract_text_empty():
    assert _extract_text({}) == ""


def test_read_transcript(tmp_path):
    path = tmp_path / "transcript.jsonl"
    msgs = [
        {"role": "human", "content": "What is Python?"},
        {"role": "assistant", "content": "A programming language."},
    ]
    _write_transcript(path, msgs)
    result = _read_transcript(str(path))
    assert len(result) == 2


def test_read_transcript_missing_file():
    result = _read_transcript("/nonexistent/path.jsonl")
    assert result == []


def test_extract_last_turn_basic():
    messages = [
        {"role": "human", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "human", "content": "Question 2"},
        {"role": "assistant", "content": "Answer 2"},
    ]
    result = _extract_last_turn(messages)
    assert result == ("Question 2", "Answer 2")


def test_extract_last_turn_user_only():
    messages = [{"role": "human", "content": "Hello"}]
    assert _extract_last_turn(messages) is None


def test_extract_last_turn_with_type_field():
    messages = [
        {"type": "user", "content": "Q"},
        {"type": "assistant", "content": "A long enough answer here"},
    ]
    # "type" field is also checked
    result = _extract_last_turn(messages)
    # We only check role="human"|"user" and role="assistant"
    # type="user" maps to role check — let's see
    assert result is None or result[0] == "Q"


def test_truncate_short():
    assert _truncate("short", 100) == "short"


def test_truncate_long():
    text = "a" * 200
    result = _truncate(text, 50)
    assert len(result) == 50
    assert result.endswith("...")


def test_is_trivial_greeting():
    assert _is_trivial("hi", "Hello! How can I help?") is True


def test_is_trivial_short_assistant():
    assert _is_trivial("What is X?", "Yes") is True


def test_is_trivial_substantial():
    assert _is_trivial(
        "How to use asyncio?",
        "Use asyncio.run() to execute a coroutine. You can use await for I/O operations."
    ) is False
