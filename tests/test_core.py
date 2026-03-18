"""Core tests for Arrow MCP server."""

import os
import tempfile
from pathlib import Path

import pytest

from arrow.chunker import (
    chunk_file,
    chunk_file_fallback,
    chunk_file_treesitter,
    compress_content,
    decompress_content,
    detect_language,
)
from arrow.discovery import discover_files
from arrow.hasher import hash_content, hash_file
from arrow.indexer import Indexer, count_tokens
from arrow.search import HybridSearcher, reciprocal_rank_fusion
from arrow.storage import Storage


@pytest.fixture
def db():
    path = tempfile.mktemp(suffix=".db")
    storage = Storage(path)
    yield storage
    storage.close()
    os.unlink(path)


@pytest.fixture
def sample_dir(tmp_path):
    """Create a sample project directory for testing."""
    (tmp_path / "main.py").write_text(
        'import os\n\ndef main():\n    print("hello")\n\nif __name__ == "__main__":\n    main()\n'
    )
    (tmp_path / "utils.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n"
    )
    (tmp_path / "README.md").write_text("# Test Project\n\nA test project.\n")
    sub = tmp_path / "lib"
    sub.mkdir()
    (sub / "helper.py").write_text(
        "class Helper:\n    def run(self):\n        pass\n"
    )
    (sub / "__init__.py").write_text("")
    return tmp_path


# --- Hasher tests ---


class TestHasher:
    def test_hash_content_string(self):
        h = hash_content("hello world")
        assert isinstance(h, str)
        assert len(h) == 32  # xxHash3-128 hex

    def test_hash_content_bytes(self):
        h = hash_content(b"hello world")
        assert isinstance(h, str)

    def test_hash_content_deterministic(self):
        assert hash_content("test") == hash_content("test")

    def test_hash_content_different(self):
        assert hash_content("a") != hash_content("b")

    def test_hash_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = hash_file(str(f))
        assert isinstance(h, str)
        assert len(h) == 32


# --- Chunker tests ---


class TestChunker:
    def test_detect_language_python(self):
        assert detect_language(Path("test.py")) == "python"

    def test_detect_language_javascript(self):
        assert detect_language(Path("test.js")) == "javascript"

    def test_detect_language_unknown(self):
        assert detect_language(Path("test.xyz")) is None

    def test_chunk_python_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n\ndef bar():\n    return 1\n")
        chunks = chunk_file(f, f.read_text())
        names = {c.name for c in chunks}
        assert "foo" in names
        assert "bar" in names

    def test_chunk_fallback(self, tmp_path):
        f = tmp_path / "test.xyz"
        content = "\n".join(f"line {i}" for i in range(200))
        chunks = chunk_file_fallback(f, content)
        assert len(chunks) >= 2

    def test_compress_decompress(self):
        original = "def hello():\n    return 'world'\n"
        compressed = compress_content(original)
        assert isinstance(compressed, bytes)
        decompressed = decompress_content(compressed)
        assert decompressed == original


# --- Discovery tests ---


class TestDiscovery:
    def test_discover_files(self, sample_dir):
        files = list(discover_files(sample_dir))
        names = {f.name for f in files}
        assert "main.py" in names
        assert "utils.py" in names
        assert "helper.py" in names

    def test_ignores_pycache(self, sample_dir):
        cache_dir = sample_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "test.pyc").write_bytes(b"\x00")
        files = list(discover_files(sample_dir))
        names = {f.name for f in files}
        assert "test.pyc" not in names

    def test_ignores_binary(self, sample_dir):
        (sample_dir / "binary.bin").write_bytes(b"\x00\x01\x02")
        files = list(discover_files(sample_dir))
        names = {f.name for f in files}
        assert "binary.bin" not in names


# --- Storage tests ---


class TestStorage:
    def test_upsert_and_get_file(self, db):
        fid = db.upsert_file("test.py", "abc123", "python")
        assert fid > 0
        rec = db.get_file("test.py")
        assert rec is not None
        assert rec.content_hash == "abc123"
        assert rec.language == "python"

    def test_upsert_updates(self, db):
        db.upsert_file("test.py", "hash1", "python")
        db.upsert_file("test.py", "hash2", "python")
        rec = db.get_file("test.py")
        assert rec.content_hash == "hash2"

    def test_delete_file(self, db):
        db.upsert_file("test.py", "abc", "python")
        db.delete_file("test.py")
        assert db.get_file("test.py") is None

    def test_insert_and_search_fts(self, db):
        fid = db.upsert_file("test.py", "abc", "python")
        db.insert_chunk(
            fid, "my_function", "function", 1, 5,
            b"compressed", "def my_function(): pass",
            "test.py::my_function", 10,
        )
        db.commit()
        results = db.search_fts("my_function", limit=5)
        assert len(results) > 0

    def test_search_symbols(self, db):
        fid = db.upsert_file("test.py", "abc", "python")
        cid = db.insert_chunk(
            fid, "foo", "function", 1, 3,
            b"x", "def foo(): pass", "test.py::foo", 5,
        )
        db.insert_symbol(cid, "foo", "function", fid)
        db.commit()
        syms = db.search_symbols("foo")
        assert len(syms) == 1
        assert syms[0].name == "foo"

    def test_project_meta(self, db):
        db.set_project_meta("root", "/tmp/test")
        assert db.get_project_meta("root") == "/tmp/test"

    def test_stats(self, db):
        stats = db.get_stats()
        assert stats["files"] == 0
        assert stats["chunks"] == 0


# --- Indexer tests ---


class TestIndexer:
    def test_index_codebase(self, db, sample_dir):
        idx = Indexer(db)
        result = idx.index_codebase(sample_dir)
        assert result["files_indexed"] > 0
        assert result["chunks_created"] > 0

    def test_incremental_indexing(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        result2 = idx.index_codebase(sample_dir)
        assert result2["files_indexed"] == 0
        assert result2["files_skipped"] > 0

    def test_force_reindex(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        result2 = idx.index_codebase(sample_dir, force=True)
        assert result2["files_indexed"] > 0

    def test_deleted_files_removed(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        (sample_dir / "utils.py").unlink()
        result2 = idx.index_codebase(sample_dir)
        assert result2["files_removed"] == 1

    def test_project_summary(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        summary = idx.generate_project_summary()
        assert summary["total_files"] > 0

    def test_count_tokens(self):
        tokens = count_tokens("hello world")
        assert tokens > 0


# --- Search tests ---


class TestSearch:
    def test_reciprocal_rank_fusion(self):
        list1 = [(1, 0.9), (2, 0.8), (3, 0.7)]
        list2 = [(2, 0.95), (3, 0.85), (4, 0.75)]
        fused = reciprocal_rank_fusion([list1, list2])
        ids = [item_id for item_id, _ in fused]
        assert 2 in ids  # Should rank high (in both lists)

    def test_hybrid_search(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        searcher = HybridSearcher(db)
        results = searcher.search("add multiply", limit=5)
        assert len(results) > 0

    def test_get_context(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        searcher = HybridSearcher(db)
        ctx = searcher.get_context("helper class", token_budget=1000)
        assert ctx["tokens_used"] <= 1000
        assert len(ctx["chunks"]) > 0
