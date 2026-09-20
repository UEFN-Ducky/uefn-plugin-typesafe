"""Installed ducky profiles → Jev Choice criteria (cap 255)."""

from __future__ import annotations

from typing import Any

from .client import _MAX_CHOICE

FALLBACK_CRITERIA: dict[str, str] = {
    "verse": "Verse compile, devices, wiring.",
    "leveldesign": "Layout, props, world building.",
    "materials": "Materials and lookdev.",
    "tester": "Playtest, devices, verification.",
    "default": "General island work.",
}

ROUTE_INSTRUCTIONS = (
    "Which installed ducky profile should handle this ask? "
    "Pick the specialist whose description matches the work."
)


def _as_map(raw: Any) -> dict[str, str]:
    if isinstance(raw, str) and raw.strip():
        import json

        raw = json.loads(raw)
    if not isinstance(raw, dict) or not raw:
        return {}
    return {str(k): str(v if v is not None else k) for k, v in list(raw.items())[:_MAX_CHOICE]}


def list_installed_criteria() -> dict[str, str]:
    try:
        from frontend.agent_profiles import list_agent_profiles_available

        rows = list_agent_profiles_available() or []
    except Exception:
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or "").strip()
        name = str(row.get("name") or pid).strip()
        if not pid:
            continue
        when = str(
            row.get("when_to_use") or row.get("description") or name
        ).strip()
        out[pid] = when or name
        if len(out) >= _MAX_CHOICE:
            break
    return out


def list_ducky_criteria(override: Any = None) -> dict[str, str]:
    mapped = _as_map(override)
    if mapped:
        return mapped
    return list_installed_criteria() or dict(FALLBACK_CRITERIA)
