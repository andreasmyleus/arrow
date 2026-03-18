# cursor-for-claude — MCP Server Plan

> En lokal, högpresterande MCP-server som ger Claude Code samma indexering, cachning och kontexthantering som Cursor IDE.

## Målgrupp & kontext

- **Alla utvecklare** — språkagnostiskt, hårdvaruagnostiskt, OS-agnostiskt
- **Alla kodbasar** — tree-sitter stödjer 64+ språk, inget hårdkodat
- **Alla plattformar** — macOS, Linux, Windows, Docker, ARM, x86
- **Alla AI-kodverktyg** — MCP-standarden funkar med Claude Code, Cursor, Windsurf, Copilot m.fl.
- **Distribution:** `pip install cursor-for-claude` eller Docker

## Problemet

Claude Code läser filer on-demand (Grep/Glob/Read) vilket äter context window. När fönstret fylls komprimeras konversationen — det tar tid och tappar information. Cursor löser detta med pre-indexering, smart retrieval och token-budget-hantering. Vi bygger samma sak som en MCP-server.

## Vad Cursor gör (som vi replikerar)

1. **AST-baserad chunking** — tree-sitter parsar kod i semantiska enheter (funktioner, klasser)
2. **Embedding-indexering** — varje chunk omvandlas till en vektor (lista med siffror) som fångar kodens "betydelse"
3. **Hybrid retrieval** — kombinerar textsökning (BM25) och semantisk sökning (vektorer)
4. **Custom reranker** — filtrerar ~500k kandidat-tokens ner till ~8k mest relevanta
5. **Inkrementell sync** — Merkle trees / content-hash för att bara omindexera ändrade filer
6. **Token-budget** — skickar aldrig mer kontext än nödvändigt till LLM:en

## Designprinciper

- **100% lokalt** — inga externa API:er, inga moln-dependencies, allt på CPU
- **Cutting edge prestanda** — snabbaste libbet för varje komponent (se benchmarks nedan)
- **Enkla, vettiga open source-projekt** — inga tunga frameworks, minimala dependencies
- **Drop-in för Claude Code** — konfigurera en gång, alltid aktiv
- **Dockeriserad** — körs på vilken hårdvara som helst (x86, ARM, Apple Silicon)
- **Multi-plattform** — macOS, Linux, Windows via Docker eller native install

---

## Tech Stack

| Komponent | Bibliotek | Språk | Varför | Benchmark |
|-----------|-----------|-------|--------|-----------|
| **MCP SDK** | `mcp` (Python SDK 2.6+) | Python | Officiell SDK, `@mcp.tool()` dekoratorer | — |
| **AST-parsning** | `tree-sitter` + `tree-sitter-languages` | C-kärna, Python-bindings | Industristandard, inkrementell parsning, **64+ språk automatiskt** | <100ms för 10k-raders fil |
| **Vektor-sökning** | `usearch` | C++-kärna, Python-bindings | Single-header, f16/i8 kvantisering | **20x snabbare** än FAISS flat |
| **Full-text/BM25** | SQLite FTS5 | C | Inbyggt i SQLite, zero dependencies | Sub-ms sökningar |
| **Embedding-modell** | `onnxruntime` + CodeRankEmbed (137M) | C++-kärna, Python-bindings | 137M params, 8k token context, MIT | **~5ms/chunk** på Apple Silicon |
| **Kompression** | `zstandard` (zstd) för index, `lz4` för cache | C-kärna, Python-bindings | Facebook-utvecklad | zstd: **3.4x snabbare** än zlib, lz4: **4 GB/s** dekompression |
| **Content-hashing** | `xxhash` (xxHash3-128) | C-kärna, Python-bindings | Snabbaste non-crypto hash | **31 GB/s** throughput |
| **Token-räkning** | `tiktoken` | Rust-kärna, Python-bindings | Exakt token-count för Claude | — |
| **Filbevakning** | `watchdog` | Python (FSEvents/inotify/ReadDirectoryChanges) | Native OS-API:er per plattform, embedded | Instant notification |
| **Databas** | `sqlite3` (stdlib) | C | WAL mode, FTS5, universellt | 800+ writes/sec |

### Varför dessa val (och inte alternativen)

