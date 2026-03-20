"""Tests for relevance-first retrieval with token ceiling."""

import json


class TestQueryAwareBudget:
    def test_auto_budget_simple(self, setup_server):
        """Simple symbol lookup should use auto ceiling."""
        from arrow.server import get_context
        result = get_context("authenticate")
        assert "budget:" in result
        assert "used:" in result
        assert "(auto)" in result

    def test_auto_budget_broad(self, setup_server):
        """Broad query should use auto ceiling."""
        from arrow.server import get_context
        result = get_context(
            "how does the authentication architecture work with middleware"
        )
        assert "budget:" in result
        assert "(auto)" in result

    def test_explicit_budget_respected(self, setup_server):
        """Explicit budget should override auto."""
        from arrow.server import get_context
        result = get_context("authenticate", token_budget=500)
        assert "budget: 500t (manual)" in result

    def test_budget_is_ceiling_not_target(self, setup_server):
        """Token budget should be a ceiling — tokens_used should be well under it."""
        import arrow.server as srv
        searcher = srv._get_searcher()
        # Give a massive budget; relevance filtering should stop well before it
        context = searcher.get_context("authenticate", token_budget=50000)
        chunks = context.get("chunks", [])
        if chunks:
            # With relevance-first, we should use far less than the budget
            assert context["tokens_used"] < 50000
            # And we should NOT have consumed even half of a 50k budget
            # (relevance cutoff should kick in long before that)
            assert context["tokens_used"] < 25000

    def test_budget_estimation_returns_ceiling(self, setup_server):
        """estimate_budget returns a generous ceiling, not a tight budget."""
        import arrow.server as srv
        searcher = srv._get_searcher()
        budget, limit, classification = searcher.estimate_budget("add")
        # Ceiling should be generous (relevance filter does the real work)
        assert budget >= 1000
        assert budget <= 8000

    def test_budget_estimation_targeted_vs_broad(self, setup_server):
        """Broad queries should get a higher ceiling than targeted ones."""
        import arrow.server as srv
        searcher = srv._get_searcher()
        targeted_budget, _, _ = searcher.estimate_budget("authenticate")
        broad_budget, _, _ = searcher.estimate_budget(
            "how does the authentication architecture work with middleware and api"
        )
        assert broad_budget >= targeted_budget

    def test_auto_budget_not_unlimited(self, setup_server):
        """Auto budget should never produce unlimited (999999) tokens."""
        from arrow.server import get_context
        result = get_context("authenticate")
        assert "unlimited" not in result
        assert "999999" not in result

    def test_relevance_cutoff_stops_low_scoring_chunks(self, setup_server):
        """get_context should not include chunks with very low relevance."""
        import arrow.server as srv
        searcher = srv._get_searcher()
        # Use a generous budget but verify relevance cutoff kicks in
        context = searcher.get_context("authenticate", token_budget=50000)
        # Relevance filtering should limit results (or return all if all relevant)
        assert context["chunks_returned"] <= context["chunks_searched"]
        # Budget should not be fully consumed — relevance stops before budget does
        assert context["tokens_used"] < 50000

    def test_no_truncation(self, setup_server):
        """Relevance-first approach should never truncate chunks."""
        import arrow.server as srv
        searcher = srv._get_searcher()
        context = searcher.get_context("authenticate", token_budget=50000)
        for chunk in context.get("chunks", []):
            assert chunk["truncated"] is False
