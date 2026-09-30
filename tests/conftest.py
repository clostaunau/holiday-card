"""Shared pytest fixtures for holiday card tests."""

import ipaddress
import os
import socket
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from holiday_card.core.data_paths import data_path


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001 (hook signature)
    """Keep the suite off the real user template layer (#79).

    Set before collection, since some modules discover templates at import.
    """
    os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="holiday-card-xdg-")


_AI_KEYS = ("OPENAI_API_KEY", "OPENROUTER_API_KEY")


def _is_loopback(family: int, address: object) -> bool:
    if family == getattr(socket, "AF_UNIX", None):
        return True
    host = address[0] if isinstance(address, tuple) and address else address
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:  # a hostname: resolving it would already be off-box
        return False


def _loopback_only(original: Callable[..., object]) -> Callable[..., object]:
    """Wrap a ``socket.socket`` connect method; in-process only (subprocesses aren't guarded)."""

    def guarded(self: socket.socket, address: object) -> object:
        if not _is_loopback(self.family, address):
            raise RuntimeError(
                f"network access is blocked in tests: connect to {address!r}; "
                "mark the test live_ai to allow it"
            )
        return original(self, address)

    return guarded


@pytest.fixture(autouse=True)
def _ai_test_isolation(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """No AI keys and no non-loopback sockets unless the test is marked ``live_ai`` (#143).

    ``monkeypatch.delenv`` edits ``os.environ``, so subprocesses inherit the
    scrubbed environment. A ``RuntimeError`` (not ``OSError``) so code that
    handles network errors cannot swallow it.
    """
    if request.node.get_closest_marker("live_ai"):
        return
    for key in _AI_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(socket.socket, "connect", _loopback_only(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _loopback_only(socket.socket.connect_ex))


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_templates_dir(fixtures_dir: Path) -> Path:
    """Return path to sample templates directory."""
    return fixtures_dir / "sample_templates"


@pytest.fixture
def reference_cards_dir(fixtures_dir: Path) -> Path:
    """Return path to reference cards directory."""
    return fixtures_dir / "reference_cards"


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    yield output_dir


@pytest.fixture
def project_root() -> Path:
    """Return path to project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def templates_dir() -> Path:
    """Return path to the bundled templates directory."""
    return data_path("templates")


@pytest.fixture
def themes_dir() -> Path:
    """Return path to the bundled themes directory."""
    return data_path("themes")
