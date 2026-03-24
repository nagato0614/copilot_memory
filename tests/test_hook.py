"""Tests for Claude Code Stop hook handler."""

import json
from pathlib import Path

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


def test_extract_text_list_with_type():
    """Text blocks with type='text' are extracted."""
    msg = {"content": [{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}]}
    assert _extract_text(msg) == "part1\npart2"


def test_extract_text_skips_tool_use():
    """tool_use blocks are not included in extracted text."""
    msg = {
        "content": [
            {"type": "text", "text": "Here is the answer."},
            {"type": "tool_use", "id": "toolu_123", "name": "Bash", "input": {"command": "ls"}},
        ]
    }
    assert _extract_text(msg) == "Here is the answer."


def test_extract_text_tool_use_only():
    """Messages with only tool_use blocks return empty string."""
    msg = {
        "content": [
            {"type": "tool_use", "id": "toolu_123", "name": "Bash", "input": {"command": "git push"}},
        ]
    }
    assert _extract_text(msg) == ""


def test_extract_text_claude_api_format():
    """Real Claude API response format is handled correctly."""
    msg = {
        "model": "claude-opus-4-6",
        "id": "msg_01BYH",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "toolu_01Aq", "name": "Bash",
             "input": {"command": "git push origin main"}},
        ],
        "stop_reason": "tool_use",
    }
    # Should return empty — no text content, only tool_use
    assert _extract_text(msg) == ""


def test_extract_text_mixed_content():
    """Mixed text + tool_use extracts only text."""
    msg = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Let me push the changes."},
            {"type": "tool_use", "id": "toolu_01", "name": "Bash",
             "input": {"command": "git push"}},
            {"type": "text", "text": "Done! Changes pushed successfully."},
        ]
    }
    assert _extract_text(msg) == "Let me push the changes.\nDone! Changes pushed successfully."


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


def test_extract_last_turn_skips_tool_only_messages():
    """Assistant messages with only tool_use are skipped."""
    messages = [
        {"role": "human", "content": "Push the code"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "I'll push now."},
        ]},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_01", "name": "Bash",
             "input": {"command": "git push"}},
        ]},
    ]
    result = _extract_last_turn(messages)
    assert result is not None
    assert result[0] == "Push the code"
    assert result[1] == "I'll push now."


def test_extract_last_turn_user_only():
    messages = [{"role": "human", "content": "Hello"}]
    assert _extract_last_turn(messages) is None


def test_extract_last_turn_real_api_format():
    """Handles real Claude API response objects in transcript."""
    messages = [
        {"role": "user", "content": "このプロジェクトの概要を教えて"},
        {
            "model": "claude-opus-4-6",
            "id": "msg_01BYH",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "このプロジェクトはMCPサーバーとして動作する長期記憶システムです。"},
            ],
            "stop_reason": "end_turn",
        },
    ]
    result = _extract_last_turn(messages)
    assert result is not None
    assert result[0] == "このプロジェクトの概要を教えて"
    assert "MCPサーバー" in result[1]


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
