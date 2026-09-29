"""Shared pytest fixtures for holiday card tests."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from holiday_card.core.data_paths import data_path


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001 (hook signature)
    """Keep the suite off the real user template layer (#79).

    Set before collection, since some modules discover templates at import.
    """
    os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="holiday-card-xdg-")


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
