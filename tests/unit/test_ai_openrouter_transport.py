"""The real urllib transport against loopback servers (#149).

Every server is ``127.0.0.1:0`` in a daemon thread, torn down per test, so
the #143 socket guard (loopback allowed) stays on. Proxy variables are
cleared because ``build_opener`` honours them.
"""

from __future__ import annotations

import contextlib
import http.server
import shutil
import socket
import ssl
import subprocess
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from holiday_card.core import ai_openrouter
from holiday_card.core.ai_errors import ProviderError
from holiday_card.core.ai_openrouter import HttpResponse, make_urllib_transport, urllib_transport

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADERS = {"Authorization": "Bearer sk-or-v1-" + "ab" * 32, "Content-Type": "application/json"}
BODY = b'{"model":"m","prompt":"p"}'

Handler = Callable[[http.server.BaseHTTPRequestHandler], None]


@dataclass
class Server:
    port: int
    log: list[dict[str, Any]] = field(default_factory=list)
    connections: list[int] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/v1/images"


_SERVERS: list[http.server.ThreadingHTTPServer] = []


@pytest.fixture(autouse=True)
def _no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


@pytest.fixture
def serve() -> Iterator[Callable[[Handler], Server]]:
    servers = _SERVERS

    def start(respond: Handler) -> Server:
        record: Server

        class _Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _any(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                record.log.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "headers": dict(self.headers.items()),
                        "body": self.rfile.read(length),
                    }
                )
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    respond(self)

            do_POST = _any  # noqa: N815 (http.server naming)
            do_GET = _any  # noqa: N815

            def log_message(self, *_args: object) -> None:
                pass

        class _Server(http.server.ThreadingHTTPServer):
            daemon_threads = True

            def verify_request(self, *_args: Any) -> bool:
                record.connections.append(1)
                return True

        httpd = _Server(("127.0.0.1", 0), _Handler)
        record = Server(port=httpd.server_address[1])
        servers.append(httpd)
        threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()
        return record

    yield start
    for httpd in servers:
        httpd.shutdown()
        httpd.server_close()
    servers.clear()


def _reply(status: int, body: bytes, headers: dict[str, str] | None = None) -> Handler:
    def respond(h: http.server.BaseHTTPRequestHandler) -> None:
        h.send_response(status)
        for k, v in {"Content-Type": "application/json", **(headers or {})}.items():
            h.send_header(k, v)
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)

    return respond


TRANSPORT = make_urllib_transport(require_https=False)


def _call(url: str, *, timeout_s: float = 5.0, max_bytes: int = 1 << 20) -> HttpResponse:
    return TRANSPORT(url, headers=HEADERS, body=BODY, timeout_s=timeout_s, max_bytes=max_bytes)


def _transient(fn: Callable[[], object]) -> ProviderError:
    with pytest.raises(ProviderError) as info:
        fn()
    assert (info.value.kind, info.value.status) == ("transient", None)
    return info.value


def test_200_json_round_trip(serve: Callable[[Handler], Server]) -> None:
    srv = serve(_reply(200, b'{"ok":true}', {"X-Generation-Id": "gen-1", "Set-Cookie": "a=1"}))
    resp = _call(srv.url)
    assert resp.status == 200
    assert resp.body == b'{"ok":true}'
    assert resp.headers["content-type"] == "application/json"
    assert resp.headers["x-generation-id"] == "gen-1"
    assert all(k == k.lower() for k in resp.headers)
    (req,) = srv.log
    assert req["method"] == "POST"
    assert req["path"] == "/api/v1/images"
    assert req["body"] == BODY
    assert req["headers"]["Authorization"] == HEADERS["Authorization"]
    assert req["headers"]["Content-Type"] == "application/json"


def test_duplicate_headers_are_joined(serve: Callable[[Handler], Server]) -> None:
    def respond(h: http.server.BaseHTTPRequestHandler) -> None:
        h.send_response(200)
        h.send_header("X-Dup", "a")
        h.send_header("x-dup", "b")
        h.send_header("Content-Length", "0")
        h.end_headers()

    assert _call(serve(respond).url).headers["x-dup"] == "a, b"


def test_error_status_is_returned_not_raised(serve: Callable[[Handler], Server]) -> None:
    body = b'{"error":{"code":403,"message":"no"}}'
    resp = _call(serve(_reply(403, body)).url)
    assert (resp.status, resp.body) == (403, body)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_is_never_followed(serve: Callable[[Handler], Server], status: int) -> None:
    target = serve(_reply(200, b"{}"))
    first = serve(_reply(status, b"moved", {"Location": target.url}))
    resp = _call(first.url)
    assert resp.status == status
    assert resp.headers["location"] == target.url
    assert len(first.log) == 1
    assert target.log == []
    assert target.connections == []


