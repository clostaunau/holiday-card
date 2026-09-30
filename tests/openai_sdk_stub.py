"""A stand-in ``openai`` module for network-free tests (issue #142).

CI does not install the ``[ai]`` extra, so tests put this into
``sys.modules["openai"]`` with ``monkeypatch.setitem``. It mirrors only
the part of the openai-python exception hierarchy the adapter's error
mapper reads (``status_code``, ``code``, ``response.headers``), with the
same constructor signatures. ``test_ai_openai_sdk_contract.py`` checks it
against the real SDK when the extra is installed.
"""

from __future__ import annotations

from types import ModuleType, SimpleNamespace
from typing import Any

MIRRORED = (
    "OpenAIError",
    "APIError",
    "APIStatusError",
    "APIConnectionError",
    "APITimeoutError",
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "UnprocessableEntityError",
    "RateLimitError",
    "InternalServerError",
)


class OpenAIError(Exception):
    pass


class APIError(OpenAIError):
    def __init__(self, message: str, request: Any, *, body: object | None) -> None:
        super().__init__(message)
        self.message = message
        self.request = request
        self.body = body
        code = body.get("code") if isinstance(body, dict) else None
        self.code: str | None = str(code) if code is not None else None


class APIStatusError(APIError):
    def __init__(self, message: str, *, response: Any, body: object | None) -> None:
        super().__init__(message, getattr(response, "request", None), body=body)
        self.response = response
        self.status_code: int = response.status_code


class APIConnectionError(APIError):
    def __init__(self, *, message: str = "Connection error.", request: Any) -> None:
        super().__init__(message, request, body=None)


class APITimeoutError(APIConnectionError):
    def __init__(self, request: Any) -> None:
        super().__init__(message="Request timed out.", request=request)


class BadRequestError(APIStatusError):
    pass


class AuthenticationError(APIStatusError):
    pass


class PermissionDeniedError(APIStatusError):
    pass


class NotFoundError(APIStatusError):
    pass


class ConflictError(APIStatusError):
    pass


class UnprocessableEntityError(APIStatusError):
    pass


class RateLimitError(APIStatusError):
    pass


class InternalServerError(APIStatusError):
    pass


_BY_STATUS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: UnprocessableEntityError,
    429: RateLimitError,
}


def fake_response(status: int, headers: dict[str, str] | None = None) -> SimpleNamespace:
    """An object with the ``status_code`` / ``headers`` / ``request`` the SDK exposes."""
    return SimpleNamespace(status_code=status, headers=dict(headers or {}), request=None)


def status_error(
    status: int,
    message: str = "provider error",
    *,
    code: str | None = None,
    headers: dict[str, str] | None = None,
) -> APIStatusError:
    """The exception the SDK's ``_make_status_error`` builds for ``status``.

    ``body`` is the already-unwrapped ``error`` object, as the SDK passes it.
    """
    if status in _BY_STATUS:
        cls = _BY_STATUS[status]
    elif status >= 500:
        cls = InternalServerError
    else:
        cls = APIStatusError
    body = {"message": message, "code": code, "type": "error", "param": None}
    return cls(message, response=fake_response(status, headers), body=body)


def make_module(**extra: Any) -> ModuleType:
    """A fresh ``openai`` module holding the mirrored classes plus ``extra``."""
    mod = ModuleType("openai")
    for name in MIRRORED:
        setattr(mod, name, globals()[name])
    for name, value in extra.items():
        setattr(mod, name, value)
    return mod
