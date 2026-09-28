"""MCP tools — same client as automation tiles."""

from __future__ import annotations

import json
from typing import Any

from . import client
from .profiles import ROUTE_INSTRUCTIONS, list_ducky_criteria


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)


def _connection_row() -> dict[str, Any]:
    key = client.api_key()
    if not key:
        return {"online": False, "detail": "No TypeSafe API key"}
    checked = client.test_api_key(key)
    return {"online": bool(checked.get("ok")), "detail": str(checked.get("detail") or "")}


def register_tools(api: Any) -> None:
    if hasattr(api, "register_secret_test"):
        api.register_secret_test(client.SECRET_KEY, client.test_api_key)

    @api.tool(name="typesafe_status", intent=client.INTENT, listener=False)
    def typesafe_status() -> str:
        """Report TypeSafe key presence, default Jev model, and connection."""
        key = client.api_key()
        row = _connection_row()
        return _dumps(
            {
                "ok": True,
                "has_key": bool(key),
                "model": client.default_model(),
                "online": row["online"],
                "detail": row["detail"],
            }
        )

    @api.tool(name="typesafe_list_models", intent=client.INTENT, listener=False)
    def typesafe_list_models() -> str:
        """List TypeSafe model aliases (GET /v1/models)."""
        key = client.api_key()
        if not key:
            return _dumps({"ok": False, "error": "Paste a TypeSafe API key in Settings → LLMs → TypeSafe."})
        try:
            return _dumps({"ok": True, **client.list_models(key)})
        except client.TypeSafeError as exc:
            return _dumps({"ok": False, "error": str(exc), "status": exc.status})

    @api.tool(name="typesafe_decide", intent=client.INTENT, listener=False)
    def typesafe_decide(state: Any, questions: dict[str, Any] | str, model: str = "") -> str:
        """Ask Jev many typed questions in one call. questions is {id: {type, instructions, criteria?}}."""
        return _dumps(client.run_decide(state, questions, model=model))

    @api.tool(name="typesafe_route_ducky", intent=client.INTENT, listener=False)
    def typesafe_route_ducky(state: Any, profiles_json: str = "") -> str:
        """Pick which installed ducky should handle state. Returns ducky/choice/confidence."""
        criteria = list_ducky_criteria(profiles_json or None)
        result = client.run_decide(
            state,
            {
                "ducky": {
                    "type": "choice",
                    "instructions": ROUTE_INSTRUCTIONS,
                    "criteria": criteria,
                }
            },
        )
        if result.get("ok"):
            result.setdefault("ducky", result.get("choice"))
        return _dumps(result)
