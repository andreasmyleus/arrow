"""SQLite storage layer with WAL mode, FTS5, and multi-project support."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 4


@dataclass
class ProjectRecord:
    id: int
    name: str
    root_path: Optional[str]
    remote_url: Optional[str]
    git_branch: Optional[str]
    git_commit: Optional[str]
    is_remote: bool
    last_indexed: Optional[float]
    index_duration: Optional[str]
    language_stats: Optional[str]
    created: float
    updated: float


@dataclass
class FileRecord:
    id: int
    path: str
    content_hash: str
    language: Optional[str]
    last_indexed: float
    project_id: Optional[int] = None
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
    project_id: Optional[int] = None


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


SCHEMA_V2_SQL = """
-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    root_path TEXT,
    remote_url TEXT,
    git_branch TEXT,
    git_commit TEXT,
    is_remote INTEGER DEFAULT 0,
    last_indexed REAL,
    index_duration TEXT,
    language_stats TEXT,
    created REAL,
    updated REAL
);

-- Files and their content hashes (scoped by project)
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    language TEXT,
    last_indexed REAL,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    summary TEXT,
    summary_hash TEXT,
    UNIQUE(project_id, path)
);

-- Code chunks (project_id denormalized for fast search filtering)
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
    token_count INTEGER,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE
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

-- Frecency: track file access for ranking boosts
CREATE TABLE IF NOT EXISTS file_access (
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    access_count INTEGER DEFAULT 1,
    last_accessed REAL,
    UNIQUE(file_id)
);

-- Tool usage analytics
CREATE TABLE IF NOT EXISTS tool_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    project_id INTEGER,
    latency_ms REAL,
    tokens_saved INTEGER DEFAULT 0,
    timestamp REAL
);

-- Conversation context: track which chunks were sent
CREATE TABLE IF NOT EXISTS session_chunks (
    session_id TEXT NOT NULL,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    tokens_sent INTEGER DEFAULT 0,
    sent_at REAL,
    UNIQUE(session_id, chunk_id)
);

-- Long-term memory: persist knowledge across sessions
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    category TEXT NOT NULL DEFAULT 'general',
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    created REAL,
    updated REAL,
    access_count INTEGER DEFAULT 0,
    UNIQUE(project_id, category, key)
);

-- FTS index for memory recall
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    key, content, category,
    content=memories,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, key, content, category)
    VALUES (new.id, new.key, new.content, new.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, content, category)
    VALUES ('delete', old.id, old.key, old.content, old.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, content, category)
    VALUES ('delete', old.id, old.key, old.content, old.category);
    INSERT INTO memories_fts(rowid, key, content, category)
    VALUES (new.id, new.key, new.content, new.category);