def test_body_of_exactly_max_bytes_is_read(serve: Callable[[Handler], Server]) -> None:
    resp = _call(serve(_reply(200, b"x" * 1000)).url, max_bytes=1000)
    assert resp.body == b"x" * 1000


def test_oversize_content_length_is_refused_before_reading(
    serve: Callable[[Handler], Server], monkeypatch: pytest.MonkeyPatch
) -> None:
    srv = serve(_reply(200, b"x" * 1001))
    reads: list[int] = []
    original = ai_openrouter._read_capped

    def spy(*args: Any, **kwargs: Any) -> bytes:
        reads.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(ai_openrouter, "_read_capped", spy)
    e = _transient(lambda: _call(srv.url, max_bytes=1000))
    assert "exceeded 1000 bytes" in str(e)
    assert reads == []


def test_oversize_chunked_body_is_refused(serve: Callable[[Handler], Server]) -> None:
    def respond(h: http.server.BaseHTTPRequestHandler) -> None:
        h.send_response(200)
        h.send_header("Transfer-Encoding", "chunked")
        h.end_headers()
        for _ in range(3):
            h.wfile.write(b"200\r\n" + b"y" * 512 + b"\r\n")
        h.wfile.write(b"0\r\n\r\n")

    e = _transient(lambda: _call(serve(respond).url, max_bytes=1000))
    assert str(e) == "OpenRouter response exceeded 1000 bytes"


def test_oversize_error_body_is_refused(serve: Callable[[Handler], Server]) -> None:
    _transient(lambda: _call(serve(_reply(502, b"z" * 2000)).url, max_bytes=1000))


def test_stall_after_headers_times_out(serve: Callable[[Handler], Server]) -> None:
    release = threading.Event()

    def respond(h: http.server.BaseHTTPRequestHandler) -> None:
        h.send_response(200)
        h.send_header("Content-Length", "100")
        h.end_headers()
        h.wfile.flush()
        release.wait(10)

    srv = serve(respond)
    start = time.monotonic()
    try:
        _transient(lambda: _call(srv.url, timeout_s=0.5))
    finally:
        release.set()
    assert time.monotonic() - start < 5


def test_trickling_body_hits_the_wall_clock_deadline(serve: Callable[[Handler], Server]) -> None:
    stop = threading.Event()

    def respond(h: http.server.BaseHTTPRequestHandler) -> None:
        h.send_response(200)
        h.send_header("Content-Length", "1000")
        h.end_headers()
        while not stop.is_set():
            h.wfile.write(b"x")
            h.wfile.flush()
            time.sleep(0.05)

    srv = serve(respond)
    start = time.monotonic()
    try:
        e = _transient(lambda: _call(srv.url, timeout_s=0.5))
    finally:
        stop.set()
    assert "timed out" in str(e)
    assert time.monotonic() - start < 5


def test_accepted_but_silent_server_times_out() -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        start = time.monotonic()
        _transient(lambda: _call(f"http://127.0.0.1:{port}/", timeout_s=0.5))
        assert time.monotonic() - start < 5
    finally:
        listener.close()


def test_closed_port_is_transient() -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    _transient(lambda: _call(f"http://127.0.0.1:{port}/"))


def test_protocol_garbage_is_transient() -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def garbage() -> None:
        conn, _ = listener.accept()
        conn.recv(65536)
        conn.sendall(b"NOT HTTP AT ALL\r\n\r\n")
        conn.close()

    threading.Thread(target=garbage, daemon=True).start()
    try:
        _transient(lambda: _call(f"http://127.0.0.1:{port}/"))
    finally:
        listener.close()


def test_production_transport_refuses_plain_http(serve: Callable[[Handler], Server]) -> None:
    srv = serve(_reply(200, b"{}"))
    e = _transient(lambda: urllib_transport(
        srv.url, headers=HEADERS, body=BODY, timeout_s=5.0, max_bytes=1000))  # fmt: skip
    assert "'http'" in str(e)
    assert srv.connections == []
    assert srv.log == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x/y", "data:,hello", "gopher://x"])
@pytest.mark.parametrize("transport", [urllib_transport, TRANSPORT], ids=["prod", "loopback"])
def test_other_schemes_are_refused(url: str, transport: Any) -> None:
    e = _transient(lambda: transport(url, headers=HEADERS, body=BODY, timeout_s=1.0, max_bytes=10))
    assert "scheme" in str(e)


