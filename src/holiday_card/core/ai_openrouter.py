"""OpenRouter ``POST /images`` client over a stdlib transport (L3, issue #149).

Builds one request for a curated model (:mod:`ai_openrouter_models`), sends
it through an injected :class:`Transport` and turns the response into the
:class:`~holiday_card.core.ai_assets.GeneratedImage` the bake consumes.
Every failure is a redacted :class:`~holiday_card.core.ai_errors.ProviderError`.
Not wired to the CLI yet (#150 registers the provider).

The production transport is ``urllib.request``, whose defaults are unsafe
for a billed, secret-bearing call, so :func:`make_urllib_transport` sets
three hardening rules:

1. **No redirects.** A 3xx is returned as a response, never followed, so no
   second host ever sees ``Authorization``.
2. **Capped read.** An oversize ``Content-Length`` is refused before the
   body is read; otherwise the body is read in 64 KiB chunks and refused
   past ``max_bytes``.
3. **Split timeouts.** Connecting has its own short timeout; every read
   then has ``timeout_s``, and ``timeout_s`` is also a wall-clock deadline
   for the whole body.

Only ``https`` is accepted. There is no retry, ever: the call is billed and
not idempotent (spec §6.3.6).

The response models ignore unknown fields (``extra="ignore"``), where the
domain models forbid them: this is a third-party response that may gain
fields at any time, and a new field must not break a working call.
"""

from __future__ import annotations

import base64
import contextlib
import email.utils
import http.client
import json
import math
import re
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, NamedTuple, NoReturn, Protocol, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from holiday_card import __version__
from holiday_card.core.ai_assets import (
    MAX_IMAGE_BYTES,
    AspectSize,
    GeneratedImage,
    ImageMediaType,
    ImagePayloadError,
    RequestShape,
    decode_b64_image,
    probe_generated_image,
)
from holiday_card.core.ai_errors import ProviderError, ProviderErrorKind, parse_retry_after, redact
from holiday_card.core.ai_openrouter_models import OpenRouterModel, openrouter_model
from holiday_card.core.images import ImageSourceError, probe_image

__all__ = [
    "ATTRIBUTION_HEADERS",
    "CONNECT_TIMEOUT_S",
    "IMAGES_URL",
    "MAX_B64_CHARS",
    "MAX_IMAGE_BYTES",
    "MAX_RESPONSE_BYTES",
    "OPENROUTER_BASE_URL",
    "READ_TIMEOUT_S",
    "HttpResponse",
    "OpenRouterImageClient",
    "Transport",
    "make_urllib_transport",
    "parse_images_response",
    "urllib_transport",
]

OPENROUTER_BASE_URL: Final = "https://openrouter.ai/api/v1"  # a constant: no env override (§6.4.6)
IMAGES_URL: Final = f"{OPENROUTER_BASE_URL}/images"
MAX_RESPONSE_BYTES: Final = 48 * 1024 * 1024
MAX_B64_CHARS: Final = 4 * math.ceil(MAX_IMAGE_BYTES / 3)  # checked before decoding
CONNECT_TIMEOUT_S: Final = 10.0
READ_TIMEOUT_S: Final = 300.0  # per socket read and the wall clock for the body
ATTRIBUTION_HEADERS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "HTTP-Referer": "https://github.com/clostaunau/holiday-card",
        "X-OpenRouter-Title": "holiday-card",
        "X-OpenRouter-App-Visibility": "hidden",
    }
)

_CHUNK = 64 * 1024
_KEY_ENV = "OPENROUTER_API_KEY"


class HttpResponse(NamedTuple):
    """One HTTP response as the transport read it."""

    status: int
    headers: Mapping[str, str]  # keys lower-cased; duplicate headers joined with ", "
    body: bytes  # at most max_bytes


class Transport(Protocol):
    """POST ``body`` to ``url``; return any status, raise ``ProviderError`` otherwise."""

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_s: float,
        max_bytes: int,
    ) -> HttpResponse: ...


# --------------------------------------------------------------------------- transport


