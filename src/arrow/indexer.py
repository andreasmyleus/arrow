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
from .git_utils import (
    get_changed_files_between, get_commit_info, get_file_at_commit,
    get_git_info, get_pr_refs, list_files_at_commit, resolve_commit,
)
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

    def _embed_chunks_async(self, chunk_ids: list[int], texts: list[str]) -> Optional[threading.Thread]:
        """Generate embeddings in a background thread."""
        if not self.embedder or not self.vector_store:
            return None

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

    def index_git_commit(
        self,
        root: str | Path,
        ref: str,
    ) -> dict:
        """Index a codebase at a specific git commit, tag, or branch.

        Creates a snapshot project named "org/repo@<short_ref>" that can be
        searched independently. Useful for comparing code across versions or
        investigating historical code.

        Args:
            root: Path to the git repository.
            ref: Git ref — commit SHA, tag, or branch name.

        Returns:
            Status dict with counts and project info.
        """
        root = Path(root).resolve()
        start_time = time.time()

        # Resolve ref to full SHA
        full_sha = resolve_commit(root, ref)
        if not full_sha:
            return {"error": f"Cannot resolve git ref: {ref}"}

        commit_info = get_commit_info(root, full_sha)
        if not commit_info:
            return {"error": f"Cannot get commit info for: {ref}"}

        # Determine project identity
        git_info = get_git_info(root)
        base_name = git_info["name"]
        short_ref = commit_info["short_sha"]

        # Use tag/branch name if ref isn't a raw SHA
        if ref != full_sha and not ref.startswith(full_sha[:7]):
            short_ref = ref

        snapshot_name = f"{base_name}@{short_ref}"

        # Check if this exact snapshot already exists
        existing = self.storage.get_project_by_name(snapshot_name)
        if existing and existing.git_commit == full_sha:
            return {
                "project_id": existing.id,
                "project_name": snapshot_name,
                "status": "already indexed",
                "commit": commit_info,
            }

        # Create or update the snapshot project
        project_id = self.storage.create_project(
            name=snapshot_name,
            root_path=str(root),
            remote_url=git_info["remote_url"],
            git_branch=short_ref,
            git_commit=full_sha,
            is_remote=False,
        )

        # List files at that commit
        all_files = list_files_at_commit(root, full_sha)
        if not all_files:
            return {"error": f"No files found at commit {ref}"}

        # All text files are indexable (fallback chunking handles unknown languages)
        files = all_files

        stats = {
            "files_scanned": len(all_files),
            "files_indexed": 0,
            "chunks_created": 0,
            "errors": 0,
            "languages": Counter(),
            "project_id": project_id,
            "project_name": snapshot_name,
            "commit": commit_info,
        }

        new_chunk_ids: list[int] = []
        new_chunk_texts: list[str] = []

        for file_path in files:
            content = get_file_at_commit(root, full_sha, file_path)
            if content is None:
                stats["errors"] += 1
                continue

            # Skip very large files (>1MB)
            if len(content) > 1_000_000:
                continue

            content_hash_val = hash_content(content)

            # Check if already indexed with same hash
            existing_file = self.storage.get_file(file_path, project_id=project_id)
            if existing_file and existing_file.content_hash == content_hash_val:
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

    def index_pr(
        self,
        root: str | Path,
        pr_number: int,
    ) -> dict:
        """Index both sides of a pull request for comparison.

        Uses `gh pr view` to get PR metadata, then indexes:
        - The merge base (common ancestor) as "org/repo@base:PR-N"
        - The PR head commit as "org/repo@pr:PR-N"

        Also returns the list of changed files for easy diffing.

        Args:
            root: Path to the git repository.
            pr_number: PR number.

        Returns:
            Status dict with base/head project info and changed files.
        """
        root = Path(root).resolve()
        start_time = time.time()

        pr_info = get_pr_refs(root, pr_number)
        if pr_info is None:
            return {
                "error": f"Cannot get PR #{pr_number} info. "
                "Is `gh` CLI installed and authenticated?"
            }

        head_sha = pr_info["head_sha"]
        # Use merge base for accurate "what was the code before this PR"
        base_sha = pr_info["merge_base"] or pr_info["base_sha"]

        if not head_sha or not base_sha:
            return {"error": f"Cannot resolve commits for PR #{pr_number}"}

        # Get changed files
        changed = get_changed_files_between(root, base_sha, head_sha)

        # Index base snapshot
        base_result = self.index_git_commit(root, base_sha)
        base_name = base_result.get("project_name", "?")

        # Rename to a PR-specific name for clarity
        git_info = get_git_info(root)
        pr_base_name = f"{git_info['name']}@base:PR-{pr_number}"
        pr_head_name = f"{git_info['name']}@pr:PR-{pr_number}"

        # Rename base project
        if "project_id" in base_result:
            self.storage.conn.execute(
                "UPDATE projects SET name = ? WHERE id = ? AND name = ?",
                (pr_base_name, base_result["project_id"], base_name),
            )
            self.storage.conn.commit()

        # Index head snapshot
        head_result = self.index_git_commit(root, head_sha)
        head_name = head_result.get("project_name", "?")

        if "project_id" in head_result:
            self.storage.conn.execute(
                "UPDATE projects SET name = ? WHERE id = ? AND name = ?",
                (pr_head_name, head_result["project_id"], head_name),
            )
            self.storage.conn.commit()

        elapsed = time.time() - start_time

        return {
            "pr_number": pr_number,
            "title": pr_info["title"],
            "base_branch": pr_info["base_branch"],
            "head_branch": pr_info["head_branch"],
            "base_project": pr_base_name,
            "head_project": pr_head_name,
            "base_commit": base_sha[:8],
            "head_commit": head_sha[:8],
            "changed_files": changed,
            "changed_file_count": len(changed),
            "base_result": {
                "files_indexed": base_result.get("files_indexed", 0),
                "status": base_result.get("status", "indexed"),
            },
            "head_result": {
                "files_indexed": head_result.get("files_indexed", 0),
                "status": head_result.get("status", "indexed"),
            },
            "elapsed": f"{elapsed:.2f}s",
        }

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
            if chunk.name and chunk.name != "<anonymous>":
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
    """Extract import/require statements from source lines.

    Returns both module paths and imported symbol names for
    cross-file resolution across all supported languages.
    """
    imports = []
    in_go_import_block = False

    for line in lines:
        stripped = line.strip()

        if language == "python":
            if stripped.startswith("import "):
                # import os, sys  /  import os.path
                for mod in stripped[7:].split(","):
                    mod = mod.strip().split(" as ")[0]
                    imports.append(mod.split(".")[0])
                    if "." in mod:
                        imports.append(mod)
            elif stripped.startswith("from "):
                parts = stripped.split()
                if len(parts) >= 4 and parts[2] == "import":
                    mod = parts[1]
                    base = mod.split(".")[0]
                    if base:  # Skip empty base from relative imports like "from .foo"
                        imports.append(base)
                    if "." in mod:
                        imports.append(mod)
                    # Also record imported names
                    syms = " ".join(parts[3:])
                    for sym in syms.split(","):
                        sym = sym.strip().split(" as ")[0]
                        if sym and sym != "*":
                            imports.append(sym)

        elif language in ("javascript", "typescript", "tsx"):
            # import { foo, bar } from 'module'
            # import foo from 'module'
            # const foo = require('module')
            if "require(" in stripped or "import " in stripped:
                # Extract module path
                for q in ('"', "'", "`"):
                    if q in stripped:
                        start = stripped.index(q) + 1
                        idx = stripped.find(q, start)
                        if idx > start:
                            imports.append(stripped[start:idx])
                        break
                # Extract named imports: { foo, bar }
                if "{" in stripped and "}" in stripped:
                    brace_s = stripped.index("{") + 1
                    brace_e = stripped.index("}")
                    names = stripped[brace_s:brace_e]
                    for name in names.split(","):
                        name = name.strip().split(" as ")[0]
                        if name:
                            imports.append(name)
                # Default import: import Foo from
                elif stripped.startswith("import "):
                    toks = stripped.split()
                    if len(toks) >= 2 and toks[1] != "*":
                        name = toks[1].rstrip(",")
                        if name != "{" and name != "type":
                            imports.append(name)

        elif language == "go":
            if stripped == "import (":
                in_go_import_block = True
                continue
            if in_go_import_block:
                if stripped == ")":
                    in_go_import_block = False
                    continue
                # Handle aliased: alias "path"
                clean = stripped.split("//")[0].strip()
                if '"' in clean:
                    start = clean.index('"') + 1
                    end = clean.rindex('"')
                    if end > start:
                        path = clean[start:end]
                        imports.append(path)
                        # Also add the last segment as symbol
                        imports.append(path.rsplit("/", 1)[-1])
            elif stripped.startswith("import "):
                if '"' in stripped:
                    start = stripped.index('"') + 1
                    end = stripped.rindex('"')
                    if end > start:
                        path = stripped[start:end]
                        imports.append(path)
                        imports.append(path.rsplit("/", 1)[-1])

        elif language == "rust":
            if stripped.startswith("use "):
                full = stripped[4:].rstrip(";").strip()
                # use crate::module::Symbol
                parts = full.split("::")
                imports.append(parts[0])
                if len(parts) > 1:
                    imports.append(full)
                    # Extract {A, B} from use mod::{A, B}
                    last = parts[-1]
                    if "{" in last:
                        names = last.strip("{}").split(",")
                        for n in names:
                            n = n.strip()
                            if n and n != "self":
                                imports.append(n)
                    else:
                        imports.append(last)

        elif language == "java":
            if stripped.startswith("import "):
                full = stripped[7:].rstrip(";").strip()
                if full.startswith("static "):
                    full = full[7:]
                imports.append(full)
                # Also add the class name (last segment)
                parts = full.rsplit(".", 1)
                if len(parts) == 2 and parts[1] != "*":
                    imports.append(parts[1])

        elif language in ("c", "cpp"):
            if stripped.startswith("#include"):
                for ds, de in [("<", ">"), ('"', '"')]:
                    if ds in stripped:
                        start = stripped.index(ds) + 1
                        end = stripped.index(de, start)
                        if end > start:
                            imports.append(stripped[start:end])
                        break

        elif language == "ruby":
            if (stripped.startswith("require ")
                    or stripped.startswith("require_relative ")):
                for q in ('"', "'"):
                    if q in stripped:
                        start = stripped.index(q) + 1
                        idx = stripped.find(q, start)
                        if idx > start:
                            imports.append(stripped[start:idx])
                        break

        elif language == "swift":
            if stripped.startswith("import "):
                mod = stripped[7:].strip()
                imports.append(mod)

        elif language == "kotlin":
            if stripped.startswith("import "):
                full = stripped[7:].strip()
                imports.append(full)
                parts = full.rsplit(".", 1)
                if len(parts) == 2:
                    imports.append(parts[1])

        elif language == "scala":
            if stripped.startswith("import "):
                full = stripped[7:].strip()
                imports.append(full)

        elif language == "elixir":
            for kw in ("import ", "alias ", "use "):
                if stripped.startswith(kw):
                    mod = stripped[len(kw):].strip()
                    mod = mod.split(",")[0].strip()
                    imports.append(mod)
                    break

        elif language == "dart":
            if stripped.startswith("import "):
                for q in ("'", '"'):
                    if q in stripped:
                        start = stripped.index(q) + 1
                        idx = stripped.find(q, start)
                        if idx > start:
                            imports.append(stripped[start:idx])
                        break

        else:
            # Universal fallback: catch common import-like statements
            for kw in ("import ", "require ", "include ", "use ", "#include "):
                if stripped.startswith(kw):
                    rest = stripped[len(kw):].rstrip(";").strip()
                    # Extract quoted string if present
                    for q in ('"', "'", "<"):
                        if q in rest:
                            close = ">" if q == "<" else q
                            start = rest.index(q) + 1
                            end = rest.find(close, start)
                            if end > start:
                                imports.append(rest[start:end])
                            break
                    else:
                        # Bare identifier: import Foo.Bar
                        tok = rest.split()[0] if rest.split() else ""
                        tok = tok.rstrip(",;")
                        if tok:
                            imports.append(tok)
                    break

    return imports
