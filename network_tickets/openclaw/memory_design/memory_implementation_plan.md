# OpenClaw Memory System — Implementation Plan

Based on the [Four-Tier Memory Management Specification](memory_management.md).

---

## Directory Structure

```
~/.openclaw/workspace/
├── MEMORY.md                              # Tier 4 — Permanent memory (general facts, preferences, architecture)
├── memory/
│   ├── instant-<SESSION_ID>.md            # Tier 1 — Session scratchpad (temporary, deleted after flush)
│   ├── <YYYY-MM-DD>.md                    # Tier 2 — Daily memory (one file per calendar day)
│   ├── week-<YYYY>-W<NN>.md              # Tier 3 — Weekly memory (one file per ISO week)
│   ├── archive/
│   │   ├── <YYYY-MM-DD>.md               # Archived daily files (moved day +7, deleted day +30)
│   │   └── week-<YYYY>-W<NN>.md          # Archived weekly files (moved month +1, deleted month +3)
│   └── entities/
│       └── <entity-slug>.md              # Entity-specific permanent memory (servers, people, projects, APIs)
```

---

## Source Code Layout

```
openclaw/
├── memory/
│   ├── __init__.py
│   ├── config.py                          # Configuration loader, YAML parsing, template variable resolution
│   ├── tokens.py                          # Token counting utility
│   ├── session.py                         # Session ID generation, session lifecycle hooks
│   ├── tiers/
│   │   ├── __init__.py
│   │   ├── instant.py                     # Tier 1 — Instant memory writer, capture/skip filter
│   │   ├── daily.py                       # Tier 2 — Daily memory manager, mid-day auto-flush
│   │   ├── weekly.py                      # Tier 3 — Weekly memory manager, pinning mechanism
│   │   └── permanent.py                   # Tier 4 — Permanent memory + entity file management
│   ├── distillation/
│   │   ├── __init__.py
│   │   ├── prompts.py                     # All distillation prompt templates
│   │   ├── instant_to_daily.py            # Flush logic: instant → daily
│   │   ├── daily_to_weekly.py             # Nightly + mid-day distillation logic
│   │   ├── weekly_to_permanent.py         # Saturday distillation logic
│   │   └── runner.py                      # Distillation orchestrator (scheduling, sequencing)
│   ├── search/
│   │   ├── __init__.py
│   │   ├── hybrid.py                      # Hybrid search engine (vector + BM25)
│   │   ├── embeddings.py                  # Embedding generation (all-MiniLM-L6-v2)
│   │   └── index.py                       # Index build, update, and deletion
│   ├── archive/
│   │   ├── __init__.py
│   │   └── cleanup.py                     # Archive moves + scheduled deletions
│   └── recovery/
│       ├── __init__.py
│       └── backup.py                      # Pre-distillation backups, conflict resolution, locking
```

---

## Implementation Steps

### Phase 1 — Core Infrastructure

#### Step 1: Create the directory scaffold

Create the runtime directories on first launch if they don't exist.

- `~/.openclaw/workspace/memory/`
- `~/.openclaw/workspace/memory/archive/`
- `~/.openclaw/workspace/memory/entities/`

Create a seed `MEMORY.md` at workspace root with the section skeleton:

```markdown
# Permanent Memory

## User Preferences

## Architecture Decisions

## Correction History
```

**File:** `config.py`

#### Step 2: Token counting utility

Implement a function that estimates token count for a Markdown string. Used by every tier to enforce budgets.

| Tier      | Budget        |
|-----------|---------------|
| Instant   | 1,500 tokens  |
| Daily     | 3,000 tokens  |
| Weekly    | 2,000 tokens  |
| Permanent | 3,000 tokens  |

Options: `tiktoken` library (accurate for OpenAI models) or a fast heuristic (word count × 1.3). Choose based on whether model-exact counts matter.

**File:** `tokens.py`

#### Step 3: Configuration loader

- Parse the YAML config block from `openclaw.yaml` (or equivalent).
- Resolve template variables: `${SESSION_ID}`, `${YYYY-MM-DD}`, `${YYYY}`, `${WW}`.
- Expose defaults for all tunable values (thresholds, schedule times, weights).
- Validate on startup: token budgets > 0, schedule times valid, storage paths writable.

**File:** `config.py`

---

### Phase 2 — Tier 1: Instant Memory

#### Step 4: Session ID generation

