"""TypeSafe / Jev — Store desktop plugin. Decision tiles + MCP tools."""

from __future__ import annotations

from typing import Any

from . import automations, tools


def _refuse_chat(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError("TypeSafe is a judge, not a chat model")


def register(api: Any) -> None:
    from . import client

    automations.register_nodes(api)
    tools.register_tools(api)
    if hasattr(api, "register_llm_provider"):
        api.register_llm_provider(
            "typesafe",
            factory=_refuse_chat,
            test_key=client.test_api_key,
        )
    api.log("typesafe tools and automation nodes registered")
