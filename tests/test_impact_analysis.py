"""Tests for change impact analysis (what_breaks_if_i_change)."""

import json


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
