"""Shared pytest fixtures for holiday card tests."""

from collections.abc import Generator
from pathlib import Path

import pytest


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
def templates_dir(project_root: Path) -> Path:
    """Return path to templates directory."""
    return project_root / "templates"


@pytest.fixture
def themes_dir(project_root: Path) -> Path:
    """Return path to themes directory."""
    return project_root / "themes"
