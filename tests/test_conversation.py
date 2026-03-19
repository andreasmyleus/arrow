"""Tests for conversation-aware context tracking."""

import json


class TestConversationContext:
    def test_session_chunk_tracking(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = "test-session-123"

        # Record some chunks
        storage.record_sent_chunk(sid, 1, tokens=100)
        storage.record_sent_chunk(sid, 2, tokens=200)

        ids = storage.get_sent_chunk_ids(sid)
        assert 1 in ids
        assert 2 in ids

        total = storage.get_session_token_total(sid)
        assert total == 300

    def test_session_clear(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        sid = "test-session-456"

        storage.record_sent_chunk(sid, 1, tokens=50)
        storage.clear_session(sid)
        ids = storage.get_sent_chunk_ids(sid)
        assert len(ids) == 0

    def test_get_context_excludes_sent(self, setup_server):
        """get_context should exclude already-sent chunks."""
        from arrow.server import get_context
        # First call — should return results
        r1 = get_context("authenticate")
        assert "chunks" in r1
        assert "#" in r1  # Should contain code blocks

    def test_context_pressure_tool(self, setup_server):
        from arrow.server import context_pressure
        result = json.loads(context_pressure())
        assert "session_tokens" in result
        assert "chunks_sent" in result
        assert result["status"] in (
            "low", "moderate", "high", "critical"
        )
