"""SQLite storage layer with WAL mode and FTS5 for BM25 search."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FileRecord:
    id: int
    path: str
    content_hash: str
    language: Optional[str]
    last_indexed: float
    summary: Optional[str] = None
    summary_hash: Optional[str] = None


@dataclass
class ChunkRecord:
    id: int
    file_id: int
    name: str
    kind: str  # function, class, method, module
    start_line: int
    end_line: int
    content: bytes  # zstd-compressed source code
    content_text: str  # plain text for FTS search
    scope_context: str  # e.g. "src/api/auth.py::AuthHandler"
    token_count: int


@dataclass
class SymbolRecord:
    id: int
    chunk_id: int
    name: str
    kind: str
    file_id: int


@dataclass
class ImportRecord:
    source_file: int
    target_file: int
    symbol: Optional[str]


SCHEMA_SQL = """
-- Files and their content hashes
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    content_hash TEXT NOT NULL,
    language TEXT,
    last_indexed REAL,
    summary TEXT,
    summary_hash TEXT
);

-- Code chunks
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    name TEXT,
    kind TEXT,
    start_line INTEGER,
    end_line INTEGER,
    content BLOB,
    content_text TEXT,
    scope_context TEXT,
    token_count INTEGER
);

-- FTS5 for BM25 search (uses content_text, not compressed content)
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    name, content_text, scope_context,
    content=chunks, content_rowid=id
);

-- Triggers to keep FTS5 in sync
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, name, content_text, scope_context)
    VALUES (new.id, new.name, new.content_text, new.scope_context);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, name, content_text, scope_context)
    VALUES ('delete', old.id, old.name, old.content_text, old.scope_context);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, name, content_text, scope_context)
    VALUES ('delete', old.id, old.name, old.content_text, old.scope_context);
    INSERT INTO chunks_fts(rowid, name, content_text, scope_context)
    VALUES (new.id, new.name, new.content_text, new.scope_context);
END;

-- Symbols (structure index)
CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE
);

-- Import relationships
CREATE TABLE IF NOT EXISTS imports (
    source_file INTEGER REFERENCES files(id) ON DELETE CASCADE,
    target_file INTEGER REFERENCES files(id) ON DELETE CASCADE,
    symbol TEXT
);

-- Project metadata
CREATE TABLE IF NOT EXISTS project (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated REAL
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source_file);
CREATE INDEX IF NOT EXISTS idx_imports_target ON imports(target_file);
"""


class Storage:
    """SQLite-backed storage with WAL mode and FTS5."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- File operations --

    def get_file_by_id(self, file_id: int) -> Optional[FileRecord]:
        row = self.conn.execute(
            "SELECT * FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if row is None:
            return None
        return FileRecord(**dict(row))

    def get_file(self, path: str) -> Optional[FileRecord]:
        row = self.conn.execute(
            "SELECT * FROM files WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return None
        return FileRecord(**dict(row))

    def upsert_file(
        self,
        path: str,
        content_hash: str,
        language: Optional[str] = None,
    ) -> int:
        now = time.time()
        self.conn.execute(
            """INSERT INTO files (path, content_hash, language, last_indexed)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                   content_hash = excluded.content_hash,
                   language = excluded.language,
                   last_indexed = excluded.last_indexed""",
            (path, content_hash, language, now),
        )
        self.conn.commit()
        # Return the file id
        row = self.conn.execute(
            "SELECT id FROM files WHERE path = ?", (path,)
        ).fetchone()
        return row["id"]

    def delete_file(self, path: str) -> None:
        self.conn.execute("DELETE FROM files WHERE path = ?", (path,))
        self.conn.commit()

    def get_all_files(self) -> list[FileRecord]:
        rows = self.conn.execute("SELECT * FROM files").fetchall()
        return [FileRecord(**dict(r)) for r in rows]

    # -- Chunk operations --

    def delete_chunks_for_file(self, file_id: int) -> None:
        self.conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))

    def insert_chunk(
        self,
        file_id: int,
        name: str,
        kind: str,
        start_line: int,
        end_line: int,
        content: bytes,
        content_text: str,
        scope_context: str,
        token_count: int,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO chunks
               (file_id, name, kind, start_line, end_line,
                content, content_text, scope_context, token_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, name, kind, start_line, end_line,
             content, content_text, scope_context, token_count),
        )
        return cur.lastrowid

    def insert_chunks_batch(self, chunks: list[tuple]) -> None:
        self.conn.executemany(
            """INSERT INTO chunks
               (file_id, name, kind, start_line, end_line,
                content, content_text, scope_context, token_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            chunks,
        )

    def get_chunks_for_file(self, file_id: int) -> list[ChunkRecord]:
        rows = self.conn.execute(
            "SELECT * FROM chunks WHERE file_id = ?", (file_id,)
        ).fetchall()
        return [ChunkRecord(**dict(r)) for r in rows]

    def search_fts(self, query: str, limit: int = 50) -> list[tuple[int, float]]:
        """BM25 search via FTS5. Returns list of (chunk_id, bm25_score)."""
        # Convert natural language query to FTS5 OR query for better recall
        fts_query = " OR ".join(
            word for word in query.split() if word.strip()
        )
        if not fts_query:
            return []
        try:
            rows = self.conn.execute(
                """SELECT rowid, bm25(chunks_fts) as score
                   FROM chunks_fts
                   WHERE chunks_fts MATCH ?
                   ORDER BY score
                   LIMIT ?""",
                (fts_query, limit),
            ).fetchall()
            return [(row["rowid"], row["score"]) for row in rows]
        except Exception:
            return []

    def get_chunk_by_id(self, chunk_id: int) -> Optional[ChunkRecord]:
        row = self.conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        if row is None:
            return None
        return ChunkRecord(**dict(row))

    def get_chunks_by_ids(self, chunk_ids: list[int]) -> list[ChunkRecord]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        rows = self.conn.execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})", chunk_ids
        ).fetchall()
        return [ChunkRecord(**dict(r)) for r in rows]

    # -- Symbol operations --

    def insert_symbol(
        self, chunk_id: int, name: str, kind: str, file_id: int
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO symbols (chunk_id, name, kind, file_id) VALUES (?, ?, ?, ?)",
            (chunk_id, name, kind, file_id),
        )
        return cur.lastrowid

    def search_symbols(
        self, name: str, kind: Optional[str] = None, limit: int = 20
    ) -> list[SymbolRecord]:
        if kind and kind != "any":
            rows = self.conn.execute(
                """SELECT * FROM symbols
                   WHERE name LIKE ? AND kind = ?
                   ORDER BY name LIMIT ?""",
                (f"{name}%", kind, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM symbols
                   WHERE name LIKE ?
                   ORDER BY name LIMIT ?""",
                (f"{name}%", limit),
            ).fetchall()
        return [SymbolRecord(**dict(r)) for r in rows]

    # -- Project metadata --

    def set_project_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            """INSERT INTO project (key, value, updated)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated = excluded.updated""",
            (key, value, time.time()),
        )
        self.conn.commit()

    def get_project_meta(self, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM project WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def get_stats(self) -> dict:
        """Get index statistics."""
        file_count = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        chunk_count = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        symbol_count = self.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        languages = self.conn.execute(
            "SELECT language, COUNT(*) as cnt FROM files WHERE language IS NOT NULL GROUP BY language ORDER BY cnt DESC"
        ).fetchall()
        return {
            "files": file_count,
            "chunks": chunk_count,
            "symbols": symbol_count,
            "languages": {r["language"]: r["cnt"] for r in languages},
        }

    def commit(self) -> None:
        self.conn.commit()
