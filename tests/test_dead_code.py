"""Tests for dead code detection."""

import json


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
