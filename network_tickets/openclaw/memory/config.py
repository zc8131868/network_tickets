"""
Configuration loader for the OpenClaw memory system.

Reads from ``openclaw.yaml`` if present, otherwise uses built-in defaults.
Resolves template variables: ${SESSION_ID}, ${YYYY-MM-DD}, ${YYYY}, ${WW}.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Workspace root — default: ~/.openclaw/workspace
# ---------------------------------------------------------------------------
DEFAULT_WORKSPACE = Path.home() / ".openclaw" / "workspace"


def workspace_root() -> Path:
    """Return the resolved workspace root, creating it if necessary."""
    root = Path(os.environ.get("OPENCLAW_WORKSPACE", str(DEFAULT_WORKSPACE)))
    root.mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# Dataclasses for typed access
# ---------------------------------------------------------------------------

@dataclass
class TierConfig:
    enabled: bool = True
    max_tokens: int = 1500
    storage_template: str = ""


@dataclass
class InstantConfig(TierConfig):
    max_tokens: int = 1500
    flush_on_compact: bool = True
    flush_on_session_end: bool = True
    storage_template: str = "memory/instant-${SESSION_ID}.md"


@dataclass
class DailyConfig(TierConfig):
    max_tokens: int = 3000
    auto_flush_threshold_tokens: int = 3000
    carry_forward_max_tokens: int = 500
    archive_after_days: int = 7
    delete_after_days: int = 30
    storage_template: str = "memory/${YYYY-MM-DD}.md"


@dataclass
class WeeklyConfig(TierConfig):
    max_tokens: int = 2000
    distill_time: str = "23:30"
    pin_after_occurrences: int = 3
    auto_pin_corrections: bool = True
    storage_template: str = "memory/week-${YYYY}-W${WW}.md"


@dataclass
class PermanentConfig(TierConfig):
    max_tokens: int = 3000
    distill_day: str = "Saturday"
    distill_time: str = "23:45"
    storage_template: str = "MEMORY.md"
    entity_dir: str = "memory/entities/"


@dataclass
class CompactionConfig:
    memory_flush_enabled: bool = True
    soft_threshold_tokens: int = 4000


@dataclass
class SearchConfig:
    enabled: bool = True
    provider: str = "local"
    embedding_model: str = "all-MiniLM-L6-v2"
    vector_weight: float = 0.7
    text_weight: float = 0.3
    candidate_multiplier: int = 4


@dataclass
class MemoryConfig:
    instant: InstantConfig = field(default_factory=InstantConfig)
    daily: DailyConfig = field(default_factory=DailyConfig)
    weekly: WeeklyConfig = field(default_factory=WeeklyConfig)
    permanent: PermanentConfig = field(default_factory=PermanentConfig)
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
    search: SearchConfig = field(default_factory=SearchConfig)


# ---------------------------------------------------------------------------
# Configuration singleton
# ---------------------------------------------------------------------------
_config: Optional[MemoryConfig] = None


def get_config() -> MemoryConfig:
    """Return the current configuration (loads defaults on first call)."""
    global _config
    if _config is None:
        _config = _load_config()
    return _config


def _load_config() -> MemoryConfig:
    """Load config from YAML file if it exists, otherwise return defaults."""
    yaml_path = workspace_root() / "openclaw.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, "r") as fh:
                raw = yaml.safe_load(fh) or {}
            return _parse_raw(raw)
        except (ImportError, Exception):
            pass
    return MemoryConfig()


def _parse_raw(raw: Dict[str, Any]) -> MemoryConfig:
    """Map a raw YAML dict to MemoryConfig."""
    mem = raw.get("agents", {}).get("defaults", {}).get("memory", {})
    tiers = mem.get("tiers", {})

    cfg = MemoryConfig()

    if "instant" in tiers:
        t = tiers["instant"]
        cfg.instant.enabled = t.get("enabled", True)
        cfg.instant.max_tokens = t.get("maxTokens", 1500)
        cfg.instant.flush_on_compact = t.get("flushOnCompact", True)
        cfg.instant.flush_on_session_end = t.get("flushOnSessionEnd", True)
        cfg.instant.storage_template = t.get("storage", cfg.instant.storage_template)

    if "daily" in tiers:
        t = tiers["daily"]
        cfg.daily.enabled = t.get("enabled", True)
        cfg.daily.max_tokens = t.get("maxTokens", 3000)
        cfg.daily.auto_flush_threshold_tokens = t.get("autoFlushThresholdTokens", 3000)
        cfg.daily.carry_forward_max_tokens = t.get("carryForwardMaxTokens", 500)
        cfg.daily.archive_after_days = t.get("archiveAfterDays", 7)
        cfg.daily.delete_after_days = t.get("deleteAfterDays", 30)
        cfg.daily.storage_template = t.get("storage", cfg.daily.storage_template)

    if "weekly" in tiers:
        t = tiers["weekly"]
        cfg.weekly.enabled = t.get("enabled", True)
        cfg.weekly.max_tokens = t.get("maxTokens", 2000)
        cfg.weekly.distill_time = t.get("distillTime", "23:30")
        cfg.weekly.pin_after_occurrences = t.get("pinAfterOccurrences", 3)
        cfg.weekly.auto_pin_corrections = t.get("autoPinCorrections", True)
        cfg.weekly.storage_template = t.get("storage", cfg.weekly.storage_template)

    if "permanent" in tiers:
        t = tiers["permanent"]
        cfg.permanent.enabled = t.get("enabled", True)
        cfg.permanent.max_tokens = t.get("maxTokens", 3000)
        cfg.permanent.distill_day = t.get("distillDay", "Saturday")
        cfg.permanent.distill_time = t.get("distillTime", "23:45")
        cfg.permanent.storage_template = t.get("storage", cfg.permanent.storage_template)
        cfg.permanent.entity_dir = t.get("entityDir", "memory/entities/")

    comp = mem.get("compaction", {}).get("memoryFlush", {})
    cfg.compaction.memory_flush_enabled = comp.get("enabled", True)
    cfg.compaction.soft_threshold_tokens = comp.get("softThresholdTokens", 4000)

    srch = mem.get("memorySearch", {})
    cfg.search.enabled = srch.get("enabled", True)
    cfg.search.provider = srch.get("provider", "local")
    cfg.search.embedding_model = srch.get("embeddingModel", "all-MiniLM-L6-v2")
    hybrid = srch.get("query", {}).get("hybrid", {})
    cfg.search.vector_weight = hybrid.get("vectorWeight", 0.7)
    cfg.search.text_weight = hybrid.get("textWeight", 0.3)
    cfg.search.candidate_multiplier = hybrid.get("candidateMultiplier", 4)

    return cfg


# ---------------------------------------------------------------------------
# Template variable resolution
# ---------------------------------------------------------------------------

def resolve_template(template: str, session_id: str = "", now: Optional[datetime] = None) -> str:
    """Resolve storage path template variables."""
    now = now or datetime.now()
    replacements = {
        "${SESSION_ID}": session_id,
        "${YYYY-MM-DD}": now.strftime("%Y-%m-%d"),
        "${YYYY}": now.strftime("%Y"),
        "${WW}": f"{now.isocalendar()[1]:02d}",
    }
    result = template
    for var, val in replacements.items():
        result = result.replace(var, val)
    return result


def resolve_path(template: str, session_id: str = "", now: Optional[datetime] = None) -> Path:
    """Resolve a storage template to an absolute workspace path."""
    return workspace_root() / resolve_template(template, session_id, now)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_config(cfg: Optional[MemoryConfig] = None) -> list[str]:
    """Return a list of validation errors (empty list = valid)."""
    cfg = cfg or get_config()
    errors: list[str] = []

    for name, tier in [
        ("instant", cfg.instant),
        ("daily", cfg.daily),
        ("weekly", cfg.weekly),
        ("permanent", cfg.permanent),
    ]:
        if tier.max_tokens <= 0:
            errors.append(f"{name}.max_tokens must be > 0, got {tier.max_tokens}")

    for name, time_str in [
        ("weekly.distill_time", cfg.weekly.distill_time),
        ("permanent.distill_time", cfg.permanent.distill_time),
    ]:
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            errors.append(f"{name} must be HH:MM, got '{time_str}'")

    valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    if cfg.permanent.distill_day not in valid_days:
        errors.append(f"permanent.distill_day must be a weekday name, got '{cfg.permanent.distill_day}'")

    weight_sum = cfg.search.vector_weight + cfg.search.text_weight
    if abs(weight_sum - 1.0) > 0.01:
        errors.append(f"search weights must sum to 1.0, got {weight_sum:.2f}")

    ws = workspace_root()
    if not os.access(ws, os.W_OK):
        errors.append(f"workspace directory is not writable: {ws}")

    return errors


# ---------------------------------------------------------------------------
# Ensure runtime directories exist
# ---------------------------------------------------------------------------

def ensure_directories() -> None:
    """Create all required runtime directories if they don't exist."""
    root = workspace_root()
    for subdir in ["memory", "memory/archive", "memory/entities"]:
        (root / subdir).mkdir(parents=True, exist_ok=True)

    permanent_path = root / "MEMORY.md"
    if not permanent_path.exists():
        permanent_path.write_text(
            "# Permanent Memory\n\n"
            "## User Preferences\n\n"
            "## Architecture Decisions\n\n"
            "## Correction History\n",
            encoding="utf-8",
        )
