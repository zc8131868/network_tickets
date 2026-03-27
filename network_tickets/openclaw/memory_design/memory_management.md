OpenClaw Four-Tier Memory Management Specification

Architecture Overview

A four-tier memory system with progressive distillation. Each tier compresses more aggressively than the last, ensuring important context survives while noise is shed.

┌─────────────────────────────────────────────────────────────────────┐
│                        INSTANT MEMORY                               │
│                   (session-scoped scratchpad)                        │
│                                                                     │
│  Trigger: /compact, session end, or token threshold (1500 tokens)   │
│  Storage: memory/instant-SESSION_ID.md                              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ flush (lightweight filter)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DAILY MEMORY                                │
│                    (one file per calendar day)                       │
│                                                                     │
│  Trigger: End-of-day distillation (last session close or midnight)  │
│  Storage: memory/YYYY-MM-DD.md                                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ nightly distillation
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        WEEKLY MEMORY                                │
│                   (one file per calendar week)                       │
│                                                                     │
│  Trigger: Saturday distillation into permanent memory               │
│  Storage: memory/week-YYYY-WNN.md                                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Saturday distillation
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PERMANENT MEMORY                               │
│              (durable facts + entity knowledge graph)               │
│                                                                     │
│  Storage: MEMORY.md + memory/entities/*.md                          │
└─────────────────────────────────────────────────────────────────────┘


---

Tier 1: Instant Memory

Purpose

Capture actionable context within a single session so it survives compaction without polluting longer-term storage with raw noise.

Storage

memory/instant-SESSION_ID.md

Each session gets its own file. The file is created on first write and deleted after successful flush to daily memory.

What to capture

Capture
Skip
Decisions made during the session
Routine commands (ls, git status, cd)
Errors encountered and their resolutions
Exploratory dead ends that led nowhere

New facts (API keys rotated, schema changed, dependency updated)
Repetitive clarification exchanges
Corrections ("use pytest not unittest")
Boilerplate code generation steps
Open questions left unresolved
Small talk and pleasantries
Configuration changes and their rationale
File reads with no resulting action

Flush triggers

1. Pre-compaction — flush before /compact clears the context window. This is the most critical trigger.
2. Session end — flush on chat close or session timeout.
3. Token threshold — if instant memory exceeds 1,500 tokens, auto-flush the oldest entries to daily memory and retain only the most recent.
File format

# Instant Memory — Session abc123

## Timestamp: 2026-03-06T14:22:00Z

### Decisions
- Switched from function-based views to class-based views for the ticket API

### Facts Learned
- The production database is on PostgreSQL 16, not 15
- Redis cache TTL is set to 300s in production

### Errors Resolved
- ImportError on `rest_framework.throttling` — fixed by upgrading djangorestframework to 3.15

### Corrections
- User prefers `ruff` over `flake8` for linting

### Open Questions
- Should the ticket model include a `priority` field or use tags instead?

Flush prompt (instant → daily)

You are distilling a session scratchpad into a daily memory log.

INPUT: The contents of the instant memory file for this session.

RULES:
1. Extract decisions, facts, errors resolved, corrections, and open questions.
2. Drop routine commands, dead-end explorations, and repetitive exchanges.
3. Preserve exact values (versions, config keys, error messages) — do not paraphrase technical details.
4. Append the output to today's daily memory file under a session heading.
5. Use concise bullet points. Each bullet should be independently understandable.

OUTPUT: Markdown to append to memory/YYYY-MM-DD.md

Lifecycle

Session starts → instant file created
    ↓
Context fills / user runs /compact → flush to daily, clear instant file
    ↓
Session continues → instant file accumulates again
    ↓
Session ends → final flush to daily, delete instant file


---

Tier 2: Daily Memory

Purpose

Consolidated log of everything meaningful that happened in a calendar day, across all sessions.

Storage

memory/YYYY-MM-DD.md

One file per day. Created on first flush from instant memory. Read automatically at session start for same-day context.

Token budget

Target: 2,000–3,000 tokens per day. Soft threshold: 3,000 tokens.

Auto-flush trigger: When a flush from instant memory would push the daily file past the soft threshold, an immediate mid-day distillation fires before the new content is appended. This distillation compresses the existing daily content into the current weekly file (using the same daily → weekly prompt), then replaces the daily file with only a carry-forward summary of items not yet captured in weekly memory. The new instant flush is then appended normally.

This prevents runaway daily files on high-activity days while preserving all information in the weekly tier.

File format

# Daily Memory — 2026-03-06

## Session 1 (09:15–11:30)

### Decisions
- Adopted class-based views for ticket API
- Chose PostgreSQL full-text search over Elasticsearch for MVP

### Facts Learned
- Production DB is PostgreSQL 16
- Redis TTL: 300s in production

### Errors Resolved
- ImportError on `rest_framework.throttling` — upgrade to djangorestframework 3.15

## Session 2 (14:00–16:45)

### Decisions
- Added `priority` field to Ticket model (integer, 1–5)
- Using `django-filter` for API query parameters

### Corrections
- Linter is `ruff`, not `flake8`

### Open Questions
- How should priority interact with SLA calculations?

Auto-flush prompt (daily → weekly, mid-day)

You are performing a mid-day distillation because the daily memory file has exceeded its token budget.

INPUT:
- The current daily memory file (over budget)
- The current weekly memory file

RULES:
1. Distill the daily file into the weekly file using the standard daily → weekly rules (merge, deduplicate, compress, preserve [PINNED] items, auto-pin corrections and 3+ occurrences).
2. Produce a carry-forward summary (target: under 500 tokens) containing only items from today that are NOT yet represented in the updated weekly file — typically the most recent session's content and any open questions specific to the current work-in-progress.
3. Replace the daily file with the carry-forward summary under a "## Carry-Forward" heading.
4. The weekly file must still stay within its 2,000-token budget. If merging would exceed this, compress more aggressively.

OUTPUT:
- Updated weekly memory file
- Replacement daily memory file (carry-forward only)

Archive policy

- Days 1–7: Active. Searchable. Read at session start if within the current day.
- After 7 days: Move to memory/archive/YYYY-MM-DD.md. No longer read at session start but still searchable via memory search.
- After 30 days: Delete archived daily files. By this point, all durable content has been distilled into weekly and permanent memory.

---

Tier 3: Weekly Memory

Purpose

Distilled patterns, recurring themes, and significant decisions across a week. Acts as a buffer between ephemeral daily context and permanent memory.

Storage

memory/week-YYYY-WNN.md

Example: memory/week-2026-W10.md for the 10th week of 2026.

Token budget

Target: 1,500–2,000 tokens per week.

Archive policy

- Current month: Active. Searchable via hybrid search.
- After 1 month: Move to memory/archive/week-YYYY-WNN.md. No longer loaded proactively but still searchable.
- After 3 months: Delete. All durable content has been distilled into permanent memory through multiple Saturday runs. Weekly files are already compressed and small, so the longer retention (vs. 30 days for daily) costs little and provides a useful fallback for recalling "what was I working on two months ago?"
Distillation schedule

Runs every night after end-of-day. Each nightly run:

1. Reads today's daily memory file
2. Reads the current weekly memory file
3. Merges new information, compressing and deduplicating
4. Writes the updated weekly file
Pinning mechanism

Some facts are important but infrequent — they may appear on Monday and not again all week. Without pinning, nightly compression could drop them before Saturday's permanent distillation.

Pin rules:
- Any item tagged [PIN] in daily memory is preserved verbatim in weekly memory until the Saturday distillation processes it.
- Corrections (user explicitly overriding a previous assumption) are auto-pinned.
- Items that appear in 3+ daily files within the same week are auto-pinned as patterns.
File format

# Weekly Memory — 2026-W10 (Mar 2–Mar 8)

## Key Decisions
- Adopted class-based views for all API endpoints
- PostgreSQL full-text search chosen over Elasticsearch
- Ticket model includes priority field (integer, 1–5)

## Patterns Observed
- User consistently prefers minimal dependencies over feature-rich libraries
- Most work sessions focus on the ticket API module

## Corrections [PINNED]
- Linter is `ruff`, not `flake8`
- Production DB is PostgreSQL 16, not 15

## Technical Context
- Using django-filter for query parameters
- djangorestframework pinned to 3.15+
- Redis cache TTL: 300s in production

## Unresolved
- Priority ↔ SLA calculation interaction

Distillation prompt (daily → weekly)

You are distilling a daily memory log into a weekly summary.

INPUT:
- Today's daily memory file
- The current weekly memory file (may be empty if this is Monday)

RULES:
1. Merge today's content into the weekly file.
2. Deduplicate: if a fact already exists in the weekly file, do not add it again.
3. Compress: combine related bullets into single, richer bullets where possible.
4. Preserve all [PINNED] items verbatim — do not compress or remove them.
5. Auto-pin any item that has appeared in 3 or more daily files this week.
6. Auto-pin all corrections (where the user overrode a previous assumption).
7. Keep decisions, patterns, corrections, technical context, and unresolved questions as separate sections.
8. Drop session-level structure (session 1, session 2) — weekly memory is thematic, not chronological.
9. Stay within 2,000 tokens.

OUTPUT: The complete updated weekly memory file in Markdown.


---

Tier 4: Permanent Memory

Purpose

Facts that will still be true next month. Core preferences, project architecture, tooling choices, and entity knowledge.

Storage

MEMORY.md                    — general permanent memory (workspace root)
memory/entities/*.md         — entity-specific files

Token budget

MEMORY.md: under 3,000 tokens. If it exceeds this, split entity-specific facts into entities/*.md files.

Distillation schedule

Runs every Saturday after the nightly daily → weekly distillation completes. The Saturday run:

1. Reads the current week's weekly memory file
2. Reads the current MEMORY.md
3. Reads relevant entity files if entities are mentioned
4. Extracts facts with month-or-longer durability
5. Updates MEMORY.md and/or entity files
6. Does not delete the weekly file (it remains searchable until end of month)
File format — MEMORY.md

# Permanent Memory

## User Preferences
- Prefers concise responses over verbose explanations
- Uses Python 3.12 and Django 5.x
- Primary editor: Cursor IDE
- Linter: ruff (not flake8)
- Test framework: pytest
- Prefers minimal dependencies over feature-rich libraries

## Project: network_tickets
- Django-based network automation ticketing system
- Database: PostgreSQL 16
- Cache: Redis (TTL 300s in production)
- API: Django REST Framework 3.15+, class-based views
- Filtering: django-filter
- Ticket model includes priority field (integer, 1–5)

## Architecture Decisions
- PostgreSQL full-text search chosen over Elasticsearch for search MVP
- Token-based authentication with 1-hour expiry

## Correction History
- [2026-03-06] Linter is ruff, not flake8
- [2026-03-06] Production DB is PostgreSQL 16, not 15

Entity files — Purpose and usage

Entity files solve a problem that a flat MEMORY.md cannot: some facts belong to a thing, not to a time period. Without entity files, facts about a server, person, or project end up scattered across multiple Saturday distillations in MEMORY.md, mixed in with unrelated content. Entity files group all knowledge about a single entity in one retrievable location.

When to create an entity file:
- A server, device, or infrastructure component you manage repeatedly
- A person (teammate, vendor) with roles, preferences, or contact details you need to recall
- A project with its own tech stack, conventions, or deployment details
- An API or external service with specific quirks, rate limits, or credential notes
When NOT to create an entity file:
- The entity is mentioned once and never referenced again
- The fact is general and not scoped to a specific thing (stays in MEMORY.md)
Entity files are created automatically by the Saturday distillation prompt when it identifies facts that clearly belong to a specific entity. They can also be created manually.

File format — Entity files

# Entity: Production Server (prod-web-01)

## System
- Ubuntu 22.04 LTS
- 16 GB RAM, 4 vCPU
- Disk: 500 GB (expanded 2026-02-15)
- Python 3.12

## Services
- Django app via gunicorn + nginx
- Connects to prod-db-01 for PostgreSQL

## Incident History
- [2026-02-14] Disk space at 95%, expanded next day

## Last Updated: 2026-03-08

Distillation prompt (weekly → permanent)

You are distilling a weekly memory summary into permanent memory.

INPUT:
- This week's weekly memory file
- The current MEMORY.md
- Any relevant entity files from memory/entities/

RULES:
1. Extract only facts with month-or-longer durability. Ask: "Will this still be true and useful 30 days from now?"
2. Drop time-bound context (sprint goals, daily tasks, in-progress work).
3. Merge into existing sections in MEMORY.md. Do not create duplicate entries.
4. If a new fact contradicts an existing entry in MEMORY.md, replace the old entry and add a dated correction to the Correction History section.
5. If a fact clearly belongs to a specific entity (person, server, project), route it to the appropriate file in memory/entities/. Create the entity file if it doesn't exist.
6. Keep MEMORY.md under 3,000 tokens. If it would exceed this, split the least-accessed section into an entity file.
7. Preserve the section structure: User Preferences, Project sections, Architecture Decisions, Correction History.
8. Unresolved questions from weekly memory should only be promoted to permanent if they represent ongoing architectural decisions, not transient debugging questions.

OUTPUT: Updated MEMORY.md and any updated/new entity files.


---

Scheduling Summary

Event
Frequency
Action
/compact or session end
As needed
Flush instant → daily
Token threshold (1,500)
As needed
Auto-flush oldest instant entries → daily
Daily token threshold (3,000)
As needed
Mid-day auto-flush daily → weekly, replace daily with carry-forward
End of day
Nightly
Distill daily → weekly
Saturday night
Weekly
Distill weekly → permanent
Day +7
Rolling
Archive daily files
Day +30
Rolling
Delete archived daily files
Month +1
Rolling
Archive weekly files
Month +3
Rolling
Delete archived weekly files


---

Directory Structure

~/.openclaw/workspace/
├── MEMORY.md                          # Permanent memory
├── memory/
│   ├── instant-SESSION_ID.md          # Active session scratchpad (temporary)
│   ├── 2026-03-06.md                  # Today's daily memory
│   ├── 2026-03-05.md                  # Yesterday's daily memory
│   ├── week-2026-W10.md               # This week's distilled memory
│   ├── week-2026-W09.md               # Last week (kept until end of month)
│   ├── archive/
│   │   ├── 2026-02-27.md              # Archived daily (deleted after 30 days)
│   │   ├── 2026-02-26.md
│   │   ├── week-2026-W05.md           # Archived weekly (deleted after 3 months)
│   │   └── week-2026-W04.md
│   └── entities/
│       ├── prod-web-01.md             # Entity: production server
│       ├── network-tickets.md         # Entity: project
│       └── john-smith.md              # Entity: person


---

Configuration

agents:
  defaults:
    memory:
      tiers:
        instant:
          enabled: true
          maxTokens: 1500
          flushOnCompact: true
          flushOnSessionEnd: true
          storage: "memory/instant-${SESSION_ID}.md"

        daily:
          enabled: true
          maxTokens: 3000
          autoFlushThresholdTokens: 3000
          carryForwardMaxTokens: 500
          archiveAfterDays: 7
          deleteAfterDays: 30
          storage: "memory/${YYYY-MM-DD}.md"

        weekly:
          enabled: true
          maxTokens: 2000
          distillTime: "23:30"
          pinAfterOccurrences: 3
          autoPinCorrections: true
          storage: "memory/week-${YYYY}-W${WW}.md"

        permanent:
          enabled: true
          maxTokens: 3000
          distillDay: "Saturday"
          distillTime: "23:45"
          storage: "MEMORY.md"
          entityDir: "memory/entities/"

    compaction:
      memoryFlush:
        enabled: true
        softThresholdTokens: 4000

    memorySearch:
      enabled: true
      provider: "local"
      embeddingModel: "all-MiniLM-L6-v2"
      query:
        hybrid:
          enabled: true
          vectorWeight: 0.7
          textWeight: 0.3
          candidateMultiplier: 4


---

Search Behavior

When the agent needs to recall information, it searches across tiers in priority order:

1. Instant memory (current session) — always in context, no search needed
2. Daily memory (today) — loaded at session start and reloaded after every /compact
3. Weekly memory (current week) — searched on demand
4. Permanent memory (MEMORY.md) — loaded at session start and reloaded after every /compact
5. Entity files — searched on demand when an entity is mentioned
6. Archived daily files — searched only via explicit memory search queries
Hybrid search (vector + BM25) applies to tiers 3–6. Tiers 1–2 and 4 are small enough to load directly into context.


---

Failure Modes and Recovery

Failure
Impact
Recovery
Process crash before instant flush
Session context lost
Accept the loss; instant memory is inherently ephemeral. Mitigate by flushing more frequently (lower token threshold).
Nightly distillation fails
Daily file not merged into weekly
Next night's distillation picks up both days. Daily files are retained until archived, so no data is lost.
Saturday distillation fails
Weekly not merged into permanent
Run manually or wait for next Saturday. Weekly files persist until end of month.
MEMORY.md exceeds token budget
Slow context loading, potential truncation

Split largest section into entity file. The permanent distillation prompt enforces the budget.
Entity file conflicts
Two distillation runs write to same entity

Use file-level locking or timestamp-based conflict resolution. Last-write-wins is acceptable since distillation is idempotent.
Corrupted memory file
Bad distillation output
Keep one-version-back copies (MEMORY.md.bak) written before each distillation.
