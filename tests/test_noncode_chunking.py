"""Tests for non-code file chunking (TOML, YAML, JSON, Markdown, Dockerfile)."""

import os
import tempfile
from pathlib import Path

import pytest

from arrow.chunker import (
    chunk_file,
    detect_language,
    _chunk_toml,
    _chunk_yaml,
    _chunk_json,
    _chunk_markdown,
    _chunk_dockerfile,
)
from arrow.indexer import Indexer
from arrow.search import HybridSearcher
from arrow.storage import Storage


@pytest.fixture
def db():
    path = tempfile.mktemp(suffix=".db")
    storage = Storage(path)
    yield storage
    storage.close()
    if os.path.exists(path):
        os.unlink(path)


# --- Language detection ---


class TestNonCodeDetection:
    def test_detect_toml(self):
        assert detect_language(Path("pyproject.toml")) == "toml"

    def test_detect_yaml(self):
        assert detect_language(Path("config.yaml")) == "yaml"
        assert detect_language(Path("ci.yml")) == "yaml"

    def test_detect_json(self):
        assert detect_language(Path("package.json")) == "json"

    def test_detect_markdown(self):
        assert detect_language(Path("README.md")) == "markdown"

    def test_detect_dockerfile(self):
        assert detect_language(Path("Dockerfile")) == "dockerfile"
        assert detect_language(Path("Dockerfile.prod")) == "dockerfile"


# --- TOML chunking ---


class TestTomlChunking:
    def test_sections(self):
        content = """\
[project]
name = "arrow"
version = "0.1.0"

[project.dependencies]
click = ">=8.0"
tiktoken = ">=0.5"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        chunks = _chunk_toml(Path("pyproject.toml"), content)
        names = [c.name for c in chunks]
        assert "project" in names
        assert "project.dependencies" in names
        assert "tool.pytest.ini_options" in names

    def test_preamble(self):
        content = """\
# This is a comment
key = "value"

[section]
foo = "bar"
"""
        chunks = _chunk_toml(Path("config.toml"), content)
        assert len(chunks) == 2
        assert chunks[0].name == "config.toml"  # preamble
        assert chunks[1].name == "section"

    def test_no_sections(self):
        content = 'key = "value"\nother = 42\n'
        chunks = _chunk_toml(Path("simple.toml"), content)
        assert len(chunks) == 1
        assert chunks[0].kind == "config"

    def test_array_of_tables(self):
        content = """\
[[tool.poetry.source]]
name = "pypi"
url = "https://pypi.org/simple"

[[tool.poetry.source]]
name = "private"
url = "https://private.example.com"
"""
        chunks = _chunk_toml(Path("pyproject.toml"), content)
        assert len(chunks) >= 1
        assert any("tool.poetry.source" in c.name for c in chunks)

    def test_chunk_file_routes_toml(self):
        content = "[project]\nname = 'test'\n"
        chunks = chunk_file(Path("pyproject.toml"), content)
        assert len(chunks) >= 1
        assert chunks[0].kind == "config"


# --- YAML chunking ---


class TestYamlChunking:
    def test_top_level_keys(self):
        content = """\
name: my-project
version: 1.0

dependencies:
  - click
  - tiktoken

scripts:
  test: pytest
"""
        chunks = _chunk_yaml(Path("config.yaml"), content)
        names = [c.name for c in chunks]
        assert "name" in names
        assert "dependencies" in names
        assert "scripts" in names

    def test_with_comments(self):
        content = """\
# CI Pipeline
---
jobs:
  build:
    runs-on: ubuntu-latest

env:
  NODE_ENV: production
"""
        chunks = _chunk_yaml(Path("ci.yml"), content)
        names = [c.name for c in chunks]
        assert "jobs" in names
        assert "env" in names

    def test_chunk_file_routes_yaml(self):
        content = "name: test\nversion: 1\n"
        chunks = chunk_file(Path("config.yaml"), content)
        assert len(chunks) >= 1
        assert chunks[0].kind == "config"


# --- JSON chunking ---


class TestJsonChunking:
    def test_top_level_keys(self):
        content = """\
{
  "name": "my-project",
  "version": "1.0.0",
  "scripts": {
    "test": "jest",
    "build": "tsc"
  },
  "dependencies": {
    "express": "^4.0.0"
  }
}
"""
        chunks = _chunk_json(Path("package.json"), content)
        names = [c.name for c in chunks]
        assert "name" in names
        assert "scripts" in names
        assert "dependencies" in names

    def test_small_json(self):
        content = '{"a": 1, "b": 2}\n'
        chunks = _chunk_json(Path("small.json"), content)
        assert len(chunks) == 1
        assert chunks[0].kind == "config"

    def test_invalid_json(self):
        content = "{not valid json"
        chunks = _chunk_json(Path("bad.json"), content)
        assert len(chunks) == 1  # falls back to whole-file chunk

    def test_chunk_file_routes_json(self):
        content = '{"name": "test"}\n'
        chunks = chunk_file(Path("package.json"), content)
        assert len(chunks) >= 1
        assert chunks[0].kind == "config"


# --- Markdown chunking ---


class TestMarkdownChunking:
    def test_headings(self):
        content = """\
# Title

Introduction text.

## Installation

Run pip install.

## Usage

