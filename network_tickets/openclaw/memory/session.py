"""
Session lifecycle management.

Responsibilities:
  - Generate unique session IDs
  - Track session start/end times
  - Orchestrate context loading (MEMORY.md + today's daily) at start and post-compact
  - Wire up /compact and session-end hooks
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import get_config, resolve_path, workspace_root


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Cached paths resolved at creation
    _instant_path: Optional[Path] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._instant_path = resolve_path(
            get_config().instant.storage_template,
            session_id=self.session_id,
            now=self.start_time,
        )

    @property
    def instant_path(self) -> Path:
        assert self._instant_path is not None
        return self._instant_path

    @property
    def daily_path(self) -> Path:
        return resolve_path(
            get_config().daily.storage_template,
            session_id=self.session_id,
            now=datetime.now(),
        )

    @property
    def weekly_path(self) -> Path:
        return resolve_path(
            get_config().weekly.storage_template,
            session_id=self.session_id,
            now=datetime.now(),
        )

    @property
    def permanent_path(self) -> Path:
        return resolve_path(
            get_config().permanent.storage_template,
            session_id=self.session_id,
        )

    @property
    def entity_dir(self) -> Path:
        return workspace_root() / get_config().permanent.entity_dir

    # -- Context loading ------------------------------------------------------

    def load_startup_context(self) -> dict[str, str]:
        """Load files that should be in context at session start.

        Returns a dict mapping source labels to their content.
        """
        context: dict[str, str] = {}

        perm = self.permanent_path
        if perm.exists():
            context["MEMORY.md"] = perm.read_text(encoding="utf-8")

        daily = self.daily_path
        if daily.exists():
            context[f"daily/{daily.name}"] = daily.read_text(encoding="utf-8")

        return context

    def load_post_compact_context(self) -> dict[str, str]:
        """Reload context after /compact (same sources as startup)."""
        return self.load_startup_context()

    # -- Lifecycle events -----------------------------------------------------

    def on_session_start(self) -> dict[str, str]:
        """Called when a new session begins. Returns startup context."""
        from .tiers.instant import InstantMemory
        self._instant_memory = InstantMemory(self)
        # Auto-create instant file at session start
        self._instant_memory._ensure_file()
        return self.load_startup_context()

    def on_compact(self) -> dict[str, str]:
        """Called before /compact clears the context window.

        1. Flush instant → daily
        2. Return refreshed context for post-compact loading
        """
        from .tiers.instant import InstantMemory
        if hasattr(self, "_instant_memory"):
            self._instant_memory.flush(reason="compact")
        return self.load_post_compact_context()

    def on_session_end(self) -> None:
        """Called when the session closes.

        1. Final flush instant → daily
        2. Delete the instant file
        """
        self.end_time = datetime.now()
        from .tiers.instant import InstantMemory
        if hasattr(self, "_instant_memory"):
            self._instant_memory.flush(reason="session_end")
            self._instant_memory.delete_file()


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
_active_session: Optional[Session] = None


def start_session() -> Session:
    """Create and register a new active session."""
    global _active_session
    _active_session = Session()
    _active_session.on_session_start()
    return _active_session


def get_active_session() -> Optional[Session]:
    return _active_session


def end_session() -> None:
    global _active_session
    if _active_session is not None:
        _active_session.on_session_end()
        _active_session = None
