"""Tests for the bundled-data resolver (issue #55, spec §P1 / D1).

Templates, themes, sentiments, fonts and the ICC profile ship inside the
wheel under ``holiday_card/data/`` and are resolved via
``importlib.resources`` — never by walking up from ``__file__`` or
falling back to the current working directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import holiday_card
from holiday_card.core.data_paths import ENV_OVERRIDES, DataPathError, data_path
from holiday_card.renderers.font_registry import CURATED_FONTS

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DATA = Path(holiday_card.__file__).parent / "data"

ALL_KINDS = ("templates", "themes", "sentiments", "fonts", "icc")
OVERRIDABLE = ("themes", "sentiments")


@pytest.fixture(autouse=True)
def _clear_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (*ENV_OVERRIDES.values(), "HOLIDAY_CARD_TEMPLATES"):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_default_resolves_under_package_data(kind: str) -> None:
    path = data_path(kind)  # type: ignore[arg-type]
    assert path == PACKAGE_DATA / kind
    assert path.is_dir()


def test_env_overrides_cover_exactly_themes_and_sentiments() -> None:
    # HOLIDAY_CARD_TEMPLATES is a search-path layer, not a replacement (#79).
    assert dict(ENV_OVERRIDES) == {
        "themes": "HOLIDAY_CARD_THEMES",
        "sentiments": "HOLIDAY_CARD_SENTIMENTS",
    }


@pytest.mark.parametrize("kind", OVERRIDABLE)
def test_env_override_replaces_bundled_dir(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_OVERRIDES[kind], str(tmp_path))  # type: ignore[index]
    assert data_path(kind) == tmp_path  # type: ignore[arg-type]


def test_env_override_expands_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "th").mkdir()
    monkeypatch.setenv("HOLIDAY_CARD_THEMES", "~/th")
    assert data_path("themes") == tmp_path / "th"


def test_templates_env_var_does_not_replace_the_bundled_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path))
    assert data_path("templates") == PACKAGE_DATA / "templates"


def test_empty_env_override_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOLIDAY_CARD_THEMES", "")
    assert data_path("themes") == PACKAGE_DATA / "themes"


@pytest.mark.parametrize("kind", OVERRIDABLE)
def test_env_override_to_missing_dir_raises(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nope"
    var = ENV_OVERRIDES[kind]  # type: ignore[index]
    monkeypatch.setenv(var, str(missing))
    with pytest.raises(DataPathError, match=var) as excinfo:
        data_path(kind)  # type: ignore[arg-type]
    assert str(missing) in str(excinfo.value)


def test_data_path_error_is_a_file_not_found_error() -> None:
    assert issubclass(DataPathError, FileNotFoundError)


@pytest.mark.parametrize("name", ["templates", "themes", "sentiments", "fonts", "assets"])
def test_repo_root_has_no_stray_data_dirs(name: str) -> None:
    assert not (REPO_ROOT / name).exists(), (
        f"{name}/ must live under src/holiday_card/data/, not the repo root"
    )


@pytest.mark.parametrize("font_id", sorted(CURATED_FONTS))
def test_every_curated_font_ships_with_its_license(font_id: str) -> None:
    ttf_name = CURATED_FONTS[font_id][0]
    family = ttf_name.split("-")[0]
    license_file = data_path("fonts") / "curated" / f"{family}-LICENSE.txt"
    assert license_file.is_file(), f"{ttf_name} has no sibling {license_file.name}"


def test_icc_profile_ships_with_a_notice() -> None:
    assert (data_path("icc") / "GRACoL2013_CRPC6.icc").is_file()
    assert (data_path("icc") / "NOTICE").is_file()


def test_root_license_exists() -> None:
    assert (REPO_ROOT / "LICENSE").is_file()