def test_tls_is_verified() -> None:
    handlers = [
        h for h in urllib_transport.opener.handlers if isinstance(h, urllib.request.HTTPSHandler)
    ]
    assert len(handlers) == 1
    context: ssl.SSLContext = handlers[0]._context  # type: ignore[attr-defined]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_redirect_handler_is_the_non_following_one() -> None:
    redirects = [
        h for h in urllib_transport.opener.handlers
        if isinstance(h, urllib.request.HTTPRedirectHandler)
    ]  # fmt: skip
    assert [type(h).__name__ for h in redirects] == ["_NoRedirect"]


def test_nothing_under_src_disables_the_https_requirement() -> None:
    result = subprocess.run(
        ["grep", "-rn", "require_https=False", str(REPO_ROOT / "src")],
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""


# --------------------------------------------------------------------------- HTTPS


@pytest.fixture
def tls_cert(tmp_path: Path) -> tuple[Path, Path]:
    """A throwaway self-signed cert for 127.0.0.1, made at test time (no committed key)."""
    if shutil.which("openssl") is None:
        pytest.skip("needs the openssl CLI")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
         "-out", str(cert), "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1",
         "-days", "1"],
        check=True, capture_output=True, timeout=60,
    )  # fmt: skip
    return cert, key


def _tls_server(
    serve: Callable[[Handler], Server], cert: Path, key: Path, respond: Handler
) -> Server:
    srv = serve(respond)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    httpd = _SERVERS[-1]
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    return srv


def _https(srv: Server) -> str:
    return srv.url.replace("http://", "https://")


def test_tls_handshake_with_a_plain_http_server_is_transient(
    serve: Callable[[Handler], Server],
) -> None:
    srv = serve(_reply(200, b"{}"))
    _transient(lambda: urllib_transport(
        _https(srv), headers=HEADERS, body=BODY, timeout_s=2.0, max_bytes=1000))  # fmt: skip
    assert srv.log == []


def test_untrusted_certificate_is_refused(
    serve: Callable[[Handler], Server], tls_cert: tuple[Path, Path]
) -> None:
    srv = _tls_server(serve, *tls_cert, _reply(200, b"{}"))
    e = _transient(lambda: urllib_transport(
        _https(srv), headers=HEADERS, body=BODY, timeout_s=2.0, max_bytes=1000))  # fmt: skip
    assert "CERTIFICATE_VERIFY_FAILED" in str(e) or "certificate" in str(e).lower()
    assert srv.log == []


def test_https_round_trip_reads_under_the_read_timeout(
    serve: Callable[[Handler], Server], tls_cert: tuple[Path, Path]
) -> None:
    cert, key = tls_cert
    release = threading.Event()

    def respond(h: http.server.BaseHTTPRequestHandler) -> None:
        if h.path.endswith("/stall"):
            h.send_response(200)
            h.send_header("Content-Length", "10")
            h.end_headers()
            h.wfile.flush()
            release.wait(10)
            return
        _reply(200, b'{"ok":true}')(h)

    srv = _tls_server(serve, cert, key, respond)
    transport = make_urllib_transport()
    (handler,) = [
        h for h in transport.opener.handlers if isinstance(h, urllib.request.HTTPSHandler)
    ]  # fmt: skip
    trusting = ssl.create_default_context(cafile=str(cert))
    handler._ssl_context = trusting  # type: ignore[attr-defined]  # trust only the test cert
    resp = transport(_https(srv), headers=HEADERS, body=BODY, timeout_s=2.0, max_bytes=1000)
    assert (resp.status, resp.body) == (200, b'{"ok":true}')
    assert srv.log[0]["headers"]["Authorization"] == HEADERS["Authorization"]
    start = time.monotonic()
    try:
        _transient(lambda: transport(
            _https(srv).replace("/images", "/stall"), headers=HEADERS, body=BODY,
            timeout_s=0.5, max_bytes=1000))  # fmt: skip
    finally:
        release.set()
    assert time.monotonic() - start < 5


def test_read_timeout_defaults_for_a_foreign_request() -> None:
    assert ai_openrouter._read_timeout(urllib.request.Request("https://x/")) == 300.0


def test_invalid_header_value_is_transient_and_not_echoed(
    serve: Callable[[Handler], Server],
) -> None:
    srv = serve(_reply(200, b"{}"))
    secret = "sk-or-v1-" + "ef" * 32
    headers = {"Authorization": f"Bearer {secret}\r\nX-Evil: 1"}
    e = _transient(
        lambda: TRANSPORT(srv.url, headers=headers, body=BODY, timeout_s=2.0, max_bytes=10)
    )
    assert secret not in str(e)
    assert e.__cause__ is None and e.__context__ is None
    assert srv.log == []
