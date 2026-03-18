"""Tests for cross-repo symbol resolution (resolve_symbol)."""

import json


class TestResolveSymbol:
    def test_resolve_symbol_local(self, setup_server):
        from arrow.server import resolve_symbol
        result = json.loads(resolve_symbol("authenticate"))
        assert "error" not in result
        assert result["query"] == "authenticate"
        assert len(result["results"]) > 0
        # Should find the definition
        names = [r["symbol"] for r in result["results"]]
        assert "authenticate" in names

    def test_resolve_symbol_cross_repo(self, setup_server):
        """Index a second project and resolve symbols across both."""
        project_dir, _, _ = setup_server
        from arrow.server import index_github_content, resolve_symbol

        # Index remote content with a matching symbol name
        index_github_content(
            owner="other", repo="lib", branch="main",
            files=[{
                "path": "shared.py",
                "content": "def authenticate(token):\n    return True\n",
            }],
        )

        result = json.loads(resolve_symbol("authenticate"))
        assert result["total"] >= 2
        projects = {r["project"] for r in result["results"]}
        assert len(projects) >= 2  # From both repos

    def test_resolve_nonexistent_symbol(self, setup_server):
        from arrow.server import resolve_symbol
        result = json.loads(resolve_symbol("zzz_nonexistent_symbol"))
        assert result["total"] == 0
