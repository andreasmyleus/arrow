"""Tests for tool analytics."""

import json


class TestToolAnalytics:
    def test_record_and_retrieve(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        storage.record_tool_call("test_tool", 42.5)
        storage.record_tool_call("test_tool", 58.3)
        stats = storage.get_tool_analytics(
            since=0  # all time
        )
        tool_stat = next(
            (s for s in stats if s["tool_name"] == "test_tool"),
            None,
        )
        assert tool_stat is not None
        assert tool_stat["calls"] == 2
        assert tool_stat["avg_latency_ms"] is not None

    def test_analytics_tool(self, setup_server):
        from arrow.server import tool_analytics
        result = json.loads(tool_analytics(24))
        assert "total_calls" in result
        assert "tools" in result
        assert isinstance(result["tools"], list)
