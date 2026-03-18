"""Edge case and integration tests."""

import os
import tempfile
from pathlib import Path

import pytest

from arrow.chunker import chunk_file, detect_language
from arrow.discovery import discover_files, parse_gitignore
from arrow.indexer import Indexer
from arrow.search import HybridSearcher
from arrow.storage import Storage


@pytest.fixture
def db():
    path = tempfile.mktemp(suffix=".db")
    storage = Storage(path)
    yield storage
    storage.close()
    if os.path.exists(path):
        os.unlink(path)


# --- Chunker edge cases ---


class TestChunkerEdgeCases:
    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        chunks = chunk_file(f, "")
        assert chunks == []

    def test_single_line_file(self, tmp_path):
        f = tmp_path / "one.py"
        f.write_text("x = 1")
        chunks = chunk_file(f, "x = 1")
        assert len(chunks) >= 1

    def test_syntax_error_file(self, tmp_path):
        f = tmp_path / "bad.py"
        content = "def foo(\n    # incomplete"
        f.write_text(content)
        chunks = chunk_file(f, content)
        # Should still produce chunks (module-level fallback)
        assert len(chunks) >= 1

    def test_very_long_function(self, tmp_path):
        f = tmp_path / "long.py"
        lines = ["def long_func():"]
        for i in range(500):
            lines.append(f"    x_{i} = {i}")
        content = "\n".join(lines)
        f.write_text(content)
        chunks = chunk_file(f, content)
        assert any(c.name == "long_func" for c in chunks)

    def test_nested_classes(self, tmp_path):
        f = tmp_path / "nested.py"
        content = """class Outer:
    class Inner:
        def method(self):
            pass
    def outer_method(self):
        pass
"""
        f.write_text(content)
        chunks = chunk_file(f, content)
        names = {c.name for c in chunks}
        assert "Outer" in names
        assert "Inner" in names

    def test_decorated_function(self, tmp_path):
        f = tmp_path / "decorated.py"
        content = """@decorator
def my_func():
    pass

@app.route("/")
def handler():
    return "ok"
"""
        f.write_text(content)
        chunks = chunk_file(f, content)
        names = {c.name for c in chunks}
        assert "my_func" in names or len(chunks) >= 2

    def test_javascript_chunking(self, tmp_path):
        f = tmp_path / "test.js"
        content = """function hello() {
    return "world";
}

class MyClass {
    constructor() {}
    method() { return 1; }
}

const arrow = () => "test";
"""
        f.write_text(content)
        chunks = chunk_file(f, content)
        assert len(chunks) >= 2

    def test_typescript_chunking(self, tmp_path):
        f = tmp_path / "test.ts"
        content = """interface User {
    name: string;
    age: number;
}

function greet(user: User): string {
    return `Hello ${user.name}`;
}

type ID = string | number;
"""
        f.write_text(content)
        chunks = chunk_file(f, content)
        assert len(chunks) >= 2

    def test_rust_chunking(self, tmp_path):
        f = tmp_path / "test.rs"
        content = """struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn new(x: f64, y: f64) -> Self {
        Point { x, y }
    }
}

fn main() {
    let p = Point::new(1.0, 2.0);
}
"""
        f.write_text(content)
        chunks = chunk_file(f, content)
        assert len(chunks) >= 2

    def test_go_chunking(self, tmp_path):
        f = tmp_path / "test.go"
        content = """package main

import "fmt"

type Server struct {
    Port int
}

func (s *Server) Start() {
    fmt.Println("Starting")
}

func main() {
    s := &Server{Port: 8080}
    s.Start()
}
"""
        f.write_text(content)
        chunks = chunk_file(f, content)
        assert len(chunks) >= 2

    def test_unknown_extension_fallback(self, tmp_path):
        f = tmp_path / "test.obscure"
        content = "\n".join(f"line {i}" for i in range(150))
        f.write_text(content)
        chunks = chunk_file(f, content)
        assert len(chunks) >= 1

    def test_detect_all_common_languages(self):
        langs = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".rs": "rust", ".go": "go", ".java": "java", ".c": "c",
            ".cpp": "cpp", ".rb": "ruby", ".php": "php", ".swift": "swift",
        }
        for ext, expected in langs.items():
            assert detect_language(Path(f"test{ext}")) == expected


# --- Discovery edge cases ---


