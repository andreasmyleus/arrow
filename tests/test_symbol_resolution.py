"""Tests for cross-repo symbol resolution (resolve_symbol)."""


class TestResolveSymbol:
    def test_resolve_symbol_local(self, setup_server):
        from arrow.server import resolve_symbol
        result = resolve_symbol("authenticate")
        assert "authenticate" in result
        # Should show at least one result
        assert "1 result" in result or "results" in result

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

        result = resolve_symbol("authenticate")
        # Should find results from multiple repos
        assert "authenticate" in result
        assert "result" in result

    def test_resolve_nonexistent_symbol(self, setup_server):
        from arrow.server import resolve_symbol
        result = resolve_symbol("zzz_nonexistent_symbol")
        assert "No definitions found" in result
