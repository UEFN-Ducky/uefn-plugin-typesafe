"""Mocked TypeSafe HTTP + flatten/validate. No live key."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest import mock

from . import client


def test_normalize_questions_ok() -> None:
    qs = client.normalize_questions(
        {
            "urgent": {"type": "noul", "instructions": "Urgent?"},
            "team": {
                "type": "choice",
                "instructions": "Which team?",
                "criteria": {"billing": "pay", "tech": "bugs"},
            },
            "mood": {
                "type": "score",
                "instructions": "Frustration",
                "criteria": ["Calm", "Mad", "Furious"],
            },
        }
    )
    assert qs["urgent"]["type"] == "noul"
    assert qs["team"]["criteria"]["billing"] == "pay"
    assert qs["mood"]["criteria"][2] == "Furious"


def test_normalize_questions_rejects_bad() -> None:
    try:
        client.normalize_questions({"x": {"type": "essay", "instructions": "hi"}})
        raise AssertionError("should fail")
    except client.TypeSafeError as exc:
        assert "noul" in str(exc)


def test_flatten_sets_gate_and_ducky() -> None:
    out = client.flatten_response(
        {
            "model": "jev-1.13.0",
            "answers": {
                "urgent": {"type": "noul", "noul": 0.91},
                "who": {
                    "type": "choice",
                    "choice": "verse",
                    "probabilities": {"verse": 0.8, "default": 0.2},
                    "confidence": 0.6,
                },
            },
            "usage": {"input_tokens": 10},
        },
        threshold=0.7,
    )
    assert out["ok"] is True
    assert out["noul"] == 0.91
    assert out["gate"] is True
    assert out["choice"] == "verse"
    assert out["ducky"] == "verse"
    assert out["confidence"] == 0.6


def test_flatten_score_gate() -> None:
    out = client.flatten_response(
        {
            "answers": {
                "sev": {
                    "type": "score",
                    "score": 0.4,
                    "legend": {"0": "ok", "1": "bad"},
                    "probabilities": {"0": 0.7, "1": 0.3},
                    "confidence": 0.5,
                }
            }
        },
        threshold=1.0,
    )
    assert out["score"] == 0.4
    assert out["gate"] is False


class _FakeResp:
    def __init__(self, body: dict) -> None:
        self._raw = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_system_one_posts_body() -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(req: object, timeout: float = 0) -> _FakeResp:
        captured["url"] = getattr(req, "full_url", "")
        captured["body"] = json.loads(req.data.decode())  # type: ignore[attr-defined]
        return _FakeResp(
            {"model": "jev-1.13.0", "answers": {"urgent": {"type": "noul", "noul": 0.2}}}
        )

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        raw = client.system_one(
            "tsk_test",
            "hello",
            {"urgent": {"type": "noul", "instructions": "Urgent?"}},
            model="jev-latest",
        )
    assert captured["url"] == "https://api.typesafe.ai/v1/systemone"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["state"] == "hello"
    assert body["questions"]["urgent"]["type"] == "noul"
    assert raw["answers"]["urgent"]["noul"] == 0.2


def test_retry_once_on_429() -> None:
    hits = {"n": 0}

    def fake_urlopen(req: object, timeout: float = 0) -> _FakeResp:
        hits["n"] += 1
        if hits["n"] == 1:
            err = urllib.error.HTTPError(
                "https://api.typesafe.ai/v1/models",
                429,
                "rate",
                {"Retry-After": "0"},
                io.BytesIO(b'{"error":"slow down"}'),
            )
            raise err
        return _FakeResp({"models": [{"name": "jev-latest"}]})

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        with mock.patch("time.sleep", lambda _s: None):
            payload = client.list_models("tsk_test")
    assert hits["n"] == 2
    assert payload["models"][0]["name"] == "jev-latest"


def test_run_decide_no_key() -> None:
    with mock.patch.object(client, "api_key", return_value=""):
        out = client.run_decide("x", {"a": {"type": "noul", "instructions": "y"}})
    assert out["ok"] is False
    assert "key" in out["error"].lower()


if __name__ == "__main__":
    test_normalize_questions_ok()
    test_normalize_questions_rejects_bad()
    test_flatten_sets_gate_and_ducky()
    test_flatten_score_gate()
    test_system_one_posts_body()
    test_retry_once_on_429()
    test_run_decide_no_key()
    print("test_client ok")
