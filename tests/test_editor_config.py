"""Tests for editor settings auto-configuration."""

import json

from copilot_memory.editor_config import deep_merge, strip_jsonc


def test_strip_jsonc_line_comments():
    text = '{\n  "key": "value" // comment\n}'
    result = json.loads(strip_jsonc(text))
    assert result == {"key": "value"}


def test_strip_jsonc_block_comments():
    text = '{\n  /* block comment */\n  "key": "value"\n}'
    result = json.loads(strip_jsonc(text))
    assert result == {"key": "value"}


def test_strip_jsonc_trailing_comma():
    text = '{\n  "a": 1,\n  "b": 2,\n}'
    result = json.loads(strip_jsonc(text))
    assert result == {"a": 1, "b": 2}


def test_strip_jsonc_url_in_string():
    """URLs with // inside strings should not be stripped."""
    text = '{"url": "https://example.com"}'
    result = json.loads(strip_jsonc(text))
    assert result["url"] == "https://example.com"


def test_strip_jsonc_complex():
    text = """{
  // Top comment
  "editor.fontSize": 14,
  "mcp": {
    "servers": {} /* inline */
  },
}"""
    result = json.loads(strip_jsonc(text))
    assert result["editor.fontSize"] == 14
    assert result["mcp"]["servers"] == {}


def test_deep_merge_simple():
    base = {"a": 1, "b": 2}
    overlay = {"b": 3, "c": 4}
    assert deep_merge(base, overlay) == {"a": 1, "b": 3, "c": 4}


def test_deep_merge_nested():
    base = {"mcp": {"servers": {"existing": {"cmd": "x"}}}}
    overlay = {"mcp": {"servers": {"new-server": {"cmd": "y"}}}}
    result = deep_merge(base, overlay)
    assert "existing" in result["mcp"]["servers"]
    assert "new-server" in result["mcp"]["servers"]


def test_deep_merge_no_overwrite_unrelated():
    base = {"editor.fontSize": 14, "mcp": {"servers": {}}}
    overlay = {"mcp": {"servers": {"copilot-memory": {"command": "python"}}}}
    result = deep_merge(base, overlay)
    assert result["editor.fontSize"] == 14
    assert "copilot-memory" in result["mcp"]["servers"]


def test_configure_vscode(tmp_path, monkeypatch):
    """configure_vscode creates/updates VS Code settings."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"editor.fontSize": 14}')

    monkeypatch.setattr(
        "copilot_memory.editor_config.get_vscode_settings_path",
        lambda: settings_path,
    )

    from copilot_memory.editor_config import configure_vscode
    result = configure_vscode()
    assert "[OK]" in result

    data = json.loads(settings_path.read_text())
    assert data["editor.fontSize"] == 14
    assert "copilot-memory" in data["mcp"]["servers"]


def test_configure_vscode_creates_new(tmp_path, monkeypatch):
    """configure_vscode creates settings.json if it doesn't exist."""
    settings_path = tmp_path / "Code" / "User" / "settings.json"

    monkeypatch.setattr(
        "copilot_memory.editor_config.get_vscode_settings_path",
        lambda: settings_path,
    )

    from copilot_memory.editor_config import configure_vscode
    configure_vscode()

    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert "copilot-memory" in data["mcp"]["servers"]


def test_configure_claude_code(tmp_path, monkeypatch):
    """configure_claude_code adds MCP server and Stop hook."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")

    monkeypatch.setattr(
        "copilot_memory.editor_config.get_claude_settings_path",
        lambda: settings_path,
    )

    from copilot_memory.editor_config import configure_claude_code
    result = configure_claude_code()
    assert "[OK]" in result

    data = json.loads(settings_path.read_text())
    assert "copilot-memory" in data["mcpServers"]
    assert "Stop" in data["hooks"]
    assert data["hooks"]["Stop"][0]["hooks"][0]["type"] == "command"


def test_configure_preserves_existing_servers(tmp_path, monkeypatch):
    """Existing MCP servers are not overwritten."""
    settings_path = tmp_path / "settings.json"
    existing = {
        "mcpServers": {
            "other-server": {"command": "other"}
        }
    }
    settings_path.write_text(json.dumps(existing))

    monkeypatch.setattr(
        "copilot_memory.editor_config.get_claude_settings_path",
        lambda: settings_path,
    )

    from copilot_memory.editor_config import configure_claude_code
    configure_claude_code()

    data = json.loads(settings_path.read_text())
    assert "other-server" in data["mcpServers"]
    assert "copilot-memory" in data["mcpServers"]


def test_backup_created(tmp_path, monkeypatch):
    """A backup file is created on first modification."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"existing": true}')

    monkeypatch.setattr(
        "copilot_memory.editor_config.get_vscode_settings_path",
        lambda: settings_path,
    )

    from copilot_memory.editor_config import configure_vscode
    result = configure_vscode()

    backup_path = tmp_path / "settings.json.copilot-memory-backup"
    assert backup_path.exists()
    assert "Backup" in result
