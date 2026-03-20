"""Tests for search precision filtering."""

import os
import tempfile

import pytest

from arrow.search import (
    HybridSearcher,
    SearchResult,
    filter_by_relevance,
    reciprocal_rank_fusion,
)
from arrow.indexer import Indexer
from arrow.storage import Storage


@pytest.fixture
def db():
    path = tempfile.mktemp(suffix=".db")
    storage = Storage(path)
    yield storage
    storage.close()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_dir(tmp_path):
    """Create a project with clearly relevant and irrelevant files."""
    # Relevant: a search module
    (tmp_path / "search.py").write_text(
        "def search(query):\n"
        "    '''Search for items matching query.'''\n"
        "    return find_matches(query)\n"
        "\n"
        "def find_matches(query):\n"
        "    return [item for item in items if query in item]\n"
    )
    # Somewhat relevant: uses search
    (tmp_path / "api.py").write_text(
        "from search import search\n"
        "\n"
        "def handle_search_request(request):\n"
        "    query = request.get('q')\n"
        "    return search(query)\n"
    )
    # Irrelevant to search: a math module
    (tmp_path / "math_utils.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
        "\n"
        "def divide(a, b):\n"
        "    if b == 0:\n"
        "        raise ValueError('division by zero')\n"
        "    return a / b\n"
    )
    # Irrelevant: a config module
    (tmp_path / "config.py").write_text(
        "import os\n"
        "\n"
        "DEBUG = os.environ.get('DEBUG', False)\n"
        "PORT = int(os.environ.get('PORT', 8080))\n"
    )
    return tmp_path


class TestFilterByRelevance:
    """Unit tests for the filter_by_relevance function."""

    def test_empty_list(self):
        assert filter_by_relevance([]) == []

    def test_single_result(self):
        result = [(1, 0.5)]
        assert filter_by_relevance(result) == result

    def test_keeps_high_scoring_results(self):
        """All results above the min_score_ratio threshold are kept."""
        scored = [(1, 1.0), (2, 0.9), (3, 0.8), (4, 0.7), (5, 0.5)]
        filtered = filter_by_relevance(scored, min_score_ratio=0.25)
        assert len(filtered) == 5  # 0.5/1.0 = 0.5 > 0.25

    def test_drops_low_scoring_tail(self):
        """Results below the min_score_ratio threshold are removed."""
        scored = [(1, 1.0), (2, 0.8), (3, 0.2), (4, 0.1), (5, 0.05)]
        filtered = filter_by_relevance(scored, min_score_ratio=0.25, floor=1)
        ids = [cid for cid, _ in filtered]
        assert 1 in ids
        assert 2 in ids
        assert 3 not in ids  # 0.2/1.0 = 0.2 < 0.25
        assert 4 not in ids
        assert 5 not in ids

    def test_score_drop_off_detection(self):
        """A sudden drop in scores triggers cutoff."""
        # Scores: 1.0, 0.9, 0.85, 0.3, 0.28 — big gap between 0.85 and 0.3
        scored = [(1, 1.0), (2, 0.9), (3, 0.85), (4, 0.3), (5, 0.28)]
        filtered = filter_by_relevance(
            scored, min_score_ratio=0.2, drop_ratio=0.4, floor=1
        )
        ids = [cid for cid, _ in filtered]
        assert len(filtered) == 3  # cut at the 0.85 -> 0.3 cliff
        assert 4 not in ids
        assert 5 not in ids

    def test_floor_protects_minimum_results(self):
        """The floor parameter ensures at least N results are returned."""
        scored = [(1, 1.0), (2, 0.1)]  # huge gap
        filtered = filter_by_relevance(scored, floor=2)
        assert len(filtered) == 2

    def test_floor_default_keeps_at_least_one(self):
        """Even with terrible scores, at least 1 result is kept."""
        scored = [(1, 1.0), (2, 0.01)]
        filtered = filter_by_relevance(scored)
        assert len(filtered) >= 1

    def test_uniform_scores_kept(self):
        """When all scores are identical, no results are dropped."""
        scored = [(i, 0.5) for i in range(10)]
        filtered = filter_by_relevance(scored)
        assert len(filtered) == 10

    def test_gradual_decline_no_cliff(self):
        """Gradual score decline without a cliff keeps more results."""
        # Each score is 90% of the previous — no cliff
        scored = [(i, 1.0 * (0.9 ** i)) for i in range(10)]
        filtered = filter_by_relevance(
            scored, min_score_ratio=0.25, drop_ratio=0.4
        )
        # 0.9^0 = 1.0, 0.9^5 = 0.59, 0.9^10 = 0.35
        # min_score_ratio=0.25 would keep up to ~0.9^13=0.25
        # drop_ratio=0.4 never triggers (each step is 0.9x previous)
        assert len(filtered) >= 8

    def test_zero_scores_handled(self):
        """Zero scores don't cause division errors."""
        scored = [(1, 0.0), (2, 0.0)]
        filtered = filter_by_relevance(scored)
        assert len(filtered) >= 1


