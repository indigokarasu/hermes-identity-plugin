"""Shared utilities for the Identity plugin.

Used by both the gateway plugin (__init__.py) and the dashboard backend (plugin_api.py).
Import with:
    from .shared import IDENTITY_FILES, resolve_active_profile, get_file_path, ...
or adjust sys.path as needed.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

IDENTITY_FILES = ["SOUL.md", "MEMORY.md", "USER.md", "AGENT.md"]


def _resolve_hermes_home() -> Path:
    """Resolve HERMES_HOME from env var, walking up from this file, or fallback."""
    env = os.environ.get("HERMES_HOME", "")
    if env:
        p = Path(env)
        if p.is_dir() and (p / "profiles").is_dir():
            return p
    # Walk up from this file
    cursor = Path(__file__).resolve()
    while cursor != cursor.parent:
        if (cursor / "profiles").is_dir():
            return cursor
        cursor = cursor.parent
    return Path("/root/.hermes")


HERMES_HOME = _resolve_hermes_home()
PROFILES_DIR = HERMES_HOME / "profiles"


def resolve_active_profile() -> str:
    """Return the active profile name."""
    active_file = HERMES_HOME / "active_profile"
    if active_file.exists():
        return active_file.read_text().strip()
    config_file = HERMES_HOME / "config.yaml"
    if config_file.exists():
        try:
            import yaml
            cfg = yaml.safe_load(config_file.read_text())
            if isinstance(cfg, dict):
                profile = cfg.get("profile")
                if profile and isinstance(profile, str):
                    return profile.strip().strip('"').strip("'")
        except Exception:
            pass
    return "default"


def get_file_path(filename: str, profile: str | None = None) -> Path:
    """Resolve an identity file path for the given profile."""
    if profile and profile != "default":
        p = PROFILES_DIR / profile / filename
        if p.exists():
            return p
    p = HERMES_HOME / filename
    if p.exists():
        return p
    if profile and profile != "default":
        return PROFILES_DIR / profile / filename
    return HERMES_HOME / filename


def get_utilization_file() -> Path:
    """Return the path to the line utilization JSON file."""
    return Path(__file__).parent / "data" / "line_utilization.json"


def load_utilization() -> dict[str, str]:
    """Load the line utilization tracking data."""
    f = get_utilization_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {}


def save_utilization(data: dict[str, str]) -> None:
    """Save the line utilization tracking data."""
    f = get_utilization_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


def now_iso() -> str:
    """Current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(iso_str: str) -> datetime:
    """Parse an ISO timestamp string."""
    return datetime.fromisoformat(iso_str)


def relative_timestamp(iso_str: str | None) -> str:
    """Human-readable relative timestamp."""
    if not iso_str:
        return "never"
    try:
        dt = parse_iso(iso_str)
    except Exception:
        return "unknown"
    delta = datetime.now(timezone.utc) - dt
    seconds = delta.total_seconds()
    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    elif seconds < 604800:
        return f"{int(seconds // 86400)}d ago"
    elif seconds < 2592000:
        return f"{int(seconds // 604800)}w ago"
    else:
        return f"{int(seconds // 2592000)}mo ago"


def color_for_timestamp(iso_str: str | None) -> str:
    """green (<6h), yellow (<24h), orange (<1wk), red (infrequent/never)."""
    if not iso_str:
        return "red"
    try:
        dt = parse_iso(iso_str)
    except Exception:
        return "red"
    hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    if hours < 6:
        return "green"
    elif hours < 24:
        return "yellow"
    elif hours < 168:
        return "orange"
    else:
        return "red"
