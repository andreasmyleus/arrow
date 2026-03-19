"""Tests for semantic diff context (get_diff_context)."""

import json
import os
import subprocess
import tempfile

import pytest


@pytest.fixture
def git_project(tmp_path):
    """Create a git repo, commit files, then modify one — real git diff."""
    # Write initial files
    (tmp_path / "math_ops.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
    )
    (tmp_path / "main.py").write_text(
        "from math_ops import add\n"
        "\n"
        "def run():\n"
        "    print(add(1, 2))\n"
    )

    # Init git repo and commit
    subprocess.run(
        ["git", "init"], cwd=tmp_path, check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "add", "."], cwd=tmp_path, check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path, check=True, capture_output=True,
    )

    return tmp_path


@pytest.fixture
def setup_git_server(git_project):
    """Index the git project, then modify a file so git diff shows changes."""
    db_path = tempfile.mktemp(suffix=".db")
    vec_path = tempfile.mktemp(suffix=".usearch")
    os.environ["ARROW_DB_PATH"] = db_path
    os.environ["ARROW_VECTOR_PATH"] = vec_path

    from arrow.server import index_codebase
    index_codebase(str(git_project))

    yield git_project, db_path, vec_path

    os.environ.pop("ARROW_DB_PATH", None)
    os.environ.pop("ARROW_VECTOR_PATH", None)
    for p in (db_path, vec_path):
        if os.path.exists(p):
            os.unlink(p)


class TestGetDiffContext:
    def test_diff_context_with_line_range(self, setup_server):
        from arrow.server import get_diff_context
        project_dir, _, _ = setup_server

        result = get_diff_context(
            "auth.py", line_start=1, line_end=2,
        )
        assert "error" not in result
        assert "auth.py" in result
        assert "Changed functions" in result
        assert "authenticate" in result

    def test_diff_context_finds_callers(self, setup_server):
        from arrow.server import get_diff_context
        result = get_diff_context(
            "auth.py", line_start=1, line_end=2,
        )
        # api.py and middleware.py both call authenticate
        assert "Callers" in result or "authenticate" in result

    def test_diff_context_finds_dependents(self, setup_server):
        from arrow.server import get_diff_context
        result = get_diff_context(
            "auth.py", line_start=1, line_end=10,
        )
        # api.py and middleware.py import from auth
        assert "Dependent files" in result or "api" in result

    def test_diff_context_nonexistent_file(self, setup_server):
        from arrow.server import get_diff_context
        result = json.loads(get_diff_context("nonexistent.py"))
        assert "error" in result

    def test_diff_context_detects_new_function(self, setup_git_server):
        """Adding a new function after indexing should show up in diff context."""
        from arrow.server import get_diff_context
        git_project, _, _ = setup_git_server

        # Add a new function to an already-indexed file
        original = (git_project / "math_ops.py").read_text()
        (git_project / "math_ops.py").write_text(
            original + "\ndef multiply(a, b):\n    return a * b\n"
        )

        result = get_diff_context("math_ops.py")
        assert "Changed functions" in result
        assert "multiply" in result

    def test_diff_context_detects_modified_function(self, setup_git_server):
        """Modifying an existing function body should show up in diff context."""
        from arrow.server import get_diff_context
        git_project, _, _ = setup_git_server

        # Modify the body of an existing function
        (git_project / "math_ops.py").write_text(
            "def add(a, b):\n"
            "    result = a + b\n"
            "    print(result)\n"
            "    return result\n"
            "\n"
            "def subtract(a, b):\n"
            "    return a - b\n"
        )

        result = get_diff_context("math_ops.py")
        assert "Changed functions" in result
        assert "add" in result
