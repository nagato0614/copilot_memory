#!/usr/bin/env bash
set -euo pipefail

# Copilot Memory - Installation Script
# Supports macOS and Ubuntu
# Usage:
#   From cloned repo:  ./install.sh
#   Via curl:           curl -fsSL https://raw.githubusercontent.com/nagato0614/copilot_memory/main/install.sh | bash

INSTALL_DIR="$HOME/.copilot-memory"
VENV_DIR="$INSTALL_DIR/venv"
REPO_URL="https://github.com/nagato0614/copilot_memory.git"

# Detect whether we're running from a cloned repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
LOCAL_MODE=false
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    LOCAL_MODE=true
fi

echo "=== Copilot Memory Installer ==="
echo ""

# 1. Check Python version
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$cmd" -c "import sys; print(sys.version_info.major)")
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            echo "[OK] Python $version found: $(command -v "$cmd")"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python >= 3.10 is required but not found."
    echo "Install Python 3.10+ and try again."
    exit 1
fi

# 2. Check SQLite version (need >= 3.34.0 for FTS5 trigram)
SQLITE_VERSION=$("$PYTHON" -c "import sqlite3; print(sqlite3.sqlite_version)")
echo "[OK] SQLite version: $SQLITE_VERSION"

# 3. Create install directory
mkdir -p "$INSTALL_DIR"
echo "[OK] Install directory: $INSTALL_DIR"

# 4. Create virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "[OK] Virtual environment already exists at $VENV_DIR"
else
    if command -v uv &>/dev/null; then
        echo "[..] Creating virtual environment with uv..."
        uv venv "$VENV_DIR" --python "$PYTHON"
    else
        echo "[..] Creating virtual environment with venv..."
        "$PYTHON" -m venv "$VENV_DIR"
    fi
    echo "[OK] Virtual environment created at $VENV_DIR"
fi

# 5. Install the package
if [ "$LOCAL_MODE" = true ]; then
    echo "[..] Installing copilot-memory from local source..."
    if command -v uv &>/dev/null; then
        uv pip install --python "$VENV_DIR/bin/python" -e "$SCRIPT_DIR"
    else
        "$VENV_DIR/bin/pip" install --upgrade pip
        "$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR"
    fi
else
    echo "[..] Installing copilot-memory from git..."
    if command -v uv &>/dev/null; then
        uv pip install --python "$VENV_DIR/bin/python" "git+$REPO_URL"
    else
        "$VENV_DIR/bin/pip" install --upgrade pip
        "$VENV_DIR/bin/pip" install "git+$REPO_URL"
    fi
fi
echo "[OK] copilot-memory installed"

# 6. Pre-download embedding model
echo "[..] Downloading embedding model (this may take a few minutes on first run)..."
"$VENV_DIR/bin/python" -c "
from copilot_memory.config import EMBEDDING_MODEL, MODEL_CACHE_DIR
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=str(MODEL_CACHE_DIR))
print('[OK] Model downloaded:', EMBEDDING_MODEL)
"

# 7. Initialize database
echo "[..] Initializing database..."
"$VENV_DIR/bin/python" -c "
from copilot_memory.db import get_connection, close_connection
conn = get_connection()
close_connection()
print('[OK] Database initialized')
"

COPILOT_MEMORY_BIN="$VENV_DIR/bin/copilot-memory"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Add the following to your editor settings:"
echo ""
echo "--- GitHub Copilot (VS Code settings.json) ---"
cat <<EOF
{
  "mcp": {
    "servers": {
      "copilot-memory": {
        "command": "$VENV_DIR/bin/python",
        "args": ["-m", "copilot_memory.server"]
      }
    }
  }
}
EOF

echo ""
echo "--- Claude Code (~/.claude/settings.json) ---"
cat <<EOF
{
  "mcpServers": {
    "copilot-memory": {
      "command": "$VENV_DIR/bin/python",
      "args": ["-m", "copilot_memory.server"]
    }
  }
}
EOF

echo ""
echo "=== Per-Project Setup ==="
echo ""
echo "To add memory instructions to your project, run inside the project directory:"
echo "  $COPILOT_MEMORY_BIN init"
echo ""
echo "Options:"
echo "  $COPILOT_MEMORY_BIN init              # Both Copilot & Claude"
echo "  $COPILOT_MEMORY_BIN init --copilot    # GitHub Copilot only"
echo "  $COPILOT_MEMORY_BIN init --claude     # Claude Code only"
echo ""

# Offer to run init in the current directory (only if interactive terminal)
if [ -t 0 ]; then
    read -p "Run 'copilot-memory init' in the current directory? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        "$COPILOT_MEMORY_BIN" init
    fi
else
    echo "Run '$COPILOT_MEMORY_BIN init' inside your project to set up memory prompts."
fi