| Val | Alternativ | Varför vi valde rätt |
|-----|-----------|---------------------|
| usearch | FAISS, hnswlib, sqlite-vec | FAISS kräver MKL/OpenBLAS (tungt), hnswlib saknar kvantisering, sqlite-vec långsammare |
| CodeRankEmbed 137M | Nomic 7B, Jina 0.5B, all-MiniLM | 137M = snabb på vilken CPU som helst, 8k context (MiniLM bara 256), Nomic/Jina för stora utan GPU |
| ONNX Runtime | llama.cpp, candle | 9x snabbare inference, auto-detect bästa backend per plattform |
| zstd | zlib-ng, lz4, brotli | Bäst balans hastighet/ratio. lz4 för hot cache, zstd för persistent lagring |
| xxHash3 | BLAKE3, SHA-256 | 31 GB/s vs 8 GB/s (BLAKE3). Vi behöver inte krypto — bara change detection |
| SQLite FTS5 | Tantivy | FTS5 redan i SQLite = zero extra deps. Tantivy snabbare men overkill för <10k filer |
| watchdog | Watchman, notify-rs | Ren Python, native OS-API per plattform (FSEvents/inotify/ReadDirectoryChanges). Watchman kräver separat daemon |

## Inspirationskällor (open source)

| Projekt | Vad vi tar | Licens |
|---------|-----------|--------|
| **codebase-memory-mcp** (713★) | Call graph-analys, tree-sitter AST, content-hash indexering, SQLite WAL | MIT |
| **code-memory** (25★) | Hybrid BM25 + dense vector search, Jina-embeddings, sqlite-vec | MIT |
| **mcp-code-indexer** (10★) | Merkle tree change detection, FTS5, filbeskrivningar, git hooks | MIT |
| **AiDex** (15★) | Cross-project sökning, tree-sitter identifiers, session management | MIT |
| **context-engine** (36★) | Token-budget-aware context assembly, retrieval-profiler | MIT |
| **Cursor IDE** (blogg/docs) | AST chunking, reranking pipeline, inkrementell Merkle-sync | Proprietär (inspiration) |

---

## MCP Tools (7 st)

### Kärn-tools

```
index_codebase(path: str, force: bool = False) → status
```
Indexera eller omindexera en kodbas. Inkrementell via xxHash3 content-hashing — bara ändrade filer omindexeras.

```
search_code(query: str, limit: int = 10) → chunks[]
```
Hybrid-sökning: BM25 (FTS5) + semantisk (usearch embeddings). Kombinerad ranking. Returnerar relevanta kodsnuttar med filsökväg och radnummer.

```
get_context(query: str, token_budget: int = 8000) → context
```
**Huvudverktyget.** Tar en fråga + token-budget, returnerar den mest relevanta koden komprimerad till exakt N tokens. Kör hybrid-sökning → reranking → token-trimning.

### Struktur-tools

```
search_structure(symbol: str, kind: str = "any") → definitions[]
```
Hitta funktioner, klasser, variabler via AST-index. Exakt och prefix-matching.

```
trace_dependencies(file: str, depth: int = 2) → graph
```
Vem importerar denna fil? Vad importerar den? Call graph med konfigurerbart djup.

### Översikt-tools

```
project_summary() → summary
```
Komprimerad projektöversikt: språkfördelning, filstruktur, entry points, nyckelmoduler. Cachad, uppdateras inkrementellt.

```
file_summary(path: str) → summary
```
Sammanfattning av en specifik fil: exporter, funktioner, dependencies, komplexitet. Cachad per content-hash.

---

## Arkitektur

```
┌─────────────────────────────────────────────┐
│              Claude Code (VSCode)            │
│         anropar tools via MCP (stdio)        │
└──────────────────┬──────────────────────────┘
                   │ JSON-RPC
┌──────────────────▼──────────────────────────┐
│           MCP Server (Python)                │
│                                              │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Indexer  │ │ Searcher │ │ Context      │  │
│  │         │ │          │ │ Assembler    │  │
│  └────┬────┘ └────┬─────┘ └──────┬───────┘  │
│       │           │              │           │
│  ┌────▼───────────▼──────────────▼────────┐  │
│  │            Storage Layer               │  │
│  │  SQLite (WAL) + FTS5 + usearch index   │  │
│  │  zstd-komprimerade chunks              │  │
│  │  xxHash3 content-hashes                │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │         Background Workers             │  │
│  │  watchdog → inkrementell omindexering  │  │
│  │  ONNX Runtime → embedding pipeline     │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## Indexeringspipeline

```
1. Fil ändrad (watchdog / git diff / manuell)
         │
2. xxHash3 → jämför med lagrat hash
         │ (bara om ändrad)
3. tree-sitter → AST
         │
4. Chunking: funktioner, klasser, metoder
   (behåll scope-kontext: filsökväg + parent-klass)
         │
5. Parallellt:
   ├─ FTS5-index (BM25)
   ├─ ONNX Runtime → CodeRankEmbed → usearch-index
   ├─ Struktur-index (symboler, imports, call graph)
   └─ zstd-komprimera chunk för cache
         │
