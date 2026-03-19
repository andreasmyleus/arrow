"""Integration test: long chain of tool calls simulating a real agent session.

Scenario: An agent is asked to add a caching layer to an existing project.
It uses Arrow tools throughout — search, edit, verify, repeat — just like
a real Claude Code session would.

This is a single test function so that file edits persist across steps
(each step builds on the previous one's side effects).
"""

import json
import os
import subprocess
import tempfile

import pytest


@pytest.fixture
def agent_project(tmp_path):
    """Create a realistic multi-file project with a git repo."""
    # --- Core modules ---
    (tmp_path / "models.py").write_text(
        "class User:\n"
        "    def __init__(self, id, name, email):\n"
        "        self.id = id\n"
        "        self.name = name\n"
        "        self.email = email\n"
        "\n"
        "class Product:\n"
        "    def __init__(self, id, title, price):\n"
        "        self.id = id\n"
        "        self.title = title\n"
        "        self.price = price\n"
    )
    (tmp_path / "database.py").write_text(
        "from models import User, Product\n"
        "\n"
        "def get_user(user_id):\n"
        "    return User(user_id, 'alice', 'alice@example.com')\n"
        "\n"
        "def get_product(product_id):\n"
        "    return Product(product_id, 'Widget', 9.99)\n"
        "\n"
        "def list_products():\n"
        "    return [get_product(i) for i in range(10)]\n"
    )
    (tmp_path / "api.py").write_text(
        "from database import get_user, get_product, list_products\n"
        "\n"
        "def user_endpoint(user_id):\n"
        "    user = get_user(user_id)\n"
        "    return {'id': user.id, 'name': user.name}\n"
        "\n"
        "def product_endpoint(product_id):\n"
        "    product = get_product(product_id)\n"
        "    return {'id': product.id, 'title': product.title}\n"
        "\n"
        "def catalog_endpoint():\n"
        "    products = list_products()\n"
        "    return [{'id': p.id, 'title': p.title} for p in products]\n"
    )
    (tmp_path / "config.py").write_text(
        "DATABASE_URL = 'sqlite:///app.db'\n"
        "CACHE_TTL = 300\n"
        "DEBUG = True\n"
    )

    # --- Tests ---
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_database.py").write_text(
        "from database import get_user, get_product, list_products\n"
        "\n"
        "def test_get_user():\n"
        "    user = get_user(1)\n"
        "    assert user.name == 'alice'\n"
        "\n"
        "def test_get_product():\n"
        "    product = get_product(1)\n"
        "    assert product.title == 'Widget'\n"
        "\n"
        "def test_list_products():\n"
        "    products = list_products()\n"
        "    assert len(products) == 10\n"
    )
    (tests / "test_api.py").write_text(
        "from api import user_endpoint, product_endpoint, catalog_endpoint\n"
        "\n"
        "def test_user_endpoint():\n"
        "    result = user_endpoint(1)\n"
        "    assert result['name'] == 'alice'\n"
        "\n"
        "def test_product_endpoint():\n"
        "    result = product_endpoint(1)\n"
        "    assert result['title'] == 'Widget'\n"
        "\n"
        "def test_catalog_endpoint():\n"
        "    result = catalog_endpoint()\n"
        "    assert len(result) == 10\n"
    )

    # --- Git init + commit ---
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path, check=True, capture_output=True,
    )

    return tmp_path


@pytest.fixture
def agent_session(agent_project):
    """Index the project and yield an active session."""
    db_path = tempfile.mktemp(suffix=".db")
    vec_path = tempfile.mktemp(suffix=".usearch")
    os.environ["ARROW_DB_PATH"] = db_path
    os.environ["ARROW_VECTOR_PATH"] = vec_path

    from arrow.server import index_codebase
    index_codebase(str(agent_project))

    yield agent_project

    os.environ.pop("ARROW_DB_PATH", None)
    os.environ.pop("ARROW_VECTOR_PATH", None)
    for p in (db_path, vec_path):
        if os.path.exists(p):
            os.unlink(p)


