"""Tests for stale index detection."""

import json


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
