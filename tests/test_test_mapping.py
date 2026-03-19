"""Tests for test mapping (get_tests_for)."""


class TestGetTestsFor:
    def test_find_tests_by_name(self, setup_server):
        from arrow.server import get_tests_for
        result = get_tests_for("authenticate")
        assert "authenticate" in result
        assert "tests for:" in result

    def test_find_tests_by_reference(self, setup_server):
        from arrow.server import get_tests_for
        result = get_tests_for("authorize")
        assert "authorize" in result
        assert "found" in result

    def test_find_tests_with_source_file(self, setup_server):
        from arrow.server import get_tests_for
        result = get_tests_for(
            "authenticate", file="auth.py",
        )
        assert "source: auth.py" in result

    def test_no_tests_for_unknown_function(self, setup_server):
        from arrow.server import get_tests_for
        result = get_tests_for("zzz_nonexistent_function")
        assert "No tests found" in result

    def test_find_class_tests(self, setup_server):
        from arrow.server import get_tests_for
        result = get_tests_for("AuthHandler")
        # TestAuthHandler references AuthHandler
        assert "AuthHandler" in result
