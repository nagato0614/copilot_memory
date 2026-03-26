"""Tests for storage operations: save, dedup, conversation splitting."""

from copilot_memory.storage import save_chunk, split_conversation, save_conversation, delete_by_source_path


def test_save_chunk_creates_entry(tmp_memory_dir):
    """Saving a chunk returns status 'saved'."""
    result = save_chunk("Python is a programming language used for web development and data science.", project="test")
    assert result.status == "saved"
    assert len(result.id) == 32


def test_save_chunk_deduplication(tmp_memory_dir):
    """Near-identical chunks are deduplicated."""
    r1 = save_chunk("Python is a programming language used for web development.")
    r2 = save_chunk("Python is a programming language used for web development.")
    assert r1.status == "saved"
    assert r2.status == "deduplicated"
    assert r1.id == r2.id


def test_save_chunk_different_entries(tmp_memory_dir):
    """Different chunks are saved separately."""
    r1 = save_chunk("Python is a programming language used for web development and data science.")
    r2 = save_chunk("Rust is a systems programming language focused on safety and performance.")
    assert r1.status == "saved"
    assert r2.status == "saved"
    assert r1.id != r2.id


def test_save_chunk_with_tags(tmp_memory_dir):
    """Chunks can be saved with tags."""
    result = save_chunk("Testing is important for software quality.", tags="python,testing")
    assert result.status == "saved"


def test_save_chunk_with_source_path(tmp_memory_dir):
    """Chunks can be saved with source_path."""
    result = save_chunk("[ファイル: /tmp/test.py]\ndef hello(): pass", source_path="/tmp/test.py")
    assert result.status == "saved"


def test_delete_by_source_path(tmp_memory_dir):
    """Chunks with a source_path can be deleted."""
    save_chunk("[ファイル: /tmp/a.py] foo関数はユーザー認証を処理するための主要なエントリポイントである。", source_path="/tmp/a.py")
    save_chunk("[ファイル: /tmp/a.py] bar関数はデータベース接続プールを管理し、コネクションの再利用を行う。", source_path="/tmp/a.py")
    save_chunk("Unrelated memory content for testing purposes that should not be deleted.", source_path="")

    deleted = delete_by_source_path("/tmp/a.py")
    assert deleted == 2


def test_split_conversation_basic():
    """Basic conversation splitting works."""
    text = "User: Hello\nAssistant: Hi there\nUser: How are you?\nAssistant: I'm fine"
    chunks = split_conversation(text)
    assert len(chunks) == 2
    assert "Hello" in chunks[0]
    assert "Hi there" in chunks[0]
    assert "How are you?" in chunks[1]
    assert "I'm fine" in chunks[1]


def test_split_conversation_variants():
    """Supports Human/AI markers."""
    text = "Human: Question about Python\nAI: Python is a great language"
    chunks = split_conversation(text)
    assert len(chunks) == 1
    assert "Question about Python" in chunks[0]
    assert "Python is a great language" in chunks[0]


def test_split_conversation_empty():
    """Empty conversation returns empty list."""
    assert split_conversation("") == []


def test_save_conversation_integration(tmp_memory_dir):
    """save_conversation parses and saves chunks."""
    text = "User: What is MCP?\nAssistant: Model Context Protocol.\nUser: How does it work?\nAssistant: Via JSON-RPC over stdio."
    result = save_conversation(text, project="test")
    assert result.saved_count == 2
    assert result.deduplicated_count == 0