def _transient(message: str) -> ProviderError:
    return ProviderError(message, kind="transient", status=None)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: the 3xx surfaces as an ``HTTPError``."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _Request(urllib.request.Request):
    """A request that carries the per-call read timeout to the connection."""

    def __init__(self, url: str, *, data: bytes, headers: Mapping[str, str], read_timeout: float):
        super().__init__(url, data=data, headers=dict(headers), method="POST")
        self.read_timeout = read_timeout


class _HTTPConnection(http.client.HTTPConnection):
    """Connect under the connect timeout, then read under ``read_timeout``."""

    def __init__(self, *args: Any, read_timeout: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._read_timeout = read_timeout

    def connect(self) -> None:
        super().connect()
        self.sock.settimeout(self._read_timeout)


class _HTTPSConnection(http.client.HTTPSConnection):
    """Connect (and handshake) under the connect timeout, then read under ``read_timeout``."""

    def __init__(self, *args: Any, read_timeout: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._read_timeout = read_timeout

    def connect(self) -> None:
        super().connect()
        self.sock.settimeout(self._read_timeout)


def _read_timeout(req: urllib.request.Request) -> float:
    return req.read_timeout if isinstance(req, _Request) else READ_TIMEOUT_S


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(partial(_HTTPConnection, read_timeout=_read_timeout(req)), req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context: ssl.SSLContext) -> None:
        super().__init__(context=context)
        self._ssl_context = context

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(
            partial(_HTTPSConnection, read_timeout=_read_timeout(req)),
            req,
            context=self._ssl_context,
        )


def _read_capped(fp: Any, max_bytes: int, deadline: float) -> bytes:
    """Read the body in chunks, refusing more than ``max_bytes`` or a missed deadline."""
    chunks: list[bytes] = []
    total = 0
    while True:
        if time.monotonic() > deadline:
            raise _transient("OpenRouter response timed out while reading the body")
        # read1: at most one socket read, so the deadline is checked between reads.
        chunk = fp.read1(min(_CHUNK, max_bytes + 1 - total))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise _transient(f"OpenRouter response exceeded {max_bytes} bytes")
        chunks.append(chunk)


def _response_headers(message: Any) -> dict[str, str]:
    joined: dict[str, str] = {}
    for key, value in message.items():
        k = key.lower()
        joined[k] = f"{joined[k]}, {value}" if k in joined else value
    return joined


class _UrllibTransport:
    """The hardened ``urllib`` transport; see the module docstring."""

    def __init__(self, *, require_https: bool) -> None:
        self._schemes = frozenset({"https"} if require_https else {"https", "http"})
        self.opener = urllib.request.build_opener(
            _NoRedirect(), _HTTPHandler(), _HTTPSHandler(ssl.create_default_context())
        )

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_s: float,
        max_bytes: int,
    ) -> HttpResponse:
        scheme = urlsplit(url).scheme.lower()
        if scheme not in self._schemes:
            raise _transient(f"OpenRouter transport refuses the {scheme!r} scheme")
        request = _Request(url, data=body, headers=headers, read_timeout=timeout_s)
        try:
            try:
                response = self.opener.open(request, timeout=CONNECT_TIMEOUT_S)
            except urllib.error.HTTPError as e:
                response = e  # a non-2xx (or unfollowed 3xx) is returned, not raised
            with response:
                deadline = time.monotonic() + timeout_s
                status = response.status if response.status is not None else 0
                resp_headers = _response_headers(response.headers)
                length = resp_headers.get("content-length", "").strip()
                if length.isdigit() and int(length) > max_bytes:
                    raise _transient(f"OpenRouter response exceeded {max_bytes} bytes")
                data = _read_capped(response, max_bytes, deadline)
        except ProviderError:
            raise
        except TimeoutError as e:
            raise _transient(f"OpenRouter request timed out ({type(e).__name__})") from e
        except (ssl.SSLError, urllib.error.URLError, http.client.HTTPException, OSError) as e:
            raise _transient(f"OpenRouter request failed ({type(e).__name__}: {e})") from e
        return HttpResponse(status, resp_headers, data)


def make_urllib_transport(*, require_https: bool = True) -> _UrllibTransport:
    """The production transport (``require_https`` is only relaxed by loopback tests)."""
    return _UrllibTransport(require_https=require_https)


urllib_transport: Final = make_urllib_transport()


# --------------------------------------------------------------------------- response models


class _Wire(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class ORImageDatum(_Wire):
    b64_json: str | None = None
    url: str | None = None  # not in the documented schema; parsed only to refuse it
    media_type: str | None = None


class ORUsage(_Wire):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost: float | None = None
    is_byok: bool | None = None


class ORImagesResponse(_Wire):
    created: int | None = None
    data: list[ORImageDatum]
    usage: ORUsage | None = None


class ORErrorMetadata(_Wire):
    error_type: str | None = None
    provider_code: str | int | None = None
    limit_source: str | None = None
    reasons: list[str] | None = None
    remedy_hint: str | None = None


class ORError(_Wire):
    code: int | None = None
    message: str = ""
    metadata: ORErrorMetadata | None = None


class ORErrorEnvelope(_Wire):
    error: ORError


# --------------------------------------------------------------------------- response parsing

_M = TypeVar("_M", bound=BaseModel)

_USAGE_STATUSES = frozenset({400, 404, 413, 422})
_REFUSAL_TYPES = frozenset({"content_policy_violation", "refusal"})
_IN_FLIGHT = "openrouter_in_flight_budget"
_GENERATION_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_MEDIA_TYPES: dict[str, ImageMediaType] = {
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/webp": "image/webp",
}


def _validated(model: type[_M], value: object) -> _M | None:
    """``model`` validated from ``value``, or ``None``: a ``ValidationError``
    echoes the input, so it is never chained onto a ``ProviderError``."""
    try:
        return model.model_validate(value)
    except ValidationError:
        return None


def _retry_after(value: str | None) -> float | None:
    """Delta-seconds or an HTTP-date (seconds from now, clamped at 0); else ``None``."""
    seconds = parse_retry_after(value)
    if seconds is not None or not value:
        return seconds
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def _status_kind(status: int, meta: ORErrorMetadata | None) -> ProviderErrorKind:
    if status in _USAGE_STATUSES:
        return "usage"
    if status == 401:
        return "environment"
    if status == 402:
        return "transient" if meta and meta.limit_source == _IN_FLIGHT else "environment"
    if status == 403:
        return "refused" if meta and meta.error_type in _REFUSAL_TYPES else "environment"
    return "transient"


def _raise_status(
    status: int,
    envelope: ORErrorEnvelope | None,
    headers: Mapping[str, str],
    redact_text: Callable[[str], str],
) -> NoReturn:
    error = envelope.error if envelope else None
    meta = error.metadata if error else None
    kind = _status_kind(status, meta)
    retry = _retry_after(headers.get("retry-after")) if kind == "transient" else None
    message = f"OpenRouter {status} {meta.error_type if meta and meta.error_type else 'error'}"
    if error and error.message:
        message += f": {error.message}"
    details = []
    if meta and meta.provider_code is not None:
        details.append(f"provider code {meta.provider_code}")
    if meta and meta.reasons:
        details.append("reasons: " + "; ".join(meta.reasons))
    if meta and meta.remedy_hint:
        details.append(f"hint: {meta.remedy_hint}")
    if details:
        message += f" ({'; '.join(details)})"
    if retry is not None:
        message += f" (retry after {retry:g} s)"
    raise ProviderError(redact_text(message), kind=kind, status=status, retry_after_s=retry)


def _bad_payload(message: str, kind: ProviderErrorKind = "transient") -> ProviderError:
    return ProviderError(f"OpenRouter returned an unusable image: {message}", kind=kind, status=200)


def _sniff(data: bytes) -> ImageMediaType | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _decode_datum(datum: ORImageDatum) -> tuple[bytes, ImageMediaType]:
    b64 = datum.b64_json
    if datum.url is not None or (b64 and b64.startswith(("http:", "https:", "data:"))):
        raise _bad_payload("it is a URL; remote images are never fetched", "refused")
    if not b64:
        raise _bad_payload("no b64_json")
    declared: ImageMediaType | None = None
    if datum.media_type is not None:
        declared = _MEDIA_TYPES.get(datum.media_type.strip().lower())
        if declared is None:
            raise _bad_payload("the media type is not image/png, image/jpeg or image/webp")
    try:
        data = decode_b64_image(b64, max_bytes=MAX_IMAGE_BYTES)
    except ImagePayloadError as e:
        raise _bad_payload(str(e)) from e
    sniffed = _sniff(data)
    if sniffed is None or (declared is not None and sniffed != declared):
        raise _bad_payload(f"its bytes are not the declared {declared or 'PNG, JPEG or WebP'}")
    try:
        probe_generated_image(data, sniffed)
    except ImagePayloadError as e:
        raise _bad_payload(str(e)) from e
    return data, sniffed


def _cost(usage: ORUsage | None) -> float | None:
    cost = usage.cost if usage else None
    return cost if cost is not None and math.isfinite(cost) and cost >= 0 else None


def _parse(
    response: HttpResponse, entry: OpenRouterModel, redact_text: Callable[[str], str]
) -> GeneratedImage:
    status, headers = response.status, response.headers
    if status != 200:
        if 300 <= status < 400:
            raise ProviderError(
                f"OpenRouter answered {status} (a redirect; not followed)",
                kind="transient",
                status=status,
            )
        envelope = None
        with contextlib.suppress(ValueError):  # a non-JSON error body maps on the status
            envelope = _validated(ORErrorEnvelope, json.loads(response.body))
        _raise_status(status, envelope, headers, redact_text)

    content_type = headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise ProviderError(
            f"OpenRouter answered 200 with content type {content_type or 'none'!r}, not JSON",
            kind="transient",
            status=200,
        )
    try:
        payload = json.loads(response.body)
    except ValueError:
        payload = None
    if isinstance(payload, dict) and "error" in payload:
        envelope = _validated(ORErrorEnvelope, payload)
        if envelope is not None:
            _raise_status(envelope.error.code or 200, envelope, headers, redact_text)
    parsed = _validated(ORImagesResponse, payload)
    if parsed is None:
        raise ProviderError(
            "OpenRouter answered 200 with a malformed images response",
            kind="transient",
            status=200,
        )
    if len(parsed.data) != 1:
        raise _bad_payload(f"{len(parsed.data)} images for n=1", "refused")

    image_bytes, media_type = _decode_datum(parsed.data[0])
    cost = _cost(parsed.usage)
    generation_id = headers.get("x-generation-id")
    return GeneratedImage(
        image_bytes=image_bytes,
        media_type=media_type,
        cost_usd=cost,
        cost_source="reported" if cost is not None else "unknown",
        model_version=None,  # /images reports no model version
        generation_id=(
            generation_id
            if generation_id is not None and _GENERATION_ID.fullmatch(generation_id)
            else None
        ),
        provider_route=entry.provider_tag,
    )


def parse_images_response(
    response: HttpResponse, *, entry: OpenRouterModel, redact: Callable[[str], str]
) -> GeneratedImage:
    """Map one ``/images`` response to a :class:`GeneratedImage` (issue #149 §5).

    Returns an image or raises :class:`ProviderError`, nothing else: an
    unexpected exception becomes ``transient``. Provider text goes through
    ``redact`` (and the ``ProviderError`` sanitiser) before it is kept.
    """
    failure: str | None = None
    try:
        return _parse(response, entry, redact)
    except ProviderError:
        raise
    except Exception as e:  # noqa: BLE001 (the contract: ProviderError and nothing else)
        failure = type(e).__name__
    # Raised outside the handler, so the unexpected error is not chained.
    raise ProviderError(
        f"OpenRouter response could not be parsed ({failure})",
        kind="transient",
        status=response.status,
    )


# --------------------------------------------------------------------------- client


def _request_headers(api_key: SecretStr) -> dict[str, str]:
    """The request headers; the one place the key is unwrapped for sending."""
    key = api_key.get_secret_value()
    if not key.strip():
        raise ProviderError(f"{_KEY_ENV} is empty", kind="environment")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"holiday-card/{__version__}",
        **ATTRIBUTION_HEADERS,
    }


def _key_redactor(api_key: SecretStr) -> Callable[[str], str]:
    """Redact the literal key (and every key-shaped token) from provider text."""
    secret = api_key.get_secret_value()
    return lambda text: redact(text, secrets=(secret,))


def _usage(message: str) -> ProviderError:
    return ProviderError(message, kind="usage", status=None)


class OpenRouterImageClient:
    """Generates one image through OpenRouter ``POST /images`` for a curated model.

    Implements :class:`~holiday_card.core.ai_assets.ImageClient` except for
    ``provider``, which #150 adds with ``AIProvider.OPENROUTER``. Stores the
    ``SecretStr`` only; headers are built per call.
    """

    def __init__(
        self, *, api_key: SecretStr, model: str, transport: Transport = urllib_transport
    ) -> None:
        self._entry = openrouter_model(model)
        _request_headers(api_key)  # refuses a blank key now, not at the first call
        self._api_key = api_key
        self._transport = transport

    @property
    def model(self) -> str:
        return self._entry.id

    def __repr__(self) -> str:
        return f"OpenRouterImageClient(model={self.model!r})"

    def _check(
        self, shape: RequestShape, reference_path: str | None, seed: int | None
    ) -> AspectSize:
        entry = self._entry
        if not isinstance(shape, AspectSize):
            raise _usage(f"{entry.id} is sized by aspect ratio and resolution, not {shape!r}")
        if shape.aspect_ratio not in entry.aspect_ratios:
            raise _usage(
                f"{entry.id} has no aspect ratio {shape.aspect_ratio!r}; "
                f"it offers {', '.join(entry.aspect_ratios)}"
            )
        if shape.resolution is not None and shape.resolution not in entry.resolutions:
            offered = ", ".join(entry.resolutions) or "none"
            raise _usage(f"{entry.id} has no resolution {shape.resolution!r}; it offers {offered}")
        if seed is not None and not entry.seed:
            raise _usage(f"{entry.id} does not take a seed")
        if reference_path is not None and entry.input_refs_max == 0:
            raise _usage(f"{entry.id} takes no reference image")
        if reference_path is None and entry.input_refs_min >= 1:
            raise _usage(f"{entry.id} needs a reference image")
        return shape

    def _body(
        self, prompt: str, shape: AspectSize, reference_path: str | None, seed: int | None
    ) -> bytes:
        entry = self._entry
        body: dict[str, Any] = {
            "model": entry.id,
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": shape.aspect_ratio,
        }
        if shape.resolution is not None:
            body["resolution"] = shape.resolution
        if "png" in entry.output_formats:
            body["output_format"] = "png"
        if seed is not None:
            body["seed"] = seed
        if reference_path is not None:
            try:
                probed = probe_image(Path(reference_path))
            except ImageSourceError as e:
                raise _usage(f"--reference: {e}") from e
            data = base64.b64encode(probed.path.read_bytes()).decode("ascii")
            url = f"data:image/{probed.format};base64,{data}"
            body["input_references"] = [{"type": "image_url", "image_url": {"url": url}}]
        provider: dict[str, Any] = {"only": [entry.provider_tag], "allow_fallbacks": False}
        if "moderation" in entry.passthrough:
            slug = entry.provider_tag.split("/")[0]
            provider["options"] = {slug: {"moderation": "auto"}}
        body["provider"] = provider
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        shape: RequestShape,
        seed: int | None,
    ) -> GeneratedImage:
        """Send one request (never retried) and parse the response.

        Raises:
            ProviderError: For a local refusal (``usage``, before any call)
                and for every transport or response failure.
        """
        aspect = self._check(shape, reference_path, seed)
        body = self._body(prompt, aspect, reference_path, seed)
        response = self._transport(
            IMAGES_URL,
            headers=_request_headers(self._api_key),
            body=body,
            timeout_s=READ_TIMEOUT_S,
            max_bytes=MAX_RESPONSE_BYTES,
        )
        return parse_images_response(
            response, entry=self._entry, redact=_key_redactor(self._api_key)
        )
