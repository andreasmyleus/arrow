"""Tests for test mapping (get_tests_for)."""

import json


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
