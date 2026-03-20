"""Tests for the improved search_regex tool with grep-like output."""

import json
import os
import re
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def regex_project(tmp_path):
    """Create a project with various patterns for regex searching."""
    (tmp_path / "errors.py").write_text(
        "import logging\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "def process_data(data):\n"
        "    try:\n"
        "        result = data['key']\n"
        "    except KeyError:\n"
        "        logger.error('Missing key')\n"
        "        return None\n"
        "\n"
        "def fetch_remote(url):\n"
        "    try:\n"
        "        response = requests.get(url)\n"
        "    except ConnectionError as e:\n"
        "        logger.warning(f'Connection failed: {e}')\n"
        "        raise\n"
    )
    (tmp_path / "config.py").write_text(
        "import os\n"
        "\n"
        "DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///app.db')\n"
        "API_KEY = os.getenv('API_KEY')\n"
        "DEBUG = os.environ.get('DEBUG', 'false')\n"
        "ARROW_HOME = os.environ.get('ARROW_HOME', '/tmp')\n"
    )
    (tmp_path / "settings.toml").write_text(
        "[database]\n"
        "url = 'sqlite:///app.db'\n"
        "pool_size = 5\n"
        "\n"
        "[logging]\n"
        "level = 'INFO'\n"
    )
    (tmp_path / "utils.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
        "\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
    )
    return tmp_path


@pytest.fixture
def indexed_regex_project(regex_project):
    """Index the regex project and set up server."""
    db_path = tempfile.mktemp(suffix=".db")
    vec_path = tempfile.mktemp(suffix=".usearch")
    os.environ["ARROW_DB_PATH"] = db_path
    os.environ["ARROW_VECTOR_PATH"] = vec_path

    from arrow.server import index_codebase
    index_codebase(str(regex_project))

    yield regex_project, db_path, vec_path

    os.environ.pop("ARROW_DB_PATH", None)
    os.environ.pop("ARROW_VECTOR_PATH", None)
    for path in (db_path, vec_path):
        if os.path.exists(path):
            os.unlink(path)


class TestSearchRegexOutput:
    """Test that search_regex produces grep-like output with line references."""

    def test_basic_match_with_line_numbers(self, indexed_regex_project):
        """Matches should show file:line references."""
        from arrow.server import search_regex

        result = search_regex(r"def \w+")
        assert "matches" in result
        # Should show line numbers with >> marker for matches
        assert ">>" in result

    def test_match_highlighting(self, indexed_regex_project):
        """Matched text should be highlighted with >>> <<< markers."""
        from arrow.server import search_regex

        result = search_regex(r"os\.environ")
        assert ">>>os.environ<<<" in result

    def test_context_lines(self, indexed_regex_project):
        """Should show context lines around matches."""
        from arrow.server import search_regex

        # With context_lines=2, should see lines around the match
        result = search_regex(r"except.*:", context_lines=2)
        assert "matches" in result
        # Context lines should not have >> marker
        lines = result.split("\n")
        context_lines_found = [
            line for line in lines
            if line.strip() and not line.startswith("#") and ">>" not in line
            and line.strip()[0:1].isdigit()
        ]
        assert len(context_lines_found) > 0, "Should have context lines without >> marker"

    def test_zero_context(self, indexed_regex_project):
        """context_lines=0 should show only matching lines."""
        from arrow.server import search_regex

        result = search_regex(r"os\.environ", context_lines=0)
        lines = result.split("\n")
        # Every numbered line should be a match (have >> marker)
        numbered_lines = [
            line for line in lines
            if line.strip() and not line.startswith("#") and not line.startswith("Regex")
            and line.strip()[0:1].isdigit()
        ]
        for line in numbered_lines:
            assert ">>" in line, f"With context=0, all lines should be matches: {line}"

    def test_no_matches(self, indexed_regex_project):
        """No matches should return clean message."""
        from arrow.server import search_regex

        result = search_regex(r"zzz_never_matches_xyz")
        assert "0 matches" in result

    def test_file_grouping(self, indexed_regex_project):
        """Results should be grouped by file with # headers."""
        from arrow.server import search_regex

        result = search_regex(r"def \w+")
        # Should have file headers
        file_headers = [line for line in result.split("\n") if line.startswith("# ")]
        assert len(file_headers) >= 2, "Should match in multiple files"

    def test_match_count_in_header(self, indexed_regex_project):
        """Header should show total match count and file count."""
        from arrow.server import search_regex

        result = search_regex(r"os\.environ")
        # Header format: "Regex /pattern/ — N matches in M files"
        first_line = result.split("\n")[0]
        assert "matches" in first_line
        assert "files" in first_line

    def test_limit_caps_matches(self, indexed_regex_project):
        """Limit should cap the number of matching lines."""
        from arrow.server import search_regex

        result = search_regex(r"def \w+", limit=2)
        assert "2 matches" in result

    def test_invalid_regex_error(self, indexed_regex_project):
        """Invalid regex should return JSON error."""
        from arrow.server import search_regex

        result = json.loads(search_regex(r"[invalid"))
        assert "error" in result

    def test_empty_pattern_error(self, indexed_regex_project):
        """Empty pattern should return JSON error."""
        from arrow.server import search_regex

        result = json.loads(search_regex(""))
        assert "error" in result

    def test_searches_non_code_files(self, indexed_regex_project):
        """Should find matches in non-code files like .toml."""
        from arrow.server import search_regex

        result = search_regex(r"pool_size")
        assert "pool_size" in result
        assert "settings.toml" in result

    def test_multipattern_regex(self, indexed_regex_project):
        """Should support alternation patterns like grep."""
        from arrow.server import search_regex

        result = search_regex(r"os\.environ|getenv|ARROW_")
        assert "matches" in result
        # Should find both os.environ and getenv
        assert "environ" in result
        assert "getenv" in result


class TestSearchRegexHelpers:
    """Test the internal helper functions."""

    def test_format_regex_results_empty(self):
        """Empty match groups should return clean message."""
        from arrow.server import _format_regex_results

        compiled = re.compile(r"test")
        result = _format_regex_results(compiled, [], 0)
        assert "0 matches" in result

    def test_format_regex_results_with_matches(self):
        """Should format matches with line numbers and highlighting."""
        from arrow.server import _format_regex_results

        compiled = re.compile(r"hello")
        match_groups = [{
            "file": "test.py",
            "abs_path": "/tmp/test.py",
            "groups": [{
                "ctx_start": 0,
                "ctx_end": 3,
                "match_lines": [1],
            }],
            "lines": ["before\n", "say hello world\n", "after\n"],
        }]
        result = _format_regex_results(compiled, match_groups, 1)
        assert "1 matches" in result
        assert "test.py" in result
        assert ">>>hello<<<" in result
        assert ">>" in result

    def test_context_merging(self):
        """Overlapping context groups should merge."""
        from arrow.server import _search_regex_on_disk

        # Create a temp file with close matches
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "close.py"
            filepath.write_text(
                "line 1\n"
                "match_a here\n"
                "line 3\n"
                "match_b here\n"
                "line 5\n"
            )
            compiled = re.compile(r"match_[ab]")
            result = _search_regex_on_disk(compiled, Path(tmpdir), 50, 1)
            # With context=1, matches on lines 2 and 4 should merge
            # (context of line 2 is 1-3, context of line 4 is 3-5, they overlap at line 3)
            assert "2 matches" in result
            # Should NOT have "..." separator since contexts merged
            assert "..." not in result
