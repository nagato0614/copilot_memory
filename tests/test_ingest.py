"""Tests for file ingestion functionality."""

from pathlib import Path

from copilot_memory.ingest import (
    _filter_chunks,
    ingest_file,
    ingest_directory,
    list_ingested,
    split_markdown,
    split_asciidoc,
    split_python,
    split_c_cpp,
    split_rust,
    split_whole,
    split_fixed_length,
    split_by_extension,
)
from copilot_memory.storage import delete_by_source_path


# --- Splitter tests ---

def test_split_markdown_headings():
    text = "# Intro\nThis is the introduction section with enough content to pass the minimum length filter.\n## Section A\nContent A has details about the first topic and more explanation here.\n## Section B\nContent B describes the second topic with additional context and details."
    chunks = split_markdown(text)
    assert len(chunks) >= 2


def test_split_markdown_single_section():
    text = "# Only One\nThis is the only section with enough content to be kept as a single chunk."
    chunks = split_markdown(text)
    assert len(chunks) == 1


def test_split_asciidoc():
    text = "= Title\nIntro text here.\n== Section 1\nContent 1 is here.\n== Section 2\nContent 2 is here."
    chunks = split_asciidoc(text)
    assert len(chunks) >= 2


def test_split_python_functions():
    text = '''import os

def hello():
    print("hello")

def world():
    print("world")

class MyClass:
    def method(self):
        pass
'''
    chunks = split_python(text)
    assert len(chunks) >= 2


def test_split_c_cpp():
    text = '''#include <stdio.h>

void hello() {
    printf("hello");
}

int main() {
    hello();
    return 0;
}
'''
    chunks = split_c_cpp(text)
    assert len(chunks) >= 1


def test_split_rust():
    text = '''use std::io;

fn hello() {
    println!("hello");
}

impl MyStruct {
    fn new() -> Self {
        MyStruct {}
    }
}
'''
    chunks = split_rust(text)
    assert len(chunks) >= 2