Generate a unique session ID on session start. UUID4 short hash (first 8 chars) is sufficient.

**File:** `session.py`

#### Step 5: Instant memory writer

- Create `memory/instant-<SESSION_ID>.md` on first write.
- Append entries under categorized headings: `Decisions`, `Facts Learned`, `Errors Resolved`, `Corrections`, `Open Questions`.
- Implement the capture/skip filter:

| Capture                                    | Skip                                     |
|--------------------------------------------|------------------------------------------|
| Decisions made during the session          | Routine commands (ls, git status, cd)     |
| Errors encountered and their resolutions   | Exploratory dead ends                     |
| New facts (API keys, schema, dependencies) | Repetitive clarification exchanges        |
| Corrections                                | Boilerplate code generation steps         |
| Open questions left unresolved             | Small talk and pleasantries               |
| Configuration changes and rationale        | File reads with no resulting action       |

**File:** `tiers/instant.py`

#### Step 6: Flush triggers

Three triggers, all calling the same flush pipeline:

1. **Pre-compaction** — Hook into `/compact` command. Flush instant → daily *before* context window clears. This is the most critical trigger.
2. **Session end** — Hook into chat close or session timeout.
3. **Token threshold** — Monitor instant file size. When it exceeds 1,500 tokens, auto-flush the oldest entries to daily and retain only the most recent.

**File:** `tiers/instant.py`

#### Step 7: Instant → Daily flush logic

- Run the instant → daily distillation prompt against the instant file contents.
- Append the distilled output to `memory/<YYYY-MM-DD>.md` under a new session heading (e.g., `## Session N (HH:MM–HH:MM)`).
- On success: delete the instant file (session end) or clear it (mid-session `/compact`).

**File:** `distillation/instant_to_daily.py`

---

### Phase 3 — Tier 2: Daily Memory

#### Step 8: Daily memory file manager

- Create `memory/<YYYY-MM-DD>.md` on first flush of the day.
- At session start: load today's daily file into context.
- **After every `/compact`:** reload today's daily file into context (prevents loss of same-day context after compaction).

**File:** `tiers/daily.py`

#### Step 9: Daily token budget enforcement (mid-day auto-flush)

Before appending a new instant flush to the daily file:

1. Estimate the resulting token count (existing daily + new content).
2. If it would exceed 3,000 tokens:
   a. Run the mid-day distillation prompt (daily → weekly).
   b. Replace the daily file with a carry-forward summary (target < 500 tokens).
   c. Append the new instant flush content normally.
3. The weekly file must still respect its 2,000-token budget. If merging would exceed, compress more aggressively.

**File:** `tiers/daily.py`, `distillation/daily_to_weekly.py`

#### Step 10: Daily archive policy

Scheduled cleanup job:

| Trigger  | Action                                                          |
|----------|-----------------------------------------------------------------|
| Day +7   | Move `memory/<date>.md` → `memory/archive/<date>.md`           |
| Day +30  | Delete `memory/archive/<date>.md`                               |

Archived files are no longer loaded at session start but remain searchable via memory search.

**File:** `archive/cleanup.py`

---

### Phase 4 — Tier 3: Weekly Memory

#### Step 11: Weekly memory file manager

- Determine the current ISO week number.
- Create or open `memory/week-<YYYY>-W<NN>.md`.

**File:** `tiers/weekly.py`

#### Step 12: Nightly distillation (daily → weekly)

Runs at end-of-day (configurable, default `23:30`):

1. Read today's daily memory file.
2. Read the current weekly memory file (may be empty on Monday).
3. Run the daily → weekly distillation prompt:
   - Merge today's content into weekly.
   - Deduplicate existing facts.
   - Compress related bullets into richer single bullets.
   - Drop session-level structure (weekly is thematic, not chronological).
   - Enforce 2,000-token budget.
4. Write the updated weekly file.

**File:** `distillation/daily_to_weekly.py`, `distillation/runner.py`

#### Step 13: Pinning mechanism

Protect important-but-infrequent facts from being compressed away:

| Rule                | Behavior                                                            |
|---------------------|---------------------------------------------------------------------|
| Explicit `[PIN]`    | Item tagged `[PIN]` in daily memory is preserved verbatim in weekly |
| Auto-pin corrections| All corrections (user overriding prior assumption) are auto-pinned  |
| Auto-pin patterns   | Items in 3+ daily files within the same week are auto-pinned        |

Pinned items survive nightly compression until Saturday's permanent distillation processes them.

