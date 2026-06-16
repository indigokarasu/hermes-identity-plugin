"""Identity plugin — view/edit identity files, switch profiles, track line utilization."""

import json
import logging
import re
from pathlib import Path

from .shared import (
    IDENTITY_FILES,
    HERMES_HOME,
    PROFILES_DIR,
    resolve_active_profile,
    get_file_path,
    load_utilization,
    save_utilization,
    now_iso,
    relative_timestamp,
    color_for_timestamp,
)

logger = logging.getLogger(__name__)

# ── ANSI helpers (agent-side terminal output only) ────────────────────────────

def _ansi(color: str) -> str:
    return {"green": "\033[92m", "yellow": "\033[93m", "orange": "\033[33m", "red": "\033[91m"}.get(color, "\033[91m")

def _reset() -> str:
    return "\033[0m"

# ── Hook: track line references ───────────────────────────────────────────────

# Simple mtime cache for pre_llm_call hook
_file_cache: dict[str, tuple[float, list[str]]] = {}

def _get_cached_lines(fpath: Path) -> list[str]:
    """Read file lines with mtime-based caching."""
    try:
        mtime = fpath.stat().st_mtime
    except OSError:
        return []
    key = str(fpath)
    cached = _file_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    _file_cache[key] = (mtime, lines)
    return lines

def _on_pre_llm_call(session_id, user_message, conversation_history, is_first_turn, model, platform, **kwargs):
    """Track which identity-file lines are referenced in user messages."""
    if not user_message:
        return None
    util = load_utilization()
    profile = resolve_active_profile()
    updated = False
    user_lower = user_message.lower()
    for fname in IDENTITY_FILES:
        fpath = get_file_path(fname, profile)
        if not fpath.exists():
            continue
        file_lines = _get_cached_lines(fpath)
        if not file_lines:
            continue
        for i, line in enumerate(file_lines):
            stripped = line.strip()
            if len(stripped) < 10 or stripped.startswith("#"):
                continue
            snippet = stripped[:60].lower()
            if snippet in user_lower:
                util[f"{fname}:{i}"] = now_iso()
                updated = True
    if updated:
        save_utilization(util)
    return None

def _on_post_tool_call(tool_name, args, result, task_id, duration_ms, **kwargs):
    """Track identity-file lines referenced in tool arguments."""
    # Quick check before expensive serialization
    if isinstance(args, dict):
        keys_str = " ".join(str(k) for k in args.keys())
        if not any(f in keys_str for f in IDENTITY_FILES):
            # Also check stringified values for file references
            vals_str = " ".join(str(v) for v in args.values() if isinstance(v, str))
            if not any(f in vals_str for f in IDENTITY_FILES):
                return
    elif isinstance(args, str):
        if not any(f in args for f in IDENTITY_FILES):
            return
    else:
        args_str = str(args)
        if not any(f in args_str for f in IDENTITY_FILES):
            return

    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
    util = load_utilization()
    profile = resolve_active_profile()
    args_lower = args_str.lower()
    for fname in IDENTITY_FILES:
        fpath = get_file_path(fname, profile)
        if not fpath.exists():
            continue
        file_lines = _get_cached_lines(fpath)
        if not file_lines:
            continue
        for i, line in enumerate(file_lines):
            stripped = line.strip()
            if len(stripped) < 10 or stripped.startswith("#"):
                continue
            if stripped[:60].lower() in args_lower:
                util[f"{fname}:{i}"] = now_iso()
    save_utilization(util)

# ── Tool handlers ─────────────────────────────────────────────────────────────