class TestSearchPrecision:
    """Integration tests verifying precision filtering in search pipeline."""

    def test_get_context_relevance_floor(self, db, sample_dir):
        """get_context should stop including chunks below the relevance floor."""
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        searcher = HybridSearcher(db)

        # Search for something specific — should get search-related chunks,
        # not math or config chunks
        ctx = searcher.get_context("search query", token_budget=8000)

        # With precision filtering, we should get fewer chunks than without
        # (the old behavior would fill the entire budget)
        assert ctx["chunks_returned"] <= ctx["chunks_searched"]

        # Verify the returned chunks are relevant
        if ctx["chunks"]:
            files = {c["file"] for c in ctx["chunks"]}
            # search.py should be present (most relevant)
            assert any("search" in f for f in files)

    def test_search_filters_irrelevant_tail(self, db, sample_dir):
        """search() should not return low-relevance chunks after filtering."""
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        searcher = HybridSearcher(db)

        results = searcher.search("search query find matches", limit=50)

        if len(results) >= 2:
            top_score = results[0].score
            # All returned results should have a reasonable score ratio
            for r in results:
                ratio = r.score / top_score if top_score > 0 else 1.0
                assert ratio >= 0.2, (
                    f"Result {r.file_path}:{r.chunk.name} has score ratio "
                    f"{ratio:.2f} which is below the expected floor"
                )

    def test_budget_estimation_is_ceiling(self, db, sample_dir):
        """estimate_budget should return generous ceilings (not tight budgets)."""
        idx = Indexer(db)
        idx.index_codebase(sample_dir)
        searcher = HybridSearcher(db)

        # Simple symbol lookup — ceiling should be reasonable
        budget, limit, classification = searcher.estimate_budget("add")
        assert budget <= 8000, f"Targeted ceiling {budget} too high"
        assert classification.query_type == "targeted"

        # Broader query — ceiling can be larger
        budget, limit, classification = searcher.estimate_budget(
            "how does the search pipeline work end to end"
        )
        assert budget <= 8000, f"Broad ceiling {budget} too high"
        assert classification.query_type == "broad"
        assert budget >= 4000, f"Broad ceiling {budget} too low"


class TestFilterByRelevanceEdgeCases:
    """Edge cases for filter_by_relevance."""

    def test_all_below_threshold(self):
        """When all but the first are below threshold, only floor kept."""
        scored = [(1, 1.0), (2, 0.1), (3, 0.05)]
        filtered = filter_by_relevance(scored, min_score_ratio=0.25, floor=1)
        assert len(filtered) == 1

    def test_two_result_cliff(self):
        """Cliff detection with only two results."""
        scored = [(1, 1.0), (2, 0.2)]
        filtered = filter_by_relevance(
            scored, min_score_ratio=0.25, drop_ratio=0.4, floor=1
        )
        assert len(filtered) == 1

    def test_rrf_scores_realistic(self):
        """Test with realistic RRF scores (small values near 1/k)."""
        # RRF with k=60: top score ~0.0164, second ~0.0161, etc.
        k = 60
        scored = [
            (i, 1.0 / (k + i + 1)) for i in range(20)
        ]
        # Scores: 0.01639, 0.01613, 0.01587, ... 0.01250
        # The ratio of last/first = 0.01250/0.01639 = 0.76 — above 0.4
        # No cliff — each step is ~98% of previous
        filtered = filter_by_relevance(scored)
        # With these gradual RRF scores, most should be kept
        assert len(filtered) == 20

    def test_rrf_with_two_lists_creates_cliff(self):
        """Items in both lists score ~2x those in only one — creates cliff."""
        list1 = [(1, 0.9), (2, 0.8), (3, 0.7)]
        list2 = [(1, 0.95), (4, 0.85), (5, 0.75)]
        fused = reciprocal_rank_fusion([list1, list2])

        # Item 1 is in both lists, items 2-5 are in only one
        # This creates a natural score cliff
        filtered = filter_by_relevance(fused, drop_ratio=0.4)
        ids = [cid for cid, _ in filtered]
        assert 1 in ids  # in both lists, highest score
