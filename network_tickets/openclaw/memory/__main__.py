"""
CLI entry point for the OpenClaw memory system.

Usage:
    python -m memory <command> [options]

Commands:
    init                Create workspace directories and seed MEMORY.md
    flush <session_id>  Flush instant memory to daily for a given session
    distill-nightly     Run nightly distillation (daily → weekly)
    distill-saturday    Run Saturday distillation (weekly → permanent)
    cleanup             Run archive moves and deletions
    search <query>      Search across memory tiers
    status              Show memory system status (file counts, sizes)
    validate            Validate configuration and file integrity
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def cmd_init(args: argparse.Namespace) -> None:
    from .config import ensure_directories, workspace_root, validate_config

    ensure_directories()
    errors = validate_config()
    root = workspace_root()
    print(f"Workspace: {root}")
    print(f"  memory/          : {'exists' if (root / 'memory').exists() else 'MISSING'}")
    print(f"  memory/archive/  : {'exists' if (root / 'memory/archive').exists() else 'MISSING'}")
    print(f"  memory/entities/ : {'exists' if (root / 'memory/entities').exists() else 'MISSING'}")
    print(f"  MEMORY.md        : {'exists' if (root / 'MEMORY.md').exists() else 'created'}")
    if errors:
        print(f"\nValidation errors: {errors}")
        sys.exit(1)
    print("\nMemory system initialized.")


def cmd_flush(args: argparse.Namespace) -> None:
    from .config import resolve_path, get_config
    from .session import Session

    session = Session(session_id=args.session_id)
    instant_path = session.instant_path

    if not instant_path.exists():
        print(f"No instant memory file found for session {args.session_id}")
        print(f"  Expected: {instant_path}")
        sys.exit(1)

    content = instant_path.read_text(encoding="utf-8")
    from .distillation.instant_to_daily import flush_instant_to_daily
    success = flush_instant_to_daily(session, content)

    if success:
        if args.delete:
            instant_path.unlink(missing_ok=True)
            print(f"Flushed and deleted instant file for session {args.session_id}")
        else:
            print(f"Flushed instant → daily for session {args.session_id}")
    else:
        print("Flush failed (empty content?)")
        sys.exit(1)


def cmd_distill_nightly(args: argparse.Namespace) -> None:
    from .distillation.runner import run_nightly

    target = datetime.strptime(args.date, "%Y-%m-%d") if args.date else None
    result = run_nightly(target_date=target)

    print(f"Nightly distillation: {'OK' if result.nightly_ok else 'skipped (no daily file)'}")
    if result.saturday_ok is not None:
        print(f"Saturday distillation: {'OK' if result.saturday_ok else 'FAILED'}")
    if result.cleanup:
        c = result.cleanup
        print(f"Cleanup: {c.total_actions} actions "
              f"(archived {len(c.daily_archived)} daily, {len(c.weekly_archived)} weekly; "
              f"deleted {len(c.daily_deleted)} daily, {len(c.weekly_deleted)} weekly)")
    if result.errors:
        print(f"Errors: {result.errors}")
        sys.exit(1)


def cmd_distill_saturday(args: argparse.Namespace) -> None:
    from .distillation.runner import run_manual_saturday

    target = datetime.strptime(args.date, "%Y-%m-%d") if args.date else None
    ok = run_manual_saturday(target_date=target)
    print(f"Saturday distillation: {'OK' if ok else 'FAILED'}")
    if not ok:
        sys.exit(1)


def cmd_cleanup(args: argparse.Namespace) -> None:
    from .archive.cleanup import run_cleanup

    report = run_cleanup(dry_run=args.dry_run)
    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}Daily archived:  {report.daily_archived or '(none)'}")
    print(f"{prefix}Daily deleted:   {report.daily_deleted or '(none)'}")
    print(f"{prefix}Weekly archived: {report.weekly_archived or '(none)'}")
    print(f"{prefix}Weekly deleted:  {report.weekly_deleted or '(none)'}")
    print(f"{prefix}Total actions: {report.total_actions}")


def cmd_search(args: argparse.Namespace) -> None:
    try:
        from .search.hybrid import HybridSearch
    except ImportError as e:
        if "numpy" in str(e).lower():
            print("Memory search requires numpy (not installed in this environment).")
            print("Read MEMORY.md and memory/YYYY-MM-DD.md directly, or run from host:")
            print("  cd /it_network/network_tickets/openclaw && python3 -m memory search \"...\"")
        else:
            raise
        return

    hs = HybridSearch()
    if not hs.load_index():
        print("No search index found. Building...")
        hs.build_index()

    results = hs.search_all(args.query, top_k=args.top_k)
    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        print(f"\n--- Result {i} (score: {r.score:.3f}) [{r.file_path}] ---")
        print(r.chunk_text[:500])


def cmd_reindex(args: argparse.Namespace) -> None:
    try:
        from .search.hybrid import HybridSearch
    except ImportError as e:
        if "numpy" in str(e).lower():
            print("Reindex requires numpy (not installed in this environment).")
            print("Run from host: cd /it_network/network_tickets/openclaw && python3 -m memory reindex")
        else:
            raise
        return

    hs = HybridSearch()
    hs.build_index()
    print(f"Index rebuilt: {hs.index.size} chunks from {len(set(e.file_path for e in hs.index.entries))} files")


def cmd_status(args: argparse.Namespace) -> None:
    from .config import workspace_root
    from .tokens import count_tokens

    root = workspace_root()
    mem_dir = root / "memory"

    perm = root / "MEMORY.md"
    perm_tokens = count_tokens(perm.read_text(encoding="utf-8")) if perm.exists() else 0

    instant_files = list(mem_dir.glob("instant-*.md")) if mem_dir.exists() else []
    daily_files = list(mem_dir.glob("????-??-??.md")) if mem_dir.exists() else []
    weekly_files = list(mem_dir.glob("week-????-W??.md")) if mem_dir.exists() else []
    entity_files = list((root / "memory/entities").glob("*.md")) if (root / "memory/entities").exists() else []
    archive_files = list((root / "memory/archive").glob("*.md")) if (root / "memory/archive").exists() else []

    print(f"Workspace:     {root}")
    print(f"MEMORY.md:     {perm_tokens} tokens")
    print(f"Instant files: {len(instant_files)}")
    print(f"Daily files:   {len(daily_files)}")
    print(f"Weekly files:  {len(weekly_files)}")
    print(f"Entity files:  {len(entity_files)}")
    print(f"Archive files: {len(archive_files)}")

    if args.json:
        data = {
            "workspace": str(root),
            "permanent_tokens": perm_tokens,
            "instant_count": len(instant_files),
            "daily_count": len(daily_files),
            "weekly_count": len(weekly_files),
            "entity_count": len(entity_files),
            "archive_count": len(archive_files),
        }
        print(json.dumps(data))


def cmd_validate(args: argparse.Namespace) -> None:
    from .config import validate_config, workspace_root
    from .recovery.backup import validate_memory_file

    errors = validate_config()
    if errors:
        print("Configuration errors:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("Configuration: OK")

    root = workspace_root()
    perm = root / "MEMORY.md"
    issues = validate_memory_file(perm)
    if issues:
        print(f"MEMORY.md issues: {issues}")
    else:
        print("MEMORY.md: OK")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m memory",
        description="OpenClaw Memory Management CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize workspace directories")

    p_flush = sub.add_parser("flush", help="Flush instant → daily")
    p_flush.add_argument("session_id", help="Session ID to flush")
    p_flush.add_argument("--delete", action="store_true", help="Delete instant file after flush")

    p_nightly = sub.add_parser("distill-nightly", help="Run nightly distillation")
    p_nightly.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to today")

    p_saturday = sub.add_parser("distill-saturday", help="Run Saturday distillation")
    p_saturday.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to today")

    p_cleanup = sub.add_parser("cleanup", help="Run archive cleanup")
    p_cleanup.add_argument("--dry-run", action="store_true", help="Preview without executing")

    p_search = sub.add_parser("search", help="Search memory")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--top-k", type=int, default=5, help="Number of results")

    sub.add_parser("reindex", help="Rebuild search index")

    p_status = sub.add_parser("status", help="Show memory system status")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")

    sub.add_parser("validate", help="Validate config and files")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "flush": cmd_flush,
        "distill-nightly": cmd_distill_nightly,
        "distill-saturday": cmd_distill_saturday,
        "cleanup": cmd_cleanup,
        "search": cmd_search,
        "reindex": cmd_reindex,
        "status": cmd_status,
        "validate": cmd_validate,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
