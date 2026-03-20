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
        # Should include source code in results
        assert "source" in result[0]
        assert "def add" in result[0]["source"]

    def test_search_structure_by_kind(self, setup_server):
        from arrow.server import search_structure
        result = json.loads(search_structure("Helper", kind="class"))
        assert isinstance(result, list)

    def test_search_structure_exact_match_priority(self, setup_server):
        """Exact matches should exclude prefix matches."""
        from arrow.server import search_structure
        result = json.loads(search_structure("add"))
        names = [r["name"] for r in result]
        # "add" is an exact match, so "add"-prefixed names (if any) are excluded
        assert "add" in names
        # Only exact matches returned when exact exists
        assert all(n == "add" for n in names)

    def test_search_structure_prefix_fallback(self, setup_server):
        """When no exact match, prefix matches are returned."""
        from arrow.server import search_structure
        # "sub" is not an exact symbol name but "subtract" starts with it
        result = json.loads(search_structure("sub"))
        assert isinstance(result, list)
        names = [r["name"] for r in result]
        assert any(n.startswith("sub") for n in names)

    def test_search_structure_includes_source(self, setup_server):
        """Results should include the actual function source code."""
        from arrow.server import search_structure
        result = json.loads(search_structure("subtract"))
        assert len(result) >= 1
        entry = result[0]
        assert "source" in entry
        assert "def subtract" in entry["source"]
        assert entry["kind"] == "function"
        assert entry["file"]
        assert entry["lines"]

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


class TestProjectAutoDetection:
    """Test that _resolve_project_id auto-detects the current project from cwd."""

    def test_detect_project_from_cwd_matches_root(self, setup_server):
        """When cwd is the project root, auto-detect returns that project."""
        project_dir, _, _ = setup_server
        from arrow.server import _detect_project_from_cwd, _get_storage

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            project_id = _detect_project_from_cwd()
            assert project_id is not None

            # Verify it's the correct project
            storage = _get_storage()
            proj = storage.get_project(project_id)
            assert proj is not None
            assert str(project_dir) in proj.root_path
        finally:
            os.chdir(original_cwd)

    def test_detect_project_from_cwd_matches_subdirectory(self, setup_server):
        """When cwd is a subdirectory of a project, auto-detect finds it."""
        project_dir, _, _ = setup_server
        from arrow.server import _detect_project_from_cwd

        subdir = project_dir / "lib"
        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            project_id = _detect_project_from_cwd()
            assert project_id is not None
        finally:
            os.chdir(original_cwd)

    def test_detect_project_from_unrelated_dir(self, setup_server):
        """When cwd is not inside any project, returns None."""
        _, _, _ = setup_server
        from arrow.server import _detect_project_from_cwd

        original_cwd = os.getcwd()
        try:
            os.chdir(tempfile.mkdtemp())
            project_id = _detect_project_from_cwd()
            assert project_id is None
        finally:
            os.chdir(original_cwd)

    def test_resolve_project_id_auto_scopes_to_cwd(self, setup_server):
        """_resolve_project_id(None) returns the cwd project, not None."""
        project_dir, _, _ = setup_server
        from arrow.server import _resolve_project_id

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            project_id = _resolve_project_id(None)
            # Should NOT be None — should auto-detect the project
            assert project_id is not None
        finally:
            os.chdir(original_cwd)

    def test_resolve_project_id_explicit_name_still_works(self, setup_server):
        """Explicit project name takes priority over cwd detection."""
        project_dir, _, _ = setup_server
        from arrow.server import _resolve_project_id, _get_storage, _PROJECT_NOT_FOUND

        storage = _get_storage()
        projects = storage.list_projects()
        project_name = projects[0].name

        project_id = _resolve_project_id(project_name)
        assert project_id is not None
        assert project_id != _PROJECT_NOT_FOUND
        assert project_id == projects[0].id

    def test_resolve_project_id_invalid_name_returns_not_found(self, setup_server):
        """Explicit but invalid project name returns _PROJECT_NOT_FOUND."""
        _, _, _ = setup_server
        from arrow.server import _resolve_project_id, _PROJECT_NOT_FOUND

        project_id = _resolve_project_id("nonexistent/project")
        assert project_id == _PROJECT_NOT_FOUND

    def test_search_code_scoped_to_cwd_project(self, setup_server):
        """search_code without project= only returns results from cwd project."""
        project_dir, _, _ = setup_server
        from arrow.server import index_github_content, search_code

        # Index a second project with overlapping keyword
        index_github_content(
            owner="other",
            repo="repo",
            branch="main",
            files=[
                {"path": "utils.py", "content": "def add(x, y):\n    return x + y\n"},
            ],
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = search_code("add")
            # Should only contain results from the cwd project, not other/repo
            assert "other/repo" not in result
            assert "Found" in result
        finally:
            os.chdir(original_cwd)