def identity_view(args: dict, **kwargs) -> str:
    filename = args.get("filename", "SOUL.md")
    if filename not in IDENTITY_FILES:
        return json.dumps({"error": f"Unknown file. Allowed: {IDENTITY_FILES}"})
    profile = args.get("profile") or resolve_active_profile()
    fpath = get_file_path(filename, profile)
    if not fpath.exists():
        return json.dumps({"error": f"File not found: {fpath}", "hint": "Use identity_edit to create it."})
    lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
    util = load_utilization()
    out = []
    out.append(f"=== {filename} (profile: {profile}) ===")
    for i, line in enumerate(lines):
        key = f"{filename}:{i}"
        ts = util.get(key)
        rel = relative_timestamp(ts) if ts else "never"
        color = color_for_timestamp(ts) if ts else "red"
        out.append(f"{_ansi(color)}[{rel}]{_reset()} {line}")
    return json.dumps({"file": filename, "profile": profile, "path": str(fpath), "total_lines": len(lines), "display": "\n".join(out)})

def identity_edit(args: dict, **kwargs) -> str:
    filename = args.get("filename", "")
    if filename not in IDENTITY_FILES:
        return json.dumps({"error": f"Unknown file. Allowed: {IDENTITY_FILES}"})
    profile = args.get("profile") or resolve_active_profile()
    fpath = get_file_path(filename, profile)
    mode = args.get("mode", "replace_line")
    fpath.parent.mkdir(parents=True, exist_ok=True)
    if mode == "overwrite":
        content = args.get("content", "")
        fpath.write_text(content, encoding="utf-8")
        return json.dumps({"ok": True, "file": str(fpath), "mode": "overwrite", "bytes": len(content)})
    if fpath.exists():
        lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = []
    if mode == "replace_line":
        line_num = args.get("line_num")
        if line_num is None:
            return json.dumps({"error": "line_num required for replace_line"})
        idx = line_num - 1
        if 0 <= idx < len(lines):
            lines[idx] = args.get("content", "")
        else:
            return json.dumps({"error": f"Line {line_num} out of range ({len(lines)} lines)"})
        fpath.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
        return json.dumps({"ok": True, "file": str(fpath), "mode": "replace_line", "line": line_num})
    if mode == "replace_section":
        section = args.get("section", "")
        new_content = args.get("content", "")
        if not section:
            return json.dumps({"error": "section required for replace_section"})
        new_lines = []
        in_section = False
        section_pat = re.compile(rf"^#{1,6}\s+{re.escape(section)}\s*$", re.IGNORECASE)
        heading_pat = re.compile(r"^#{1,6}\s+")
        inserted = False
        for line in lines:
            if section_pat.match(line):
                new_lines.append(line)
                new_lines.append(new_content)
                in_section = True
                inserted = True
                continue
            if in_section and heading_pat.match(line):
                in_section = False
            if not in_section:
                new_lines.append(line)
        if not inserted:
            new_lines.append(f"# {section}")
            new_lines.append(new_content)
        fpath.write_text(("\n".join(new_lines) + "\n") if new_lines else "", encoding="utf-8")
        return json.dumps({"ok": True, "file": str(fpath), "mode": "replace_section", "section": section})
    if mode == "append":
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(args.get("content", ""))
        return json.dumps({"ok": True, "file": str(fpath), "mode": "append"})
    return json.dumps({"error": f"Unknown mode: {mode}"})

def identity_switch_profile(args: dict, **kwargs) -> str:
    profile = args.get("profile", "")
    if not profile:
        return json.dumps({"error": "profile name required", "current": resolve_active_profile()})
    if profile == "default":
        active_file = HERMES_HOME / "active_profile"
        if active_file.exists():
            active_file.unlink()
        return json.dumps({"ok": True, "active_profile": "default", "note": "Switched to default (root). Restart Hermes session for full effect."})
    profile_dir = PROFILES_DIR / profile
    if not profile_dir.exists():
        available = [d.name for d in sorted(PROFILES_DIR.iterdir()) if d.is_dir()]
        available.insert(0, "default")
        return json.dumps({"error": f"Profile '{profile}' not found", "available": available})
    (HERMES_HOME / "active_profile").write_text(profile, encoding="utf-8")
    return json.dumps({"ok": True, "active_profile": profile, "note": "Restart Hermes session for full effect."})