**File:** `tiers/weekly.py`

#### Step 14: Weekly archive policy

| Trigger   | Action                                                              |
|-----------|---------------------------------------------------------------------|
| Month +1  | Move `memory/week-*.md` → `memory/archive/week-*.md`               |
| Month +3  | Delete `memory/archive/week-*.md`                                   |

**File:** `archive/cleanup.py`

---

### Phase 5 — Tier 4: Permanent Memory

#### Step 15: Saturday distillation (weekly → permanent)

Runs Saturday night (configurable, default `23:45`), after the nightly daily → weekly completes:

1. Read the current week's weekly memory file.
2. Read `MEMORY.md`.
3. Read relevant entity files if entities are mentioned.
4. Run the weekly → permanent distillation prompt:
   - Extract only facts with month-or-longer durability.
   - Drop time-bound context (sprint goals, daily tasks, in-progress work).
   - Merge into existing MEMORY.md sections; no duplicates.
   - Replace contradicted entries and log to Correction History.
   - Route entity-scoped facts to `memory/entities/<slug>.md`.
5. Write updated `MEMORY.md` and any updated/new entity files.
6. Do **not** delete the weekly file (it remains searchable until month +1).

**File:** `distillation/weekly_to_permanent.py`, `distillation/runner.py`

#### Step 16: MEMORY.md budget enforcement

After Saturday distillation, check if `MEMORY.md` exceeds 3,000 tokens. If so:

- Identify the least-accessed section.
- Split it into a new entity file under `memory/entities/`.
- Replace the section in MEMORY.md with a one-line reference (e.g., `See memory/entities/network-tickets.md`).

**File:** `tiers/permanent.py`

#### Step 17: Entity file management

- Auto-create entity files when the Saturday distillation prompt identifies entity-scoped facts.
- Each entity file follows the standard format with sections relevant to the entity type and a `## Last Updated` timestamp.
- Creation rules:

| Create                                               | Don't create                                           |
|------------------------------------------------------|--------------------------------------------------------|
| Servers, devices, infra components managed repeatedly | Entity mentioned once and never referenced again       |
| People with roles, preferences, contact details      | General facts not scoped to a specific thing           |
| Projects with own tech stack and conventions          |                                                        |
| APIs/services with specific quirks or rate limits     |                                                        |

**File:** `tiers/permanent.py`

---

### Phase 6 — Search & Retrieval

#### Step 18: Session-start and post-compact context loading

Automatically load into context at **session start** and **after every `/compact`**:

| Source                         | Load behavior                   |
|--------------------------------|---------------------------------|
| `MEMORY.md`                    | Always loaded                   |
| `memory/<today>.md`            | Always loaded                   |
| `memory/instant-<session>.md`  | Always in context (current session) |

Weekly, entity, and archived files are **not** preloaded — they are searched on demand.

**File:** `session.py`

#### Step 19: Hybrid search engine

Implement local hybrid search combining vector similarity and BM25 text matching.

- Embedding model: `all-MiniLM-L6-v2`
- Weights: 70% vector, 30% text
- Candidate multiplier: 4× (retrieve 4× candidates, re-rank, return top N)
- Search priority order:

| Priority | Tier                  | Method                              |
|----------|-----------------------|-------------------------------------|
| 1        | Instant memory        | Already in context, no search       |
| 2        | Daily memory (today)  | Already in context, no search       |
| 3        | Weekly memory         | Hybrid search on demand             |
| 4        | Permanent (MEMORY.md) | Already in context, no search       |
| 5        | Entity files          | Hybrid search when entity mentioned |
| 6        | Archived files        | Hybrid search on explicit query     |

**File:** `search/hybrid.py`

#### Step 20: Index management

- Build vector embeddings for all memory files in tiers 3–6.
- Re-index on file creation, update, archive, and deletion.
- Store index locally (e.g., SQLite with `sqlite-vss`, or flat FAISS index).

**File:** `search/embeddings.py`, `search/index.py`

---

### Phase 7 — Failure Recovery & Housekeeping

#### Step 21: Pre-distillation backups

- Write `MEMORY.md.bak` before each Saturday distillation.
- Optionally write `week-<YYYY>-W<NN>.md.bak` before nightly distillation.
- Keep only one version back (overwrite previous `.bak`).

**File:** `recovery/backup.py`

#### Step 22: Distillation failure recovery

