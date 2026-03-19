"""Arrow MCP Server — Extended Demo (9-17)

Multi-project, cross-repo, export/import, conversation awareness, analytics.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

os.environ["ARROW_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["ARROW_VECTOR_PATH"] = tempfile.mktemp(suffix=".usearch")

from arrow.server import (
    index_codebase,
    index_github_content,
    list_projects,
    search_code,
    get_context,
    search_structure,
    resolve_symbol,
    export_index,
    import_index,
    file_summary,
    trace_dependencies,
    tool_analytics,
    project_summary,
    remove_project,
    context_pressure,
)


def p(label, data):
    """Pretty-print JSON result."""
    if isinstance(data, str):
        data = json.loads(data)
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    return data


# ── SETUP: Index Arrow's own codebase ─────────────────────────────────
print("Setting up: indexing Arrow's codebase...")
r = json.loads(index_codebase(str(Path(__file__).parent / "src" / "arrow")))
print(f"  Indexed: {r['files_indexed']} files, {r['chunks_created']} chunks")
print(f"  Project: {r['project_name']}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 9: Multi-Project Indexing
# ══════════════════════════════════════════════════════════════════════
d = p("DEMO 9: Multi-Project Indexing (index remote GitHub content)", None) if False else None

print(f"\n{'='*70}")
print("  DEMO 9: Multi-Project Indexing (index remote GitHub content)")
print(f"{'='*70}")

# Index a fake remote project (simulating GitHub MCP content)
r9 = json.loads(index_github_content(
    owner="fastapi",
    repo="fastapi",
    branch="main",
    files=[
        {"path": "app/main.py", "content": (
            "from fastapi import FastAPI\n"
            "from app.routes import api_router\n"
            "from app.db import get_database\n\n"
            "app = FastAPI(title='MyAPI', version='2.0')\n"
            "app.include_router(api_router)\n\n"
            "@app.on_event('startup')\n"
            "async def startup():\n"
            "    await get_database().connect()\n"
        )},
        {"path": "app/routes.py", "content": (
            "from fastapi import APIRouter, Depends\n"
            "from app.db import get_database\n"
            "from app.auth import require_auth\n\n"
            "api_router = APIRouter(prefix='/api/v2')\n\n"
            "@api_router.get('/users')\n"
            "async def list_users(db=Depends(get_database)):\n"
            "    return await db.fetch_all('SELECT * FROM users')\n\n"
            "@api_router.post('/users')\n"
            "async def create_user(data: dict, auth=Depends(require_auth)):\n"
            "    return await get_database().execute(\n"
            "        'INSERT INTO users VALUES (:name)', data\n"
            "    )\n"
        )},
        {"path": "app/db.py", "content": (
            "import databases\n\n"
            "DATABASE_URL = 'postgresql://localhost/myapp'\n"
            "_db = databases.Database(DATABASE_URL)\n\n"
            "def get_database():\n"
            "    return _db\n\n"
            "async def run_migration(version: str):\n"
            "    \"\"\"Run database migration to target version.\"\"\"\n"
            "    async with _db.connection() as conn:\n"
            "        await conn.execute(f'SELECT migrate({version})')\n"
        )},
        {"path": "app/auth.py", "content": (
            "from fastapi import Header, HTTPException\n"
            "import jwt\n\n"
            "SECRET = 'super-secret-key'\n\n"
            "def require_auth(authorization: str = Header(...)):\n"
            "    try:\n"
            "        token = authorization.split(' ')[1]\n"
            "        return jwt.decode(token, SECRET, algorithms=['HS256'])\n"
            "    except Exception:\n"
            "        raise HTTPException(status_code=401, detail='Invalid token')\n\n"
            "def create_token(user_id: int) -> str:\n"
            "    return jwt.encode({'user_id': user_id}, SECRET, algorithm='HS256')\n"
        )},
    ],
))
print(f"  Remote project indexed: {r9['project_name']}")
print(f"  Files: {r9['files_indexed']}, Chunks: {r9['chunks_created']}")

# List all projects
projects = json.loads(list_projects())
print(f"\n  All indexed projects ({len(projects)}):")
for proj in projects:
    print(f"    {proj['name']:30s}  {proj['files']} files, {proj['chunks']} chunks"
          f"  branch={proj.get('git_branch', 'N/A')}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 10: Cross-Repo Symbol Resolution
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 10: Cross-Repo Symbol Resolution")
print(f"{'='*70}")

for symbol in ["get_database", "require_auth", "Storage"]:
    r10 = json.loads(resolve_symbol(symbol))
    print(f"\n  resolve_symbol('{symbol}') -> {r10['total']} definitions:")
    for sym in r10['results']:
        print(f"    [{sym['kind']:10s}] {sym['project']:30s}  {sym['file']}:{sym['lines']}  {sym['symbol']}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 11: Scoped vs Cross-Project Search
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 11: Scoped vs Cross-Project Search")
print(f"{'='*70}")

# Cross-project search
r11a = json.loads(search_code("database connection", limit=5))
print(f"\n  search_code('database connection') — ALL projects ({len(r11a)} results):")
for res in r11a[:5]:
    print(f"    {res['project']:30s}  {res['file']:30s}  score={res.get('score', '?')}")

# Scoped search
r11b = json.loads(search_code("database connection", limit=5, project="fastapi/fastapi"))
print(f"\n  search_code('database connection', project='fastapi/fastapi') ({len(r11b)} results):")
for res in r11b[:5]:
    print(f"    {res['project']:30s}  {res['file']:30s}  score={res.get('score', '?')}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 12: Export & Import Index
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 12: Export & Import Index")
print(f"{'='*70}")

bundle = json.loads(export_index("fastapi/fastapi"))
stats = bundle['stats']
print(f"\n  Exported fastapi/fastapi:")
print(f"    Files:   {stats['files']}")
print(f"    Chunks:  {stats['chunks']}")
print(f"    Symbols: {stats['symbols']}")
print(f"    Imports: {stats['imports']}")
print(f"    Bundle size: {len(json.dumps(bundle)):,d} bytes")

# Remove and re-import
json.loads(remove_project("fastapi/fastapi"))
print(f"\n  Removed fastapi/fastapi")
projects_after = json.loads(list_projects())
print(f"  Projects remaining: {len(projects_after)}")

# Import it back
r12 = json.loads(import_index(json.dumps(bundle)))
print(f"\n  Re-imported: {r12.get('project', r12.get('project_name', '?'))}")
print(f"  Files: {r12.get('files_imported', r12.get('files', '?'))}")
print(f"  Chunks: {r12.get('chunks_imported', r12.get('chunks', '?'))}")

projects_after2 = json.loads(list_projects())
print(f"  Projects now: {len(projects_after2)}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 13: File Summary
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 13: File Summary (detailed file breakdown)")
print(f"{'='*70}")

for fpath in ["app/routes.py", "app/auth.py"]:
    r13 = json.loads(file_summary(fpath, project="fastapi/fastapi"))
    if "error" in r13:
        print(f"\n  file_summary('{fpath}'): {r13['error']}")
        continue
    print(f"\n  file_summary('{fpath}'):")
    print(f"    Language: {r13['language']}, Tokens: {r13['total_tokens']}, Chunks: {r13['total_chunks']}")
    if r13.get('functions'):
        print(f"    Functions:")
        for fn in r13['functions']:
            print(f"      {fn['name']:30s}  lines {fn['lines']}  ({fn['tokens']} tokens)")
    if r13.get('classes'):
        print(f"    Classes:")
        for cls in r13['classes']:
            print(f"      {cls['name']:30s}  lines {cls['lines']}  ({cls['tokens']} tokens)")

# ══════════════════════════════════════════════════════════════════════
# DEMO 14: Trace Dependencies
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 14: Trace Dependencies")
print(f"{'='*70}")

for fpath in ["app/main.py", "app/db.py"]:
    r14 = json.loads(trace_dependencies(fpath, project="fastapi/fastapi"))
    if "error" in r14:
        print(f"\n  trace_dependencies('{fpath}'): {r14['error']}")
        continue
    print(f"\n  trace_dependencies('{fpath}'):")
    print(f"    Imports: {r14['imports']}")
    print(f"    Imported by: {r14['imported_by']}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 15: Conversation-Aware Context
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 15: Conversation-Aware Context (no duplicate chunks)")
print(f"{'='*70}")

# First call — gets fresh results
r15a = json.loads(get_context("search and retrieval", token_budget=8000))
chunks1 = [c['name'] for c in r15a.get('chunks', [])]
print(f"\n  First call:  {r15a['tokens_used']} tokens, {r15a['chunks_returned']} chunks")
print(f"    Chunks: {', '.join(chunks1[:6])}{'...' if len(chunks1) > 6 else ''}")

# Second call — same query, should skip already-sent chunks
r15b = json.loads(get_context("search and retrieval", token_budget=8000))
chunks2 = [c['name'] for c in r15b.get('chunks', [])]
print(f"\n  Second call: {r15b['tokens_used']} tokens, {r15b['chunks_returned']} chunks")
if chunks2:
    print(f"    Chunks: {', '.join(chunks2[:6])}{'...' if len(chunks2) > 6 else ''}")
else:
    print(f"    (no new chunks — all already sent!)")

# Check context pressure
r15c = json.loads(context_pressure())
print(f"\n  Context pressure: {r15c['context_pressure_pct']}% "
      f"({r15c['session_tokens']} / {r15c['compact_threshold']} tokens)")
print(f"  Chunks sent this session: {r15c['chunks_sent']}")
print(f"  Status: {r15c['status']}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 16: Tool Analytics
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 16: Tool Analytics")
print(f"{'='*70}")

r16 = json.loads(tool_analytics(hours=1))
print(f"\n  Tool usage in last hour:")
print(f"  Total calls: {r16['total_calls']}")
print(f"  Total tokens saved: {r16['total_tokens_saved']:,d}")
if r16['tools']:
    print(f"\n  {'Tool':<30s} {'Calls':>6s} {'Avg ms':>8s} {'Tokens Saved':>14s}")
    print(f"  {'-'*60}")
    for t in sorted(r16['tools'], key=lambda x: x['calls'], reverse=True):
        name = t.get('tool_name', t.get('tool', '?'))
        print(f"  {name:<30s} {t['calls']:>6d} {t.get('avg_latency_ms', 0):>8.1f} "
              f"{(t.get('total_tokens_saved') or 0):>14,d}")

# ══════════════════════════════════════════════════════════════════════
# DEMO 17: Project Summary
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("  DEMO 17: Project Summary")
print(f"{'='*70}")

r17 = json.loads(project_summary())
if "error" not in r17:
    print(f"\n  {json.dumps(r17, indent=2)[:1500]}")
else:
    print(f"\n  {r17}")

# ── Done ──────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  ALL DEMOS COMPLETE (9-17)")
print(f"{'='*70}")

# Cleanup
db = os.environ.get("ARROW_DB_PATH")
vec = os.environ.get("ARROW_VECTOR_PATH")
if db and os.path.exists(db):
    os.unlink(db)
if vec and os.path.exists(vec):
    os.unlink(vec)