6. Uppdatera SQLite (WAL mode, batch-writes)
```

## Sökpipeline (get_context)

```
1. Query in
         │
2. Parallellt:
   ├─ BM25-sökning (FTS5) → top 50
   └─ Embedding-sökning (usearch) → top 50
         │
3. Merge + reciprocal rank fusion
         │
4. Expandera: hämta importerade/anropade funktioner (1 nivå)
         │
5. Token-budget trimning:
   - Räkna tokens (tiktoken)
   - Fyll budgeten med högst rankade chunks
   - Inkludera scope-kontext (filsökväg, klass-signatur)
         │
6. Returnera komprimerad kontext
```

---

## Databasschema (SQLite)

```sql
-- Filer och deras hash
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    content_hash TEXT NOT NULL,      -- xxHash3-128
    language TEXT,
    last_indexed REAL,
    summary TEXT,                     -- cachad sammanfattning
    summary_hash TEXT                 -- hash av fil vid sammanfattning
);

-- Kodchunks
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    file_id INTEGER REFERENCES files(id),
    name TEXT,                        -- funktionsnamn, klassnamn
    kind TEXT,                        -- function, class, method, module
    start_line INTEGER,
    end_line INTEGER,
    content BLOB,                     -- zstd-komprimerad källkod
    scope_context TEXT,               -- "src/api/auth.py::AuthHandler"
    token_count INTEGER
);

-- FTS5 för BM25-sökning
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    name, content, scope_context,
    content=chunks, content_rowid=id
);

-- Struktur/imports
CREATE TABLE symbols (
    id INTEGER PRIMARY KEY,
    chunk_id INTEGER REFERENCES chunks(id),
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_id INTEGER REFERENCES files(id)
);

CREATE TABLE imports (
    source_file INTEGER REFERENCES files(id),
    target_file INTEGER REFERENCES files(id),
    symbol TEXT
);

-- Projektmetadata
CREATE TABLE project (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated REAL
);
```

Vektor-embeddings lagras separat i usearch-index (`.usearch`-fil) med chunk_id som nyckel.

---

## Claude Code-konfiguration

### Registrera MCP-servern (körs alltid lokalt)

```bash
claude mcp add --transport stdio cursor-for-claude -- python /path/to/cursor-for-claude/server.py
```

### Instruera Claude Code att alltid använda den

Lägg till i projektets `CLAUDE.md`:

```markdown
## Kodbaskontext

Detta projekt har en MCP-server `cursor-for-claude` för snabb kodsökning.

VIKTIGT: Använd ALLTID dessa MCP-tools INNAN du läser filer manuellt:
- `get_context(query, token_budget)` — för att hitta relevant kod för en uppgift
- `search_code(query)` — för att söka i kodbasen semantiskt
- `search_structure(symbol)` — för att hitta definitioner
- `project_summary()` — för att förstå projektstrukturen

Dessa tools är snabbare och använder mindre context window än Grep/Glob/Read.
Läs bara enskilda filer med Read när du behöver se exakt innehåll efter sökning.
```

### Alternativt: global konfiguration (alla projekt)

Lägg i `~/.claude/CLAUDE.md` för att aktivera i alla projekt.

---

## Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim

# Installera build-dependencies för tree-sitter och native libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

# Ladda ner embedding-modellen vid build (cachas i Docker layer)
RUN python -c "from server import download_model; download_model()"

EXPOSE 8080
# HTTP-transport för Docker, stdio för lokal
CMD ["python", "server.py", "--transport", "http", "--port", "8080"]
```

### Multi-arch build (x86 + ARM)

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t cursor-for-claude:latest --push .
```

### Köra med Docker

```bash
# Montera din kodbas som volym
docker run -v /path/to/your/project:/workspace \
  -p 8080:8080 cursor-for-claude:latest

