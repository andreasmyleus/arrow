"""Tests for semantic diff context (get_diff_context)."""

import json


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