# ─────────────────────────────────────────────────────────────────────────────
#  Main integration test — full agent session
# ─────────────────────────────────────────────────────────────────────────────

def test_full_agent_session(agent_session):  # noqa: C901, PLR0915
    """Simulate a complete agent session adding a caching layer.

    Touches every public MCP tool at least once, plus error paths
    and edge cases. All in one function so file edits accumulate.
    """
    project = agent_session

    from arrow.server import (
        context_pressure,
        detect_stale_index,
        export_index,
        file_summary,
        find_dead_code,
        get_context,
        get_diff_context,
        get_tests_for,
        import_index,
        index_codebase,
        index_github_content,
        list_projects,
        project_summary,
        remove_project,
        resolve_symbol,
        search_code,
        search_regex,
        search_structure,
        store_memory,
        recall_memory,
        list_memories,
        delete_memory,
        tool_analytics,
        trace_dependencies,
        what_breaks_if_i_change,
    )

    # ── 1: project_summary — orient ──────────────────────────────────
    result = json.loads(project_summary())
    assert result["total_files"] >= 6
    assert "python" in result["languages"]
    assert "structure" in result

    # ── 2: list_projects ─────────────────────────────────────────────
    projects = json.loads(list_projects())
    assert isinstance(projects, list)
    assert len(projects) >= 1
    project_name = projects[0]["name"]
    assert projects[0]["files"] >= 6
    assert "git_branch" in projects[0]

    # ── 3: project_summary scoped to project ─────────────────────────
    result = json.loads(project_summary(project=project_name))
    assert result["total_files"] >= 6

    # ── 4: search_code — basic query ─────────────────────────────────
    result = search_code("get_user get_product database")
    assert "Found" in result
    assert "database.py" in result
    assert "get_user" in result

    # ── 5: search_code — with limit ──────────────────────────────────
    result = search_code("def", limit=3)
    assert "Found" in result

    # ── 6: search_code — no results ──────────────────────────────────
    result = search_code("zzz_completely_nonexistent_symbol")
    assert "Found 0 results" in result

    # ── 7: search_code — scoped to project ───────────────────────────
    result = search_code("get_user", project=project_name)
    assert "get_user" in result

    # ── 8: search_structure — function ───────────────────────────────
    result = json.loads(search_structure("get_user"))
    names = [r["name"] for r in result]
    assert "get_user" in names

    # ── 9: search_structure — class by kind ──────────────────────────
    result = json.loads(search_structure("Product", kind="class"))
    assert any(r["name"] == "Product" for r in result)

    # ── 10: search_structure — no results ────────────────────────────
    result = json.loads(search_structure("zzz_nope"))
    assert result == []

    # ── 11: get_context — semantic retrieval ─────────────────────────
    result = get_context("database user product query", token_budget=2000)
    assert "budget: 2000t" in result
    assert "used:" in result

    # ── 12: get_context — scoped to project ──────────────────────────
    result = get_context(
        "get_user database product", token_budget=1000, project=project_name,
    )
    assert "budget: 1000t" in result or "No results" in result

    # ── 13: trace_dependencies on database.py ────────────────────────
    result = json.loads(trace_dependencies("database.py"))
    assert "imports" in result
    assert "imported_by" in result
    assert result["language"] == "python"
    assert result["depth"] == 2
    # api.py and tests import from database
    assert any("api" in p for p in result["imported_by"])

    # ── 14: trace_dependencies — depth=1 ─────────────────────────────
    result = json.loads(trace_dependencies("database.py", depth=1))
    assert result["depth"] == 1
    assert "transitive_importers" not in result or result.get("transitive_importers") == {}

    # ── 15: trace_dependencies — nonexistent file error ──────────────
    result = json.loads(trace_dependencies("nonexistent.py"))
    assert "error" in result

    # ── 16: trace_dependencies — empty string error ──────────────────
    result = json.loads(trace_dependencies(""))
    assert "error" in result

    # ── 17: what_breaks_if_i_change — with function ──────────────────
    result = json.loads(what_breaks_if_i_change("database.py", "get_user"))
    assert "callers" in result
    assert "risk" in result
    assert "affected_tests" in result
    assert "summary" in result
    caller_files = [c["file"] for c in result["callers"]]
    assert any("api" in f for f in caller_files)
    # Should find tests
    assert result["summary"]["total_tests"] > 0

    # ── 18: what_breaks_if_i_change — whole file (no function) ───────
    result = json.loads(what_breaks_if_i_change("database.py"))
    assert len(result["symbols_analyzed"]) >= 3  # get_user, get_product, list_products
    assert result["summary"]["total_callers"] > 0

    # ── 19: what_breaks_if_i_change — nonexistent file error ─────────
    result = json.loads(what_breaks_if_i_change("nonexistent.py"))
    assert "error" in result

    # ── 20: get_tests_for — by function name ─────────────────────────
    result = get_tests_for("get_user")
    assert "tests for:" in result or "test_get_user" in result
    assert "test_database" in result

    # ── 21: get_tests_for — with file param ──────────────────────────
    result = get_tests_for("get_user", file="database.py")
    assert "test_database" in result

    # ── 22: get_tests_for — no results ───────────────────────────────
    result = get_tests_for("zzz_nonexistent_func")
    assert "No tests found" in result

    # ── 23: get_tests_for — empty string error ───────────────────────
    result = json.loads(get_tests_for(""))
    assert "error" in result

    # ── 24: file_summary on database.py ──────────────────────────────
    result = json.loads(file_summary("database.py"))
    assert result["language"] == "python"
    func_names = [f["name"] for f in result["functions"]]
    assert "get_user" in func_names
    assert "get_product" in func_names
    assert "list_products" in func_names
    assert result["total_chunks"] > 0

    # ── 25: file_summary — nonexistent file error ────────────────────
    result = json.loads(file_summary("nonexistent.py"))
    assert "error" in result

    # ── 26: detect_stale_index — should be fresh ─────────────────────
    result = json.loads(detect_stale_index())
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["drift_pct"] == 0
    assert result[0]["recommendation"] == "index is fresh"
    assert result[0]["total_files"] >= 6

    # ── 27: detect_stale_index — scoped to project ───────────────────
    result = json.loads(detect_stale_index(project=project_name))
    assert isinstance(result, list)

    # ── 28: resolve_symbol — User class ──────────────────────────────
    result = resolve_symbol("User")
    assert "User" in result
    assert "models" in result
    assert "class" in result

    # ── 29: resolve_symbol — nonexistent ─────────────────────────────
    result = resolve_symbol("ZzzNonexistentSymbol")
    assert "No definitions found" in result

    # ── 30: resolve_symbol — empty string error ──────────────────────
    result = json.loads(resolve_symbol(""))
    assert "error" in result

    # ── 31: search_regex — positive match ────────────────────────────
    result = search_regex(r"def get_\w+")
    assert "matches" in result
    assert "get_user" in result

    # ── 32: search_regex — no matches ────────────────────────────────
    result = search_regex(r"zzz_never_matches_anything")
    assert "0 matches" in result

    # ── 33: search_regex — invalid regex error ───────────────────────
    result = json.loads(search_regex(r"[invalid"))
    assert "error" in result

    # ── 34: search_regex — empty pattern error ───────────────────────
    result = json.loads(search_regex(""))
    assert "error" in result

    # ── 35: search_regex — with limit ────────────────────────────────
    result = search_regex(r"def \w+", limit=2)
    assert "matches" in result

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 2: Agent creates new files (cache layer) and verifies
    # ═══════════════════════════════════════════════════════════════════

    # ── 36: Create cache.py — new file ───────────────────────────────
    (project / "cache.py").write_text(
        "from config import CACHE_TTL\n"
        "\n"
        "_store = {}\n"
        "\n"
        "def cache_get(key):\n"
        "    entry = _store.get(key)\n"
        "    if entry is None:\n"
        "        return None\n"
        "    return entry['value']\n"
        "\n"
        "def cache_set(key, value):\n"
        "    _store[key] = {'value': value, 'ttl': CACHE_TTL}\n"
        "\n"
        "def cache_clear():\n"
        "    _store.clear()\n"
    )

    # Auto-reindex picks up new file on next tool call
    result = search_code("cache_get cache_set")
    assert "cache.py" in result
    assert "cache_get" in result

    # ── 37: search_structure confirms new symbols ────────────────────
    result = json.loads(search_structure("cache_get"))
    names = [r["name"] for r in result]
    assert "cache_get" in names

    # ── 38: file_summary on the new file ─────────────────────────────
    result = json.loads(file_summary("cache.py"))
    assert result["language"] == "python"
    func_names = [f["name"] for f in result["functions"]]
    assert "cache_get" in func_names
    assert "cache_set" in func_names
    assert "cache_clear" in func_names

    # ── 39: Modify database.py to use cache ──────────────────────────
    (project / "database.py").write_text(
        "from models import User, Product\n"
        "from cache import cache_get, cache_set\n"
        "\n"
        "def get_user(user_id):\n"
        "    key = f'user:{user_id}'\n"
        "    cached = cache_get(key)\n"
        "    if cached:\n"
        "        return cached\n"
        "    user = User(user_id, 'alice', 'alice@example.com')\n"
        "    cache_set(key, user)\n"
        "    return user\n"
        "\n"
        "def get_product(product_id):\n"
        "    key = f'product:{product_id}'\n"
        "    cached = cache_get(key)\n"
        "    if cached:\n"
        "        return cached\n"
        "    product = Product(product_id, 'Widget', 9.99)\n"
        "    cache_set(key, product)\n"
        "    return product\n"
        "\n"
        "def list_products():\n"
        "    return [get_product(i) for i in range(10)]\n"
    )

    # Auto-reindex picks up the edit
    result = search_code("cache_get database from cache import")
    assert "database.py" in result

    # ── 40: get_diff_context sees database.py changes ────────────────
    result = get_diff_context("database.py")
    assert "Changed functions" in result
    assert "get_user" in result or "get_product" in result

    # ── 41: get_diff_context with explicit line range ────────────────
    result = get_diff_context("database.py", line_start=1, line_end=5)
    assert "database.py" in result

    # ── 42: get_diff_context — nonexistent file error ────────────────
    result = json.loads(get_diff_context("nonexistent.py"))
    assert "error" in result

    # ── 43: trace_dependencies — database.py now imports cache ───────
    result = json.loads(trace_dependencies("database.py"))
    imports = result["imports"]
    assert any("cache" in m for m in imports)

    # ── 44: Add test_cache.py ────────────────────────────────────────
    (project / "tests" / "test_cache.py").write_text(
        "from cache import cache_get, cache_set, cache_clear\n"
        "\n"
        "def test_cache_miss():\n"
        "    cache_clear()\n"
        "    assert cache_get('nonexistent') is None\n"
        "\n"
        "def test_cache_hit():\n"
        "    cache_clear()\n"
        "    cache_set('key', 42)\n"
        "    assert cache_get('key') == 42\n"
        "\n"
        "def test_cache_clear():\n"
        "    cache_set('key', 'value')\n"
        "    cache_clear()\n"
        "    assert cache_get('key') is None\n"
    )

    result = search_code("test_cache_miss test_cache_hit")
    assert "test_cache.py" in result

    # ── 45: get_tests_for cache_get (finds test_cache.py) ────────────
    result = get_tests_for("cache_get")
    assert "test_cache" in result
    assert "cache_get" in result

    # ── 46: Add service.py ───────────────────────────────────────────
    (project / "service.py").write_text(
        "from database import get_user, get_product\n"
        "from cache import cache_clear\n"
        "\n"
        "def get_user_profile(user_id):\n"
        "    user = get_user(user_id)\n"
        "    return {'name': user.name, 'email': user.email}\n"
        "\n"
        "def refresh_product_cache():\n"
        "    cache_clear()\n"
        "    return 'cache cleared'\n"
    )

    result = search_code("get_user_profile refresh_product_cache")
    assert "service.py" in result

    # ── 47: what_breaks_if_i_change cache.py ─────────────────────────
    result = json.loads(what_breaks_if_i_change("cache.py", "cache_get"))
    result_str = json.dumps(result)
    assert "database" in result_str or "cache_get" in result_str

    # ── 48: Full dependency chain api -> db -> cache -> config ───────
    api_deps = json.loads(trace_dependencies("api.py"))
    assert any("database" in m for m in api_deps["imports"])

    db_deps = json.loads(trace_dependencies("database.py"))
    assert any("cache" in m for m in db_deps["imports"])

    cache_deps = json.loads(trace_dependencies("cache.py"))
    assert any("config" in m for m in cache_deps["imports"])

    # ── 49: project_summary shows growth ─────────────────────────────
    result = json.loads(project_summary())
    assert result["total_files"] >= 9

    # ── 50: get_diff_context on new untracked service.py ─────────────
    result = get_diff_context("service.py")
    assert "get_user_profile" in result or "service.py" in result

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 3: Memory system
    # ═══════════════════════════════════════════════════════════════════

    # ── 51: store_memory ─────────────────────────────────────────────
    mem1 = json.loads(store_memory(
        "caching_architecture",
        "Added in-memory cache layer between API and database. "
        "cache.py provides cache_get/cache_set/cache_clear. "
        "database.py wraps all queries with cache lookups.",
        category="architecture",
    ))
    assert "id" in mem1
    mem1_id = mem1["id"]

    # ── 52: store_memory — second memory, different category ─────────
    mem2 = json.loads(store_memory(
        "db_conventions",
        "All database functions should check cache before querying.",
        category="convention",
    ))
    assert "id" in mem2
    mem2_id = mem2["id"]

    # ── 53: store_memory — update existing key ───────────────────────
    mem1_updated = json.loads(store_memory(
        "caching_architecture",
        "UPDATED: In-memory cache with TTL from config.py. "
        "Three functions: cache_get, cache_set, cache_clear.",
        category="architecture",
    ))
    assert "id" in mem1_updated

    # ── 54: recall_memory — search ───────────────────────────────────
    recalled = json.loads(recall_memory("cache layer architecture"))
    assert recalled["total"] >= 1
    assert "cache" in recalled["memories"][0]["content"].lower()

    # ── 55: recall_memory — with category filter ─────────────────────
    recalled = json.loads(recall_memory("database", category="convention"))
    assert recalled["total"] >= 1

    # ── 56: recall_memory — empty string error ───────────────────────
    recalled = json.loads(recall_memory(""))
    assert "error" in recalled

    # ── 57: list_memories — all ──────────────────────────────────────
    memories = json.loads(list_memories())
    assert memories["total"] >= 2

    # ── 58: list_memories — filtered by category ─────────────────────
    memories = json.loads(list_memories(category="architecture"))
    assert memories["total"] >= 1
    assert all(m["category"] == "architecture" for m in memories["memories"])

    # ── 59: delete_memory — by id ────────────────────────────────────
    delete_result = json.loads(delete_memory(memory_id=mem2_id))
    assert delete_result["deleted"] >= 1

    # ── 60: delete_memory — by key ───────────────────────────────────
    delete_result = json.loads(delete_memory(key="caching_architecture"))
    assert delete_result["deleted"] >= 1

    # ── 61: delete_memory — no args error ────────────────────────────
    delete_result = json.loads(delete_memory())
    assert "error" in delete_result

    # ── 62: list_memories — should be empty now ──────────────────────
    memories = json.loads(list_memories())
    assert memories["total"] == 0

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 4: Analytics and observability
    # ═══════════════════════════════════════════════════════════════════

    # ── 63: find_dead_code ───────────────────────────────────────────
    result = json.loads(find_dead_code())
    assert "dead_code" in result
    assert isinstance(result["dead_code"], list)
    assert "total" in result

    # ── 64: find_dead_code — scoped to project ───────────────────────
    result = json.loads(find_dead_code(project=project_name))
    assert "dead_code" in result

    # ── 65: context_pressure ─────────────────────────────────────────
    result = json.loads(context_pressure())
    assert "chunks_sent" in result
    assert "session_tokens" in result
    assert "session_id" in result
    assert result["status"] in ("low", "moderate", "high", "critical")

    # ── 66: tool_analytics ───────────────────────────────────────────
    result = json.loads(tool_analytics())
    assert "tools" in result
    assert "total_calls" in result
    assert "window_hours" in result
    assert result["total_calls"] > 0

    # ── 67: tool_analytics — custom window ───────────────────────────
    result = json.loads(tool_analytics(hours=1))
    assert result["window_hours"] == 1

    # ── 68: tool_analytics — error on hours < 1 ─────────────────────
    result = json.loads(tool_analytics(hours=0))
    assert "error" in result

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 5: index_codebase force re-index
    # ═══════════════════════════════════════════════════════════════════

    # ── 69: index_codebase — force re-index ──────────────────────────
    result = json.loads(index_codebase(str(project), force=True))
    assert "project_id" in result
    assert "files_indexed" in result or "files_skipped" in result
    assert result.get("files_indexed", 0) > 0

    # ── 70: index_codebase — invalid path error ──────────────────────
    result = json.loads(index_codebase("/nonexistent/path"))
    assert "error" in result

    # ── 71: index_codebase — empty string error ──────────────────────
    result = json.loads(index_codebase(""))
    assert "error" in result

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 6: index_github_content (remote repo simulation)
    # ═══════════════════════════════════════════════════════════════════

    # ── 72: index_github_content — index remote files ────────────────
    result = json.loads(index_github_content(
        owner="testorg",
        repo="testrepo",
        branch="main",
        files=[
            {"path": "lib/utils.py", "content": (
                "def slugify(text):\n"
                "    return text.lower().replace(' ', '-')\n"
                "\n"
                "def truncate(text, length=100):\n"
                "    return text[:length]\n"
            )},
            {"path": "lib/validators.py", "content": (
                "import re\n"
                "\n"
                "def is_email(text):\n"
                "    return bool(re.match(r'.+@.+\\..+', text))\n"
            )},
        ],
    ))
    assert result["files_indexed"] == 2
    assert result["project_name"] == "testorg/testrepo"

    # ── 73: search_code across local + remote projects ───────────────
    result = search_code("slugify truncate")
    assert "slugify" in result

    # ── 74: search_code scoped to remote project ─────────────────────
    result = search_code("slugify", project="testorg/testrepo")
    assert "slugify" in result

    # ── 75: resolve_symbol finds remote definition ───────────────────
    result = resolve_symbol("slugify")
    assert "slugify" in result
    assert "testorg/testrepo" in result

    # ── 76: file_summary on remote file ──────────────────────────────
    result = json.loads(file_summary("lib/utils.py", project="testorg/testrepo"))
    assert result["language"] == "python"
    func_names = [f["name"] for f in result["functions"]]
    assert "slugify" in func_names

    # ── 77: list_projects shows both local and remote ────────────────
    projects = json.loads(list_projects())
    names = [p["name"] for p in projects]
    assert project_name in names
    assert "testorg/testrepo" in names

    # ── 78: index_github_content — empty owner error ─────────────────
    result = json.loads(index_github_content(
        owner="", repo="r", branch="main", files=[{"path": "a.py", "content": "x"}],
    ))
    assert "error" in result

    # ── 79: index_github_content — empty files error ─────────────────
    result = json.loads(index_github_content(
        owner="o", repo="r", branch="main", files=[],
    ))
    assert "error" in result

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 7: index_git_commit (snapshot indexing)
    # ═══════════════════════════════════════════════════════════════════

    # ── 80: index_git_commit — index HEAD ────────────────────────────
    from arrow.server import index_git_commit
    result = json.loads(index_git_commit(str(project), "HEAD"))
    # Should create a snapshot project
    assert "error" not in result

    # ── 81: index_git_commit — invalid path error ────────────────────
    result = json.loads(index_git_commit("", "HEAD"))
    assert "error" in result

    # ── 82: index_git_commit — invalid ref error ─────────────────────
    result = json.loads(index_git_commit(str(project), ""))
    assert "error" in result

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 8: Export/import round-trip
    # ═══════════════════════════════════════════════════════════════════

    # ── 83: export_index ─────────────────────────────────────────────
    bundle_str = export_index(project_name)
    bundle = json.loads(bundle_str)
    assert bundle["version"] == 1
    assert bundle["stats"]["files"] >= 9
    assert bundle["stats"]["chunks"] > 0
    assert bundle["stats"]["symbols"] > 0
    assert bundle["stats"]["imports"] > 0
    assert bundle["project"]["name"] == project_name

    # ── 84: export_index — nonexistent project error ─────────────────
    result = json.loads(export_index("nonexistent/project"))
    assert "error" in result

    # ── 85: export_index — empty string error ────────────────────────
    result = json.loads(export_index(""))
    assert "error" in result

    # ── 86: remove_project ───────────────────────────────────────────
    remove_result = json.loads(remove_project(project_name))
    assert "removed" in remove_result

    # ── 87: remove_project — verify gone ─────────────────────────────
    projects = json.loads(list_projects())
    assert all(p["name"] != project_name for p in projects)

    # ── 88: remove_project — nonexistent error ───────────────────────
    result = json.loads(remove_project("nonexistent/project"))
    assert "error" in result

    # ── 89: remove_project — empty string error ──────────────────────
    result = json.loads(remove_project(""))
    assert "error" in result

    # ── 90: import_index ─────────────────────────────────────────────
    import_result = json.loads(import_index(bundle_str))
    assert import_result["status"] == "imported"
    assert import_result["files"] >= 9
    assert import_result["chunks"] > 0
    assert import_result["symbols"] > 0

    # ── 91: import_index — invalid JSON error ────────────────────────
    result = json.loads(import_index("not json"))
    assert "error" in result

    # ── 92: import_index — duplicate project error ───────────────────
    result = json.loads(import_index(bundle_str))
    assert "error" in result
    assert "already exists" in result["error"]

    # ── 93: Search still works after reimport ────────────────────────
    result = search_code("cache_get database")
    assert "cache" in result

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 9: Remove remote project and verify isolation
    # ═══════════════════════════════════════════════════════════════════

    # ── 94: remove remote project ────────────────────────────────────
    result = json.loads(remove_project("testorg/testrepo"))
    assert "removed" in result

    # ── 95: search scoped to removed project returns no results ──────
    result = search_code("slugify", project="testorg/testrepo")
    # Should either return 0 results or an error
    assert "Found 0 results" in result or "error" in result.lower()

    # ═══════════════════════════════════════════════════════════════════
    #  Phase 10: Final validation
    # ═══════════════════════════════════════════════════════════════════

    # ── 96: All new symbols still searchable ─────────────────────────
    for symbol in ("cache_get", "cache_set", "cache_clear",
                   "get_user_profile", "refresh_product_cache"):
        structs = json.loads(search_structure(symbol))
        names = [s["name"] for s in structs]
        assert symbol in names, f"{symbol} not found in structure index"

    # ── 97: get_context still returns relevant chunks ────────────────
    result = get_context("caching database", token_budget=4000)
    assert "cache" in result.lower()

    # ── 98: detect_stale_index after all modifications ───────────────
    result = json.loads(detect_stale_index())
    assert isinstance(result, list)
