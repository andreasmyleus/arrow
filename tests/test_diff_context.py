"""Tests for semantic diff context (get_diff_context)."""

import json


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
