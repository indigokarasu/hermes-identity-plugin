"""Identity dashboard plugin — FastAPI backend routes."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

import sys
from pathlib import Path

# Add plugin root to path so we can import shared
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from shared import (
    IDENTITY_FILES,
    HERMES_HOME,
    PROFILES_DIR,
    resolve_active_profile,
    get_file_path,
    load_utilization,
    save_utilization,
    relative_timestamp,
    color_for_timestamp,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/view")
async def view_file(filename: str, profile: str | None = None) -> dict[str, Any]:
    """Return file content with per-line utilization data."""
    if filename not in IDENTITY_FILES:
        raise HTTPException(400, f"Unknown file. Allowed: {IDENTITY_FILES}")
    profile = profile or resolve_active_profile()
    fpath = get_file_path(filename, profile)
    if not fpath.exists():
        raise HTTPException(404, f"File not found: {fpath}")

    lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
    util = load_utilization()

    result_lines = []
    for i, line in enumerate(lines):
        key = f"{filename}:{i}"
        ts = util.get(key)
        result_lines.append({
            "line_num": i + 1,
            "content": line,
            "utilized_at": ts,
            "relative": relative_timestamp(ts),
            "color": color_for_timestamp(ts),
        })

    referenced = sum(1 for l in result_lines if l["utilized_at"] is not None)

    return {
        "filename": filename,
        "profile": profile,
        "path": str(fpath),
        "total_lines": len(lines),
        "referenced_lines": referenced,
        "lines": result_lines,
    }


@router.post("/edit")
async def edit_file(body: dict[str, Any]) -> dict[str, Any]:
    """Edit an identity file. Supports modes: overwrite, replace_line, replace_section, append."""
    import re

    filename = body.get("filename", "")
    if filename not in IDENTITY_FILES:
        raise HTTPException(400, f"Unknown file. Allowed: {IDENTITY_FILES}")

    profile = body.get("profile") or resolve_active_profile()
    fpath = get_file_path(filename, profile)
    mode = body.get("mode", "replace_line")
    fpath.parent.mkdir(parents=True, exist_ok=True)

    if mode == "overwrite":
        content = body.get("content", "")
        fpath.write_text(content, encoding="utf-8")
        return {"ok": True, "file": str(fpath), "mode": "overwrite", "bytes": len(content)}

    if fpath.exists():
        file_lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        file_lines = []

    if mode == "replace_line":
        line_num = body.get("line_num")
        if line_num is None:
            raise HTTPException(400, "line_num required for replace_line")
        idx = line_num - 1
        if 0 <= idx < len(file_lines):
            file_lines[idx] = body.get("content", "")
        else:
            raise HTTPException(400, f"Line {line_num} out of range ({len(file_lines)} lines)")
        fpath.write_text(("\n".join(file_lines) + "\n") if file_lines else "", encoding="utf-8")
        return {"ok": True, "file": str(fpath), "mode": "replace_line", "line": line_num}

    if mode == "replace_section":
        section = body.get("section", "")
        new_content = body.get("content", "")
        if not section:
            raise HTTPException(400, "section required for replace_section")
        new_lines: list[str] = []
        in_section = False
        section_pat = re.compile(rf"^#{1,6}\s+{re.escape(section)}\s*$", re.IGNORECASE)
        heading_pat = re.compile(r"^#{1,6}\s+")
        inserted = False
        for line in file_lines:
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
        return {"ok": True, "file": str(fpath), "mode": "replace_section", "section": section}

    if mode == "append":
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(body.get("content", ""))
        return {"ok": True, "file": str(fpath), "mode": "append"}

    raise HTTPException(400, f"Unknown mode: {mode}")


@router.get("/profiles")
async def list_profiles() -> dict[str, Any]:
    """List all available profiles and their identity files."""
    profiles: list[dict[str, Any]] = []
    for d in sorted(PROFILES_DIR.iterdir()):
        if not d.is_dir():
            continue
        pfiles = [f for f in IDENTITY_FILES if (d / f).exists()]
        profiles.append({"name": d.name, "identity_files": pfiles})
    root_files = [f for f in IDENTITY_FILES if (HERMES_HOME / f).exists()]
    if root_files:
        profiles.insert(0, {"name": "default", "identity_files": root_files})
    return {"current_profile": resolve_active_profile(), "profiles": profiles}


@router.post("/switch-profile")
async def switch_profile(body: dict[str, Any]) -> dict[str, Any]:
    """Switch the active profile."""
    profile = body.get("profile", "")
    if not profile:
        raise HTTPException(400, "profile name required")
    if profile == "default":
        active_file = HERMES_HOME / "active_profile"
        if active_file.exists():
            active_file.unlink()
        return {"ok": True, "active_profile": "default"}
    profile_dir = PROFILES_DIR / profile
    if not profile_dir.exists():
        available = [d.name for d in sorted(PROFILES_DIR.iterdir()) if d.is_dir()]
        available.insert(0, "default")
        raise HTTPException(404, f"Profile '{profile}' not found", detail={"available": available})
    (HERMES_HOME / "active_profile").write_text(profile, encoding="utf-8")
    return {"ok": True, "active_profile": profile}


@router.get("/dashboard")
async def utilization_dashboard(profile: str | None = None) -> dict[str, Any]:
    """Return utilization data for all identity files."""
    profile = profile or resolve_active_profile()
    util = load_utilization()
    files_data: list[dict[str, Any]] = []
    total_refd = 0
    total_lines = 0

    for fname in IDENTITY_FILES:
        fpath = get_file_path(fname, profile)
        if not fpath.exists():
            files_data.append({
                "name": fname,
                "exists": False,
                "total_lines": 0,
                "referenced_lines": 0,
                "lines": [],
            })
            continue
        lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        total_lines += len(lines)
        refd = 0
        line_data: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            key = f"{fname}:{i}"
            ts = util.get(key)
            if ts:
                refd += 1
                total_refd += 1
            line_data.append({
                "line_num": i + 1,
                "content": line,
                "utilized_at": ts,
                "relative": relative_timestamp(ts),
                "color": color_for_timestamp(ts),
            })
        files_data.append({
            "name": fname,
            "exists": True,
            "total_lines": len(lines),
            "referenced_lines": refd,
            "lines": line_data,
        })

    return {
        "profile": profile,
        "total_lines": total_lines,
        "referenced_lines": total_refd,
        "files": files_data,
    }


@router.post("/reset-usage")
async def reset_usage() -> dict[str, Any]:
    """Clear all utilization tracking data."""
    save_utilization({})
    return {"ok": True, "message": "Utilization data cleared"}
