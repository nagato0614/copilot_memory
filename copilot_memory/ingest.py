"""File ingestion: split files into chunks and store in memory."""

import re
from pathlib import Path

from .storage import save_chunk, delete_by_source_path

# Extensions that are split as whole files (diagram/config with holistic meaning)
WHOLE_FILE_EXTENSIONS = {".puml", ".plantuml"}
WHOLE_FILE_NAMES = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}

SUPPORTED_EXTENSIONS = {
    # Documents
    ".md", ".adoc",
    # Diagrams
    ".puml", ".plantuml",
    # Source code
    ".c", ".cpp", ".h", ".hpp",
    ".java",
    ".py",
    ".rs",
    ".dart",
    # Config/data
    ".yml", ".yaml", ".toml", ".json", ".xml",
    ".txt", ".rst", ".sql", ".sh",
    ".dockerfile",
}

MIN_CHUNK_LEN = 30


def _filter_chunks(chunks: list[str]) -> list[str]:
    """Filter out empty/trivial chunks, merging tiny ones into previous."""
    result = []
    for chunk in chunks:
        stripped = chunk.strip()
        if len(stripped) >= MIN_CHUNK_LEN:
            result.append(stripped)
        elif stripped and result:
            result[-1] += "\n" + stripped
    if not result and chunks:
        text = chunks[0].strip()
        if text:
            return [text]
    return result


# --- Splitters ---

def split_markdown(text: str) -> list[str]:
    """Split Markdown by headings (# / ## / ###)."""
    sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
    return _filter_chunks(sections)


def split_asciidoc(text: str) -> list[str]:
    """Split AsciiDoc by headings (= / == / ===)."""
    sections = re.split(r"(?=^={1,3}\s)", text, flags=re.MULTILINE)
    return _filter_chunks(sections)


def split_whole(text: str) -> list[str]:
    """Return entire text as a single chunk. Falls back to fixed-length if too large."""
    text = text.strip()
    if not text:
        return []
    if len(text) > 3000:
        return split_fixed_length(text)
    return [text]


def split_python(text: str) -> list[str]:
    """Split Python by top-level def/class/async def definitions."""
    sections = re.split(r"(?=^(?:def |class |async def ))", text, flags=re.MULTILINE)
    return _filter_chunks(sections)


def split_c_cpp(text: str) -> list[str]:
    """Split C/C++ by function boundaries (closing brace at column 0)."""
    lines = text.split("\n")
    chunks = []
    current: list[str] = []
    for line in lines:
        current.append(line)
        if line.strip() == "}" and not line.startswith(" ") and not line.startswith("\t"):
            chunks.append("\n".join(current))
            current = []
    if current:
        remaining = "\n".join(current).strip()
        if remaining:
            if chunks:
                chunks[-1] += "\n" + remaining
            else:
                chunks.append(remaining)
    return _filter_chunks(chunks)


def split_java(text: str) -> list[str]:
    """Split Java by class/method definitions (heuristic)."""
    sections = re.split(
        r"(?=^\s{0,4}(?:public|private|protected|static|@)\s)",
        text, flags=re.MULTILINE,
    )
    return _filter_chunks(sections)


def split_rust(text: str) -> list[str]:
    """Split Rust by fn/impl/struct/enum definitions."""
    sections = re.split(
        r"(?=^(?:pub\s+)?(?:fn |impl |struct |enum |mod |trait ))",
        text, flags=re.MULTILINE,
    )
    return _filter_chunks(sections)


def split_dart(text: str) -> list[str]:
    """Split Dart by class/function definitions."""
    sections = re.split(
        r"(?=^(?:class |abstract class |mixin |void |Future|String |int |double |bool |Widget ))",
        text, flags=re.MULTILINE,
    )
    return _filter_chunks(sections)


def split_fixed_length(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Split text into fixed-length chunks with overlap, respecting line boundaries."""
    lines = text.split("\n")
    chunks = []
    current_lines: list[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) + 1 > max_chars and current_lines:
            chunks.append("\n".join(current_lines))
            # Carry over overlap lines
            overlap_lines: list[str] = []
            overlap_len = 0
            for prev_line in reversed(current_lines):
                if overlap_len + len(prev_line) + 1 > overlap:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_len += len(prev_line) + 1
            current_lines = overlap_lines
            current_len = overlap_len
        current_lines.append(line)
        current_len += len(line) + 1

    if current_lines:
        chunks.append("\n".join(current_lines))

    return _filter_chunks(chunks)


def split_by_extension(text: str, ext: str, filename: str = "") -> list[str]:
    """Dispatch to appropriate splitter based on file extension."""
    if filename.lower() in WHOLE_FILE_NAMES:
        return split_whole(text)
    if ext in (".md",):
        return split_markdown(text)
    elif ext in (".adoc",):
        return split_asciidoc(text)
    elif ext in WHOLE_FILE_EXTENSIONS:
        return split_whole(text)
    elif ext in (".py",):
        return split_python(text)
    elif ext in (".c", ".cpp", ".h", ".hpp"):
        return split_c_cpp(text)
    elif ext in (".java",):
        return split_java(text)
    elif ext in (".rs",):
        return split_rust(text)
    elif ext in (".dart",):
        return split_dart(text)
    else:
        return split_fixed_length(text)


def ingest_file(path: str, project: str = "") -> dict:
    """Ingest a file: delete old chunks, split, and re-register.

    Returns: {"path": str, "chunks_saved": int, "chunks_deduped": int, "deleted_old": int}
    """
    abs_path = str(Path(path).resolve())
    filename = Path(abs_path).name
    ext = Path(abs_path).suffix.lower()

    # Re-register: delete existing chunks for this path
    deleted = delete_by_source_path(abs_path)

    # Read file
    text = Path(abs_path).read_text(encoding="utf-8")

    # Split by extension
    chunks = split_by_extension(text, ext, filename)

    # Auto-tag with file extension
    ext_tag = f"file:{ext.lstrip('.')}" if ext else "file:txt"

    saved = 0
    deduped = 0
    for chunk_text in chunks:
        content = f"[ファイル: {abs_path}]\n{chunk_text}"
        result = save_chunk(content, project=project, tags=ext_tag, source_path=abs_path)
        if result.status == "saved":
            saved += 1
        else:
            deduped += 1

    return {
        "path": abs_path,
        "chunks_saved": saved,
        "chunks_deduped": deduped,
        "deleted_old": deleted,
    }


def ingest_directory(
    path: str, project: str = "", extensions: set[str] | None = None
) -> list[dict]:
    """Ingest all supported files in a directory recursively."""
    p = Path(path)
    allowed = extensions or SUPPORTED_EXTENSIONS
    results = []
    for f in sorted(p.rglob("*")):
        if f.is_file() and (f.suffix.lower() in allowed or f.name.lower() in WHOLE_FILE_NAMES):
            results.append(ingest_file(str(f), project=project))
    return results


def list_ingested() -> list[dict]:
    """List all ingested files with their chunk counts."""
    from .db import get_connection
    conn = get_connection()
    rows = list(conn.execute(
        "SELECT source_path, COUNT(*) as chunk_count, MAX(created_at) as last_ingested "
        "FROM chunks WHERE source_path != '' GROUP BY source_path ORDER BY source_path"
    ))
    return [
        {"path": row[0], "chunks": row[1], "last_ingested": row[2]}
        for row in rows
    ]
