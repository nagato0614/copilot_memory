"""Tests for MCP server startup and JSON-RPC communication."""

import json
import subprocess
import sys
import os


def _start_server(tmp_dir: str):
    """Start the MCP server subprocess."""
    env = os.environ.copy()
    env["COPILOT_MEMORY_DIR"] = tmp_dir
    return subprocess.Popen(
        [sys.executable, "-m", "copilot_memory.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def _send_recv(proc, request: dict) -> dict | None:
    """Send a JSON-RPC request and read the response."""
    msg = json.dumps(request) + "\n"
    proc.stdin.write(msg.encode())
    proc.stdin.flush()
    line = proc.stdout.readline().decode()
    return json.loads(line) if line else None


def test_server_initialize(tmp_memory_dir):
    """Server responds to initialize request."""
    proc = _start_server(str(tmp_memory_dir))
    try:
        resp = _send_recv(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        })
        assert resp is not None
        assert "result" in resp
        assert resp["result"]["serverInfo"]["name"] == "copilot-memory"
    finally:
        proc.terminate()
        proc.wait()


def test_server_lists_tools(tmp_memory_dir):
    """Server lists all three tools."""
    proc = _start_server(str(tmp_memory_dir))
    try:
        _send_recv(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        })
        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode())
        proc.stdin.flush()

        resp = _send_recv(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
        })
        assert resp is not None
        tools = resp["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        assert tool_names == {"search_memory", "save_memory", "save_conversation"}
    finally:
        proc.terminate()
        proc.wait()


def test_server_save_and_search(tmp_memory_dir):
    """Server can save a memory and search for it."""
    proc = _start_server(str(tmp_memory_dir))
    try:
        _send_recv(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        })
        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode())
        proc.stdin.flush()

        # Save
        resp = _send_recv(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "save_memory",
                "arguments": {
                    "content": "Pythonでデコレータを使うには@decorator構文を関数定義の前に記述する。functools.wrapsを使うとメタデータが保持される。",
                    "project": "test",
                    "tags": "python,decorator"
                }
            }
        })
        assert resp is not None
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["status"] == "saved"

        # Search
        resp = _send_recv(proc, {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": {"query": "Python decorator", "limit": 5}
            }
        })
        assert resp is not None
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["count"] >= 1
        assert "デコレータ" in content["results"][0]["content"]
    finally:
        proc.terminate()
        proc.wait()
