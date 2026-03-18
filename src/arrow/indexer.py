"""Indexing engine: orchestrates file discovery, hashing, chunking, and storage."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Optional

import tiktoken

from .chunker import chunk_file, compress_content, detect_language
from .discovery import discover_files
from .git_utils import get_git_info
from .hasher import hash_content, hash_file
from .storage import Storage

logger = logging.getLogger(__name__)

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

    def __init__(self, storage: Storage, vector_store=None, embedder=None):
        self.storage = storage
        self.vector_store = vector_store
        self.embedder = embedder

    def _embed_chunks_async(self, chunk_ids: list[int], texts: list[str]) -> None:
        """Generate embeddings in a background thread."""
        if not self.embedder or not self.vector_store:
            return

        def _do_embed():
            try:
                if not self.embedder.ready:
                    if not self.embedder.load():
                        logger.warning("Embedder failed to load, skipping vectors")
                        return

                logger.info("Generating embeddings for %d chunks...", len(texts))
                vectors = self.embedder.embed_batch(texts)
                self.vector_store.add(chunk_ids, vectors)
                self.vector_store.save()
                logger.info("Embeddings generated and saved")
            except Exception:
                logger.exception("Embedding generation failed")

        thread = threading.Thread(target=_do_embed, daemon=True)
        thread.start()
        return thread

    def _resolve_project(self, root: Path) -> int:
        """Find or create a project for this root path, using git info."""
        # Check if project already exists for this path
        existing = self.storage.get_project_by_root(str(root))
        if existing:
            # Update git info
            git_info = get_git_info(root)
            self.storage.update_project_git(
                existing.id, git_info["branch"], git_info["commit"]
            )
            if git_info["remote_url"]:
                self.storage.conn.execute(
                    "UPDATE projects SET remote_url = ? WHERE id = ?",
                    (git_info["remote_url"], existing.id),
                )
                self.storage.conn.commit()
            return existing.id

        # New project — detect git info
        git_info = get_git_info(root)
        project_id = self.storage.create_project(
            name=git_info["name"],
            root_path=str(root),
            remote_url=git_info["remote_url"],
            git_branch=git_info["branch"],
            git_commit=git_info["commit"],
        )
        return project_id

    def index_codebase(
        self, root: str | Path, force: bool = False
    ) -> dict:
        """Index or re-index a codebase.

        Automatically detects git info and creates/updates the project.

        Args:
            root: Path to the codebase root.
            force: If True, re-index all files regardless of hash.

        Returns:
            Status dict with counts and project info.
        """
        root = Path(root).resolve()
        start_time = time.time()

        # Resolve project (creates if needed, updates git info)
        project_id = self._resolve_project(root)

        stats = {
            "files_scanned": 0,
            "files_indexed": 0,
            "files_skipped": 0,
            "files_removed": 0,
            "chunks_created": 0,
            "errors": 0,
            "languages": Counter(),
            "project_id": project_id,
        }

        seen_paths: set[str] = set()
        new_chunk_ids: list[int] = []
        new_chunk_texts: list[str] = []

        for filepath in discover_files(root):
            stats["files_scanned"] += 1
            rel_path = str(filepath.relative_to(root))
            seen_paths.add(rel_path)

            try:
                content_hash = hash_file(str(filepath))
            except OSError:
                logger.warning("Cannot hash %s", rel_path)
                stats["errors"] += 1
                continue

            if not force:
                existing = self.storage.get_file(rel_path, project_id=project_id)
                if existing and existing.content_hash == content_hash:
                    stats["files_skipped"] += 1
                    continue

            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                logger.warning("Cannot read %s", rel_path)
                stats["errors"] += 1
                continue

            language = detect_language(filepath)
            if language:
                stats["languages"][language] += 1

            file_id = self.storage.upsert_file(
                rel_path, content_hash, language, project_id=project_id
            )
            self.storage.delete_chunks_for_file(file_id)

            chunks = chunk_file(filepath, content)

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
                    project_id,
                ))

            if batch:
                self.storage.insert_chunks_batch(batch)
                stats["chunks_created"] += len(batch)

                # Collect new chunks for embedding
                file_chunks = self.storage.get_chunks_for_file(file_id)
                for fc in file_chunks:
                    new_chunk_ids.append(fc.id)
                    new_chunk_texts.append(fc.content_text or "")

            # Extract and store symbols + imports for structure analysis
            self._extract_structure(file_id, filepath, content, language)

            stats["files_indexed"] += 1

        # Remove deleted files — scoped to this project only
        existing_files = self.storage.get_all_files(project_id=project_id)
        for file_rec in existing_files:
            if file_rec.path not in seen_paths:
                self.storage.delete_file(file_rec.path, project_id=project_id)
                stats["files_removed"] += 1

        self.storage.commit()

        elapsed = time.time() - start_time
        lang_stats = json.dumps(dict(stats["languages"].most_common()))

        # Update project metadata
        self.storage.update_project_indexed(project_id, f"{elapsed:.2f}s", lang_stats)

        # Generate embeddings in background
        if new_chunk_ids:
            self._embed_chunks_async(new_chunk_ids, new_chunk_texts)
            stats["embedding_status"] = "generating in background"
        else:
            stats["embedding_status"] = "no new chunks"

        # Add project info to result
        project = self.storage.get_project(project_id)
        if project:
            stats["project_name"] = project.name
            stats["git_branch"] = project.git_branch
            stats["git_commit"] = project.git_commit

        stats["elapsed"] = f"{elapsed:.2f}s"
        stats["languages"] = dict(stats["languages"].most_common())
        return stats

    def index_remote_files(
        self,
        owner: str,
        repo: str,
        branch: str,
        files: list[dict],
    ) -> dict:
        """Index files from a remote GitHub repo (content passed by Claude).

        Args:
            owner: GitHub org/user.
            repo: Repository name.
            branch: Branch name.
            files: List of {"path": "...", "content": "..."} dicts.

        Returns:
            Status dict.
        """
        start_time = time.time()
        name = f"{owner}/{repo}"
        remote_url = f"https://github.com/{owner}/{repo}"

        project_id = self.storage.create_project(
            name=name,
            remote_url=remote_url,
            git_branch=branch,
            is_remote=True,
        )

        stats = {
            "files_indexed": 0,
            "chunks_created": 0,
            "errors": 0,
            "languages": Counter(),
            "project_id": project_id,
            "project_name": name,
        }

        new_chunk_ids: list[int] = []
        new_chunk_texts: list[str] = []

        for file_info in files:
            file_path = file_info["path"]
            content = file_info["content"]
            content_hash_val = hash_content(content)

            # Check if already indexed with same hash
            existing = self.storage.get_file(file_path, project_id=project_id)
            if existing and existing.content_hash == content_hash_val:
                continue

            virtual_path = PurePosixPath(file_path)
            language = detect_language(virtual_path)
            if language:
                stats["languages"][language] += 1

            file_id = self.storage.upsert_file(
                file_path, content_hash_val, language, project_id=project_id
            )
            self.storage.delete_chunks_for_file(file_id)

            chunks = chunk_file(virtual_path, content)

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
                    project_id,
                ))

            if batch:
                self.storage.insert_chunks_batch(batch)
                stats["chunks_created"] += len(batch)

                file_chunks = self.storage.get_chunks_for_file(file_id)
                for fc in file_chunks:
                    new_chunk_ids.append(fc.id)
                    new_chunk_texts.append(fc.content_text or "")

            self._extract_structure(file_id, virtual_path, content, language)
            stats["files_indexed"] += 1

        self.storage.commit()

        elapsed = time.time() - start_time
        lang_stats = json.dumps(dict(stats["languages"].most_common()))
        self.storage.update_project_indexed(project_id, f"{elapsed:.2f}s", lang_stats)

        if new_chunk_ids:
            self._embed_chunks_async(new_chunk_ids, new_chunk_texts)

        stats["elapsed"] = f"{elapsed:.2f}s"
        stats["languages"] = dict(stats["languages"].most_common())
        return stats

    def _extract_structure(
        self, file_id: int, filepath, content: str, language: Optional[str]
    ) -> None:
        """Extract symbols and imports from a file for structure analysis."""
        if not language:
            return

        # Delete old symbols/imports for this file
        self.storage.conn.execute(
            "DELETE FROM symbols WHERE file_id = ?", (file_id,)
        )
        self.storage.conn.execute(
            "DELETE FROM imports WHERE source_file = ?", (file_id,)
        )

        lines = content.splitlines()

        # Extract imports (language-specific patterns)
        import_lines = _extract_imports(lines, language)
        for imp in import_lines:
            self.storage.conn.execute(
                "INSERT INTO imports (source_file, target_file, symbol) VALUES (?, NULL, ?)",
                (file_id, imp),
            )

        # Store symbols from chunks
        chunks = self.storage.get_chunks_for_file(file_id)
        for chunk in chunks:
            if chunk.name and chunk.name != "<anonymous>" and not chunk.name.startswith("chunk_"):
                self.storage.insert_symbol(
                    chunk_id=chunk.id,
                    name=chunk.name,
                    kind=chunk.kind,
                    file_id=file_id,
                )

    def generate_project_summary(
        self, project_id: Optional[int] = None
    ) -> dict:
        """Generate a project summary. If project_id is None, summarizes all."""
        db_stats = self.storage.get_stats(project_id=project_id)

        if project_id:
            project = self.storage.get_project(project_id)
            root_path = project.root_path if project else None
            all_files = self.storage.get_all_files(project_id=project_id)
            last_indexed = project.last_indexed if project else None
            index_duration = project.index_duration if project else None
        else:
            # Summary across all projects
            projects = self.storage.list_projects()
            root_path = ", ".join(
                p.root_path for p in projects if p.root_path
            ) or None
            all_files = self.storage.get_all_files()
            last_indexed = max(
                (p.last_indexed for p in projects if p.last_indexed), default=None
            )
            index_duration = None

        dir_counts: Counter = Counter()
        entry_points: list[str] = []

        entry_point_names = {
            "main.py", "app.py", "server.py", "index.js", "index.ts",
            "main.go", "main.rs", "Main.java", "Program.cs",
            "main.c", "main.cpp", "lib.rs", "manage.py",
            "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
            "Makefile", "CMakeLists.txt",
        }

        for f in all_files:
            parts = Path(f.path).parts
            if len(parts) > 1:
                dir_counts[parts[0]] += 1
            else:
                dir_counts["."] += 1
            if Path(f.path).name in entry_point_names:
                entry_points.append(f.path)

        top_dirs = [
            {"directory": d, "files": c}
            for d, c in dir_counts.most_common(20)
        ]

        return {
            "root": str(root_path) if root_path else None,
            "total_files": db_stats["files"],
            "total_chunks": db_stats["chunks"],
            "total_symbols": db_stats["symbols"],
            "languages": db_stats["languages"],
            "structure": top_dirs,
            "entry_points": entry_points,
            "last_indexed": last_indexed,
            "index_duration": index_duration,
        }


def _extract_imports(lines: list[str], language: str) -> list[str]:
    """Extract import/require statements from source lines."""
    imports = []
    for line in lines:
        stripped = line.strip()
        if language == "python":
            if stripped.startswith("import "):
                mod = stripped.split()[1].split(".")[0]
                imports.append(mod)
            elif stripped.startswith("from "):
                parts = stripped.split()
                if len(parts) >= 2:
                    mod = parts[1].split(".")[0]
                    imports.append(mod)
        elif language in ("javascript", "typescript", "tsx"):
            if "require(" in stripped or "import " in stripped:
                for q in ('"', "'", "`"):
                    if q in stripped:
                        start = stripped.index(q) + 1
                        end = stripped.index(q, start) if q in stripped[start:] else -1
                        if end > start:
                            imports.append(stripped[start:end])
                        break
        elif language == "go":
            if stripped.startswith('"') and stripped.endswith('"'):
                imports.append(stripped.strip('"'))
            elif stripped.startswith("import "):
                if '"' in stripped:
                    start = stripped.index('"') + 1
                    end = stripped.rindex('"')
                    if end > start:
                        imports.append(stripped[start:end])
        elif language == "rust":
            if stripped.startswith("use "):
                mod = stripped[4:].split("::")[0].rstrip(";").strip()
                imports.append(mod)
        elif language == "java":
            if stripped.startswith("import "):
                mod = stripped[7:].rstrip(";").strip()
                imports.append(mod)
        elif language in ("c", "cpp"):
            if stripped.startswith("#include"):
                for delim_start, delim_end in [("<", ">"), ('"', '"')]:
                    if delim_start in stripped:
                        start = stripped.index(delim_start) + 1
                        end = stripped.index(delim_end, start)
                        if end > start:
                            imports.append(stripped[start:end])
                        break
        elif language == "ruby":
            if stripped.startswith("require ") or stripped.startswith("require_relative "):
                for q in ('"', "'"):
                    if q in stripped:
                        start = stripped.index(q) + 1
                        end = stripped.index(q, start) if q in stripped[start:] else -1
                        if end > start:
                            imports.append(stripped[start:end])
                        break
    return imports
