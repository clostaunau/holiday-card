"""Self-tests for the suite's AI isolation guard in ``tests/conftest.py`` (#143).

Unless a test is marked ``live_ai``, it never sees ``OPENAI_API_KEY`` /
``OPENROUTER_API_KEY`` and cannot ``connect`` a socket anywhere but loopback.
The key checks run a nested pytest with sentinel keys exported, so they fail
even on a CI host that has no key set.
"""

from __future__ import annotations

import _socket
import http.server
import os
import socket
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = "HOLIDAY_CARD_ISOLATION_PROBE"
_KEYS = ("OPENAI_API_KEY", "OPENROUTER_API_KEY")
_probe_only = pytest.mark.skipif(not os.environ.get(_PROBE), reason="run by a nested pytest")


def test_non_loopback_connect_is_blocked() -> None:
    # 203.0.113.0/24 is TEST-NET-3: never routable, so only the guard can answer.
    with pytest.raises(RuntimeError, match="network access is blocked in tests"):
        socket.create_connection(("203.0.113.1", 9), timeout=1)


def test_connect_ex_is_blocked_too() -> None:
    blocked = pytest.raises(RuntimeError, match=r"connect to \('203\.0\.113\.1', 9\)")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s, blocked:
        s.connect_ex(("203.0.113.1", 9))


def test_a_hostname_other_than_localhost_is_blocked() -> None:
    blocked = pytest.raises(RuntimeError, match="mark the test live_ai")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s, blocked:
        s.connect(("example.com", 443))


def test_loopback_connect_is_allowed() -> None:
    class _Ok(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Ok)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            assert response.read() == b"ok"
    finally:
        server.shutdown()
        server.server_close()


def _run_probe(name: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "OPENAI_API_KEY": "sk-test-sentinel",
        "OPENROUTER_API_KEY": "sk-or-v1-sentinel",
        _PROBE: "1",
    }
    return subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "--color=no", "-p", "no:cacheprovider",
            f"{__file__}::{name}",
        ],
        env=env,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_ai_keys_are_scrubbed() -> None:
    result = _run_probe("test_probe_env_has_no_ai_keys")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_live_ai_marker_keeps_keys_and_network() -> None:
    result = _run_probe("test_probe_live_ai_keeps_keys_and_network")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


@_probe_only
def test_probe_env_has_no_ai_keys() -> None:
    assert [k for k in _KEYS if k in os.environ] == []


@_probe_only
@pytest.mark.live_ai
def test_probe_live_ai_keeps_keys_and_network() -> None:
    # Never connects anywhere: it only checks the guard stepped aside.
    assert os.environ["OPENAI_API_KEY"] == "sk-test-sentinel"
    assert os.environ["OPENROUTER_API_KEY"] == "sk-or-v1-sentinel"
    assert socket.socket.connect is _socket.socket.connect
    assert socket.socket.connect_ex is _socket.socket.connect_ex
