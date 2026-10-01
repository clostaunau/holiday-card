"""Loader for the hand-written OpenRouter response fixtures (#149).

Importable from any test as ``openrouter_fixtures`` because
``tests/conftest.py`` puts ``tests/`` on ``sys.path`` (like ``ast_imports``).
Each ``tests/fixtures/openrouter/*.json`` except the golden request is
``{"status": int, "headers": {lower-case: str}, "body": <JSON>}``, or
``"body_text"`` for a non-JSON body.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from holiday_card.core.ai_openrouter import HttpResponse

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "openrouter"
GOLDEN_REQUEST = "request_moo_a6.json"
REFERENCE_PNG = FIXTURES_DIR / "reference_8x8.png"


def response_fixture_names() -> list[str]:
    """Every response fixture's stem, sorted (the golden request excluded)."""
    return sorted(p.stem for p in FIXTURES_DIR.glob("*.json") if p.name != GOLDEN_REQUEST)


def fixture_raw(name: str) -> dict[str, Any]:
    raw: dict[str, Any] = json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return raw


def to_response(raw: dict[str, Any]) -> HttpResponse:
    """An ``HttpResponse`` from a fixture-shaped mapping."""
    if "body_text" in raw:
        body = str(raw["body_text"]).encode()
    else:
        body = json.dumps(raw["body"]).encode()
    return HttpResponse(int(raw["status"]), dict(raw["headers"]), body)


def load_response(name: str) -> HttpResponse:
    return to_response(fixture_raw(name))


@dataclass
class FakeTransport:
    """Records every call and returns queued responses (or raises queued errors)."""

    responses: list[HttpResponse | Exception] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(
        self,
        url: str,
        *,
        headers: Any,
        body: bytes,
        timeout_s: float,
        max_bytes: int,
    ) -> HttpResponse:
        self.calls.append(
            {"url": url, "headers": dict(headers), "body": body,
             "timeout_s": timeout_s, "max_bytes": max_bytes}
        )  # fmt: skip
        nxt = self.responses.pop(0) if self.responses else load_response("ok_png")
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    @property
    def body(self) -> dict[str, Any]:
        parsed: dict[str, Any] = json.loads(self.calls[-1]["body"])
        return parsed