END;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id);
CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source_file);
CREATE INDEX IF NOT EXISTS idx_imports_target ON imports(target_file);
"""


class Storage:
    """SQLite-backed storage with WAL mode, FTS5, and multi-project support."""

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
        """Initialize or migrate the database schema."""
        # Check if this is a v1 database (has old 'project' table, no 'projects')
        tables = {
            r[0] for r in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "project" in tables and "projects" not in tables:
            self._migrate_v1_to_v2()
        elif "projects" not in tables:
            self._conn.executescript(SCHEMA_V2_SQL)
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            self._conn.commit()

        # Migrate v2 -> v3 if needed
        if "projects" in tables and "file_access" not in tables:
            self._migrate_v2_to_v3()

        # Migrate v3 -> v4 if needed
        if "file_access" in tables and "memories" not in tables:
            self._migrate_v3_to_v4()

    def _migrate_v1_to_v2(self) -> None:
        """Migrate from v1 (single-project) to v2 (multi-project) schema."""
        conn = self._conn

        # Read old project metadata
        old_root = None
        old_meta = {}
        try:
            rows = conn.execute("SELECT key, value FROM project").fetchall()
            for r in rows:
                old_meta[r[0]] = r[1]
            old_root = old_meta.get("root_path")
        except Exception:
            pass

        now = time.time()

        # Create new tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                root_path TEXT,
                remote_url TEXT,
                git_branch TEXT,
                git_commit TEXT,
                is_remote INTEGER DEFAULT 0,
                last_indexed REAL,
                index_duration TEXT,
                language_stats TEXT,
                created REAL,
                updated REAL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)

        # Insert default project from old metadata
        project_name = Path(old_root).name if old_root else "default"
        conn.execute(
            """INSERT INTO projects (name, root_path, last_indexed,
               index_duration, language_stats, created, updated)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (project_name, old_root,
             float(old_meta.get("last_indexed", 0)) if old_meta.get("last_indexed") else None,
             old_meta.get("index_duration"),
             old_meta.get("language_stats"),
             now, now),
        )
        default_pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Migrate files table: add project_id, change UNIQUE constraint
        conn.execute("ALTER TABLE files ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE")
        conn.execute(f"UPDATE files SET project_id = {default_pid}")

        # Recreate files table with new UNIQUE constraint
        conn.execute("""
            CREATE TABLE files_new (
                id INTEGER PRIMARY KEY,
                path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                language TEXT,
                last_indexed REAL,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                summary TEXT,
                summary_hash TEXT,
                UNIQUE(project_id, path)
            )
        """)
        conn.execute("""
            INSERT INTO files_new (id, path, content_hash, language, last_indexed, project_id, summary, summary_hash)
            SELECT id, path, content_hash, language, last_indexed, project_id, summary, summary_hash FROM files
        """)
        conn.execute("DROP TABLE files")
        conn.execute("ALTER TABLE files_new RENAME TO files")

        # Add project_id to chunks
        conn.execute("ALTER TABLE chunks ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE")
        conn.execute(f"UPDATE chunks SET project_id = {default_pid}")

        # Rebuild FTS5
        try:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        except Exception:
            pass

        # Create new indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id)")

        # Drop old project table
        conn.execute("DROP TABLE IF EXISTS project")

        # Set schema version
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,)
        )
        conn.commit()

    def _migrate_v2_to_v3(self) -> None:
        """Migrate v2 -> v3: add frecency, analytics, session tables."""
        conn = self._conn
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_access (
                file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
                project_id INTEGER
                    REFERENCES projects(id) ON DELETE CASCADE,
                access_count INTEGER DEFAULT 1,
                last_accessed REAL,
                UNIQUE(file_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                project_id INTEGER,
                latency_ms REAL,
                tokens_saved INTEGER DEFAULT 0,
                timestamp REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_chunks (
                session_id TEXT NOT NULL,
                chunk_id INTEGER
                    REFERENCES chunks(id) ON DELETE CASCADE,
                tokens_sent INTEGER DEFAULT 0,
                sent_at REAL,
                UNIQUE(session_id, chunk_id)
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version"
            " (version) VALUES (?)",
            (3,)
        )
        conn.commit()

    def _migrate_v3_to_v4(self) -> None:
        """Migrate v3 -> v4: add long-term memory table."""
        conn = self._conn
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER
                    REFERENCES projects(id) ON DELETE CASCADE,
                category TEXT NOT NULL DEFAULT 'general',
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                created REAL,
                updated REAL,
                access_count INTEGER DEFAULT 0,
                UNIQUE(project_id, category, key)
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(
                key, content, category,
                content=memories,
                content_rowid=id
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai
            AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(
                    rowid, key, content, category
                ) VALUES (
                    new.id, new.key, new.content, new.category
                );
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad
            AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(
                    memories_fts, rowid, key, content, category
                ) VALUES (
                    'delete', old.id, old.key,
                    old.content, old.category
                );
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au
            AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(
                    memories_fts, rowid, key, content, category
                ) VALUES (
                    'delete', old.id, old.key,
                    old.content, old.category
                );
                INSERT INTO memories_fts(
                    rowid, key, content, category
                ) VALUES (
                    new.id, new.key, new.content, new.category
                );
            END
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version"
            " (version) VALUES (?)",
            (SCHEMA_VERSION,)
        )
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- Project operations --

    def create_project(
        self,
        name: str,
        root_path: Optional[str] = None,
        remote_url: Optional[str] = None,
        git_branch: Optional[str] = None,
        git_commit: Optional[str] = None,
        is_remote: bool = False,
    ) -> int:
        """Create or update a project. Returns project ID."""
        now = time.time()
        self.conn.execute(
            """INSERT INTO projects (name, root_path, remote_url, git_branch, git_commit,
                   is_remote, created, updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                   root_path = COALESCE(excluded.root_path, root_path),
                   remote_url = COALESCE(excluded.remote_url, remote_url),
                   git_branch = COALESCE(excluded.git_branch, git_branch),
                   git_commit = COALESCE(excluded.git_commit, git_commit),
                   updated = excluded.updated""",
            (name, root_path, remote_url, git_branch, git_commit, int(is_remote), now, now),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return row["id"]

    def get_project(self, project_id: int) -> Optional[ProjectRecord]:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def get_project_by_name(self, name: str) -> Optional[ProjectRecord]:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def get_project_by_root(self, root_path: str) -> Optional[ProjectRecord]:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE root_path = ?", (root_path,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def list_projects(self) -> list[ProjectRecord]:
        rows = self.conn.execute(
            "SELECT * FROM projects ORDER BY updated DESC"
        ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def update_project_git(
        self, project_id: int, branch: Optional[str], commit: Optional[str]
    ) -> None:
        self.conn.execute(
            """UPDATE projects SET git_branch = ?, git_commit = ?, updated = ?
               WHERE id = ?""",
            (branch, commit, time.time(), project_id),
        )
        self.conn.commit()

    def update_project_indexed(
        self, project_id: int, duration: str, language_stats: str
    ) -> None:
        self.conn.execute(
            """UPDATE projects SET last_indexed = ?, index_duration = ?,
               language_stats = ?, updated = ?
               WHERE id = ?""",
            (time.time(), duration, language_stats, time.time(), project_id),
        )
        self.conn.commit()

    def delete_project(self, project_id: int) -> None:
        """Delete a project and all its data (cascading)."""
        self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.conn.commit()

    def _row_to_project(self, row: sqlite3.Row) -> ProjectRecord:
        d = dict(row)
        d["is_remote"] = bool(d.get("is_remote", 0))
        return ProjectRecord(**d)

    # -- File operations --

    def get_file_by_id(self, file_id: int) -> Optional[FileRecord]:
        row = self.conn.execute(
            "SELECT * FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if row is None:
            return None
        return FileRecord(**dict(row))

    def get_file(self, path: str, project_id: Optional[int] = None) -> Optional[FileRecord]:
        if project_id is not None:
            row = self.conn.execute(
                "SELECT * FROM files WHERE path = ? AND project_id = ?",
                (path, project_id),
            ).fetchone()
        else:
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
        project_id: Optional[int] = None,
    ) -> int:
        now = time.time()
        self.conn.execute(
            """INSERT INTO files (path, content_hash, language, last_indexed, project_id)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(project_id, path) DO UPDATE SET
                   content_hash = excluded.content_hash,
                   language = excluded.language,
                   last_indexed = excluded.last_indexed""",
            (path, content_hash, language, now, project_id),
        )
        self.conn.commit()
        if project_id is not None:
            row = self.conn.execute(
                "SELECT id FROM files WHERE path = ? AND project_id = ?",
                (path, project_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT id FROM files WHERE path = ?", (path,)
            ).fetchone()
        return row["id"]

    def delete_file(self, path: str, project_id: Optional[int] = None) -> None:
        if project_id is not None:
            self.conn.execute(
                "DELETE FROM files WHERE path = ? AND project_id = ?",
                (path, project_id),
            )
        else:
            self.conn.execute("DELETE FROM files WHERE path = ?", (path,))
        self.conn.commit()

    def get_all_files(self, project_id: Optional[int] = None) -> list[FileRecord]:
        if project_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM files WHERE project_id = ?", (project_id,)
            ).fetchall()
        else:
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
        project_id: Optional[int] = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO chunks
               (file_id, name, kind, start_line, end_line,
                content, content_text, scope_context, token_count, project_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, name, kind, start_line, end_line,
             content, content_text, scope_context, token_count, project_id),
        )
        return cur.lastrowid

    def insert_chunks_batch(self, chunks: list[tuple]) -> None:
        """Insert chunks in batch. Tuples must have 10 elements (including project_id)."""
        self.conn.executemany(
            """INSERT INTO chunks
               (file_id, name, kind, start_line, end_line,
                content, content_text, scope_context, token_count, project_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            chunks,
        )

    def get_chunks_for_file(self, file_id: int) -> list[ChunkRecord]:
        rows = self.conn.execute(
            "SELECT * FROM chunks WHERE file_id = ?", (file_id,)
        ).fetchall()
        return [ChunkRecord(**dict(r)) for r in rows]

    def search_fts(
        self, query: str, limit: int = 50, project_id: Optional[int] = None
    ) -> list[tuple[int, float]]:
        """BM25 search via FTS5. Returns list of (chunk_id, bm25_score)."""
        fts_query = " OR ".join(
            word for word in query.split() if word.strip()
        )
        if not fts_query:
            return []
        try:
            if project_id is not None:
                # Join with chunks table to filter by project
                rows = self.conn.execute(
                    """SELECT cf.rowid, bm25(chunks_fts) as score
                       FROM chunks_fts cf
                       JOIN chunks c ON c.id = cf.rowid
                       WHERE cf.chunks_fts MATCH ?
                       AND c.project_id = ?
                       ORDER BY score
                       LIMIT ?""",
                    (fts_query, project_id, limit),
                ).fetchall()
            else:
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
        self, name: str, kind: Optional[str] = None, limit: int = 20,
        project_id: Optional[int] = None,
    ) -> list[SymbolRecord]:
        if project_id is not None:
            if kind and kind != "any":
                rows = self.conn.execute(
                    """SELECT s.* FROM symbols s
                       JOIN files f ON f.id = s.file_id
                       WHERE s.name LIKE ? AND s.kind = ? AND f.project_id = ?
                       ORDER BY s.name LIMIT ?""",
                    (f"{name}%", kind, project_id, limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT s.* FROM symbols s
                       JOIN files f ON f.id = s.file_id
                       WHERE s.name LIKE ? AND f.project_id = ?
                       ORDER BY s.name LIMIT ?""",
                    (f"{name}%", project_id, limit),
                ).fetchall()
        else:
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

    # -- Project metadata (legacy compat) --

    def set_project_meta(self, key: str, value: str) -> None:
        """Legacy method — stores in first project's metadata or ignores."""
        pass

    def get_project_meta(self, key: str) -> Optional[str]:
        """Legacy method — returns from first project's data."""
        if key == "root_path":
            projects = self.list_projects()
            if projects:
                return projects[0].root_path
        return None

    # -- Stats --

    def get_stats(self, project_id: Optional[int] = None) -> dict:
        """Get index statistics, optionally scoped to a project."""
        if project_id is not None:
            file_count = self.conn.execute(
                "SELECT COUNT(*) FROM files WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
            chunk_count = self.conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
            symbol_count = self.conn.execute(
                """SELECT COUNT(*) FROM symbols s JOIN files f ON f.id = s.file_id
                   WHERE f.project_id = ?""", (project_id,)
            ).fetchone()[0]
            languages = self.conn.execute(
                """SELECT language, COUNT(*) as cnt FROM files
                   WHERE language IS NOT NULL AND project_id = ?
                   GROUP BY language ORDER BY cnt DESC""",
                (project_id,),
            ).fetchall()
        else:
            file_count = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            chunk_count = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            symbol_count = self.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
            languages = self.conn.execute(
                """SELECT language, COUNT(*) as cnt FROM files
                   WHERE language IS NOT NULL
                   GROUP BY language ORDER BY cnt DESC"""
            ).fetchall()
        return {
            "files": file_count,
            "chunks": chunk_count,
            "symbols": symbol_count,
            "languages": {r["language"]: r["cnt"] for r in languages},
        }

    def get_callers_of_symbol(
        self, symbol_name: str, project_id: Optional[int] = None
    ) -> list[dict]:
        """Find all chunks that reference a symbol name (callers/dependents).

        Searches content_text for the symbol name in chunks that are NOT
        the definition itself.
        """
        if project_id is not None:
            rows = self.conn.execute(
                """SELECT c.id, c.name, c.kind, c.start_line, c.end_line,
                          c.content_text, c.file_id, c.project_id,
                          f.path as file_path
                   FROM chunks c
                   JOIN files f ON f.id = c.file_id
                   WHERE c.content_text LIKE ?
                   AND c.name != ?
                   AND c.project_id = ?
                   LIMIT 50""",
                (f"%{symbol_name}%", symbol_name, project_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT c.id, c.name, c.kind, c.start_line, c.end_line,
                          c.content_text, c.file_id, c.project_id,
                          f.path as file_path
                   FROM chunks c
                   JOIN files f ON f.id = c.file_id
                   WHERE c.content_text LIKE ?
                   AND c.name != ?
                   LIMIT 50""",
                (f"%{symbol_name}%", symbol_name),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_test_files(self, project_id: Optional[int] = None) -> list[FileRecord]:
        """Get all test files in a project (files matching test patterns)."""
        if project_id is not None:
            rows = self.conn.execute(
                """SELECT * FROM files WHERE project_id = ?
                   AND (path LIKE '%test_%' OR path LIKE '%_test.%'
                        OR path LIKE '%tests/%' OR path LIKE '%spec/%'
                        OR path LIKE '%__tests__%')""",
                (project_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM files
                   WHERE path LIKE '%test_%' OR path LIKE '%_test.%'
                        OR path LIKE '%tests/%' OR path LIKE '%spec/%'
                        OR path LIKE '%__tests__%'"""
            ).fetchall()
        return [FileRecord(**dict(r)) for r in rows]

    def find_chunks_referencing(
        self, symbol_name: str, file_ids: list[int]
    ) -> list[dict]:
        """Find chunks in specific files that reference a symbol."""
        if not file_ids:
            return []
        placeholders = ",".join("?" for _ in file_ids)
        rows = self.conn.execute(
            f"""SELECT c.id, c.name, c.kind, c.start_line, c.end_line,
                       c.content_text, c.file_id, f.path as file_path
                FROM chunks c
                JOIN files f ON f.id = c.file_id
                WHERE c.file_id IN ({placeholders})
                AND c.content_text LIKE ?""",
            file_ids + [f"%{symbol_name}%"],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_importers_of_file(
        self, file_path: str, project_id: Optional[int] = None
    ) -> list[dict]:
        """Find all files that import from a given file (by stem or module name)."""
        stem = Path(file_path).stem
        if project_id is not None:
            rows = self.conn.execute(
                """SELECT DISTINCT f.id, f.path, f.language, f.project_id
                   FROM imports i
                   JOIN files f ON f.id = i.source_file
                   WHERE i.symbol LIKE ?
                   AND f.project_id = ?""",
                (f"%{stem}%", project_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT DISTINCT f.id, f.path, f.language, f.project_id
                   FROM imports i
                   JOIN files f ON f.id = i.source_file
                   WHERE i.symbol LIKE ?""",
                (f"%{stem}%",),
            ).fetchall()
        return [dict(r) for r in rows]

    def resolve_symbol_across_repos(
        self, symbol_name: str, exclude_project_id: Optional[int] = None
    ) -> list[dict]:
        """Find a symbol definition across all indexed repos.

        Used for cross-repo import resolution.
        """
        if exclude_project_id is not None:
            rows = self.conn.execute(
                """SELECT s.name, s.kind, f.path, f.project_id, p.name as project_name,
                          c.start_line, c.end_line, c.content_text
                   FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   JOIN chunks c ON c.id = s.chunk_id
                   JOIN projects p ON p.id = f.project_id
                   WHERE s.name = ?
                   AND f.project_id != ?
                   LIMIT 20""",
                (symbol_name, exclude_project_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT s.name, s.kind, f.path, f.project_id, p.name as project_name,
                          c.start_line, c.end_line, c.content_text
                   FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   JOIN chunks c ON c.id = s.chunk_id
                   JOIN projects p ON p.id = f.project_id
                   WHERE s.name = ?
                   LIMIT 20""",
                (symbol_name,),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_fts_hits(self, query: str, project_id: Optional[int] = None) -> int:
        """Count how many chunks match an FTS query. Used for budget estimation."""
        fts_query = " OR ".join(w for w in query.split() if w.strip())
        if not fts_query:
            return 0
        try:
            if project_id is not None:
                row = self.conn.execute(
                    """SELECT COUNT(*) FROM chunks_fts cf
                       JOIN chunks c ON c.id = cf.rowid
                       WHERE cf.chunks_fts MATCH ? AND c.project_id = ?""",
                    (fts_query, project_id),
                ).fetchone()
            else:
                row = self.conn.execute(
                    "SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH ?",
                    (fts_query,),
                ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    # -- Frecency tracking --

    def record_file_access(
        self, file_id: int, project_id: Optional[int] = None
    ) -> None:
        """Record that a file was accessed (for frecency ranking)."""
        now = time.time()
        self.conn.execute(
            """INSERT INTO file_access
               (file_id, project_id, access_count, last_accessed)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(file_id) DO UPDATE SET
                   access_count = access_count + 1,
                   last_accessed = ?""",
            (file_id, project_id, now, now),
        )
        self.conn.commit()

    def get_frecency_scores(
        self, project_id: Optional[int] = None
    ) -> dict[int, float]:
        """Get frecency scores for files. Higher = more relevant.

        Score = access_count * recency_decay where decay halves
        every 24 hours.
        """
        now = time.time()
        if project_id is not None:
            rows = self.conn.execute(
                """SELECT file_id, access_count, last_accessed
                   FROM file_access WHERE project_id = ?""",
                (project_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT file_id, access_count, last_accessed"
                " FROM file_access"
            ).fetchall()

        scores = {}
        for row in rows:
            age_hours = (now - row["last_accessed"]) / 3600
            decay = 0.5 ** (age_hours / 24)
            scores[row["file_id"]] = row["access_count"] * decay
        return scores

    # -- Tool analytics --

    def record_tool_call(
        self,
        tool_name: str,
        latency_ms: float,
        tokens_saved: int = 0,
        project_id: Optional[int] = None,
    ) -> None:
        """Record a tool invocation for analytics."""
        self.conn.execute(
            """INSERT INTO tool_analytics
               (tool_name, project_id, latency_ms,
                tokens_saved, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (tool_name, project_id, latency_ms,
             tokens_saved, time.time()),
        )
        self.conn.commit()

    def get_tool_analytics(
        self, since: Optional[float] = None
    ) -> list[dict]:
        """Get aggregated tool usage analytics."""
        if since:
            rows = self.conn.execute(
                """SELECT tool_name,
                          COUNT(*) as calls,
                          AVG(latency_ms) as avg_latency_ms,
                          SUM(tokens_saved) as total_tokens_saved
                   FROM tool_analytics
                   WHERE timestamp >= ?
                   GROUP BY tool_name
                   ORDER BY calls DESC""",
                (since,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT tool_name,
                          COUNT(*) as calls,
                          AVG(latency_ms) as avg_latency_ms,
                          SUM(tokens_saved) as total_tokens_saved
                   FROM tool_analytics
                   GROUP BY tool_name
                   ORDER BY calls DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    # -- Session / conversation context --

    def record_sent_chunk(
        self, session_id: str, chunk_id: int,
        tokens: int = 0,
    ) -> None:
        """Record that a chunk was sent to Claude in a session."""
        self.conn.execute(
            """INSERT OR IGNORE INTO session_chunks
               (session_id, chunk_id, tokens_sent, sent_at)
               VALUES (?, ?, ?, ?)""",
            (session_id, chunk_id, tokens, time.time()),
        )
        self.conn.commit()

    def get_sent_chunk_ids(self, session_id: str) -> set[int]:
        """Get chunk IDs already sent in this session."""
        rows = self.conn.execute(
            "SELECT chunk_id FROM session_chunks"
            " WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        return {r["chunk_id"] for r in rows}

    def get_session_token_total(self, session_id: str) -> int:
        """Get total tokens sent in this session."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(tokens_sent), 0) as total"
            " FROM session_chunks WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["total"] if row else 0

    def get_session_chunks_detail(
        self, session_id: str
    ) -> list[dict]:
        """Get all sent chunks with their details for compaction."""
        rows = self.conn.execute(
            """SELECT sc.chunk_id, sc.tokens_sent, sc.sent_at,
                      c.name, c.kind, c.start_line, c.end_line,
                      c.file_id, c.content_text, c.project_id
               FROM session_chunks sc
               JOIN chunks c ON c.id = sc.chunk_id
               WHERE sc.session_id = ?
               ORDER BY sc.sent_at""",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_session(self, session_id: str) -> None:
        """Clear session context (e.g. on conversation reset)."""
        self.conn.execute(
            "DELETE FROM session_chunks WHERE session_id = ?",
            (session_id,),
        )
        self.conn.commit()

    # -- Long-term memory --

    def store_memory(
        self, key: str, content: str,
        category: str = "general",
        project_id: Optional[int] = None,
    ) -> int:
        """Store or update a memory. Returns memory ID."""
        now = time.time()
        # ON CONFLICT doesn't trigger for NULL project_id,
        # so check manually.
        existing = self.conn.execute(
            "SELECT id FROM memories"
            " WHERE project_id IS ? AND category = ? AND key = ?",
            (project_id, category, key),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE memories SET content = ?, updated = ?"
                " WHERE id = ?",
                (content, now, existing["id"]),
            )
            self.conn.commit()
            return existing["id"]
        self.conn.execute(
            """INSERT INTO memories
               (project_id, category, key, content,
                created, updated, access_count)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (project_id, category, key, content, now, now),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM memories"
            " WHERE project_id IS ? AND category = ? AND key = ?",
            (project_id, category, key),
        ).fetchone()
        return row["id"] if row else 0

    def recall_memory(
        self, query: str,
        category: Optional[str] = None,
        project_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Recall memories by FTS search. Bumps access count."""
        where = []
        params: list = []
        if category:
            where.append("m.category = ?")
            params.append(category)
        if project_id is not None:
            where.append("m.project_id = ?")
            params.append(project_id)

        where_sql = (
            " AND " + " AND ".join(where) if where else ""
        )

        # Join terms with OR so partial matches work
        # (FTS5 default is implicit AND which is too strict)
        terms = query.strip().split()
        if len(terms) > 1:
            fts_query = " OR ".join(terms)
        else:
            fts_query = query

        try:
            rows = self.conn.execute(
                f"""SELECT m.id, m.project_id, m.category,
                           m.key, m.content, m.created, m.updated,
                           m.access_count
                    FROM memories_fts fts
                    JOIN memories m ON m.id = fts.rowid
                    WHERE memories_fts MATCH ?{where_sql}
                    ORDER BY rank
                    LIMIT ?""",
                [fts_query, *params, limit],
            ).fetchall()
        except Exception:
            rows = []

        results = [dict(r) for r in rows]
        # Bump access count for recalled memories
        for mem in results:
            self.conn.execute(
                "UPDATE memories SET access_count ="
                " access_count + 1 WHERE id = ?",
                (mem["id"],),
            )
        if results:
            self.conn.commit()
        return results

    def list_memories(
        self, category: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> list[dict]:
        """List all memories, optionally filtered."""
        where = []
        params: list = []
        if category:
            where.append("category = ?")
            params.append(category)
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)

        where_sql = (
            " WHERE " + " AND ".join(where) if where else ""
        )

        rows = self.conn.execute(
            f"""SELECT id, project_id, category, key, content,
                       created, updated, access_count
                FROM memories{where_sql}
                ORDER BY updated DESC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_memory(
        self, memory_id: Optional[int] = None,
        key: Optional[str] = None,
        category: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> int:
        """Delete memory by ID or by key+category. Returns count."""
        if memory_id is not None:
            self.conn.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )
        elif key is not None:
            if category:
                self.conn.execute(
                    "DELETE FROM memories"
                    " WHERE key = ? AND category = ?"
                    " AND project_id IS ?",
                    (key, category, project_id),
                )
            else:
                self.conn.execute(
                    "DELETE FROM memories"
                    " WHERE key = ? AND project_id IS ?",
                    (key, project_id),
                )
        else:
            return 0
        count = self.conn.execute(
            "SELECT changes()"
        ).fetchone()[0]
        self.conn.commit()
        return count

    # -- Stale index detection --

    def get_index_staleness(
        self, project_id: int
    ) -> Optional[dict]:
        """Check how stale the index is vs the working tree."""
        project = self.get_project(project_id)
        if not project or not project.root_path:
            return None

        root = Path(project.root_path)
        if not root.is_dir():
            return None

        indexed_files = {
            f.path: f.content_hash
            for f in self.get_all_files(project_id=project_id)
        }
        return {
            "project": project.name,
            "indexed_files": len(indexed_files),
            "last_indexed": project.last_indexed,
        }

    # -- Dead code detection --

    def find_dead_code(
        self, project_id: Optional[int] = None
    ) -> list[dict]:
        """Find functions/methods with zero callers in the index."""
        if project_id is not None:
            symbols = self.conn.execute(
                """SELECT s.name, s.kind, f.path, s.chunk_id
                   FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   WHERE f.project_id = ?
                   AND s.kind IN ('function', 'method')""",
                (project_id,),
            ).fetchall()
        else:
            symbols = self.conn.execute(
                """SELECT s.name, s.kind, f.path, s.chunk_id
                   FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   WHERE s.kind IN ('function', 'method')"""
            ).fetchall()

        dead = []
        for sym in symbols:
            name = sym["name"]
            # Skip private/dunder/test/main
            if (name.startswith("_")
                    or name.startswith("test")
                    or name in ("main", "setup", "teardown")):
                continue

            # Check if any other chunk references this name
            count = self.conn.execute(
                """SELECT COUNT(*) FROM chunks
                   WHERE content_text LIKE ?
                   AND id != ?""",
                (f"%{name}%", sym["chunk_id"]),
            ).fetchone()[0]

            if count == 0:
                chunk = self.get_chunk_by_id(sym["chunk_id"])
                dead.append({
                    "name": name,
                    "kind": sym["kind"],
                    "file": sym["path"],
                    "lines": (
                        f"{chunk.start_line}-{chunk.end_line}"
                        if chunk else "?"
                    ),
                })
        return dead

    def commit(self) -> None:
        self.conn.commit()
