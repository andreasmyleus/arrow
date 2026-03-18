"""Tests for storage layer methods."""


class TestStorageNewMethods:
    def test_count_fts_hits(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        count = storage.count_fts_hits("authenticate")
        assert count >= 0

    def test_get_test_files(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        test_files = storage.get_test_files()
        test_paths = [f.path for f in test_files]
        assert any("test_" in p for p in test_paths)

    def test_get_importers_of_file(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        importers = storage.get_importers_of_file("auth.py")
        # api.py and middleware.py import from auth
        importer_paths = [i["path"] for i in importers]
        assert len(importer_paths) > 0

    def test_resolve_symbol_across_repos(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        results = storage.resolve_symbol_across_repos("authenticate")
        assert len(results) > 0
        assert results[0]["name"] == "authenticate"
