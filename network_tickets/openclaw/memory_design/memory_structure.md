What was created
Source code — 22 Python modules
openclaw/memory/
├── __init__.py                          # Package root (v0.1.0)
├── config.py                            # YAML config loader, template resolution, validation
├── tokens.py                            # Token counting (tiktoken or word*1.3 heuristic)
├── session.py                           # Session ID, lifecycle hooks, context loading
├── tiers/
│   ├── __init__.py
│   ├── instant.py                       # Tier 1 — scratchpad writer, capture/skip filter, flush triggers
│   ├── daily.py                         # Tier 2 — daily file manager, token budget, mid-day auto-flush
│   ├── weekly.py                        # Tier 3 — weekly file manager, pinning mechanism
│   └── permanent.py                     # Tier 4 — MEMORY.md + entity files, budget enforcement
├── distillation/
│   ├── __init__.py
│   ├── prompts.py                       # All 4 distillation prompt templates
│   ├── instant_to_daily.py              # Flush pipeline: instant → daily
│   ├── daily_to_weekly.py               # Nightly + mid-day distillation
│   ├── weekly_to_permanent.py           # Saturday distillation + entity routing
│   └── runner.py                        # Orchestrator: nightly, Saturday, cleanup scheduling
├── search/
│   ├── __init__.py
│   ├── embeddings.py                    # Vector embeddings (sentence-transformers or TF-IDF fallback)
│   ├── hybrid.py                        # Hybrid search engine (70% vector + 30% BM25)
│   └── index.py                         # Index build, update, persistence
├── archive/
│   ├── __init__.py
│   └── cleanup.py                       # Rolling archive moves + deletions
└── recovery/
    ├── __init__.py
    └── backup.py                        # Pre-distillation backups, fcntl file locking, corruption detection
Runtime data — ~/.openclaw/workspace/
~/.openclaw/workspace/
├── MEMORY.md                            # Seeded with section skeleton
└── memory/
    ├── archive/                         # Ready for aged file archival
    └── entities/                        # Ready for entity-specific knowledge files
Integration test results
All 10 checks passed: directory scaffolding, session ID generation, instant memory write + capture/skip filter, flush to daily, weekly file creation, entity file management, hybrid search indexing + querying, schedule checks, backup/validation, and file locking.

Key design decisions in the implementation
LLM-optional — every distillation accepts an optional llm_callable. Without one, a structural no-LLM fallback handles merging (so the system works even without an API key).
numpy only for search — the embedding/search layer uses numpy directly with a TF-IDF hash-trick fallback, so sentence-transformers is optional.
Workspace via env var — OPENCLAW_WORKSPACE overrides the default ~/.openclaw/workspace/ path.
Idempotent distillation — all merges deduplicate, so re-running after a failure is safe.

**Running inside OpenClaw (container)**  
- The gateway runs in Docker. Workspace in container: `/home/node/.openclaw/workspace`.  
- Memory CLI is mounted at `/home/node/openclaw`. Use: `cd /home/node/openclaw && PYTHONPATH=/home/node/openclaw python3 -m memory <command>`.  
- Search/reindex need numpy (not in gateway image); they fail with a clear message—read MEMORY.md and daily files, or run search on the host.

**Cron (OpenClaw built-in)**  
- Memory distillation and cleanup are scheduled via **OpenClaw’s built-in cron** (not the sidecar). Add 3 jobs: nightly 23:30 (`distill-nightly`), Saturday 23:45 (`distill-saturday`), daily 04:00 (`cleanup`). Run via exec: `cd /home/node/openclaw && PYTHONPATH=/home/node/openclaw python3 -m memory <command>`.  
- Optional: the `openclaw-memory-cron` sidecar (in docker-compose) is commented out; uncomment to use it instead of OpenClaw cron.