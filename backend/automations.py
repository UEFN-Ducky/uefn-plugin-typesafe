"""Automations + Pipelines tiles. Same client as MCP tools."""

from __future__ import annotations

import json
from typing import Any

from . import client
from .profiles import ROUTE_INSTRUCTIONS, list_ducky_criteria

NODES = (
    "typesafe.noul",
    "typesafe.choice",
    "typesafe.score",
    "typesafe.decide",
    "typesafe.route_ducky",
)


def register_nodes(api: Any) -> None:
    if not hasattr(api, "register_automation_node"):
        return
    api.register_automation_node("typesafe.noul", handle_noul)
    api.register_automation_node("typesafe.choice", handle_choice)
    api.register_automation_node("typesafe.score", handle_score)
    api.register_automation_node("typesafe.decide", handle_decide)
    api.register_automation_node("typesafe.route_ducky", handle_route_ducky)


def _pair(ctx: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = ctx.get("config") if isinstance(ctx.get("config"), dict) else {}
    payload = ctx.get("payload") if isinstance(ctx.get("payload"), dict) else {}
    return cfg, payload


def _parse_json(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return fallback
    return fallback


def pick_state(cfg: dict[str, Any], payload: dict[str, Any]) -> Any:
    field = str(cfg.get("state_field") or "").strip()
    if field:
        val = payload.get(field)
        if val not in (None, ""):
            return val
    for key in ("prompt", "text", "content"):
        val = payload.get(key)
        if val not in (None, ""):
            return val
    if cfg.get("state") not in (None, ""):
        return cfg.get("state")
    slim = {
        key: payload[key]
        for key in payload
        if key in ("prompt", "text", "title", "message")
    }
    if slim:
        return slim
    skip = {"files", "artifact_dir", "caller_conv_id", "group_id"}
    return {key: payload[key] for key in list(payload)[:8] if key not in skip}


def _threshold(cfg: dict[str, Any]) -> float:
    raw = cfg.get("threshold")
    if raw in (None, ""):
        return client.DEFAULT_THRESHOLD
    try:
        return float(raw)
    except (TypeError, ValueError):
        return client.DEFAULT_THRESHOLD


def _run(cfg: dict[str, Any], payload: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
    return client.run_decide(
        pick_state(cfg, payload),
        questions,
        model=str(cfg.get("model") or ""),
        threshold=_threshold(cfg),
    )


def handle_noul(ctx: dict[str, Any]) -> dict[str, Any]:
    cfg, payload = _pair(ctx)
    instructions = str(cfg.get("instructions") or "Is this an actionable request?").strip()
    question: dict[str, Any] = {"type": "noul", "instructions": instructions}
    crit = _parse_json(cfg.get("criteria"), None)
    if isinstance(crit, dict) and crit:
        question["criteria"] = crit
    return _run(cfg, payload, {"gate": question})


def handle_choice(ctx: dict[str, Any]) -> dict[str, Any]:
    cfg, payload = _pair(ctx)
    criteria = _parse_json(cfg.get("criteria"), None)
    if not isinstance(criteria, dict) or not criteria:
        return {"ok": False, "error": "choice node needs a criteria map"}
    return _run(
        cfg,
        payload,
        {
            "choice": {
                "type": "choice",
                "instructions": str(cfg.get("instructions") or "Which option fits?").strip(),
                "criteria": criteria,
            }
        },
    )


def handle_score(ctx: dict[str, Any]) -> dict[str, Any]:
    cfg, payload = _pair(ctx)
    criteria = _parse_json(cfg.get("criteria"), None)
    if not isinstance(criteria, list):
        return {"ok": False, "error": "score node needs a criteria list of 2-10 levels"}
    return _run(
        cfg,
        payload,
        {
            "score": {
                "type": "score",
                "instructions": str(cfg.get("instructions") or "Rate this.").strip(),
                "criteria": criteria,
            }
        },
    )


def handle_decide(ctx: dict[str, Any]) -> dict[str, Any]:
    cfg, payload = _pair(ctx)
    questions = _parse_json(cfg.get("questions"), None)
    if not isinstance(questions, dict) or not questions:
        return {"ok": False, "error": "decide node needs a questions object"}
    return _run(cfg, payload, questions)


def handle_route_ducky(ctx: dict[str, Any]) -> dict[str, Any]:
    cfg, payload = _pair(ctx)
    criteria = list_ducky_criteria(cfg.get("criteria"))
    return _run(
        cfg,
        payload,
        {
            "ducky": {
                "type": "choice",
                "instructions": str(cfg.get("instructions") or ROUTE_INSTRUCTIONS).strip(),
                "criteria": criteria,
            }
        },
    )
