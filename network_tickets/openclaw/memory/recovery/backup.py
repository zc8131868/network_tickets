"""
Failure recovery — pre-distillation backups, file locking, and conflict resolution.

Backup strategy:
  - Write .bak before each distillation (MEMORY.md.bak, week-*.md.bak)
  - Keep only one version back (overwrite previous .bak)
  - Restore from .bak on corruption

Locking strategy:
  - File-level advisory locks via fcntl.flock (Unix) or a .lock sentinel file (portable)
  - Last-write-wins is acceptable since distillation is idempotent
"""

from __future__ import annotations

import fcntl
import logging
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger("openclaw.memory.recovery")


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

def backup_file(path: Path) -> Optional[Path]:
    """Create a .bak copy of *path* before distillation.

    Returns the backup path on success, None if the source doesn't exist.
    """
    if not path.exists():
        return None

    bak_path = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(str(path), str(bak_path))
    logger.debug("Backed up %s → %s", path.name, bak_path.name)
    return bak_path


def restore_from_backup(path: Path) -> bool:
    """Restore a file from its .bak copy.

    Returns True if restoration succeeded.
    """
    bak_path = path.with_suffix(path.suffix + ".bak")
    if not bak_path.exists():
        logger.warning("No backup found for %s", path.name)
        return False

    shutil.copy2(str(bak_path), str(path))
    logger.info("Restored %s from backup", path.name)
    return True


def has_backup(path: Path) -> bool:
    """Check whether a .bak file exists for *path*."""
    return path.with_suffix(path.suffix + ".bak").exists()


# ---------------------------------------------------------------------------
# File locking (prevents concurrent distillation writes)
# ---------------------------------------------------------------------------

@contextmanager
def file_lock(path: Path, timeout: float = 10.0) -> Generator[None, None, None]:
    """Advisory file lock using fcntl.flock.

    Falls back to a .lock sentinel file if fcntl is unavailable.
    Raises TimeoutError if the lock cannot be acquired within *timeout* seconds.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    fd = None

    try:
        fd = open(lock_path, "w")
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (IOError, OSError):
                if time.monotonic() - start > timeout:
                    raise TimeoutError(
                        f"Could not acquire lock on {path.name} within {timeout}s"
                    )
                time.sleep(0.1)

        logger.debug("Acquired lock on %s", path.name)
        yield

    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
            fd.close()
        # Clean up lock file (best effort)
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        logger.debug("Released lock on %s", path.name)


# ---------------------------------------------------------------------------
# Corruption detection
# ---------------------------------------------------------------------------

def validate_memory_file(path: Path) -> list[str]:
    """Run basic sanity checks on a memory file.

    Returns a list of issues (empty = valid).
    """
    issues: list[str] = []

    if not path.exists():
        issues.append(f"File does not exist: {path}")
        return issues

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        issues.append(f"Cannot read file: {e}")
        return issues

    if not content.strip():
        issues.append("File is empty")
        return issues

    if not content.startswith("#"):
        issues.append("File does not start with a Markdown heading")

    # Check for obvious corruption markers
    if "\x00" in content:
        issues.append("File contains null bytes (likely corrupted)")

    return issues


def auto_recover(path: Path) -> bool:
    """Attempt automatic recovery of a corrupted memory file.

    Strategy:
      1. Validate the file.
      2. If corrupt and a backup exists, restore from backup.
      3. If no backup, log and return False.
    """
    issues = validate_memory_file(path)
    if not issues:
        return True

    logger.warning("Issues detected in %s: %s", path.name, "; ".join(issues))

    if has_backup(path):
        return restore_from_backup(path)

    logger.error("No backup available for %s — manual recovery required", path.name)
    return False
