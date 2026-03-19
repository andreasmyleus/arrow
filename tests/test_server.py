"""Tests for MCP server tool functions."""

import json
import os
import tempfile

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


@pytest.fixture
def project_dir_b(tmp_path):
    """Create a second project for multi-project testing."""
    d = tmp_path / "project_b"
    d.mkdir()
    (d / "server.py").write_text(
        "def start_server():\n    print('running')\n"
    )
    (d / "db.py").write_text(
        "class Database:\n    def connect(self):\n        pass\n"
    )
    return d


class TestServerTools:
    def test_index_codebase(self, setup_server):
        project_dir, _, _ = setup_server
        from arrow.server import index_codebase
        result = json.loads(index_codebase(str(project_dir)))
        assert result["files_skipped"] > 0 or result["files_indexed"] == 0

    def test_index_codebase_invalid_path(self, setup_server):
        from arrow.server import index_codebase
        result = json.loads(index_codebase("/nonexistent/path"))
        assert "error" in result

    def test_index_returns_project_info(self, setup_server):
        project_dir, _, _ = setup_server
        from arrow.server import index_codebase
        result = json.loads(index_codebase(str(project_dir), force=True))
        assert "project_id" in result
        assert "project_name" in result

    def test_list_projects(self, setup_server):
        from arrow.server import list_projects
        result = json.loads(list_projects())
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "name" in result[0]
        assert "files" in result[0]
        assert "git_branch" in result[0]

    def test_project_summary(self, setup_server):
        from arrow.server import project_summary
        result = json.loads(project_summary())
        assert result["total_files"] > 0
        assert "languages" in result
        assert "structure" in result

    def test_search_code(self, setup_server):
        from arrow.server import search_code
        result = search_code("add")
        assert "Found" in result
        assert "results" in result
        # Should contain file references and code content
        assert "#" in result

    def test_search_code_no_results(self, setup_server):
        from arrow.server import search_code
        result = search_code("zzzznonexistent")
        assert "Found 0 results" in result

    def test_get_context(self, setup_server):
        from arrow.server import get_context
        result = get_context("add function", token_budget=2000)
        assert "budget: 2000t" in result
        assert "used:" in result

    def test_search_structure(self, setup_server):
        from arrow.server import search_structure
        result = json.loads(search_structure("add"))
        assert isinstance(result, list)
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

    def test_remove_project(self, setup_server):
        from arrow.server import list_projects, remove_project
        projects = json.loads(list_projects())
        name = projects[0]["name"]
        result = json.loads(remove_project(name))
        assert "removed" in result
        # Should be gone
        projects2 = json.loads(list_projects())
        names = [p["name"] for p in projects2]
        assert name not in names

    def test_remove_nonexistent_project(self, setup_server):
        from arrow.server import remove_project
        result = json.loads(remove_project("nonexistent/repo"))
        assert "error" in result

    def test_tools_auto_index_when_no_projects(self):
        """Tools should auto-index cwd when no project is indexed."""
        db_path = tempfile.mktemp(suffix=".db")
        os.environ["ARROW_DB_PATH"] = db_path
        os.environ["ARROW_VECTOR_PATH"] = tempfile.mktemp(suffix=".usearch")

        try:
            from arrow.server import project_summary, search_code, get_context
            # Should auto-index cwd instead of returning error
            result = json.loads(project_summary())
            assert "error" not in result
            assert result.get("total_files", 0) > 0

            result = search_code("test")
            assert "Found" in result

            result = get_context("test")
            assert "error" not in result
        finally:
            os.environ.pop("ARROW_DB_PATH", None)
            os.environ.pop("ARROW_VECTOR_PATH", None)
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestMultiProject:
    def test_index_two_projects(self, setup_server, project_dir_b):
        from arrow.server import index_codebase, list_projects
        index_codebase(str(project_dir_b))

        projects = json.loads(list_projects())
        assert len(projects) >= 2

    def test_search_across_projects(self, setup_server, project_dir_b):
        from arrow.server import index_codebase, search_code
        index_codebase(str(project_dir_b))

        # Search all projects
        results = search_code("function class def")
        assert "Found" in results
        assert "results" in results

    def test_search_scoped_to_project(self, setup_server, project_dir_b):
        from arrow.server import index_codebase, search_code, list_projects
        index_codebase(str(project_dir_b))

        projects = json.loads(list_projects())
        name_b = [p["name"] for p in projects if "project_b" in (p.get("root_path") or "")]
        if name_b:
            results = search_code("function", project=name_b[0])
            assert "Found" in results

    def test_index_github_content(self, setup_server):
        from arrow.server import index_github_content, list_projects
        result = json.loads(index_github_content(
            owner="testorg",
            repo="testrepo",
            branch="main",
            files=[
                {"path": "app.py", "content": "def app(): return 'hello'"},
            ],
        ))
        assert result["files_indexed"] == 1
        assert result["project_name"] == "testorg/testrepo"

        projects = json.loads(list_projects())
        names = [p["name"] for p in projects]
        assert "testorg/testrepo" in names