def identity_list_profiles(args: dict, **kwargs) -> str:
    profiles = []
    for d in sorted(PROFILES_DIR.iterdir()):
        if not d.is_dir():
            continue
        pfiles = [f for f in IDENTITY_FILES if (d / f).exists()]
        profiles.append({"name": d.name, "identity_files": pfiles})
    root_files = [f for f in IDENTITY_FILES if (HERMES_HOME / f).exists()]
    if root_files:
        profiles.insert(0, {"name": "default", "identity_files": root_files})
    return json.dumps({"current_profile": resolve_active_profile(), "profiles": profiles})

def identity_dashboard(args: dict, **kwargs) -> str:
    profile = args.get("profile") or resolve_active_profile()
    util = load_utilization()
    show_all = args.get("show_all", False)
    out = []
    out.append("+" + "-" * 50 + "+")
    out.append(f"| IDENTITY DASHBOARD  profile: {profile:<27}|")
    out.append("+" + "-" * 50 + "+")
    out.append(f"  {_ansi('green')}GREEN  = <6h   {_reset()}{_ansi('yellow')}YELLOW = <24h{_reset()}  {_ansi('orange')}ORANGE = <1wk{_reset()}  {_ansi('red')}RED    = infrequent{_reset()}")
    out.append("")
    total_refd = 0
    total_lines = 0
    for fname in IDENTITY_FILES:
        fpath = get_file_path(fname, profile)
        if not fpath.exists():
            out.append(f"-- {fname} -- MISSING --")
            out.append("")
            continue
        lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        total_lines += len(lines)
        refd = 0
        file_out = []
        for i, line in enumerate(lines):
            key = f"{fname}:{i}"
            ts = util.get(key)
            rel = relative_timestamp(ts) if ts else "never"
            color = color_for_timestamp(ts) if ts else "red"
            if ts:
                refd += 1
                total_refd += 1
            if show_all or ts:
                display = line.strip()[:80] if line.strip() else "(blank)"
                file_out.append(f"  {_ansi(color)}{rel:>8}{_reset()} | {display}")
        out.append(f"-- {fname} ({refd}/{len(lines)} referenced) --")
        out.extend(file_out if file_out else ["  (no references tracked yet)"])
        out.append("")
    out.append(f"Total: {total_refd}/{total_lines} lines referenced")
    return json.dumps({"profile": profile, "total_lines": total_lines, "referenced_lines": total_refd, "display": "\n".join(out)})

def identity_reset_usage(args: dict, **kwargs) -> str:
    save_utilization({})
    return json.dumps({"ok": True, "message": "Utilization data cleared"})

# ── Slash command handlers ────────────────────────────────────────────────────

def _handle_slash_identity(raw_args: str) -> str:
    args = raw_args.strip().split()
    if args and args[0] in IDENTITY_FILES:
        result = identity_view({"filename": args[0]})
    else:
        result = identity_dashboard({})
    data = json.loads(result)
    return data.get("display", result)

def _handle_slash_switch(raw_args: str) -> str:
    profile = raw_args.strip()
    if not profile:
        return f"Current profile: {resolve_active_profile()}\nUsage: /identity-switch <profile>"
    data = json.loads(identity_switch_profile({"profile": profile}))
    if data.get("ok"):
        return f"[OK] Switched to: {data['active_profile']}\nNote: {data['note']}"
    return f"Error: {data.get('error', 'unknown')}"

def _handle_slash_dashboard(raw_args: str) -> str:
    data = json.loads(identity_dashboard({"show_all": "--all" in raw_args}))
    return data.get("display", str(data))

# ── CLI command ───────────────────────────────────────────────────────────────

