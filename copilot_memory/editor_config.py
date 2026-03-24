"""Auto-configure editor settings for copilot-memory MCP server."""

import json
import re
import shutil
import sys
from pathlib import Path


def get_vscode_settings_path() -> Path:
    """Get the VS Code user settings.json path (platform-dependent)."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json"
    else:
        return Path.home() / ".config" / "Code" / "User" / "settings.json"


def get_claude_settings_path() -> Path:
    """Get the Claude Code settings.json path."""
    return Path.home() / ".claude" / "settings.json"


def get_venv_python() -> str:
    """Get the absolute path to the copilot-memory venv Python."""
    from .config import MEMORY_DIR

    return str(MEMORY_DIR / "venv" / "bin" / "python")


def get_copilot_memory_command() -> str:
    """Get the absolute path to the copilot-memory CLI."""
    from .config import MEMORY_DIR

    return str(MEMORY_DIR / "venv" / "bin" / "copilot-memory")


def strip_jsonc(text: str) -> str:
    """Strip JSONC comments and trailing commas to produce valid JSON.

    Handles:
    - // line comments (not inside strings)
    - /* block comments */
    - Trailing commas before } or ]
    """
    # Remove block comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # Remove line comments (not inside strings)
    lines = []
    for line in text.split("\n"):
        in_string = False
        escape = False
        result = []
        for i, ch in enumerate(line):
            if escape:
                result.append(ch)
                escape = False
                continue
            if ch == "\\":
                result.append(ch)
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if not in_string and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            result.append(ch)
        lines.append("".join(result))
    text = "\n".join(lines)

    # Remove trailing commas before } or ]
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    return text


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base, returning a new dict."""
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def backup_file(path: Path) -> Path | None:
    """Create a backup of a file before modifying it. Returns backup path or None."""
    if not path.exists():
        return None
    backup_path = path.with_suffix(path.suffix + ".copilot-memory-backup")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)
        return backup_path
    return None


def _read_json_settings(path: Path) -> dict:
    """Read a JSON/JSONC settings file, returning {} if not found."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        return json.loads(strip_jsonc(text))
    except json.JSONDecodeError:
        return {}


def _write_json_settings(path: Path, data: dict) -> None:
    """Write settings as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def configure_vscode() -> str:
    """Add copilot-memory MCP server to VS Code settings.json.

    Returns a status message.
    """
    path = get_vscode_settings_path()
    python_path = get_venv_python()

    overlay = {
        "mcp": {
            "servers": {
                "copilot-memory": {
                    "command": python_path,
                    "args": ["-m", "copilot_memory.server"],
                }
            }
        }
    }

    existing = _read_json_settings(path)
    backup = backup_file(path)
    merged = deep_merge(existing, overlay)
    _write_json_settings(path, merged)

    msg = f"[OK] VS Code settings updated: {path}"
    if backup:
        msg += f"\n     Backup: {backup}"
    return msg


def configure_claude_code() -> str:
    """Add copilot-memory MCP server + Stop hook to Claude Code settings.json.

    Returns a status message.
    """
    path = get_claude_settings_path()
    python_path = get_venv_python()
    hook_command = get_copilot_memory_command()

    overlay = {
        "mcpServers": {
            "copilot-memory": {
                "command": python_path,
                "args": ["-m", "copilot_memory.server"],
            }
        },
        "hooks": {
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{hook_command} hook-save",
                            "timeout": 60,
                        }
                    ],
                }
            ],
        },
    }

    existing = _read_json_settings(path)
    backup = backup_file(path)
    merged = deep_merge(existing, overlay)
    _write_json_settings(path, merged)

    msg = f"[OK] Claude Code settings updated: {path}"
    if backup:
        msg += f"\n     Backup: {backup}"
    return msg
