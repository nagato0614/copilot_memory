"""Tests for the CLI init and uninstall subcommands."""

import argparse

from copilot_memory.cli import _inject_into_file, _wrap_with_markers, cmd_uninstall, MARKER_START, MARKER_END


def test_inject_creates_new_file(tmp_path):
    """Creates file if it doesn't exist."""
    target = tmp_path / "CLAUDE.md"
    block = _wrap_with_markers("test content")
    _inject_into_file(target, block)
    assert target.exists()
    content = target.read_text()
    assert MARKER_START in content
    assert "test content" in content
    assert MARKER_END in content


def test_inject_appends_to_existing(tmp_path):
    """Appends to existing file without markers."""
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My Project\n\nExisting content.\n")
    block = _wrap_with_markers("memory instructions")
    _inject_into_file(target, block)
    content = target.read_text()
    assert content.startswith("# My Project")
    assert "Existing content." in content
    assert MARKER_START in content
    assert "memory instructions" in content


def test_inject_replaces_existing_block(tmp_path):
    """Replaces existing marked block (idempotent)."""
    target = tmp_path / "CLAUDE.md"
    old_block = _wrap_with_markers("old instructions")
    target.write_text(f"# My Project\n\n{old_block}")
    new_block = _wrap_with_markers("new instructions")
    _inject_into_file(target, new_block)
    content = target.read_text()
    assert "old instructions" not in content
    assert "new instructions" in content
    assert content.count(MARKER_START) == 1


def test_inject_creates_parent_dirs(tmp_path):
    """Creates .github/ directory if needed."""
    target = tmp_path / ".github" / "copilot-instructions.md"
    block = _wrap_with_markers("test")
    _inject_into_file(target, block)
    assert target.exists()
    assert MARKER_START in target.read_text()


def test_inject_preserves_content_outside_markers(tmp_path):
    """Content before and after markers is preserved."""
    target = tmp_path / "CLAUDE.md"
    old_block = _wrap_with_markers("old")
    target.write_text(f"BEFORE\n\n{old_block}\nAFTER\n")
    new_block = _wrap_with_markers("new")
    _inject_into_file(target, new_block)
    content = target.read_text()
    assert "BEFORE" in content
    assert "AFTER" in content
    assert "new" in content
    assert "old" not in content


def test_wrap_with_markers():
    """Markers wrap content correctly."""
    result = _wrap_with_markers("hello")
    assert result == f"{MARKER_START}\nhello\n{MARKER_END}\n"


def test_wrap_strips_trailing_whitespace():
    """Trailing whitespace in content is stripped before wrapping."""
    result = _wrap_with_markers("hello\n\n\n")
    assert result == f"{MARKER_START}\nhello\n{MARKER_END}\n"


def test_uninstall_removes_directory(tmp_path, monkeypatch):
    """Uninstall removes the install directory."""
    install_dir = tmp_path / ".copilot-memory"
    install_dir.mkdir()
    (install_dir / "memory.db").write_text("fake")
    (install_dir / "venv").mkdir()

    import copilot_memory.config as config_mod
    monkeypatch.setattr(config_mod, "MEMORY_DIR", install_dir)

    args = argparse.Namespace(yes=True)
    cmd_uninstall(args)
    assert not install_dir.exists()


def test_uninstall_nonexistent_directory(tmp_path, monkeypatch, capsys):
    """Uninstall with no install directory prints message and exits cleanly."""
    install_dir = tmp_path / ".copilot-memory"

    import copilot_memory.config as config_mod
    monkeypatch.setattr(config_mod, "MEMORY_DIR", install_dir)

    args = argparse.Namespace(yes=True)
    cmd_uninstall(args)
    output = capsys.readouterr().out
    assert "Nothing to uninstall" in output
