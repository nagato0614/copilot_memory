"""Tests for Claude Code hook handlers (Stop + UserPromptSubmit)."""

import json
from pathlib import Path
from io import StringIO
from unittest.mock import patch

from copilot_memory.hook import (
    _extract_last_turn,
    _extract_text,
    _get_role,
    _is_trivial,
    _read_transcript,
    _truncate,
    handle_prompt_hook,
)


def _write_transcript(path: Path, messages: list[dict]) -> None:
    """Write a JSONL transcript file."""
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


# --- _extract_text ---

def test_extract_text_string():
    assert _extract_text({"content": "hello"}) == "hello"


def test_extract_text_list_with_type():
    msg = {"content": [{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}]}
    assert _extract_text(msg) == "part1\npart2"


def test_extract_text_skips_tool_use():
    msg = {
        "content": [
            {"type": "text", "text": "Here is the answer."},
            {"type": "tool_use", "id": "toolu_123", "name": "Bash", "input": {"command": "ls"}},
        ]
    }
    assert _extract_text(msg) == "Here is the answer."


def test_extract_text_tool_use_only():
    msg = {"content": [{"type": "tool_use", "id": "toolu_123", "name": "Bash", "input": {"command": "git push"}}]}
    assert _extract_text(msg) == ""


def test_extract_text_mixed_content():
    msg = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Let me push the changes."},
            {"type": "tool_use", "id": "toolu_01", "name": "Bash", "input": {"command": "git push"}},
            {"type": "text", "text": "Done! Changes pushed successfully."},
        ]
    }
    assert _extract_text(msg) == "Let me push the changes.\nDone! Changes pushed successfully."


def test_extract_text_empty():
    assert _extract_text({}) == ""


def test_extract_text_nested_message():
    msg = {"message": {"role": "assistant", "content": "nested text"}}
    assert _extract_text(msg) == "nested text"


# --- _get_role ---

def test_get_role_direct():
    assert _get_role({"role": "user"}) == "user"


def test_get_role_nested():
    assert _get_role({"message": {"role": "assistant"}}) == "assistant"


def test_get_role_missing():
    assert _get_role({}) == ""


# --- _read_transcript ---

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
    assert _read_transcript("/nonexistent/path.jsonl") == []


# --- _extract_last_turn ---

def test_extract_last_turn_basic():
    messages = [
        {"role": "human", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "human", "content": "Question 2"},
        {"role": "assistant", "content": "Answer 2"},
    ]
    result = _extract_last_turn(messages)
    assert result == ("Question 2", "Answer 2")


def test_extract_last_turn_pairing_correct():
    """Q&A pairing must match the same turn."""
    messages = [
        {"role": "human", "content": "VSCodeの認証問題について"},
        {"role": "assistant", "content": "OAuth トークンの競合が原因です。"},
        {"role": "human", "content": "hook.pyを修正して"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Edit", "input": {}}]},
        {"role": "assistant", "content": [{"type": "text", "text": "hook.pyのペアリングを修正しました。"}]},
    ]
    result = _extract_last_turn(messages)
    assert result is not None
    assert result[0] == "hook.pyを修正して"
    assert "ペアリング" in result[1]


def test_extract_last_turn_skips_tool_only_messages():
    messages = [
        {"role": "human", "content": "Push the code"},
        {"role": "assistant", "content": [{"type": "text", "text": "I'll push now."}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_01", "name": "Bash", "input": {"command": "git push"}}]},
    ]
    result = _extract_last_turn(messages)
    assert result is not None
    assert result[0] == "Push the code"
    assert result[1] == "I'll push now."


def test_extract_last_turn_many_turns():
    messages = [
        {"role": "human", "content": "Turn 1 question"},
        {"role": "assistant", "content": "Turn 1 answer is here with enough text."},
        {"role": "human", "content": "Turn 2 question"},
        {"role": "assistant", "content": "Turn 2 answer is here with enough text."},
        {"role": "human", "content": "Turn 3 question"},
        {"role": "assistant", "content": "Turn 3 answer is here with enough text."},
    ]
    result = _extract_last_turn(messages)
    assert result == ("Turn 3 question", "Turn 3 answer is here with enough text.")


def test_extract_last_turn_user_only():
    assert _extract_last_turn([{"role": "human", "content": "Hello"}]) is None


def test_extract_last_turn_assistant_before_user():
    messages = [
        {"role": "assistant", "content": "Welcome!"},
        {"role": "human", "content": "Hi there"},
        {"role": "assistant", "content": "How can I help?"},
    ]
    result = _extract_last_turn(messages)
    assert result == ("Hi there", "How can I help?")


# --- _truncate ---

def test_truncate_short():
    assert _truncate("short", 100) == "short"


def test_truncate_long():
    text = "a" * 200
    result = _truncate(text, 50)
    assert len(result) == 50
    assert result.endswith("...")


# --- _is_trivial ---

def test_is_trivial_greeting():
    assert _is_trivial("hi", "Hello! How can I help?") is True


def test_is_trivial_short_assistant():
    assert _is_trivial("What is X?", "Yes") is True


def test_is_trivial_substantial():
    assert _is_trivial(
        "How to use asyncio?",
        "Use asyncio.run() to execute a coroutine. You can use await for I/O operations."
    ) is False


# --- handle_prompt_hook ---

def test_handle_prompt_hook_outputs_results(tmp_memory_dir, capsys):
    """Prompt hook outputs search results to stdout."""
    from copilot_memory.storage import save_chunk
    save_chunk("Pythonでデコレータを使うには@decoratorを関数定義の前に記述する。functools.wrapsを使うとメタデータが保持される。", project="test")

    stdin_data = json.dumps({"user_prompt": "Pythonのデコレータについて教えて"})
    with patch("sys.stdin", StringIO(stdin_data)):
        handle_prompt_hook()

    captured = capsys.readouterr()
    assert "[copilot-memory]" in captured.out
    assert "デコレータ" in captured.out


def test_handle_prompt_hook_short_query(capsys):
    stdin_data = json.dumps({"user_prompt": "hi"})
    with patch("sys.stdin", StringIO(stdin_data)):
        handle_prompt_hook()
    assert capsys.readouterr().out == ""


def test_handle_prompt_hook_no_results(tmp_memory_dir, capsys):
    stdin_data = json.dumps({"user_prompt": "completely unrelated topic xyz123"})
    with patch("sys.stdin", StringIO(stdin_data)):
        handle_prompt_hook()
    assert capsys.readouterr().out == ""


def test_handle_prompt_hook_empty_stdin(capsys):
    with patch("sys.stdin", StringIO("")):
        handle_prompt_hook()
    assert capsys.readouterr().out == ""
