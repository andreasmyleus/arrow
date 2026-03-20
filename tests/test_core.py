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
from arrow.search import (
    HybridSearcher,
    reciprocal_rank_fusion,
    _extract_query_concepts,
    _filename_match_boost,
)
from arrow.storage import Storage


@pytest.fixture
def db():
    path = tempfile.mktemp(suffix=".db")
    storage = Storage(path)
    yield storage
    storage.close()
    if os.path.exists(path):
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
        # Create a project first
        pid = db.create_project("test-project", root_path="/tmp/test")
        fid = db.upsert_file("test.py", "abc123", "python", project_id=pid)
        assert fid > 0
        rec = db.get_file("test.py", project_id=pid)
        assert rec is not None
        assert rec.content_hash == "abc123"
        assert rec.language == "python"
        assert rec.project_id == pid

    def test_upsert_updates(self, db):
        pid = db.create_project("test-project", root_path="/tmp/test")
        db.upsert_file("test.py", "hash1", "python", project_id=pid)
        db.upsert_file("test.py", "hash2", "python", project_id=pid)
        rec = db.get_file("test.py", project_id=pid)
        assert rec.content_hash == "hash2"

    def test_delete_file(self, db):
        pid = db.create_project("test-project", root_path="/tmp/test")
        db.upsert_file("test.py", "abc", "python", project_id=pid)
        db.delete_file("test.py", project_id=pid)
        assert db.get_file("test.py", project_id=pid) is None

    def test_insert_and_search_fts(self, db):
        pid = db.create_project("test-project", root_path="/tmp/test")
        fid = db.upsert_file("test.py", "abc", "python", project_id=pid)
        db.insert_chunk(
            fid, "my_function", "function", 1, 5,
            b"compressed", "def my_function(): pass",
            "test.py::my_function", 10, project_id=pid,
        )
        db.commit()
        results = db.search_fts("my_function", limit=5)
        assert len(results) > 0

    def test_search_fts_project_scoped(self, db):
        pid1 = db.create_project("project-a", root_path="/tmp/a")
        pid2 = db.create_project("project-b", root_path="/tmp/b")
        fid1 = db.upsert_file("test.py", "abc", "python", project_id=pid1)
        fid2 = db.upsert_file("test.py", "def", "python", project_id=pid2)
        db.insert_chunk(
            fid1, "func_a", "function", 1, 5,
            b"x", "def func_a(): pass", "test.py::func_a", 10, project_id=pid1,
        )
        db.insert_chunk(
            fid2, "func_b", "function", 1, 5,
            b"x", "def func_b(): pass", "test.py::func_b", 10, project_id=pid2,
        )
        db.commit()

        # Scoped to project 1
        results = db.search_fts("func", limit=10, project_id=pid1)
        chunk_ids = [cid for cid, _ in results]
        chunks = db.get_chunks_by_ids(chunk_ids)
        assert all(c.project_id == pid1 for c in chunks)

    def test_search_symbols(self, db):
        pid = db.create_project("test-project", root_path="/tmp/test")
        fid = db.upsert_file("test.py", "abc", "python", project_id=pid)
        cid = db.insert_chunk(
            fid, "foo", "function", 1, 3,
            b"x", "def foo(): pass", "test.py::foo", 5, project_id=pid,
        )
        db.insert_symbol(cid, "foo", "function", fid)
        db.commit()
        syms = db.search_symbols("foo")
        assert len(syms) == 1
        assert syms[0].name == "foo"

    def test_search_symbols_exact_match_priority(self, db):
        """Exact matches should sort before prefix matches."""
        pid = db.create_project("test-project", root_path="/tmp/test")
        fid = db.upsert_file("test.py", "abc", "python", project_id=pid)
        # Create "search" (exact) and "search_code" (prefix)
        cid1 = db.insert_chunk(
            fid, "search", "function", 1, 3,
            b"x", "def search(): pass", "test.py::search",
            5, project_id=pid,
        )
        cid2 = db.insert_chunk(
            fid, "search_code", "function", 5, 10,
            b"y", "def search_code(): pass", "test.py::search_code",
            8, project_id=pid,
        )
        db.insert_symbol(cid1, "search", "function", fid)
        db.insert_symbol(cid2, "search_code", "function", fid)
        db.commit()

        syms = db.search_symbols("search")
        assert len(syms) == 2
        # Exact match "search" must come first
        assert syms[0].name == "search"
        assert syms[1].name == "search_code"

    def test_search_symbols_kind_filter(self, db):
        """Kind filter should work with exact-match ordering."""
        pid = db.create_project("test-project", root_path="/tmp/test")
        fid = db.upsert_file("test.py", "abc", "python", project_id=pid)
        cid1 = db.insert_chunk(
            fid, "run", "function", 1, 3,
            b"x", "def run(): pass", "test.py::run",
            5, project_id=pid,
        )
        cid2 = db.insert_chunk(
            fid, "run", "method", 5, 10,
            b"y", "def run(self): pass", "cls::run",
            8, project_id=pid,
        )
        db.insert_symbol(cid1, "run", "function", fid)
        db.insert_symbol(cid2, "run", "method", fid)
        db.commit()

        syms = db.search_symbols("run", kind="function")
        assert len(syms) == 1
        assert syms[0].kind == "function"

    def test_project_crud(self, db):
        pid = db.create_project(
            "org/repo", root_path="/tmp/repo",
            git_branch="main", git_commit="abc123",
        )
        assert pid > 0

        proj = db.get_project(pid)
        assert proj.name == "org/repo"
        assert proj.git_branch == "main"

        proj2 = db.get_project_by_name("org/repo")
        assert proj2.id == pid

        proj3 = db.get_project_by_root("/tmp/repo")
        assert proj3.id == pid

        projects = db.list_projects()
        assert len(projects) >= 1

        db.update_project_git(pid, "develop", "def456")
        proj = db.get_project(pid)
        assert proj.git_branch == "develop"
        assert proj.git_commit == "def456"

    def test_delete_project_cascades(self, db):
        pid = db.create_project("test-project", root_path="/tmp/test")
        fid = db.upsert_file("test.py", "abc", "python", project_id=pid)
        db.insert_chunk(
            fid, "func", "function", 1, 3,
            b"x", "def func(): pass", "test.py::func", 5, project_id=pid,
        )
        db.commit()
        assert db.get_stats(project_id=pid)["files"] == 1

        db.delete_project(pid)
        assert db.get_project(pid) is None
        assert db.get_stats(project_id=pid)["files"] == 0

    def test_same_path_different_projects(self, db):
        pid1 = db.create_project("project-a", root_path="/tmp/a")
        pid2 = db.create_project("project-b", root_path="/tmp/b")

        fid1 = db.upsert_file("main.py", "hash1", "python", project_id=pid1)
        fid2 = db.upsert_file("main.py", "hash2", "python", project_id=pid2)
        assert fid1 != fid2

        rec1 = db.get_file("main.py", project_id=pid1)
        rec2 = db.get_file("main.py", project_id=pid2)
        assert rec1.content_hash == "hash1"
        assert rec2.content_hash == "hash2"

    def test_project_meta_legacy(self, db):
        # Legacy set_project_meta should not crash
        db.set_project_meta("root", "/tmp/test")

    def test_stats(self, db):
        stats = db.get_stats()
        assert stats["files"] == 0
        assert stats["chunks"] == 0

    def test_stats_project_scoped(self, db):
        pid1 = db.create_project("project-a", root_path="/tmp/a")
        pid2 = db.create_project("project-b", root_path="/tmp/b")
        db.upsert_file("a.py", "h1", "python", project_id=pid1)
        db.upsert_file("b.py", "h2", "python", project_id=pid2)

        stats1 = db.get_stats(project_id=pid1)
        stats2 = db.get_stats(project_id=pid2)
        stats_all = db.get_stats()

        assert stats1["files"] == 1
        assert stats2["files"] == 1
        assert stats_all["files"] == 2