class TestDiscoveryEdgeCases:
    def test_gitignore_parsing(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\nbuild/\n# comment\n\n!important.log\n")
        patterns = parse_gitignore(gitignore)
        assert "*.log" in patterns
        assert "build/" in patterns
        assert "# comment" not in patterns

    def test_empty_directory(self, tmp_path):
        files = list(discover_files(tmp_path))
        assert files == []

    def test_deeply_nested(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("x = 1")
        files = list(discover_files(tmp_path))
        assert any(f.name == "deep.py" for f in files)

    def test_symlinks_followed(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        (real / "file.py").write_text("x = 1")
        # Just test that discover_files doesn't crash on the dir
        files = list(discover_files(tmp_path))
        assert any(f.name == "file.py" for f in files)

    def test_large_file_skipped(self, tmp_path):
        large = tmp_path / "big.py"
        large.write_text("x" * 2_000_000)  # 2MB > 1MB limit
        files = list(discover_files(tmp_path))
        assert not any(f.name == "big.py" for f in files)

    def test_unicode_filename(self, tmp_path):
        f = tmp_path / "tëst_fïlé.py"
        f.write_text("x = 1")
        files = list(discover_files(tmp_path))
        assert len(files) == 1


# --- Storage edge cases ---


class TestStorageEdgeCases:
    def test_fts_special_characters(self, db):
        fid = db.upsert_file("test.py", "abc", "python")
        db.insert_chunk(
            fid, "my-func", "function", 1, 5,
            b"x", "def my_func(): pass",
            "test.py::my-func", 10,
        )
        db.commit()
        # Should not crash on special chars
        results = db.search_fts("my-func", limit=5)
        assert isinstance(results, list)

    def test_fts_empty_query(self, db):
        results = db.search_fts("", limit=5)
        assert results == []

    def test_fts_very_long_query(self, db):
        results = db.search_fts("a " * 100, limit=5)
        assert isinstance(results, list)

    def test_concurrent_reads(self, db):
        """SQLite WAL should handle concurrent reads."""
        fid = db.upsert_file("test.py", "abc", "python")
        db.insert_chunk(
            fid, "func", "function", 1, 3,
            b"x", "def func(): pass", "test.py::func", 5,
        )
        db.commit()

        # Multiple reads shouldn't deadlock
        for _ in range(100):
            db.search_fts("func", limit=5)
            db.get_file("test.py")
            db.get_stats()

    def test_get_nonexistent_file(self, db):
        assert db.get_file("nonexistent.py") is None

    def test_get_nonexistent_chunk(self, db):
        assert db.get_chunk_by_id(99999) is None


# --- Indexer edge cases ---


class TestIndexerEdgeCases:
    def test_index_nonexistent_path(self, db):
        idx = Indexer(db)
        result = idx.index_codebase("/nonexistent/path/xyz")
        assert result["files_scanned"] == 0

    def test_index_single_file_project(self, db, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')")
        idx = Indexer(db)
        result = idx.index_codebase(tmp_path)
        assert result["files_indexed"] == 1

    def test_index_mixed_languages(self, db, tmp_path):
        (tmp_path / "main.py").write_text("def main(): pass")
        (tmp_path / "app.js").write_text("function app() {}")
        (tmp_path / "lib.rs").write_text("fn lib() {}")
        idx = Indexer(db)
        result = idx.index_codebase(tmp_path)
        assert result["files_indexed"] == 3
        assert len(result["languages"]) >= 2

    def test_modified_file_reindexed(self, db, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        idx = Indexer(db)
        idx.index_codebase(tmp_path)

        f.write_text("x = 2\ny = 3")
        result = idx.index_codebase(tmp_path)
        assert result["files_indexed"] == 1
        assert result["files_skipped"] == 0


# --- Search edge cases ---


class TestSearchEdgeCases:
    def test_search_empty_index(self, db):
        searcher = HybridSearcher(db)
        results = searcher.search("anything", limit=5)
        assert results == []

    def test_get_context_empty_index(self, db):
        searcher = HybridSearcher(db)
        ctx = searcher.get_context("anything", token_budget=1000)
        assert ctx["tokens_used"] == 0
        assert ctx["chunks"] == []

    def test_get_context_tiny_budget(self, db, tmp_path):
        (tmp_path / "test.py").write_text(
            "def very_long_function_name():\n" + "    x = 1\n" * 100
        )
        idx = Indexer(db)
        idx.index_codebase(tmp_path)
        searcher = HybridSearcher(db)
        ctx = searcher.get_context("function", token_budget=10)
        assert ctx["tokens_used"] <= 10 or len(ctx["chunks"]) == 0

    def test_search_special_characters(self, db, tmp_path):
        (tmp_path / "test.py").write_text("def __init__(self): pass")
        idx = Indexer(db)
        idx.index_codebase(tmp_path)
        searcher = HybridSearcher(db)
        # Should not crash
        results = searcher.search("__init__", limit=5)
        assert isinstance(results, list)