def test_split_whole_small():
    text = "Small file content here."
    chunks = split_whole(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_whole_large():
    text = "\n".join([f"Line {i}: some content here" for i in range(200)])
    chunks = split_whole(text)
    assert len(chunks) > 1  # Falls back to fixed-length


def test_split_fixed_length():
    text = "\n".join([f"Line {i}: some content here" for i in range(100)])
    chunks = split_fixed_length(text, max_chars=500, overlap=100)
    assert len(chunks) > 1
    # All chunks should have content
    for c in chunks:
        assert len(c) > 0


def test_split_fixed_length_overlap():
    text = "\n".join([f"Line {i}" for i in range(50)])
    chunks = split_fixed_length(text, max_chars=100, overlap=30)
    if len(chunks) >= 2:
        # Overlap means some content should appear in consecutive chunks
        last_lines_of_first = set(chunks[0].split("\n")[-3:])
        first_lines_of_second = set(chunks[1].split("\n")[:3])
        assert last_lines_of_first & first_lines_of_second


def test_split_by_extension_dispatch():
    assert len(split_by_extension("# Head\nThis is enough text content for markdown section splitting to work properly.", ".md")) >= 1
    assert len(split_by_extension("@startuml\nAlice -> Bob: Hello\nBob -> Alice: Hi\n@enduml", ".puml")) == 1
    assert len(split_by_extension("def foo():\n    \"\"\"A function.\"\"\"\n    return 'hello world'\n\ndef bar():\n    \"\"\"Another function.\"\"\"\n    return 42", ".py")) >= 1


def test_filter_chunks_removes_empty():
    chunks = _filter_chunks(["", "   ", "valid content that is long enough"])
    assert len(chunks) == 1
    assert "valid" in chunks[0]


def test_filter_chunks_merges_small():
    chunks = _filter_chunks(["long enough content for a chunk here", "tiny"])
    assert len(chunks) == 1
    assert "tiny" in chunks[0]


# --- Integration tests ---

def test_ingest_file_markdown(tmp_memory_dir, tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Section 1\nContent for section one.\n## Section 2\nContent for section two.\n")
    result = ingest_file(str(md_file), project="test")
    assert result["chunks_saved"] >= 1
    assert result["deleted_old"] == 0


def test_ingest_file_python(tmp_memory_dir, tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text('def hello():\n    """Say hello."""\n    print("hello")\n\ndef world():\n    """Say world."""\n    print("world")\n')
    result = ingest_file(str(py_file), project="test")
    assert result["chunks_saved"] >= 1


def test_ingest_file_puml(tmp_memory_dir, tmp_path):
    puml_file = tmp_path / "test.puml"
    puml_file.write_text("@startuml\nAlice -> Bob: Hello\nBob -> Alice: Hi\n@enduml\n")
    result = ingest_file(str(puml_file), project="test")
    assert result["chunks_saved"] == 1  # Whole file


def test_ingest_file_reregister(tmp_memory_dir, tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text('def hello():\n    print("hello")\n\ndef world():\n    print("world")\n')

    r1 = ingest_file(str(py_file), project="test")
    assert r1["deleted_old"] == 0

    # Re-ingest same file
    r2 = ingest_file(str(py_file), project="test")
    assert r2["deleted_old"] == r1["chunks_saved"]


def test_ingest_file_source_path(tmp_memory_dir, tmp_path):
    """Ingested file chunks have source_path set."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Some content that is long enough to be a valid chunk.\n")
    result = ingest_file(str(txt_file), project="test")
    assert result["chunks_saved"] >= 1

    # Verify source_path via search
    from copilot_memory.search import hybrid_search
    results = hybrid_search("content long enough", limit=3)
    found = [r for r in results if r.source_path == str(txt_file.resolve())]
    assert len(found) > 0


def test_ingest_file_has_prefix(tmp_memory_dir, tmp_path):
    """Ingested chunks have [ファイル: ...] prefix."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Important documentation content here for testing.\n")
    ingest_file(str(txt_file), project="test")

    from copilot_memory.search import hybrid_search
    results = hybrid_search("documentation content", limit=3)
    assert len(results) > 0
    assert "[ファイル:" in results[0].content


def test_ingest_directory(tmp_memory_dir, tmp_path):
    (tmp_path / "a.md").write_text("# Doc A\nContent for document A.\n")
    (tmp_path / "b.py").write_text('def func():\n    """A function."""\n    return 1\n')
    (tmp_path / "c.jpg").write_bytes(b"\xff\xd8")  # Not supported

    results = ingest_directory(str(tmp_path), project="test")
    paths = {r["path"] for r in results}
    assert any("a.md" in p for p in paths)
    assert any("b.py" in p for p in paths)
    assert not any("c.jpg" in p for p in paths)


def test_ingest_directory_skips_build_dir_by_sentinel(tmp_memory_dir, tmp_path):
    """Directories with build sentinel files are skipped."""
    # Source file
    (tmp_path / "main.cpp").write_text('int main() { return 0; }\n')

    # Build directory with CMakeCache.txt sentinel
    build = tmp_path / "build"
    build.mkdir()
    (build / "CMakeCache.txt").write_text("# CMake cache")
    (build / "main.cpp.o").write_bytes(b"\x00" * 100)
    (build / "output.cpp").write_text("// generated\nint x = 1;\n")

    results = ingest_directory(str(tmp_path), project="test")
    paths = {r["path"] for r in results}
    assert any("main.cpp" in p for p in paths)
    assert not any("build" in p for p in paths)


def test_ingest_directory_skips_build_dir_by_artifacts(tmp_memory_dir, tmp_path):
    """Directories with high ratio of compiled artifacts are skipped."""
    (tmp_path / "src.rs").write_text('fn main() { println!("hello"); }\n')

    # Directory full of .o files (artifact ratio > 50%)
    out = tmp_path / "out"
    out.mkdir()
    for i in range(5):
        (out / f"file{i}.o").write_bytes(b"\x00" * 50)
    (out / "helper.c").write_text("void helper() {}\n")

    results = ingest_directory(str(tmp_path), project="test")
    paths = {r["path"] for r in results}
    assert any("src.rs" in p for p in paths)
    assert not any("out" in p for p in paths)


def test_ingest_directory_skips_pycache(tmp_memory_dir, tmp_path):
    """__pycache__ directories are skipped."""
    (tmp_path / "app.py").write_text('def run():\n    """Run the app."""\n    pass\n')
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "app.cpython-312.pyc").write_bytes(b"\x00" * 50)

    results = ingest_directory(str(tmp_path), project="test")
    paths = {r["path"] for r in results}
    assert any("app.py" in p for p in paths)
    assert not any("__pycache__" in p for p in paths)


def test_ingest_directory_skips_hidden(tmp_memory_dir, tmp_path):
    """Hidden directories are skipped."""
    (tmp_path / "visible.py").write_text('def visible():\n    """Visible."""\n    pass\n')
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text('def secret(): pass\n')

    results = ingest_directory(str(tmp_path), project="test")
    paths = {r["path"] for r in results}
    assert any("visible.py" in p for p in paths)
    assert not any("secret.py" in p for p in paths)


def test_list_ingested(tmp_memory_dir, tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Content for listing test that is long enough.\n")
    ingest_file(str(txt_file), project="test")

    files = list_ingested()
    assert len(files) >= 1
    assert any(str(txt_file.resolve()) in f["path"] for f in files)
