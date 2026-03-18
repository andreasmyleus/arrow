"""Tests for MCP server tool functions."""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path):
    """Create a sample project for server tool testing."""
    (tmp_path / "main.py").write_text(
        "from utils import add\n\ndef main():\n    result = add(1, 2)\n    print(result)\n"
    )
    (tmp_path / "utils.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n"
    )
    (tmp_path / "config.json").write_text('{"debug": true}')
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "__init__.py").write_text("")
    (lib / "helper.py").write_text(
        "class Helper:\n    def run(self):\n        return 'done'\n"
    )
    return tmp_path


@pytest.fixture(autouse=True)
def clean_server_state():
    """Reset server global state between tests."""
    import arrow.server as srv
    srv._storage = None
    srv._indexer = None
    srv._vector_store = None
    srv._embedder = None
    srv._searcher = None
    srv._watcher = None
    yield
    # Cleanup
    if srv._watcher is not None:
        srv._watcher.stop()
    if srv._storage is not None:
        srv._storage.close()


@pytest.fixture
def setup_server(project_dir):
    """Set up server with a temp DB and index a project."""
    db_path = tempfile.mktemp(suffix=".db")
    vec_path = tempfile.mktemp(suffix=".usearch")
    os.environ["ARROW_DB_PATH"] = db_path
    os.environ["ARROW_VECTOR_PATH"] = vec_path

    from arrow.server import index_codebase
    index_codebase(str(project_dir))

    yield project_dir, db_path, vec_path

    os.environ.pop("ARROW_DB_PATH", None)
    os.environ.pop("ARROW_VECTOR_PATH", None)
    for p in (db_path, vec_path):
        if os.path.exists(p):
            os.unlink(p)


class TestServerTools:
    def test_index_codebase(self, setup_server):
        project_dir, _, _ = setup_server
        from arrow.server import index_codebase
        result = json.loads(index_codebase(str(project_dir)))
        # Second call should skip all files
        assert result["files_skipped"] > 0 or result["files_indexed"] == 0

    def test_index_codebase_invalid_path(self, setup_server):
        from arrow.server import index_codebase
        result = json.loads(index_codebase("/nonexistent/path"))
        assert "error" in result

    def test_project_summary(self, setup_server):
        from arrow.server import project_summary
        result = json.loads(project_summary())
        assert result["total_files"] > 0
        assert "languages" in result
        assert "structure" in result

    def test_search_code(self, setup_server):
        from arrow.server import search_code
        result = json.loads(search_code("add"))
        assert isinstance(result, list)
        assert len(result) > 0
        assert "file" in result[0]
        assert "content" in result[0]

    def test_search_code_no_results(self, setup_server):
        from arrow.server import search_code
        result = json.loads(search_code("zzzznonexistent"))
        assert isinstance(result, list)

    def test_get_context(self, setup_server):
        from arrow.server import get_context
        result = json.loads(get_context("add function", token_budget=2000))
        assert "tokens_used" in result
        assert result["tokens_used"] <= 2000
        assert "chunks" in result

    def test_search_structure(self, setup_server):
        from arrow.server import search_structure
        result = json.loads(search_structure("add"))
        assert isinstance(result, list)
        # Should find the add function
        names = [r["name"] for r in result]
        assert "add" in names

    def test_search_structure_by_kind(self, setup_server):
        from arrow.server import search_structure
        result = json.loads(search_structure("Helper", kind="class"))
        assert isinstance(result, list)

    def test_trace_dependencies(self, setup_server):
        from arrow.server import trace_dependencies
        result = json.loads(trace_dependencies("main.py"))
        assert "imports" in result
        assert "imported_by" in result

    def test_trace_dependencies_nonexistent(self, setup_server):
        from arrow.server import trace_dependencies
        result = json.loads(trace_dependencies("nonexistent.py"))
        assert "error" in result

    def test_file_summary(self, setup_server):
        from arrow.server import file_summary
        result = json.loads(file_summary("utils.py"))
        assert result["language"] == "python"
        assert result["total_chunks"] > 0
        func_names = [f["name"] for f in result["functions"]]
        assert "add" in func_names

    def test_file_summary_nonexistent(self, setup_server):
        from arrow.server import file_summary
        result = json.loads(file_summary("nonexistent.py"))
        assert "error" in result

    def test_tools_before_indexing(self):
        """Tools should return error when no project is indexed."""
        db_path = tempfile.mktemp(suffix=".db")
        os.environ["ARROW_DB_PATH"] = db_path
        os.environ["ARROW_VECTOR_PATH"] = tempfile.mktemp(suffix=".usearch")

        try:
            from arrow.server import project_summary, search_code, get_context
            for tool_fn in [project_summary, lambda: search_code("test"),
                            lambda: get_context("test")]:
                result = json.loads(tool_fn())
                assert "error" in result
        finally:
            os.environ.pop("ARROW_DB_PATH", None)
            os.environ.pop("ARROW_VECTOR_PATH", None)
            if os.path.exists(db_path):
                os.unlink(db_path)
