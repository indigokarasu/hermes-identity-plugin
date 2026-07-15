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

# AGENT.md does not exist on most profiles; when requested and not found,
# the plugin falls back to HERMES.md (which IS present on indigo).
_AGENT_FALLBACK = "HERMES.md"

# Files that may live under <profile>/memories/ instead of <profile>/ root
_MEMORIES_FILES = {"MEMORY.md", "USER.md"}


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


# ── Dashboard open-profile detection ──────────────────────────────────────

def _get_dashboard_open_profile() -> str:
    """Read ``--open-profile`` from /proc/self/cmdline.

    The dashboard server passes ``--open-profile <name>`` to tell the web UI
    which profile tab to open.  The plugin API runs *inside* the dashboard
    process and should honour this value as the default profile instead of
    the stale ``active_profile`` file which may reference a non-existent
    profile (e.g. ``commons``).

    Returns the empty string when not running in a dashboard context.
    """
    try:
        with open("/proc/self/cmdline", "rb") as f:
            raw = f.read().decode("utf-8", errors="replace")
        args = raw.split("\0")
        for i, a in enumerate(args):
            if a == "--open-profile" and i + 1 < len(args):
                return args[i + 1].strip()
    except Exception:
        pass
    return ""


def resolve_active_profile(resolve_dashboard: bool = True) -> str:
    """Return the active profile name.

    When *resolve_dashboard* is True (the default) and the current process
    is a dashboard server (``--open-profile`` is set), that value takes
    precedence over the stale ``active_profile`` file.  This ensures the
    plugin API shows the profile the user asked to open, not whatever
    ``/root/.hermes/active_profile`` contains (often ``commons`` — a
    non-existent profile resulting in a fallback to root files).

    Priority:
      1. Dashboard's ``--open-profile`` (if *resolve_dashboard* is True)
      2. ``HERMES_HOME/active_profile`` file
      3. ``config.yaml`` profile key
      4. ``"default"``
    """
    if resolve_dashboard:
        dp = _get_dashboard_open_profile()
        if dp:
            return dp

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
    """Resolve an identity file path for the given profile.

    Search order (profile root → profile memories/ → hermes root → root memories/):

    1. ``<profile>/<filename>`` (e.g. ``profiles/indigo/SOUL.md``)
    2. ``<profile>/memories/<filename>`` (e.g. ``profiles/indigo/memories/MEMORY.md``)
    3. ``HERMES_HOME/<filename>`` (root-level fallback)
    4. ``HERMES_HOME/memories/<filename>`` (root-level memories)
    5. If AGENT.md is requested and not found, try ``HERMES_HOME/<profile>/HERMES.md``
    """
    if profile and profile != "default":
        p = PROFILES_DIR / profile / filename
        if p.exists():
            return p
        # Try memories/ subdir (MEMORY.md, USER.md often live here)
        if filename in _MEMORIES_FILES:
            p = PROFILES_DIR / profile / "memories" / filename
            if p.exists():
                return p
        # AGENT.md → HERMES.md fallback
        if filename == "AGENT.md":
            p = PROFILES_DIR / profile / _AGENT_FALLBACK
            if p.exists():
                return p

    p = HERMES_HOME / filename
    if p.exists():
        return p
    # Root-level memories/
    if filename in _MEMORIES_FILES:
        p = HERMES_HOME / "memories" / filename
        if p.exists():
            return p
    # AGENT.md → HERMES.md at root level
    if filename == "AGENT.md":
        p = HERMES_HOME / _AGENT_FALLBACK
        if p.exists():
            return p

    # Return the best-guess path even if it doesn't exist
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


# ── Line matching heuristic helpers ────────────────────────────────────────

# Tokens too common to count as an agent "using" a fact line.
_STOP_WORDS: set[str] = {
    # pronouns / short identity bits
    "they", "them", "their", "he", "him", "his", "she", "her", "hers",
    "it", "its", "we", "us", "our", "you", "your", "me", "my", "i",
    # common short words that trigger false positives
    "the", "and", "for", "are", "but", "not", "you", "all", "can",
    "had", "her", "was", "one", "our", "out", "has", "have", "been",
    "some", "same", "also", "very", "just", "than", "them", "then",
    "that", "this", "with", "will", "what", "when", "where", "which",
    "who", "how", "why",
}

# Minimum value length (in chars) to qualify as a match.  Shorter values
# produce too many false positives (pronouns, single words).
_MIN_VALUE_LEN = 8


def _match_identity_line(stripped: str, text: str) -> bool:
    """Check whether *text* (lowercased) indicates the agent used a fact line.

    Two matching strategies:

    1. **Verbatim prefix** — the first 60 chars of the line appear in *text*.
       Catches exact references (e.g. the agent echoes a SOUL.md fragment).

    2. **Value match** — for ``key: value`` lines, the value portion (after
       the first ``:``) appears in *text*, has length ≥ *_MIN_VALUE_LEN*,
       and is not a stop-word.  Catches natural-language usage (e.g. the
       agent says "I'm Indigo" and ``Name: Indigo Karasu`` has value
       ``Indigo Karasu`` → match).

    This is a heuristic — there is no ground-truth per-line usage signal
    because the whole identity file loads into the system prompt every turn.
    The goal is to surface markers that plausibly reflect the agent leaning
    on a fact, not to count every prompt-byte.
    """
    snippet = stripped[:60].lower()
    if not snippet:
        return False

    if snippet in text:
        return True

    # Value-match for key: value lines
    if ":" in stripped:
        _, _, value = stripped.partition(":")
        value = value.strip()
        if len(value) >= _MIN_VALUE_LEN and value.lower() not in _STOP_WORDS:
            if value.lower() in text:
                return True

    return False