# --- Indexer tests ---


class TestIndexer:
    def test_index_codebase(self, db, sample_dir):
        idx = Indexer(db)
        result = idx.index_codebase(sample_dir)
        assert result["files_indexed"] > 0
        assert result["chunks_created"] > 0
        assert "project_id" in result

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
        result = idx.index_codebase(sample_dir)
        summary = idx.generate_project_summary(project_id=result["project_id"])
        assert summary["total_files"] > 0

    def test_count_tokens(self):
        tokens = count_tokens("hello world")
        assert tokens > 0

    def test_multi_project_isolation(self, db, tmp_path):
        """Indexing two projects doesn't interfere with each other."""
        dir_a = tmp_path / "project_a"
        dir_b = tmp_path / "project_b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "a.py").write_text("def func_a(): pass")
        (dir_b / "b.py").write_text("def func_b(): pass")

        idx = Indexer(db)
        result_a = idx.index_codebase(dir_a)
        result_b = idx.index_codebase(dir_b)

        assert result_a["project_id"] != result_b["project_id"]

        # Each project should have exactly 1 file
        files_a = db.get_all_files(project_id=result_a["project_id"])
        files_b = db.get_all_files(project_id=result_b["project_id"])
        assert len(files_a) == 1
        assert len(files_b) == 1
        assert files_a[0].path == "a.py"
        assert files_b[0].path == "b.py"

    def test_deleted_files_scoped_to_project(self, db, tmp_path):
        """Deleting files in one project doesn't affect another."""
        dir_a = tmp_path / "project_a"
        dir_b = tmp_path / "project_b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "shared.py").write_text("x = 1")
        (dir_b / "shared.py").write_text("y = 2")

        idx = Indexer(db)
        result_a = idx.index_codebase(dir_a)
        result_b = idx.index_codebase(dir_b)

        # Delete shared.py from project_a
        (dir_a / "shared.py").unlink()
        result_a2 = idx.index_codebase(dir_a)
        assert result_a2["files_removed"] == 1

        # project_b should still have its shared.py
        files_b = db.get_all_files(project_id=result_b["project_id"])
        assert len(files_b) == 1

    def test_index_remote_files(self, db):
        idx = Indexer(db)
        result = idx.index_remote_files(
            owner="testorg",
            repo="testrepo",
            branch="main",
            files=[
                {"path": "src/main.py", "content": "def main(): pass"},
                {"path": "src/utils.py", "content": "def add(a, b): return a + b"},
            ],
        )
        assert result["files_indexed"] == 2
        assert result["project_name"] == "testorg/testrepo"

        proj = db.get_project_by_name("testorg/testrepo")
        assert proj is not None
        assert proj.is_remote
        assert proj.git_branch == "main"

    def test_index_git_commit(self, db, tmp_path):
        import subprocess
        # Create a git repo with two commits
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "remote", "add", "origin",
             "https://github.com/testorg/testrepo.git"],
            capture_output=True,
        )
        (tmp_path / "main.py").write_text("def hello():\n    return 'v1'\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "v1",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )
        from arrow.git_utils import get_git_info
        first_commit = get_git_info(tmp_path)["commit"]

        (tmp_path / "main.py").write_text("def hello():\n    return 'v2'\n")
        (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "v2",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )

        idx = Indexer(db)

        # Index at first commit — should only have main.py
        result = idx.index_git_commit(tmp_path, first_commit)
        assert "error" not in result
        assert result["files_indexed"] == 1  # only main.py (README.md not a code file)
        assert result["project_name"].endswith(first_commit[:7])
        assert result["commit"]["message"] == "v1"

        # Index at HEAD — should have both files
        result2 = idx.index_git_commit(tmp_path, "HEAD")
        assert "error" not in result2
        assert result2["files_indexed"] == 2

        # Both snapshots exist as separate projects
        projects = db.list_projects()
        snapshot_names = [p.name for p in projects]
        assert any(first_commit[:7] in n for n in snapshot_names)

    def test_index_git_commit_invalid_ref(self, db, tmp_path):
        import subprocess
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        (tmp_path / "file.py").write_text("x = 1")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )
        idx = Indexer(db)
        result = idx.index_git_commit(tmp_path, "nonexistent_ref_xyz")
        assert "error" in result


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

    def test_hybrid_search_project_scoped(self, db, tmp_path):
        dir_a = tmp_path / "project_a"
        dir_b = tmp_path / "project_b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "a.py").write_text("def alpha_func(): pass")
        (dir_b / "b.py").write_text("def beta_func(): pass")

        idx = Indexer(db)
        result_a = idx.index_codebase(dir_a)
        result_b = idx.index_codebase(dir_b)

        searcher = HybridSearcher(db)

        # Search all
        all_results = searcher.search("func", limit=10)
        assert len(all_results) >= 2

        # Search scoped to project_a
        results_a = searcher.search(
            "func", limit=10, project_id=result_a["project_id"]
        )
        for r in results_a:
            assert r.project_name == dir_a.name

    def test_get_context(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        searcher = HybridSearcher(db)
        ctx = searcher.get_context("helper class", token_budget=1000)
        assert ctx["tokens_used"] <= 1000
        assert len(ctx["chunks"]) > 0

    def test_get_context_has_project_field(self, db, sample_dir):
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        searcher = HybridSearcher(db)
        ctx = searcher.get_context("main function", token_budget=4000)
        if ctx["chunks"]:
            assert "project" in ctx["chunks"][0]

    def test_rrf_k20_favors_top_ranks(self):
        """With k=20, items appearing at rank 0 in both lists should score
        significantly higher than items only in one list at a low rank."""
        # Item 1 is #1 in both lists; item 99 is #49 in one list only
        list1 = [(1, 0.9)] + [(i, 0.5) for i in range(2, 51)]
        list2 = [(1, 0.9)] + [(i + 50, 0.5) for i in range(2, 51)]
        fused = reciprocal_rank_fusion([list1, list2])
        scores = dict(fused)
        # Item 1 should score ~2 * 1/(20+1) = 0.095
        # A single-list item at rank 49 scores 1/(20+50) = 0.014
        assert scores[1] > scores.get(50, 0) * 3

    def test_filename_boost_in_ranking(self, db, tmp_path):
        """Files whose name matches query concepts should rank higher."""
        # Create two files: frecency.py (should rank higher for "frecency" query)
        # and utils.py (also defines a frecency function but in a generic file)
        (tmp_path / "frecency.py").write_text(
            "def calculate_frecency(file_id):\n"
            "    '''Calculate frecency score.'''\n"
            "    return 1.0\n"
        )
        (tmp_path / "utils.py").write_text(
            "def update_frecency(file_id, weight):\n"
            "    '''Update frecency for a file.'''\n"
            "    frecency = weight * 0.5\n"
            "    return frecency\n"
        )

        idx = Indexer(db)
        idx.index_codebase(tmp_path)
        searcher = HybridSearcher(db)
        results = searcher.search("frecency", limit=5)

        assert len(results) >= 2
        # frecency.py should rank first due to filename match boost
        assert "frecency.py" in results[0].file_path


# --- Query concept extraction tests ---


class TestQueryConceptExtraction:
    def test_filters_stop_words(self):
        concepts = _extract_query_concepts("how is frecency calculated")
        assert "frecency" in concepts
        assert "calculated" in concepts
        assert "how" not in concepts
        assert "is" not in concepts

    def test_splits_snake_case(self):
        concepts = _extract_query_concepts("reciprocal_rank_fusion")
        assert "reciprocal_rank_fusion" in concepts
        assert "reciprocal" in concepts
        assert "rank" in concepts  # 4 chars, not a stop word
        assert "fusion" in concepts

    def test_short_tokens_filtered(self):
        concepts = _extract_query_concepts("a to be or")
        assert concepts == []

    def test_code_terms_filtered(self):
        """Common code-related words should be filtered as stop words."""
        concepts = _extract_query_concepts("find the function definition")
        assert "find" not in concepts
        assert "function" not in concepts
        assert "definition" in concepts


class TestFilenameMatchBoost:
    def test_exact_stem_match(self):
        assert _filename_match_boost("src/frecency.py", ["frecency"]) == 2.0

    def test_partial_stem_match(self):
        assert _filename_match_boost("src/vector_store.py", ["vector"]) == 1.5

    def test_no_match(self):
        assert _filename_match_boost("src/server.py", ["frecency"]) == 1.0

    def test_empty_concepts(self):
        assert _filename_match_boost("src/anything.py", []) == 1.0

    def test_case_insensitive(self):
        assert _filename_match_boost("src/Frecency.py", ["frecency"]) == 2.0
