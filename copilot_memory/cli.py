"""CLI dispatcher for copilot-memory: routes to MCP server or init subcommand."""

import argparse
import pathlib
import re
import shutil
import sys
from importlib import resources

MARKER_START = "<!-- copilot-memory:start -->"
MARKER_END = "<!-- copilot-memory:end -->"


def _load_template(name: str) -> str:
    """Load a prompt template from package data."""
    ref = resources.files("copilot_memory.templates").joinpath(name)
    return ref.read_text(encoding="utf-8")


def _wrap_with_markers(content: str) -> str:
    """Wrap template content with copilot-memory markers."""
    return f"{MARKER_START}\n{content.rstrip()}\n{MARKER_END}\n"


def _inject_into_file(filepath: pathlib.Path, block: str) -> str:
    """Inject or replace the marked block in a file. Returns status message."""
    if filepath.exists():
        existing = filepath.read_text(encoding="utf-8")
        pattern = re.compile(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
            re.DOTALL,
        )
        if pattern.search(existing):
            new_content = pattern.sub(block.rstrip(), existing)
            filepath.write_text(new_content, encoding="utf-8")
            return f"Updated existing memory block in {filepath}"
        else:
            separator = "\n\n" if existing and not existing.endswith("\n\n") else (
                "\n" if existing and not existing.endswith("\n") else ""
            )
            filepath.write_text(existing + separator + block, encoding="utf-8")
            return f"Appended memory instructions to {filepath}"
    else:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(block, encoding="utf-8")
        return f"Created {filepath} with memory instructions"


def cmd_init(args: argparse.Namespace) -> None:
    """Handle the 'init' subcommand."""
    project_dir = pathlib.Path.cwd()

    do_copilot = args.copilot or (not args.copilot and not args.claude)
    do_claude = args.claude or (not args.copilot and not args.claude)
    do_editor = not args.no_editor

    if do_copilot:
        template = _load_template("copilot-instructions.md")
        block = _wrap_with_markers(template)
        target = project_dir / ".github" / "copilot-instructions.md"
        print(_inject_into_file(target, block))

    if do_claude:
        template = _load_template("CLAUDE.md")
        block = _wrap_with_markers(template)
        target = project_dir / "CLAUDE.md"
        print(_inject_into_file(target, block))

    if do_editor:
        from .editor_config import configure_claude_code, configure_vscode

        print()
        if do_copilot:
            try:
                print(configure_vscode())
            except Exception as e:
                print(f"[WARN] Could not configure VS Code: {e}")
        if do_claude:
            try:
                print(configure_claude_code())
            except Exception as e:
                print(f"[WARN] Could not configure Claude Code: {e}")

    print()
    print("Done! Memory instructions have been added to your project.")


def cmd_uninstall(args: argparse.Namespace) -> None:
    """Handle the 'uninstall' subcommand. Removes ~/.copilot-memory/ entirely."""
    from .config import MEMORY_DIR

    install_dir = MEMORY_DIR

    if not install_dir.exists():
        print(f"{install_dir} does not exist. Nothing to uninstall.")
        return

    # Show what will be deleted
    print("The following directory will be deleted:")
    print(f"  {install_dir}")
    print()
    print("This includes:")
    print("  - Virtual environment (venv)")
    print("  - Embedding model cache")
    print("  - Memory database (memory.db)")
    print()

    if not args.yes:
        try:
            reply = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if reply != "y":
            print("Aborted.")
            return

    shutil.rmtree(install_dir)
    print(f"[OK] Removed {install_dir}")
    print()
    print("Don't forget to remove the MCP server entry from your editor settings:")
    print('  - VS Code: Remove "copilot-memory" from settings.json > mcp.servers')
    print('  - Claude Code: Remove "copilot-memory" from ~/.claude/settings.json > mcpServers')


def main() -> None:
    """Main entry point: dispatches to server or CLI subcommands."""
    if len(sys.argv) <= 1:
        from .server import main as server_main
        server_main()
        return

    parser = argparse.ArgumentParser(
        prog="copilot-memory",
        description="Local long-term memory for AI coding assistants",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("serve", help="Start the MCP server (default if no command given)")

    init_parser = subparsers.add_parser("init", help="Initialize memory prompts in current project")
    init_parser.add_argument("--copilot", action="store_true", help="Only set up GitHub Copilot instructions")
    init_parser.add_argument("--claude", action="store_true", help="Only set up Claude Code instructions")
    init_parser.add_argument("--no-editor", action="store_true", help="Skip editor settings configuration")

    subparsers.add_parser("hook-save", help="Save memory from Claude Code Stop hook (reads stdin)")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove copilot-memory installation (~/.copilot-memory/)")
    uninstall_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "hook-save":
        from .hook import handle_stop_hook
        handle_stop_hook()
    elif args.command == "uninstall":
        cmd_uninstall(args)
    elif args.command == "serve":
        from .server import main as server_main
        server_main()
    else:
        parser.print_help()
