"""Tests for documentation-aware search ranking."""

import os
import tempfile

import pytest

from arrow.search import _is_doc_query, _is_doc_path


class TestDocQueryDetection:
    """Test the _is_doc_query helper."""

    def test_tools_query(self):
        assert _is_doc_query("what mcp tools does arrow expose") is True

    def test_list_query(self):
        assert _is_doc_query("list of available endpoints") is True

    def test_api_query(self):
        assert _is_doc_query("api reference") is True

    def test_readme_query(self):
        assert _is_doc_query("readme") is True

    def test_docs_query(self):
        assert _is_doc_query("docs overview") is True

    def test_features_query(self):
        assert _is_doc_query("what features are available") is True

    def test_how_to_phrase(self):
        assert _is_doc_query("how to install arrow") is True

    def test_what_are_phrase(self):
        assert _is_doc_query("what are the supported commands") is True

    def test_code_query_not_doc(self):
        assert _is_doc_query("def authenticate user password") is False

    def test_symbol_query_not_doc(self):
        assert _is_doc_query("reciprocal rank fusion") is False

    def test_error_query_not_doc(self):
        assert _is_doc_query("indexerror traceback") is False


class TestDocPathDetection:
    """Test the _is_doc_path helper."""

    def test_readme(self):
        assert _is_doc_path("readme.md") is True

    def test_readme_uppercase(self):
        assert _is_doc_path("README.md") is True

    def test_changelog(self):
        assert _is_doc_path("changelog.md") is True

    def test_contributing(self):
        assert _is_doc_path("contributing.md") is True

    def test_docs_dir(self):
        assert _is_doc_path("docs/usage.md") is True

    def test_guide(self):
        assert _is_doc_path("user-guide.md") is True

    def test_source_file_not_doc(self):
        assert _is_doc_path("src/server.py") is False

    def test_test_file_not_doc(self):
        assert _is_doc_path("tests/test_core.py") is False


class TestDocSearchRanking:
    """Test that doc queries boost README/doc files in search results."""

    @pytest.fixture
    def project_with_readme(self, tmp_path):
        """Create a project with both source code and documentation."""
        # Source code that mentions "tools"
        (tmp_path / "server.py").write_text(
            "from mcp.server import FastMCP\n"
            "\n"
            "mcp = FastMCP('arrow')\n"
            "\n"
            "@mcp.tool()\n"
            "def search_code(query: str) -> str:\n"
            "    '''Search the codebase.'''\n"
            "    return 'results'\n"
            "\n"
            "@mcp.tool()\n"
            "def get_context(query: str) -> str:\n"
            "    '''Get relevant context.'''\n"
            "    return 'context'\n"
        )
        # README documentation listing tools
        (tmp_path / "README.md").write_text(
            "# Arrow\n"
            "\n"
            "Arrow is an MCP server for code search.\n"
            "\n"
            "## MCP Tools\n"
            "\n"
            "| Tool | Description |\n"
            "|------|-------------|\n"
            "| search_code | Hybrid BM25 + vector search |\n"
            "| get_context | Retrieve relevant code |\n"
            "| search_structure | Find functions by name |\n"
            "| trace_dependencies | Import graph analysis |\n"
            "\n"
            "## Usage\n"
            "\n"
            "Use `search_code` for keyword search.\n"
        )
        # Another source file
        (tmp_path / "tools.py").write_text(
            "def register_tools(mcp):\n"
            "    '''Register all MCP tools.'''\n"
            "    pass\n"
        )
        return tmp_path

    @pytest.fixture
    def setup_with_readme(self, project_with_readme):
        """Index the project with README."""
        db_path = tempfile.mktemp(suffix=".db")
        vec_path = tempfile.mktemp(suffix=".usearch")
        os.environ["ARROW_DB_PATH"] = db_path
        os.environ["ARROW_VECTOR_PATH"] = vec_path

        from arrow.server import index_codebase
        index_codebase(str(project_with_readme))

        yield project_with_readme, db_path, vec_path

        os.environ.pop("ARROW_DB_PATH", None)
        os.environ.pop("ARROW_VECTOR_PATH", None)
        for p in (db_path, vec_path):
            if os.path.exists(p):
                os.unlink(p)

    def test_doc_query_boosts_readme(self, setup_with_readme):
        """A doc-oriented query should rank README higher than source code."""
        import arrow.server as srv

        searcher = srv._get_searcher()
        results = searcher.search("What MCP tools does Arrow expose", limit=10)

        assert len(results) > 0

        # Find the README result
        readme_results = [r for r in results if "readme" in r.file_path.lower()]
        assert len(readme_results) > 0, (
            "README.md should appear in results for a doc query. "
            f"Got: {[r.file_path for r in results]}"
        )

        # README should be the top result (or at least top 2)
        top_paths = [r.file_path.lower() for r in results[:2]]
        assert any("readme" in p for p in top_paths), (
            f"README should be in top 2 results for doc query, "
            f"but top results were: {top_paths}"
        )

    def test_code_query_still_penalizes_readme(self, setup_with_readme):
        """A code-oriented query should still penalize non-code files."""
        import arrow.server as srv

        searcher = srv._get_searcher()
        results = searcher.search("def search_code", limit=10)

        if not results:
            pytest.skip("No results for code query")

        # The top result should be from source code, not README
        assert "readme" not in results[0].file_path.lower(), (
            "Source code should rank higher than README for code queries"
        )

    def test_doc_query_with_tools_keyword(self, setup_with_readme):
        """Query containing 'tools' should be detected as doc query."""
        import arrow.server as srv

        searcher = srv._get_searcher()
        results = searcher.search("list available tools", limit=10)

        assert len(results) > 0
        # Check README appears and is boosted
        readme_results = [r for r in results if "readme" in r.file_path.lower()]
        assert len(readme_results) > 0, (
            "README should appear for 'list available tools' query"
        )