Import and call.

### Advanced Usage

More details.
"""
        chunks = _chunk_markdown(Path("README.md"), content)
        names = [c.name for c in chunks]
        assert "Title" in names
        assert "Installation" in names
        assert "Usage" in names

    def test_heading_hierarchy(self):
        """H2 sections should include their H3 subsections."""
        content = """\
# Top

## Section A

### Sub A1

Content A1.

### Sub A2

Content A2.

## Section B

Content B.
"""
        chunks = _chunk_markdown(Path("doc.md"), content)
        # "Section A" chunk should extend until "Section B" starts
        section_a = next(c for c in chunks if c.name == "Section A")
        assert "Sub A1" in section_a.content
        assert "Sub A2" in section_a.content

    def test_no_headings(self):
        content = "Just some plain text.\nNo headings here.\n"
        chunks = _chunk_markdown(Path("notes.md"), content)
        assert len(chunks) == 1
        assert chunks[0].kind == "doc"

    def test_chunk_file_routes_markdown(self):
        content = "# Title\n\nSome text.\n"
        chunks = chunk_file(Path("README.md"), content)
        assert len(chunks) >= 1
        assert chunks[0].kind == "doc"


# --- Dockerfile chunking ---


class TestDockerfileChunking:
    def test_single_stage(self):
        content = """\
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .
HEALTHCHECK CMD curl -f http://localhost:8080/health
CMD ["python", "-m", "arrow"]
"""
        chunks = _chunk_dockerfile(Path("Dockerfile"), content)
        assert len(chunks) == 1
        assert "HEALTHCHECK" in chunks[0].content

    def test_multi_stage(self):
        content = """\
FROM python:3.11-slim AS builder

RUN pip install build
COPY . .
RUN python -m build

FROM python:3.11-slim AS runtime

COPY --from=builder /app/dist /app/dist
RUN pip install /app/dist/*.whl
HEALTHCHECK CMD curl -f http://localhost:8080/health
CMD ["python", "-m", "arrow"]
"""
        chunks = _chunk_dockerfile(Path("Dockerfile"), content)
        assert len(chunks) == 2
        names = [c.name for c in chunks]
        assert "builder" in names
        assert "runtime" in names

    def test_chunk_file_routes_dockerfile(self):
        content = "FROM python:3.11\nRUN echo hello\n"
        chunks = chunk_file(Path("Dockerfile"), content)
        assert len(chunks) >= 1
        assert chunks[0].kind == "config"


# --- Integration: indexing + search ---


class TestNonCodeIndexing:
    def test_toml_is_indexed_and_searchable(self, db, tmp_path):
        """pyproject.toml should be indexed and findable via search."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "arrow"\nversion = "0.1.0"\n\n'
            "[project.dependencies]\n"
            'click = ">=8.0"\n'
            'tiktoken = ">=0.5"\n'
        )
        (tmp_path / "main.py").write_text("def main(): pass\n")

        idx = Indexer(db)
        result = idx.index_codebase(tmp_path)
        assert result["files_indexed"] >= 2

        searcher = HybridSearcher(db)
        results = searcher.search(
            "pyproject dependencies",
            limit=5,
            project_id=result["project_id"],
        )
        assert len(results) > 0
        paths = [r.file_path for r in results]
        assert any("pyproject.toml" in p for p in paths)

    def test_dockerfile_is_indexed_and_searchable(self, db, tmp_path):
        """Dockerfile should be indexed and findable via search."""
        (tmp_path / "Dockerfile").write_text(
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN pip install -e .\n"
            "HEALTHCHECK CMD curl -f http://localhost:8080/health\n"
            'CMD ["python", "-m", "arrow"]\n'
        )
        (tmp_path / "main.py").write_text("def main(): pass\n")

        idx = Indexer(db)
        result = idx.index_codebase(tmp_path)

        searcher = HybridSearcher(db)
        results = searcher.search(
            "Docker healthcheck",
            limit=5,
            project_id=result["project_id"],
        )
        assert len(results) > 0
        paths = [r.file_path for r in results]
        assert any("Dockerfile" in p for p in paths)

    def test_yaml_is_indexed_and_searchable(self, db, tmp_path):
        (tmp_path / "config.yaml").write_text(
            "name: my-app\n"
            "database:\n"
            "  host: localhost\n"
            "  port: 5432\n"
        )
        (tmp_path / "main.py").write_text("def main(): pass\n")

        idx = Indexer(db)
        result = idx.index_codebase(tmp_path)

        searcher = HybridSearcher(db)
        results = searcher.search(
            "database config",
            limit=5,
            project_id=result["project_id"],
        )
        assert len(results) > 0

    def test_markdown_is_indexed_and_searchable(self, db, tmp_path):
        (tmp_path / "README.md").write_text(
            "# My Project\n\n"
            "## Installation\n\n"
            "Run pip install my-project.\n\n"
            "## Usage\n\n"
            "Import and use.\n"
        )
        (tmp_path / "main.py").write_text("def main(): pass\n")

        idx = Indexer(db)
        result = idx.index_codebase(tmp_path)

        searcher = HybridSearcher(db)
        results = searcher.search(
            "installation instructions",
            limit=5,
            project_id=result["project_id"],
        )
        assert len(results) > 0
