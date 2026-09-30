"""The one provider-neutral AI error type (issue #142, spec §6.1 / §6.4).

Standard library only, so it imports without the ``[ai]`` extra. Every
provider adapter maps its SDK / HTTP errors to :class:`ProviderError`,
whose constructor keeps only sanitised text: secrets and key-shaped
tokens are redacted, terminal escapes and control characters are
stripped, and the text is truncated. No code path can build a
``ProviderError`` that carries raw provider text.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Literal

__all__ = [
    "MAX_PROVIDER_TEXT",
    "ProviderError",
    "ProviderErrorKind",
    "parse_retry_after",
    "redact",
    "sanitize_provider_text",
]

ProviderErrorKind = Literal["refused", "environment", "usage", "transient"]
MAX_PROVIDER_TEXT = 500

_REDACTED = "[REDACTED]"
_MIN_SECRET_LEN = 8
_KEY_PATTERNS = (
    re.compile(r"sk-or-v1-[0-9A-Za-z]{8,}"),
    # Also OpenAI's masked "sk-proj-****…abcd" form (up to the ellipsis).
    re.compile(r"sk-[A-Za-z0-9_*\-]{8,}"),
)
# ESC-introduced CSI / OSC / two-byte sequences, and the 8-bit CSI.
_ESCAPES = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?"
    r"|\x1b[@-Z\\-_]"
    r"|\x9b[0-?]*[ -/]*[@-~]"
)
# C0 and C1 controls except "\t" (0x09) and "\n" (0x0a); DEL too.
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_DELTA_SECONDS = re.compile(r"\d+(?:\.\d+)?")


def redact(text: str, *, secrets: Iterable[str] = ()) -> str:
    """Replace every literal secret (8+ chars) and key-shaped token."""
    for secret in sorted({s for s in secrets if len(s) >= _MIN_SECRET_LEN}, key=len, reverse=True):
        text = text.replace(secret, _REDACTED)
    for pattern in _KEY_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


def sanitize_provider_text(text: str, *, secrets: Iterable[str] = ()) -> str:
    """Strip escapes and controls, redact, then truncate provider text.

    Stripping comes first so a key split by an escape sequence is glued
    back together before :func:`redact` looks for it; redaction comes
    before truncation so a key straddling the cut is still caught.
    """
    text = _CONTROLS.sub("", _ESCAPES.sub("", text))
    text = redact(text, secrets=secrets)
    if len(text) > MAX_PROVIDER_TEXT:
        text = text[:MAX_PROVIDER_TEXT] + "…"
    return text


class ProviderError(Exception):
    """An AI provider refused, failed or rejected a request.

    ``kind`` decides the CLI exit code: ``refused`` (6), ``transient``
    (7, retryable), ``environment`` (4) and ``usage`` (2).
    """

    kind: ProviderErrorKind
    status: int | None
    retry_after_s: float | None

    def __init__(
        self,
        message: str,
        *,
        kind: ProviderErrorKind,
        status: int | None = None,
        retry_after_s: float | None = None,
        secrets: Iterable[str] = (),
    ) -> None:
        clean = sanitize_provider_text(message, secrets=secrets)
        super().__init__(clean)
        self.kind = kind
        self.status = status
        self.retry_after_s = retry_after_s


def parse_retry_after(value: str | None) -> float | None:
    """Seconds from a ``Retry-After`` delta-seconds value; else ``None``.

    An HTTP-date, a negative or a non-numeric value gives ``None``.
    """
    if value is None or not _DELTA_SECONDS.fullmatch(value.strip()):
        return None
    seconds = float(value.strip())
    return seconds if math.isfinite(seconds) else None