def _setup_cli(subparser):
    subs = subparser.add_subparsers(dest="identity_command")
    subs.add_parser("view", help="View an identity file")
    subs.add_parser("edit", help="Edit an identity file")
    subs.add_parser("switch", help="Switch profile")
    subs.add_parser("profiles", help="List profiles")
    subs.add_parser("dashboard", help="Show utilization dashboard")
    subs.add_parser("reset-usage", help="Reset utilization data")

def _handle_cli(args):
    cmd = getattr(args, "identity_command", None) or "dashboard"
    if cmd == "profiles":
        print(json.dumps(json.loads(identity_list_profiles({})), indent=2))
    elif cmd == "switch":
        print("Usage: hermes identity switch <profile-name>")
    elif cmd == "view":
        print("Usage: hermes identity view <filename>")
    elif cmd == "edit":
        print("Usage: hermes identity edit <filename>")
    elif cmd == "reset-usage":
        print(json.loads(identity_reset_usage({}))["message"])
    else:
        data = json.loads(identity_dashboard({}))
        print(data.get("display", str(data)))

# ── Registration ──────────────────────────────────────────────────────────────

def register(ctx):
    ctx.register_tool(name="identity_view", toolset="identity",
        schema={"name": "identity_view",
            "description": "View an identity file (SOUL.md, MEMORY.md, USER.md, AGENT.md) with utilization timestamps shown as color-coded ANSI lines.",
            "parameters": {"type": "object",
                "properties": {"filename": {"type": "string", "enum": IDENTITY_FILES, "description": "Which identity file to view"},
                    "profile": {"type": "string", "description": "Profile name (defaults to active)"}},
                "required": ["filename"]}},
        handler=identity_view)
    ctx.register_tool(name="identity_edit", toolset="identity",
        schema={"name": "identity_edit",
            "description": "Edit an identity file. Modes: overwrite, replace_line (needs line_num), replace_section (needs section), append.",
            "parameters": {"type": "object",
                "properties": {"filename": {"type": "string", "enum": IDENTITY_FILES},
                    "mode": {"type": "string", "enum": ["overwrite", "replace_line", "replace_section", "append"]},
                    "content": {"type": "string", "description": "New text"},
                    "line_num": {"type": "integer"}, "section": {"type": "string"},
                    "profile": {"type": "string"}},
                "required": ["filename"]}},
        handler=identity_edit)
    ctx.register_tool(name="identity_switch_profile", toolset="identity",
        schema={"name": "identity_switch_profile",
            "description": "Switch the active Hermes profile.",
            "parameters": {"type": "object",
                "properties": {"profile": {"type": "string", "description": "Profile name"}},
                "required": ["profile"]}},
        handler=identity_switch_profile)
    ctx.register_tool(name="identity_list_profiles", toolset="identity",
        schema={"name": "identity_list_profiles",
            "description": "List all available Hermes profiles.",
            "parameters": {"type": "object", "properties": {}}},
        handler=identity_list_profiles)
    ctx.register_tool(name="identity_dashboard", toolset="identity",
        schema={"name": "identity_dashboard",
            "description": "Utilization dashboard with color-coded timestamps (green/yellow/orange/red).",
            "parameters": {"type": "object",
                "properties": {"profile": {"type": "string"},
                    "show_all": {"type": "boolean", "description": "Show all lines including unreferenced"}}},
            },
        handler=identity_dashboard)
    ctx.register_tool(name="identity_reset_usage", toolset="identity",
        schema={"name": "identity_reset_usage",
            "description": "Reset utilization tracking.",
            "parameters": {"type": "object", "properties": {}}},
        handler=identity_reset_usage)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_command("identity", _handle_slash_identity, description="View identity files and utilization")
    ctx.register_command("identity-switch", _handle_slash_switch, description="Switch profile")
    ctx.register_command("identity-dashboard", _handle_slash_dashboard, description="Show utilization dashboard")
    ctx.register_cli_command(name="identity", help="Manage identity files and profiles",
        setup_fn=_setup_cli, handler_fn=_handle_cli)
