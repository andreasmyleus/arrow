"""Indexing engine: orchestrates file discovery, hashing, chunking, and storage."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Optional

import tiktoken

from .chunker import Chunk, chunk_file, compress_content, detect_language
from .discovery import discover_files
from .hasher import hash_content, hash_file
from .storage import Storage

logger = logging.getLogger(__name__)

# Lazy-load tiktoken encoder
_encoder: Optional[tiktoken.Encoding] = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (cl100k_base, used by Claude)."""
    return len(_get_encoder().encode(text))


class Indexer:
    """Orchestrates indexing of a codebase."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def index_codebase(
        self, root: str | Path, force: bool = False
    ) -> dict:
        """Index or re-index a codebase.

        Args:
            root: Path to the codebase root.
            force: If True, re-index all files regardless of hash.

        Returns:
            Status dict with counts.
        """
        root = Path(root).resolve()
        start_time = time.time()

        stats = {
            "files_scanned": 0,
            "files_indexed": 0,
            "files_skipped": 0,
            "files_removed": 0,
            "chunks_created": 0,
            "errors": 0,
            "languages": Counter(),
        }

        # Track which files we've seen (to detect deletions)
        seen_paths: set[str] = set()

        for filepath in discover_files(root):
            stats["files_scanned"] += 1
            rel_path = str(filepath.relative_to(root))
            seen_paths.add(rel_path)

            try:
                content_hash = hash_file(str(filepath))
            except OSError as e:
                logger.warning(f"Cannot read {rel_path}: {e}")
                stats["errors"] += 1
                continue

            # Check if file needs re-indexing
            if not force:
                existing = self.storage.get_file(rel_path)
                if existing and existing.content_hash == content_hash:
                    stats["files_skipped"] += 1
                    continue

            # Read file content
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                logger.warning(f"Cannot read {rel_path}: {e}")
                stats["errors"] += 1
                continue

            language = detect_language(filepath)
            if language:
                stats["languages"][language] += 1

            # Upsert file record
            file_id = self.storage.upsert_file(rel_path, content_hash, language)

            # Delete old chunks for this file
            self.storage.delete_chunks_for_file(file_id)

            # Chunk the file
            chunks = chunk_file(filepath, content)

            # Store chunks
            batch = []
            for chunk in chunks:
                compressed = compress_content(chunk.content)
                token_count = count_tokens(chunk.content)
                batch.append((
                    file_id,
                    chunk.name,
                    chunk.kind,
                    chunk.start_line,
                    chunk.end_line,
                    compressed,
                    chunk.content,
                    chunk.scope_context,
                    token_count,
                ))

            if batch:
                self.storage.insert_chunks_batch(batch)
                stats["chunks_created"] += len(batch)

            stats["files_indexed"] += 1

        # Remove files that no longer exist
        existing_files = self.storage.get_all_files()
        for file_rec in existing_files:
            if file_rec.path not in seen_paths:
                self.storage.delete_file(file_rec.path)
                stats["files_removed"] += 1

        self.storage.commit()

        elapsed = time.time() - start_time

        # Store project metadata
        self.storage.set_project_meta("root_path", str(root))
        self.storage.set_project_meta("last_indexed", str(time.time()))
        self.storage.set_project_meta("index_duration", f"{elapsed:.2f}s")
        self.storage.set_project_meta(
            "language_stats",
            json.dumps(dict(stats["languages"].most_common())),
        )

        stats["elapsed"] = f"{elapsed:.2f}s"
        stats["languages"] = dict(stats["languages"].most_common())
        return stats

    def generate_project_summary(self, root: Optional[str | Path] = None) -> dict:
        """Generate a compressed project summary.

        Returns language distribution, file structure, key modules, and stats.
        """
        db_stats = self.storage.get_stats()
        root_path = root or self.storage.get_project_meta("root_path")

        # Get language distribution
        languages = db_stats["languages"]

        # Get file structure (top-level directories and their file counts)
        all_files = self.storage.get_all_files()
        dir_counts: Counter = Counter()
        entry_points: list[str] = []

        entry_point_names = {
            "main.py",
            "app.py",
            "server.py",
            "index.js",
            "index.ts",
            "main.go",
            "main.rs",
            "Main.java",
            "Program.cs",
            "main.c",
            "main.cpp",
            "lib.rs",
            "mod.rs",
            "manage.py",
            "setup.py",
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "Makefile",
            "CMakeLists.txt",
        }

        for f in all_files:
            parts = Path(f.path).parts
            if len(parts) > 1:
                dir_counts[parts[0]] += 1
            else:
                dir_counts["."] += 1

            if Path(f.path).name in entry_point_names:
                entry_points.append(f.path)

        # Top directories by file count
        top_dirs = [
            {"directory": d, "files": c}
            for d, c in dir_counts.most_common(20)
        ]

        summary = {
            "root": str(root_path) if root_path else None,
            "total_files": db_stats["files"],
            "total_chunks": db_stats["chunks"],
            "total_symbols": db_stats["symbols"],
            "languages": languages,
            "structure": top_dirs,
            "entry_points": entry_points,
            "last_indexed": self.storage.get_project_meta("last_indexed"),
            "index_duration": self.storage.get_project_meta("index_duration"),
        }

        return summary