| Failure                          | Impact                          | Recovery                                                              |
|----------------------------------|---------------------------------|-----------------------------------------------------------------------|
| Crash before instant flush       | Session context lost            | Accept loss; instant memory is ephemeral. Mitigate with lower threshold. |
| Nightly distillation fails       | Daily not merged into weekly    | Next night picks up both days. Daily files retained until archived.    |
| Saturday distillation fails      | Weekly not merged into permanent| Run manually or wait for next Saturday. Weekly files persist until month +1. |
| MEMORY.md exceeds token budget   | Slow context loading            | Split largest section into entity file.                               |
| Corrupted memory file            | Bad distillation output         | Restore from `.bak` file.                                             |

**File:** `recovery/backup.py`, `distillation/runner.py`

#### Step 23: File-level locking

- Implement locking for entity files to prevent concurrent distillation conflicts.
- Strategy: file-level lock (e.g., `fcntl.flock`) or timestamp-based conflict resolution.
- Last-write-wins is acceptable since distillation is idempotent.

**File:** `recovery/backup.py`

#### Step 24: Scheduled cleanup jobs

Single cleanup runner that executes on a rolling basis:

| Schedule | Action                                                  |
|----------|---------------------------------------------------------|
| Daily    | Archive daily files older than 7 days                   |
| Daily    | Delete archived daily files older than 30 days          |
| Monthly  | Archive weekly files older than 1 month                 |
| Monthly  | Delete archived weekly files older than 3 months        |

**File:** `archive/cleanup.py`

---

### Phase 8 — Integration Hooks

#### Step 25: `/compact` command hook

Wire up the full compaction sequence:

1. Flush instant memory → daily (pre-compaction).
2. Clear the context window.
3. Reload `MEMORY.md` + today's daily file into context (post-compaction).

**File:** `session.py`

#### Step 26: Session lifecycle hooks

| Event         | Actions                                                                       |
|---------------|-------------------------------------------------------------------------------|
| Session start | Generate session ID → create instant file → load MEMORY.md + today's daily    |
| `/compact`    | Flush instant → daily → clear context → reload MEMORY.md + daily              |
| Session end   | Final flush instant → daily → delete instant file → trigger nightly if EOD    |

**File:** `session.py`

#### Step 27: Configuration validation

Validate all config values on startup:

- Token budgets are positive integers.
- Schedule times are valid `HH:MM` format.
- `distillDay` is a valid day name.
- Storage path templates contain expected variables.
- Embedding model name is recognized.
- Search weights sum to 1.0.
- Workspace directory is writable.

**File:** `config.py`

---

## Scheduling Summary

| Event                          | Frequency | Action                                                         |
|--------------------------------|-----------|----------------------------------------------------------------|
| `/compact` or session end      | As needed | Flush instant → daily; reload MEMORY.md + daily post-compact   |
| Token threshold (1,500)        | As needed | Auto-flush oldest instant entries → daily                      |
| Daily token threshold (3,000)  | As needed | Mid-day auto-flush daily → weekly, replace daily with carry-forward |
| End of day                     | Nightly   | Distill daily → weekly                                         |
| Saturday night                 | Weekly    | Distill weekly → permanent                                     |
| Day +7                         | Rolling   | Archive daily files                                            |
| Day +30                        | Rolling   | Delete archived daily files                                    |
| Month +1                       | Rolling   | Archive weekly files                                           |
| Month +3                       | Rolling   | Delete archived weekly files                                   |

---

## Implementation Order (Recommended)

| Order | Phase                      | Steps   | Dependency        |
|-------|----------------------------|---------|-------------------|
| 1     | Core Infrastructure        | 1–3     | None              |
| 2     | Tier 1: Instant Memory     | 4–7     | Phase 1           |
| 3     | Tier 2: Daily Memory       | 8–10    | Phase 2           |
| 4     | Tier 3: Weekly Memory      | 11–14   | Phase 3           |
| 5     | Tier 4: Permanent Memory   | 15–17   | Phase 4           |
| 6     | Search & Retrieval         | 18–20   | Phases 1–5        |
| 7     | Failure Recovery           | 21–24   | Phases 1–5        |
| 8     | Integration Hooks          | 25–27   | All prior phases  |

Each phase can be tested independently before moving to the next. Tier 1 + Tier 2 alone provide immediate value (session scratchpad + daily log). Tiers 3–4 add progressive compression. Search and recovery harden the system.