# Registrera i Claude Code (HTTP-transport för Docker)
claude mcp add --transport http cursor-for-claude http://localhost:8080/mcp
```

### Köra utan Docker (native, snabbast)

```bash
pip install cursor-for-claude
claude mcp add --transport stdio cursor-for-claude -- cursor-for-claude serve
```

### Plattformsspecifika optimeringar

| Plattform | ONNX Backend | Notering |
|-----------|-------------|----------|
| macOS Apple Silicon | CoreML + Accelerate | Snabbast, ARM NEON |
| macOS Intel | CPU (AVX2) | Bra prestanda |
| Linux x86 | CPU (AVX2/AVX-512) | Bra prestanda |
| Linux ARM (Raspberry Pi, etc.) | CPU (NEON) | Fungerar, långsammare embedding |
| Windows | CPU (AVX2) / DirectML | DirectML om GPU finns |
| Docker (alla plattformar) | CPU auto-detect | ONNX Runtime väljer bästa backend |

ONNX Runtime detekterar automatiskt tillgängliga instruktioner (NEON/AVX2/AVX-512) — ingen manuell konfiguration behövs.

---

## Fasplan

### Fas 1 — Grundläggande indexering (v0.1)
- [ ] Skapa repo: `cursor-for-claude/`, pyproject.toml, MIT-licens
- [ ] MCP-server skeleton med `mcp` Python SDK (MCPServer + @mcp.tool)
- [ ] Automatisk språkdetektering via filändelse → tree-sitter grammar
- [ ] tree-sitter chunking: alla 64+ språk som tree-sitter-languages stödjer
- [ ] Fallback-chunking för okända filtyper (radbaserad med intelligent split)
- [ ] SQLite-lagring med WAL mode
- [ ] xxHash3 content-hashing för inkrementell indexering
- [ ] `.gitignore`-aware — skippa `node_modules/`, `venv/`, `dist/`, etc.
- [ ] `index_codebase(path)` tool
- [ ] `project_summary()` tool
- [ ] Registrera i Claude Code (`claude mcp add`), verifiera med `/mcp`
- [ ] README med installation + quickstart

### Fas 2 — Hybrid sökning (v0.2)
- [ ] FTS5 virtual table + BM25-sökning (funkar standalone utan ML)
- [ ] ONNX Runtime + CodeRankEmbed 137M (CPU, auto-detect bästa backend)
- [ ] Automatisk modell-nedladdning i bakgrunden vid första körning (~50MB)
- [ ] Graceful degradation: servern startar direkt med FTS5, semantisk sökning aktiveras när modellen är redo
- [ ] usearch vektor-index (f16 kvantisering för mindre minne)
- [ ] Reciprocal rank fusion (BM25 + embedding scores, fallback till enbart BM25)
- [ ] `search_code(query)` tool
- [ ] `get_context(query, token_budget)` tool — huvudverktyget
- [ ] tiktoken token-räkning för exakt budget

### Fas 3 — Strukturanalys (v0.3)
- [ ] Generisk import/export-extraktion via tree-sitter queries per språk
- [ ] Call graph: funktionsanrop inom projektet
- [ ] Plugin-arkitektur: lägg till språkspecifika regler utan att ändra kärnan
- [ ] `search_structure(symbol)` tool
- [ ] `trace_dependencies(file)` tool

### Fas 4 — Smart context & caching (v0.4)
- [ ] `file_summary(path)` med cachning per content-hash
- [ ] watchdog file watcher → automatisk bakgrunds-omindexering (alla OS)
- [ ] zstd-kompression av lagrade chunks (persistent)
- [ ] lz4 för in-memory query-cache
- [ ] Inkrementell indexering via `git diff` (snabbaste path)

### Fas 5 — Docker & multi-plattform (v0.5)
- [ ] Dockerfile med multi-stage build (slim)
- [ ] Multi-arch: `linux/amd64` + `linux/arm64`
- [ ] docker-compose.yml för enkel start
- [ ] HTTP-transport (streamable-http) för Docker-deploy
- [ ] Auto-detect ONNX backend (CoreML / AVX2 / NEON / DirectML)
- [ ] Embedding-modell pre-cached i Docker image
- [ ] Health check endpoint
- [ ] Testa på: macOS (ARM + Intel), Ubuntu, Windows, Raspberry Pi

### Fas 6 — Polish & release (v1.0)
- [ ] Cross-project sökning (indexera flera repos)
- [ ] Benchmark-suite: mät context-reduktion, söktid, indexeringstid
- [ ] CI/CD med GitHub Actions (test alla plattformar + Docker build + PyPI)
- [ ] Paketera: `pip install cursor-for-claude`
- [ ] Publicera till PyPI + Docker Hub
- [ ] Demo-video + bloggpost
- [ ] Contributing guide för open source-bidrag

---

## Förväntad effekt

| Mätvärde | Utan MCP-server | Med MCP-server |
|----------|-----------------|----------------|
| Context per fråga | ~20-50k tokens (hela filer) | ~4-8k tokens (relevanta chunks) |
| Tid till context-komprimering | Snabbare (3-5x fler frågor innan taket) | — |
| Sökhastighet | Sekunder (Grep genom alla filer) | Millisekunder (index lookup) |
| Omindexering | N/A | <1s inkrementell |

---

## Licens

MIT — öppen källkod, fritt att använda och bidra till.