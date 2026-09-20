"""Automation tiles + plugin.json graphs. No live TypeSafe key."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from . import automations, client, profiles

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_json_nodes_and_templates() -> None:
    data = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    ids = {n["id"] for n in data["contributes"]["automations"]["nodes"]}
    assert ids == set(automations.NODES)
    tpls = {t["id"] for t in data["contributes"]["automations"]["templates"]}
    assert tpls == {
        "typesafe-route-specialist",
        "typesafe-gate-then-act",
        "typesafe-verse-vs-art",
        "typesafe-guardrail",
        "typesafe-score-then-continue",
        "typesafe-manual-gate",
    }
    specialist = next(
        t for t in data["contributes"]["automations"]["templates"] if t["id"] == "typesafe-route-specialist"
    )
    types = {n["type"] for n in specialist["graph"]["nodes"]}
    assert "typesafe.route_ducky" in types
    assert "pipeline.agent" in types
    assert "ducky.spawn" not in types


def test_register_nodes() -> None:
    names: list[str] = []

    class Api:
        def register_automation_node(self, name: str, _fn: object) -> None:
            names.append(name)

    automations.register_nodes(Api())
    assert names == list(automations.NODES)


def test_choice_requires_criteria() -> None:
    assert automations.handle_choice({"config": {}}) == {
        "ok": False,
        "error": "choice node needs a criteria map",
    }


def test_noul_writes_gate() -> None:
    def fake_decide(state, questions, *, model="", threshold=0.7, api_key_value=""):
        assert questions["gate"]["type"] == "noul"
        return client.flatten_response(
            {"answers": {"gate": {"type": "noul", "noul": 0.95}}},
            threshold=threshold,
        )

    with mock.patch.object(client, "run_decide", fake_decide):
        out = automations.handle_noul(
            {
                "config": {"instructions": "Actionable?", "threshold": 0.7},
                "payload": {"prompt": "fix the verse compile"},
            }
        )
    assert out["ok"] is True
    assert out["gate"] is True
    assert out["noul"] == 0.95


def test_route_ducky_sets_ducky() -> None:
    def fake_decide(state, questions, *, model="", threshold=0.7, api_key_value=""):
        assert questions["ducky"]["type"] == "choice"
        assert "verse" in questions["ducky"]["criteria"]
        return client.flatten_response(
            {
                "answers": {
                    "ducky": {
                        "type": "choice",
                        "choice": "verse",
                        "probabilities": {"verse": 1},
                        "confidence": 0.9,
                    }
                }
            }
        )

    with mock.patch.object(client, "run_decide", fake_decide):
        with mock.patch.object(profiles, "list_ducky_criteria", return_value=dict(profiles.FALLBACK_CRITERIA)):
            out = automations.handle_route_ducky({"config": {}, "payload": {"prompt": "script error 3509"}})
    assert out["ducky"] == "verse"
    assert out["choice"] == "verse"


def test_pick_state_prefers_prompt() -> None:
    assert automations.pick_state({}, {"prompt": "hi", "text": "no"}) == "hi"
    assert automations.pick_state({"state_field": "content"}, {"content": "x", "prompt": "y"}) == "x"


def test_install_contract() -> None:
    """Store install gates: id, skill folder, no secrets packed, py_compile."""
    import py_compile
    import zipfile

    data = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    assert data["id"] == "typesafe"
    assert "typesafe_api_key" in data["secret_keys"]
    skill = (ROOT / "skills" / "typesafe" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---")
    assert "name: typesafe" in skill.split("---", 2)[1]
    for path in (ROOT / "backend").glob("*.py"):
        if path.name.startswith("test_"):
            continue
        py_compile.compile(str(path), doraise=True)
    sys_path_zip = ROOT / "deploy" / "typesafe-1.0.0.ducky-plugin.zip"
    if sys_path_zip.is_file():
        with zipfile.ZipFile(sys_path_zip) as zf:
            names = zf.namelist()
        assert "plugin.json" in names
        assert "backend/__init__.py" in names
        assert "skills/typesafe/SKILL.md" in names
        assert not any(n.endswith(".env") or n.endswith(".key") for n in names)
        assert "backend/test_client.py" not in names
        assert not any(n.startswith(".github/") for n in names)


if __name__ == "__main__":
    test_plugin_json_nodes_and_templates()
    test_register_nodes()
    test_choice_requires_criteria()
    test_noul_writes_gate()
    test_route_ducky_sets_ducky()
    test_pick_state_prefers_prompt()
    test_install_contract()
    print("test_automations ok")
