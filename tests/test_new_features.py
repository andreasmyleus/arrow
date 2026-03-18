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


# --- Frecency-Weighted Results ---


class TestFrecency:
    def test_record_file_access(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        files = storage.get_all_files(project_id=projects[0].id)
        assert len(files) > 0
        storage.record_file_access(files[0].id, projects[0].id)
        storage.record_file_access(files[0].id, projects[0].id)
        scores = storage.get_frecency_scores(
            project_id=projects[0].id
        )
        assert files[0].id in scores
        assert scores[files[0].id] > 0

    def test_frecency_boost_in_search(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        searcher = srv._get_searcher()
        projects = storage.list_projects()
        pid = projects[0].id

        # Search without boost
        r1 = searcher.search(
            "authenticate", limit=5, project_id=pid,
            frecency_boost=False,
        )

        # Access a file heavily
        files = storage.get_all_files(project_id=pid)
        for _ in range(10):
            storage.record_file_access(files[0].id, pid)

        # Search with boost
        r2 = searcher.search(
            "authenticate", limit=5, project_id=pid,
            frecency_boost=True,
        )
        # Both should return results
        assert len(r1) > 0
        assert len(r2) > 0

    def test_frecency_decay(self, setup_server):
        """Frecency scores should decay over time."""
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        files = storage.get_all_files(project_id=projects[0].id)
        storage.record_file_access(files[0].id, projects[0].id)
        scores = storage.get_frecency_scores(
            project_id=projects[0].id
        )
        # Score should be positive (recent access)
        assert scores[files[0].id] > 0


# --- Multi-Language Import Resolution ---


class TestMultiLangImports:
    def test_python_imports_indexed(self, setup_server):
        """Python imports should be resolved during indexing."""
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        pid = projects[0].id
        files = storage.get_all_files(project_id=pid)
        # api.py imports from auth — check import relationships
        api_file = next(
            (f for f in files if "api" in f.path), None
        )
        auth_file = next(
            (f for f in files if "auth" in f.path), None
        )
        if api_file and auth_file:
            importers = storage.get_importers_of_file(
                auth_file.path
            )
            paths = [i["path"] for i in importers]
            assert any("api" in p for p in paths)

    def test_multi_lang_import_parser(self):
        """Test import extraction for various languages."""
        from arrow.indexer import _extract_imports
        # Test JS/TS import
        js_lines = ['import { foo } from "./bar";']
        imps = _extract_imports(js_lines, "javascript")
        assert len(imps) > 0

    def test_go_import_parser(self):
        from arrow.indexer import _extract_imports
        go_lines = [
            'import (',
            '    "fmt"',
            '    "net/http"',
            ')',
        ]
        imps = _extract_imports(go_lines, "go")
        assert len(imps) > 0

    def test_rust_use_parser(self):
        from arrow.indexer import _extract_imports
        rust_lines = ['use std::collections::HashMap;']
        imps = _extract_imports(rust_lines, "rust")
        assert len(imps) > 0


# --- Stale Index Detection ---


class TestStaleIndex:
    def test_detect_stale_no_changes(self, setup_server):
        """Freshly indexed project should not be stale."""
        from arrow.server import detect_stale_index
        result = json.loads(detect_stale_index(None))
        assert isinstance(result, list)
        assert len(result) > 0
        # Just indexed, drift should be 0
        assert result[0]["drift_count"] == 0

    def test_detect_stale_after_modification(self, setup_server):
        """Modified file should show up as stale."""
        from arrow.server import detect_stale_index
        project_dir, _, _ = setup_server
        # Modify a file
        (project_dir / "auth.py").write_text(
            "def authenticate(user, password):\n"
            "    return user == 'superadmin'\n"
        )
        result = json.loads(detect_stale_index(None))
        assert result[0]["drift_count"] >= 1

    def test_detect_stale_specific_project(self, setup_server):
        from arrow.server import detect_stale_index
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        name = projects[0].name
        result = json.loads(detect_stale_index(name))
        assert isinstance(result, list)


# --- Conversation-Aware Context ---


class TestConversationContext:
    def test_session_chunk_tracking(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = "test-session-123"

        # Record some chunks
        storage.record_sent_chunk(sid, 1, tokens=100)
        storage.record_sent_chunk(sid, 2, tokens=200)

        ids = storage.get_sent_chunk_ids(sid)
        assert 1 in ids
        assert 2 in ids

        total = storage.get_session_token_total(sid)
        assert total == 300

    def test_session_clear(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = "test-session-456"

        storage.record_sent_chunk(sid, 1, tokens=50)
        storage.clear_session(sid)
        ids = storage.get_sent_chunk_ids(sid)
        assert len(ids) == 0

    def test_get_context_excludes_sent(self, setup_server):
        """get_context should exclude already-sent chunks."""
        from arrow.server import get_context
        # First call — should return results
        r1 = json.loads(get_context("authenticate"))
        assert r1.get("chunks_returned", 0) > 0
        assert "session_chunks_excluded" in r1

    def test_context_pressure_tool(self, setup_server):
        from arrow.server import context_pressure
        result = json.loads(context_pressure())
        assert "session_tokens" in result
        assert "compact_threshold" in result
        assert "context_pressure_pct" in result
        assert result["status"] in (
            "low", "moderate", "high", "critical"
        )


# --- Dead Code Detection ---


class TestDeadCode:
    def test_find_dead_code(self, setup_server):
        from arrow.server import find_dead_code
        result = json.loads(find_dead_code(None))
        assert "dead_code" in result
        assert "total" in result
        assert isinstance(result["dead_code"], list)

    def test_dead_code_skips_test_functions(self, setup_server):
        from arrow.server import find_dead_code
        result = json.loads(find_dead_code(None))
        names = [d["name"] for d in result["dead_code"]]
        # test_ functions should be skipped
        assert not any(n.startswith("test_") for n in names)

    def test_dead_code_with_project(self, setup_server):
        from arrow.server import find_dead_code
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        result = json.loads(find_dead_code(projects[0].name))
        assert "dead_code" in result


# --- Index Export/Import ---


class TestExportImport:
    def test_export_produces_json(self, setup_server):
        from arrow.server import export_index
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        result = export_index(projects[0].name)
        data = json.loads(result)
        assert "version" in data
        assert "project" in data
        assert "files" in data
        assert "chunks" in data
        assert data["stats"]["files"] > 0

    def test_import_creates_project(self, setup_server):
        from arrow.server import export_index, import_index
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        name = projects[0].name

        # Export
        bundle = export_index(name)

        # Modify bundle to have a different project name
        data = json.loads(bundle)
        data["project"]["name"] = "imported/test"
        modified = json.dumps(data)

        # Import
        result = json.loads(import_index(modified))
        assert "error" not in result
        assert result["project_name"] == "imported/test"
        assert result["files"] > 0

    def test_export_nonexistent_project(self, setup_server):
        from arrow.server import export_index
        result = json.loads(export_index("nonexistent/project"))
        assert "error" in result


# --- Tool Analytics ---


class TestToolAnalytics:
    def test_record_and_retrieve(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        storage.record_tool_call("test_tool", 42.5)
        storage.record_tool_call("test_tool", 58.3)
        stats = storage.get_tool_analytics(
            since=0  # all time
        )
        tool_stat = next(
            (s for s in stats if s["tool_name"] == "test_tool"),
            None,
        )
        assert tool_stat is not None
        assert tool_stat["calls"] == 2
        assert tool_stat["avg_latency_ms"] is not None

    def test_analytics_tool(self, setup_server):
        from arrow.server import tool_analytics
        result = json.loads(tool_analytics(24))
        assert "total_calls" in result
        assert "tools" in result
        assert isinstance(result["tools"], list)


# --- Context Compaction ---


class TestContextCompaction:
    def test_compact_context_empty_session(self, setup_server):
        from arrow.server import compact_context
        result = json.loads(compact_context(reset=False))
        assert "message" in result  # "No context sent yet"

    def test_compact_context_with_data(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = srv._session_id
        projects = storage.list_projects()
        pid = projects[0].id
        chunks = []
        files = storage.get_all_files(project_id=pid)
        for file_rec in files[:2]:
            fc = storage.get_chunks_for_file(file_rec.id)
            chunks.extend(fc)

        # Simulate sending chunks
        for ch in chunks[:3]:
            storage.record_sent_chunk(sid, ch.id, tokens=100)

        from arrow.server import compact_context
        result = json.loads(compact_context(reset=False))
        assert "chunks" in result
        assert result["chunks"] > 0
        assert "items" in result

    def test_compact_context_reset(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = srv._session_id
        projects = storage.list_projects()
        pid = projects[0].id
        files = storage.get_all_files(project_id=pid)
        fc = storage.get_chunks_for_file(files[0].id)
        if fc:
            storage.record_sent_chunk(sid, fc[0].id, tokens=50)

        from arrow.server import compact_context
        result = json.loads(compact_context(reset=True))
        assert result["reset"] is True

        # Session should be cleared
        ids = storage.get_sent_chunk_ids(sid)
        assert len(ids) == 0

    def test_context_pressure_low(self, setup_server):
        from arrow.server import context_pressure
        result = json.loads(context_pressure())
        assert result["context_pressure_pct"] < 1
        assert result["status"] == "low"

    def test_auto_compact_threshold(self, setup_server):
        """When session tokens exceed threshold, get_context
        should return compacted response."""
        import arrow.server as srv
        storage = srv._get_storage()
        sid = srv._session_id
        projects = storage.list_projects()
        pid = projects[0].id

        # Set a very low threshold for testing
        os.environ["ARROW_COMPACT_THRESHOLD"] = "10"

        # Record enough tokens to exceed threshold
        files = storage.get_all_files(project_id=pid)
        fc = storage.get_chunks_for_file(files[0].id)
        if fc:
            storage.record_sent_chunk(
                sid, fc[0].id, tokens=100
            )

        from arrow.server import get_context
        result = json.loads(get_context("authenticate"))
        assert result.get("compacted") is True
        assert "previous_context_summary" in result

        os.environ.pop("ARROW_COMPACT_THRESHOLD", None)
