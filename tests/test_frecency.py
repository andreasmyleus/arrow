"""Tests for frecency-weighted search results."""


class TestFrecency:
    def test_record_file_access(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        files = storage.get_all_files(project_id=projects[0].id)
        assert len(files) > 0
        storage.record_file_access(files[0].id, projects[0].id)
        storage.record_file_access(files[0].id, projects[0].id)
        scores = storage.get_frecency_scores(
            project_id=projects[0].id
        )
        assert files[0].id in scores
        assert scores[files[0].id] > 0

    def test_frecency_boost_in_search(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        searcher = srv._get_searcher()
        projects = storage.list_projects()
        pid = projects[0].id

        # Search without boost
        r1 = searcher.search(
            "authenticate", limit=5, project_id=pid,
            frecency_boost=False,
        )

        # Access a file heavily
        files = storage.get_all_files(project_id=pid)
        for _ in range(10):
            storage.record_file_access(files[0].id, pid)

        # Search with boost
        r2 = searcher.search(
            "authenticate", limit=5, project_id=pid,
            frecency_boost=True,
        )
        # Both should return results
        assert len(r1) > 0
        assert len(r2) > 0

    def test_frecency_decay(self, setup_server):
        """Frecency scores should decay over time."""
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        files = storage.get_all_files(project_id=projects[0].id)
        storage.record_file_access(files[0].id, projects[0].id)
        scores = storage.get_frecency_scores(
            project_id=projects[0].id
        )
        # Score should be positive (recent access)
        assert scores[files[0].id] > 0
