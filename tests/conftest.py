"""Shared fixtures for Arrow test suite."""

import os
import tempfile

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
