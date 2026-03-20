# Arrow Benchmark & Fix Prompt

Run a full benchmark of Arrow MCP tools vs traditional Claude Code tools (Glob/Grep/Read), then fix every issue found.

## Step 1: Re-index and prepare

1. Force re-index the codebase: `index_codebase("/Users/andreas/arrow", force=true)`
2. Note the git SHA, file count, and chunk count
3. Create a timestamped run directory: `benchmarks/reports/run-YYYY-MM-DDTHHMM/`
4. Check for previous benchmark runs in `benchmarks/reports/` and read the last summary for comparison

## Step 2: Run all 30 benchmark queries

Use the test spec at `benchmarks/arrow_vs_traditional_test_spec.md` for the full query list.

**For each query, dispatch an independent background agent** that:
1. Records a start timestamp (`python3 -c "import time; print(int(time.time()*1000))"`)
2. **Round 1 — Traditional:** Answers the question using ONLY Glob, Grep, Read (no Arrow tools). Records tool calls, tokens (~4/line), wall time, quality (1-5), precision (%).
3. **Round 2 — Arrow:** Answers the SAME question using ONLY the designated Arrow tool(s) from the spec. Uses `project="andreasmyleus/arrow"` and `deduplicate=false`. Records tokens, chunks, wall time, quality, precision.
4. Writes a per-query report to `benchmarks/reports/run-YYYY-MM-DDTHHMM/NN-slug.md` using the format from the spec.

**Important:**
- Launch agents in parallel batches (6-8 at a time) for speed
- Each agent runs independently (no shared session state) to avoid cross-query dedup bias
- Use `run_in_background=true` on all agents
- Be honest in both rounds — don't over-read or under-read to skew results

## Step 3: Compile summary

Once all 30 reports are written:

1. Read all per-query reports and extract metrics (tool calls, tokens, time, quality, precision, winner)
2. Write `benchmarks/reports/run-YYYY-MM-DDTHHMM/summary.md` with:
   - Results table (all 30 queries)
   - Per-tool summary (wins/losses/avg quality per Arrow tool)
   - Totals (traditional vs Arrow aggregate metrics)
   - Comparison with previous run (if exists)
   - Analysis: where Arrow wins, where it fails, key issues identified
   - Prioritized recommendations for fixes

## Step 4: Fix every issue identified

For each recommendation from the analysis:

1. Dispatch a parallel agent per fix (use `isolation: "worktree"` if available, otherwise work directly on main)
2. Each agent must:
   - Read the relevant source files first
   - Make surgical changes (minimal diff)
   - Run `pytest tests/ -x -q` to verify nothing breaks
   - Commit with a descriptive message
3. If worktree agents fail to persist commits (worktrees get cleaned up), re-do the fixes directly on main in a single agent
4. Fix any pre-existing test failures discovered during the process

## Step 5: Verify and push

1. Run the full test suite: `pytest tests/ -x -q`
2. Verify all fixes are committed: `git log --oneline -N`
3. Push to remote: `git push origin main`
4. Report the final state: commits pushed, tests passing, fixes applied

## Rules

- **Parallel everything:** Benchmark queries run as independent agents. Fixes run as independent agents. Maximize concurrency.
- **Honest benchmarking:** Don't game results. Traditional tools are often better for simple lookups — report that accurately.
- **Surgical fixes:** Only change what's needed. Don't refactor. Don't add unnecessary abstractions.
- **Tests must pass:** Every fix must be verified with `pytest tests/ -x -q` before committing.
- **No push without confirmation:** Ask before pushing to remote (unless instructed to push).
