"""Tests for context window compaction."""

import json
import os


class TestContextCompaction:
    def test_compact_context_empty_session(self, setup_server):
        from arrow.server import compact_context
        result = json.loads(compact_context(reset=False))
        assert "message" in result  # "No context sent yet"

    def test_compact_context_with_data(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = srv._session_id
        projects = storage.list_projects()
        pid = projects[0].id
        chunks = []
        files = storage.get_all_files(project_id=pid)
        for file_rec in files[:2]:
            fc = storage.get_chunks_for_file(file_rec.id)
            chunks.extend(fc)

        # Simulate sending chunks
        for ch in chunks[:3]:
            storage.record_sent_chunk(sid, ch.id, tokens=100)

        from arrow.server import compact_context
        result = json.loads(compact_context(reset=False))
        assert "chunks" in result
        assert result["chunks"] > 0
        assert "items" in result

    def test_compact_context_reset(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = srv._session_id
        projects = storage.list_projects()
        pid = projects[0].id
        files = storage.get_all_files(project_id=pid)
        fc = storage.get_chunks_for_file(files[0].id)
        if fc:
            storage.record_sent_chunk(sid, fc[0].id, tokens=50)

        from arrow.server import compact_context
        result = json.loads(compact_context(reset=True))
        assert result["reset"] is True

        # Session should be cleared
        ids = storage.get_sent_chunk_ids(sid)
        assert len(ids) == 0

    def test_context_pressure_low(self, setup_server):
        from arrow.server import context_pressure
        result = json.loads(context_pressure())
        assert result["context_pressure_pct"] < 1
        assert result["status"] == "low"

    def test_auto_compact_threshold(self, setup_server):
        """When session tokens exceed threshold, get_context
        should return compacted response."""
        import arrow.server as srv
        storage = srv._get_storage()
        sid = srv._session_id
        projects = storage.list_projects()
        pid = projects[0].id

        # Set a very low threshold for testing
        os.environ["ARROW_COMPACT_THRESHOLD"] = "10"

        # Record enough tokens to exceed threshold
        files = storage.get_all_files(project_id=pid)
        fc = storage.get_chunks_for_file(files[0].id)
        if fc:
            storage.record_sent_chunk(
                sid, fc[0].id, tokens=100
            )

        from arrow.server import get_context
        result = json.loads(get_context("authenticate"))
        assert result.get("compacted") is True
        assert "previous_context_summary" in result

        os.environ.pop("ARROW_COMPACT_THRESHOLD", None)
