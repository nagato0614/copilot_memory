"""Tests for storage operations: save, dedup, conversation splitting."""

from copilot_memory.storage import save_chunk, split_conversation, save_conversation


def test_save_chunk_creates_entry(tmp_memory_dir):
    """Saving a chunk returns status 'saved'."""
    result = save_chunk("What is Python?", "A programming language.", project="test")
    assert result.status == "saved"
    assert len(result.id) == 32  # UUID hex


def test_save_chunk_deduplication(tmp_memory_dir):
    """Near-identical chunks are deduplicated."""
    r1 = save_chunk("What is Python?", "A programming language.")
    r2 = save_chunk("What is Python?", "A programming language.")
    assert r1.status == "saved"
    assert r2.status == "deduplicated"
    assert r1.id == r2.id


def test_save_chunk_different_entries(tmp_memory_dir):
    """Different chunks are saved separately."""
    r1 = save_chunk("What is Python?", "A programming language.")
    r2 = save_chunk("What is Rust?", "A systems programming language.")
    assert r1.status == "saved"
    assert r2.status == "saved"
    assert r1.id != r2.id


def test_save_chunk_with_tags(tmp_memory_dir):
    """Chunks can be saved with tags."""
    result = save_chunk("Q", "A", tags="python,testing")
    assert result.status == "saved"


def test_split_conversation_basic():
    """Basic conversation splitting works."""
    text = "User: Hello\nAssistant: Hi there\nUser: How are you?\nAssistant: I'm fine"
    pairs = split_conversation(text)
    assert len(pairs) == 2
    assert pairs[0] == ("Hello", "Hi there")
    assert pairs[1] == ("How are you?", "I'm fine")


def test_split_conversation_variants():
    """Supports Human/AI and Q/A markers."""
    text = "Human: Question\nAI: Answer"
    pairs = split_conversation(text)
    assert len(pairs) == 1
    assert pairs[0][0] == "Question"
    assert pairs[0][1] == "Answer"


def test_split_conversation_empty():
    """Empty conversation returns empty list."""
    assert split_conversation("") == []


def test_save_conversation_integration(tmp_memory_dir):
    """save_conversation parses and saves Q&A pairs."""
    text = "User: What is MCP?\nAssistant: Model Context Protocol.\nUser: How does it work?\nAssistant: Via JSON-RPC over stdio."
    result = save_conversation(text, project="test")
    assert result.saved_count == 2
    assert result.deduplicated_count == 0
