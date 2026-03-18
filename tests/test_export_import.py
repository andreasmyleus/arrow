"""Tests for index export/import."""

import json


class TestExportImport:
    def test_export_produces_json(self, setup_server):
        from arrow.server import export_index
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        result = export_index(projects[0].name)
        data = json.loads(result)
        assert "version" in data
        assert "project" in data
        assert "files" in data
        assert "chunks" in data
        assert data["stats"]["files"] > 0

    def test_import_creates_project(self, setup_server):
        from arrow.server import export_index, import_index
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        name = projects[0].name

        # Export
        bundle = export_index(name)

        # Modify bundle to have a different project name
        data = json.loads(bundle)
        data["project"]["name"] = "imported/test"
        modified = json.dumps(data)

        # Import
        result = json.loads(import_index(modified))
        assert "error" not in result
        assert result["project_name"] == "imported/test"
        assert result["files"] > 0

    def test_export_nonexistent_project(self, setup_server):
        from arrow.server import export_index
        result = json.loads(export_index("nonexistent/project"))
        assert "error" in result
