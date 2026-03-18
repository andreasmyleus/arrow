"""Tests for query-aware token budgeting."""

import json


class TestQueryAwareBudget:
    def test_auto_budget_simple(self, setup_server):
        """Simple symbol lookup should get a small budget."""
        from arrow.server import get_context
        result = json.loads(get_context("add"))
        assert result["token_budget"] <= 3000

    def test_auto_budget_broad(self, setup_server):
        """Broad query should get a larger budget."""
        from arrow.server import get_context
        result = json.loads(get_context(
            "how does the authentication architecture work with middleware"
        ))
        assert result["token_budget"] >= 1500

    def test_explicit_budget_respected(self, setup_server):
        """Explicit budget should override auto."""
        from arrow.server import get_context
        result = json.loads(get_context("add", token_budget=500))
        assert result["token_budget"] == 500
        assert result["tokens_used"] <= 500

    def test_budget_estimation(self, setup_server):
        """Test the estimate_budget method directly."""
        import arrow.server as srv
        searcher = srv._get_searcher()
        budget = searcher.estimate_budget("add")
        assert budget >= 500
        assert budget <= 12000
