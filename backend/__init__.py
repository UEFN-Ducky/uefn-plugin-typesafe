"""TypeSafe / Jev — Store desktop plugin. Decision tiles + MCP tools."""

from __future__ import annotations

from typing import Any

from . import automations, tools


def register(api: Any) -> None:
    automations.register_nodes(api)
    tools.register_tools(api)
    api.log("typesafe tools and automation nodes registered")
