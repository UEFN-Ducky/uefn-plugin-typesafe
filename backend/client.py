"""TypeSafe / Jev HTTP client. Stdlib only."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

PLUGIN_ID = "typesafe"
SECRET_KEY = "typesafe"
# Previous Settings tab stored the key under this name.
_LEGACY_SECRET_KEY = "typesafe_api_key"
BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
DEFAULT_THRESHOLD = 0.7
INTENT = r"\b(jev|typesafe|system ?one|noul)\b"
_MAX_CHOICE = 255
_RETRY_STATUSES = frozenset({429, 529})


class TypeSafeError(Exception):
    def __init__(self, message: str, status: int = 0, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def api_key(explicit: str = "") -> str:
    if (explicit or "").strip():
        return explicit.strip()
    try:
        from backend.agent.secrets import get_key, set_key

        current = (get_key(SECRET_KEY) or "").strip()
        if current:
            return current
        legacy = (get_key(_LEGACY_SECRET_KEY) or "").strip()
        if not legacy:
            return ""
        try:
            set_key(SECRET_KEY, legacy)
        except Exception:
            pass
        return legacy
    except Exception:
        return ""


def default_model() -> str:
    try:
        from frontend.ui_web.plugin_host_api import prefs_all_get

        slot = (prefs_all_get() or {}).get(PLUGIN_ID) or {}
        model = str(slot.get("model") or "").strip()
        if model:
            return model
    except Exception:
        pass
    return DEFAULT_MODEL


def normalize_questions(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = json.loads(raw) if raw.strip() else {}
    if not isinstance(raw, dict) or not raw:
        raise TypeSafeError("questions must be a non-empty object")
    out: dict[str, Any] = {}
    for key, q in raw.items():
        if not isinstance(q, dict):
            raise TypeSafeError(f"question {key} must be an object")
        kind = str(q.get("type") or "").strip().lower()
        instructions = str(q.get("instructions") or "").strip()
        if kind not in ("noul", "choice", "score"):
            raise TypeSafeError(f"question {key}: type must be noul, choice, or score")
        if not instructions:
            raise TypeSafeError(f"question {key}: instructions required")
        item: dict[str, Any] = {"type": kind, "instructions": instructions}
        crit = q.get("criteria")
        if kind == "choice":
            if not isinstance(crit, dict) or not crit:
                raise TypeSafeError(f"question {key}: choice needs a criteria map")
            item["criteria"] = {
                str(name): None if val is None else str(val)
                for name, val in list(crit.items())[:_MAX_CHOICE]
            }
        elif kind == "score":
            if not isinstance(crit, list) or not (2 <= len(crit) <= 10):
                raise TypeSafeError(f"question {key}: score needs 2-10 levels")
            item["criteria"] = [str(level) for level in crit]
        elif isinstance(crit, dict) and crit:
            item["criteria"] = {
                str(name): str(val) for name, val in crit.items() if val not in (None, "")
            }
        out[str(key)] = item
    return out


def flatten_response(payload: dict[str, Any], *, threshold: float = DEFAULT_THRESHOLD) -> dict[str, Any]:
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    out: dict[str, Any] = {
        "ok": True,
        "model": payload.get("model"),
        "answers": answers,
        "usage": payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
    }
    first_noul = first_choice = first_score = None
    for ans in answers.values():
        if not isinstance(ans, dict):
            continue
        kind = str(ans.get("type") or "")
        if kind == "noul" and first_noul is None:
            first_noul = ans
        elif kind == "choice" and first_choice is None:
            first_choice = ans
        elif kind == "score" and first_score is None:
            first_score = ans
    if first_noul is not None:
        noul = float(first_noul.get("noul") or 0)
        out["noul"] = noul
        out["gate"] = noul >= threshold
    if first_choice is not None:
        choice = str(first_choice.get("choice") or "")
        out["choice"] = choice
        out["ducky"] = choice
        out["probabilities"] = first_choice.get("probabilities") or {}
        if first_choice.get("confidence") is not None:
            out["confidence"] = first_choice.get("confidence")
        out.setdefault("gate", bool(choice))
    if first_score is not None:
        score = float(first_score.get("score") or 0)
        out["score"] = score
        out["legend"] = first_score.get("legend") or {}
        out.setdefault("probabilities", first_score.get("probabilities") or {})
        if first_score.get("confidence") is not None:
            out["confidence"] = first_score.get("confidence")
        out.setdefault("gate", score >= threshold)
    return out


def _retry_after(headers: Any) -> float:
    raw = ""
    try:
        raw = str(headers.get("Retry-After") or headers.get("retry-after") or "")
    except Exception:
        raw = ""
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def _request(
    method: str,
    path: str,
    api_key_value: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    if not api_key_value:
        raise TypeSafeError("TypeSafe API key required", status=401)
    url = BASE_URL.rstrip("/") + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key_value}",
        "Accept": "application/json",
        "User-Agent": "UEFN-Ducky-TypeSafe/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    delay = 0.5
    last: TypeSafeError | None = None
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw.strip() else {}
            if not isinstance(payload, dict):
                raise TypeSafeError("TypeSafe returned a non-object")
            return payload
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                if isinstance(parsed, dict):
                    detail = str(parsed.get("error") or parsed.get("message") or detail)
            except json.JSONDecodeError:
                pass
            wait = _retry_after(exc.headers)
            last = TypeSafeError(detail or f"HTTP {exc.code}", status=int(exc.code), retry_after=wait)
            if exc.code in _RETRY_STATUSES and attempt < 3:
                time.sleep(wait or delay)
                delay *= 2
                continue
            raise last from exc
        except urllib.error.URLError as exc:
            raise TypeSafeError(str(exc.reason or exc)) from exc
    raise last or TypeSafeError("TypeSafe request failed")


def list_models(api_key_value: str) -> dict[str, Any]:
    return _request("GET", "/v1/models", api_key_value)


def system_one(
    api_key_value: str,
    state: Any,
    questions: dict[str, Any],
    model: str = "",
) -> dict[str, Any]:
    return _request(
        "POST",
        "/v1/systemone",
        api_key_value,
        {
            "state": state,
            "model": (model or default_model()).strip() or DEFAULT_MODEL,
            "questions": normalize_questions(questions),
        },
    )


def run_decide(
    state: Any,
    questions: Any,
    *,
    model: str = "",
    threshold: float = DEFAULT_THRESHOLD,
    api_key_value: str = "",
) -> dict[str, Any]:
    key = api_key(api_key_value)
    if not key:
        return {"ok": False, "error": "Paste a TypeSafe API key in Settings → LLMs → TypeSafe."}
    try:
        raw = system_one(key, state, questions, model=model)
        out = flatten_response(raw, threshold=threshold)
        out["state"] = state
        return out
    except TypeSafeError as exc:
        return {"ok": False, "error": str(exc), "status": exc.status}


def test_api_key(key: str = "") -> dict[str, Any]:
    token = (key or "").strip() or api_key()
    if not token:
        return {"ok": False, "detail": "No TypeSafe API key"}
    try:
        payload = list_models(token)
        models = payload.get("models") if isinstance(payload.get("models"), list) else payload
        count = len(models) if isinstance(models, list) else 1
        return {"ok": True, "detail": f"TypeSafe reachable ({count} model aliases)"}
    except TypeSafeError as exc:
        return {"ok": False, "detail": str(exc)}
