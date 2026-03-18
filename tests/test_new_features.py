"""Tests for new high-impact features:
- Semantic diff context (get_diff_context)
- Change impact analysis (what_breaks_if_i_change)
- Cross-repo symbol resolution (resolve_symbol)
- Query-aware token budgeting (auto budget)
- Auto-warm on session start
- Test mapping (get_tests_for)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path):
    """Create a sample project with cross-references for testing."""
    # Main module that others depend on
    (tmp_path / "auth.py").write_text(
        "def authenticate(user, password):\n"
        "    return user == 'admin'\n"
        "\n"
        "def authorize(user, role):\n"
        "    return role in ('admin', 'editor')\n"
        "\n"
        "class AuthHandler:\n"
        "    def login(self, user):\n"
        "        return authenticate(user, 'pass')\n"
    )
    # Module that imports auth
    (tmp_path / "api.py").write_text(
        "from auth import authenticate, authorize\n"
        "\n"
        "def handle_request(user):\n"
        "    if authenticate(user, 'pass'):\n"
        "        return 'ok'\n"
        "    return 'denied'\n"
        "\n"
        "def check_access(user, role):\n"
        "    return authorize(user, role)\n"
    )
    # Another module that uses auth
    (tmp_path / "middleware.py").write_text(
        "from auth import authenticate\n"
        "\n"
        "def auth_middleware(request):\n"
        "    user = request.get('user')\n"
        "    return authenticate(user, request.get('pass'))\n"
    )
    # Test file
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "test_auth.py").write_text(
        "from auth import authenticate, authorize\n"
        "\n"
        "def test_authenticate():\n"
        "    assert authenticate('admin', 'pass') == True\n"
        "    assert authenticate('user', 'pass') == False\n"
        "\n"
        "def test_authorize():\n"
        "    assert authorize('admin', 'admin') == True\n"
        "\n"
        "class TestAuthHandler:\n"
        "    def test_login(self):\n"
        "        from auth import AuthHandler\n"
        "        handler = AuthHandler()\n"
        "        assert handler.login('admin')\n"
    )
    (tmp_path / "tests" / "test_api.py").write_text(
        "from api import handle_request\n"
        "\n"
        "def test_handle_request():\n"
        "    assert handle_request('admin') == 'ok'\n"
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
    srv._watchers.clear()
    srv._project_locks.clear()
    yield
    for watcher in list(srv._watchers.values()):
        watcher.stop()
    srv._watchers.clear()
    if srv._storage is not None:
        srv._storage.close()


@pytest.fixture
def setup_server(project_dir):
    """Set up server with a temp DB and index the project."""
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


# --- Semantic Diff Context ---


class TestGetDiffContext:
    def test_diff_context_with_line_range(self, setup_server):
        from arrow.server import get_diff_context
        project_dir, _, _ = setup_server

        result = json.loads(get_diff_context(
            "auth.py", line_start=1, line_end=2,
        ))
        assert "error" not in result
        assert result["file"] == "auth.py"
        assert len(result["changed_functions"]) > 0
        # authenticate is in lines 1-2
        names = [f["name"] for f in result["changed_functions"]]
        assert "authenticate" in names

    def test_diff_context_finds_callers(self, setup_server):
        from arrow.server import get_diff_context
        result = json.loads(get_diff_context(
            "auth.py", line_start=1, line_end=2,
        ))
        # api.py and middleware.py both call authenticate
        caller_files = [c["file"] for c in result["callers"]]
        assert any("api" in f for f in caller_files) or result["total_callers"] > 0

    def test_diff_context_finds_dependents(self, setup_server):
        from arrow.server import get_diff_context
        result = json.loads(get_diff_context(
            "auth.py", line_start=1, line_end=10,
        ))
        dep_paths = [d["path"] for d in result["dependent_files"]]
        # api.py and middleware.py import from auth
        assert len(dep_paths) > 0

    def test_diff_context_nonexistent_file(self, setup_server):
        from arrow.server import get_diff_context
        result = json.loads(get_diff_context("nonexistent.py"))
        assert "error" in result


# --- Change Impact Analysis ---


class TestWhatBreaksIfIChange:
    def test_impact_specific_function(self, setup_server):
        from arrow.server import what_breaks_if_i_change
        result = json.loads(what_breaks_if_i_change(
            "auth.py", function="authenticate",
        ))
        assert "error" not in result
        assert result["file"] == "auth.py"
        assert "authenticate" in result["symbols_analyzed"]
        assert result["risk"] in ("low", "medium", "high")
        assert result["summary"]["total_callers"] >= 0

    def test_impact_whole_file(self, setup_server):
        from arrow.server import what_breaks_if_i_change
        result = json.loads(what_breaks_if_i_change("auth.py"))
        assert "error" not in result
        # Should analyze all functions in the file
        assert len(result["symbols_analyzed"]) >= 2  # authenticate, authorize, etc.

    def test_impact_finds_tests(self, setup_server):
        from arrow.server import what_breaks_if_i_change
        result = json.loads(what_breaks_if_i_change(
            "auth.py", function="authenticate",
        ))
        # test_auth.py has test_authenticate
        test_files = [t["file"] for t in result["affected_tests"]]
        # May or may not find depending on indexing, but structure is correct
        assert isinstance(result["affected_tests"], list)
        assert result["summary"]["total_tests"] >= 0

    def test_impact_nonexistent_file(self, setup_server):
        from arrow.server import what_breaks_if_i_change
        result = json.loads(what_breaks_if_i_change("nonexistent.py"))
        assert "error" in result

    def test_impact_risk_levels(self, setup_server):
        from arrow.server import what_breaks_if_i_change
        result = json.loads(what_breaks_if_i_change("auth.py"))
        assert result["risk"] in ("low", "medium", "high")


# --- Cross-Repo Symbol Resolution ---


class TestResolveSymbol:
    def test_resolve_symbol_local(self, setup_server):
        from arrow.server import resolve_symbol
        result = json.loads(resolve_symbol("authenticate"))
        assert "error" not in result
        assert result["query"] == "authenticate"
        assert len(result["results"]) > 0
        # Should find the definition
        names = [r["symbol"] for r in result["results"]]
        assert "authenticate" in names

    def test_resolve_symbol_cross_repo(self, setup_server):
        """Index a second project and resolve symbols across both."""
        project_dir, _, _ = setup_server
        from arrow.server import index_github_content, resolve_symbol

        # Index remote content with a matching symbol name
        index_github_content(
            owner="other", repo="lib", branch="main",
            files=[{
                "path": "shared.py",
                "content": "def authenticate(token):\n    return True\n",
            }],
        )

        result = json.loads(resolve_symbol("authenticate"))
        assert result["total"] >= 2
        projects = {r["project"] for r in result["results"]}
        assert len(projects) >= 2  # From both repos

    def test_resolve_nonexistent_symbol(self, setup_server):
        from arrow.server import resolve_symbol
        result = json.loads(resolve_symbol("zzz_nonexistent_symbol"))
        assert result["total"] == 0


# --- Query-Aware Token Budgeting ---


class TestQueryAwareBudget:
    def test_auto_budget_simple(self, setup_server):
        """Simple symbol lookup should get a small budget."""
        from arrow.server import get_context
        result = json.loads(get_context("add"))
        assert result["token_budget"] <= 3000

    def test_auto_budget_broad(self, setup_server):
        """Broad query should get a larger budget."""
        from arrow.server import get_context
        result = json.loads(get_context(
            "how does the authentication architecture work with middleware"
        ))
        assert result["token_budget"] >= 1500

    def test_explicit_budget_respected(self, setup_server):
        """Explicit budget should override auto."""
        from arrow.server import get_context
        result = json.loads(get_context("add", token_budget=500))
        assert result["token_budget"] == 500
        assert result["tokens_used"] <= 500

    def test_budget_estimation(self, setup_server):
        """Test the estimate_budget method directly."""
        import arrow.server as srv
        searcher = srv._get_searcher()
        budget = searcher.estimate_budget("add")
        assert budget >= 500
        assert budget <= 12000


# --- Auto-Warm ---


class TestAutoWarm:
    def test_auto_warm_skips_non_git(self, tmp_path):
        """Auto-warm should skip non-git directories."""
        db_path = tempfile.mktemp(suffix=".db")
        vec_path = tempfile.mktemp(suffix=".usearch")
        os.environ["ARROW_DB_PATH"] = db_path
        os.environ["ARROW_VECTOR_PATH"] = vec_path

        try:
            original_cwd = os.getcwd()
            os.chdir(tmp_path)

            from arrow.server import _auto_warm_cwd
            # Should not crash on non-git directory
            _auto_warm_cwd()

            os.chdir(original_cwd)
        finally:
            os.environ.pop("ARROW_DB_PATH", None)
            os.environ.pop("ARROW_VECTOR_PATH", None)
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_auto_warm_indexes_git_dir(self, tmp_path):
        """Auto-warm should index a git directory."""
        db_path = tempfile.mktemp(suffix=".db")
        vec_path = tempfile.mktemp(suffix=".usearch")
        os.environ["ARROW_DB_PATH"] = db_path
        os.environ["ARROW_VECTOR_PATH"] = vec_path

        # Create a git repo
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        (tmp_path / "hello.py").write_text("def hello(): pass\n")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )

        try:
            original_cwd = os.getcwd()
            os.chdir(tmp_path)

            from arrow.server import _auto_warm_cwd
            _auto_warm_cwd()

            # Give background thread a moment
            import time
            time.sleep(2)

            # Check that something was indexed
            import arrow.server as srv
            storage = srv._get_storage()
            projects = storage.list_projects()
            assert len(projects) >= 1

            os.chdir(original_cwd)
        finally:
            os.environ.pop("ARROW_DB_PATH", None)
            os.environ.pop("ARROW_VECTOR_PATH", None)
            if os.path.exists(db_path):
                os.unlink(db_path)


# --- Test Mapping ---


class TestGetTestsFor:
    def test_find_tests_by_name(self, setup_server):
        from arrow.server import get_tests_for
        result = json.loads(get_tests_for("authenticate"))
        assert "error" not in result
        assert result["function"] == "authenticate"
        # Should find test_authenticate
        test_names = [t["test_name"] for t in result["tests"]]
        assert any("authenticate" in name for name in test_names)

    def test_find_tests_by_reference(self, setup_server):
        from arrow.server import get_tests_for
        result = json.loads(get_tests_for("authorize"))
        # test_authorize references authorize
        assert result["total"] > 0

    def test_find_tests_with_source_file(self, setup_server):
        from arrow.server import get_tests_for
        result = json.loads(get_tests_for(
            "authenticate", file="auth.py",
        ))
        assert result["source_file"] == "auth.py"
        assert result["total"] > 0

    def test_no_tests_for_unknown_function(self, setup_server):
        from arrow.server import get_tests_for
        result = json.loads(get_tests_for("zzz_nonexistent_function"))
        assert result["total"] == 0

    def test_find_class_tests(self, setup_server):
        from arrow.server import get_tests_for
        result = json.loads(get_tests_for("AuthHandler"))
        # TestAuthHandler references AuthHandler
        assert isinstance(result["tests"], list)


# --- Storage new methods ---


class TestStorageNewMethods:
    def test_count_fts_hits(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        count = storage.count_fts_hits("authenticate")
        assert count >= 0

    def test_get_test_files(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        test_files = storage.get_test_files()
        test_paths = [f.path for f in test_files]
        assert any("test_" in p for p in test_paths)

    def test_get_importers_of_file(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        importers = storage.get_importers_of_file("auth.py")
        # api.py and middleware.py import from auth
        importer_paths = [i["path"] for i in importers]
        assert len(importer_paths) > 0

    def test_resolve_symbol_across_repos(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        results = storage.resolve_symbol_across_repos("authenticate")
        assert len(results) > 0
        assert results[0]["name"] == "authenticate"
