"""OpenRouter ``POST /images`` client over a stdlib transport (L3, issue #149)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple


class HttpResponse(NamedTuple):
    """One HTTP response as the transport read it."""

    status: int
    headers: Mapping[str, str]
    body: bytes
