"""Template image paths resolve relative to the template file (D5, issue #64).

``load_template_from_file`` rewrites every ``image_elements[].source_path``
to an absolute path inside the template's directory. Absolute paths, ``..``
and symlink escapes are ``TemplateLoadError``s, so ``holiday-card validate``
fails on them too.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from holiday_card.cli.commands import app
from holiday_card.core.templates import (
    TemplateLoadError,
    load_template,
    load_template_from_file,
)

FIXTURE_IMAGE = Path(__file__).parent.parent / "fixtures" / "sample_photo.jpg"

PHOTO_TEMPLATES = (
    "christmas-photo-ornament",
    "christmas-family-photo",
    "christmas-holiday-masterpiece",
    "birthday-photo",
    "mothers-day-photo",
)


def _template(source_path: str) -> dict[str, Any]:
    return {
        "id": "t-image",
        "name": "Image",
        "occasion": "generic",
        "fold_type": "half_fold",
        "panels": [
            {
                "id": "front",
                "position": "front",
                "x": 4.25,
                "y": 0,
                "width": 4.25,
                "height": 5.5,
                "image_elements": [
                    {
                        "source_path": source_path,
                        "x": 0.5,
                        "y": 0.5,
                        "width": 1.0,
                        "height": 1.0,
                    }
                ],
            }
        ],
    }


def _write(directory: Path, source_path: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "t.yaml"
    path.write_text(yaml.safe_dump(_template(source_path)))
    return path


def _source(template_path: Path) -> str:
    return load_template_from_file(template_path).panels[0].image_elements[0].source_path


def test_relative_source_path_resolves_against_template_dir(tmp_path: Path) -> None:
    tdir = tmp_path / "tpl"
    path = _write(tdir, "sample_photo.jpg")
    shutil.copy(FIXTURE_IMAGE, tdir / "sample_photo.jpg")
    assert _source(path) == str((tdir / "sample_photo.jpg").resolve())


def test_resolution_ignores_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tdir = tmp_path / "tpl"
    path = _write(tdir, "sample_photo.jpg")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert _source(path) == str((tdir / "sample_photo.jpg").resolve())


def test_absolute_source_path_is_load_error(tmp_path: Path) -> None:
    secret = tmp_path / "secret.env"
    secret.write_text("AWS_SECRET_ACCESS_KEY=hunter2")
    path = _write(tmp_path / "tpl", str(secret))
    with pytest.raises(TemplateLoadError, match="absolute") as exc_info:
        load_template_from_file(path)
    assert "panels[0].image_elements[0].source_path" in str(exc_info.value)


def test_dotdot_source_path_is_load_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "tpl", "../secret.env")
    with pytest.raises(TemplateLoadError, match=r"\.\."):
        load_template_from_file(path)


def test_symlink_escape_is_load_error(tmp_path: Path) -> None:
    secret = tmp_path / "secret.env"
    secret.write_text("AWS_SECRET_ACCESS_KEY=hunter2")
    tdir = tmp_path / "tpl"
    path = _write(tdir, "photo.jpg")
    (tdir / "photo.jpg").symlink_to(secret)
    with pytest.raises(TemplateLoadError, match="outside"):
        load_template_from_file(path)


def test_validate_rejects_absolute_image_path(tmp_path: Path) -> None:
    path = _write(tmp_path / "tpl", "/etc/hosts")
    result = CliRunner().invoke(app, ["validate", str(path)])
    assert result.exit_code != 0
    assert "absolute" in result.output


@pytest.mark.parametrize("template_id", PHOTO_TEMPLATES)
def test_shipped_photo_templates_resolve_to_bundled_placeholder(template_id: str) -> None:
    template = load_template(template_id)
    sources = [
        img.source_path for panel in template.panels for img in panel.image_elements
    ]
    assert sources, f"{template_id} ships no image_elements"
    for source in sources:
        assert Path(source).is_absolute()
        assert Path(source).is_file(), f"{template_id}: {source} missing"


@pytest.fixture
def fake_photo_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A template catalog whose ``photo.jpg`` passes containment but is text."""
    tdir = tmp_path / "catalog" / "generic"
    path = _write(tdir, "photo.jpg")
    (tdir / "photo.jpg").write_text("AWS_SECRET_ACCESS_KEY=hunter2")
    monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path / "catalog"))
    return path.parent / "photo.jpg"


@pytest.mark.usefixtures("fake_photo_catalog")
@pytest.mark.parametrize("fmt", ["svg", "pdf"])
def test_create_with_non_image_template_photo_exits_two(tmp_path: Path, fmt: str) -> None:
    out = tmp_path / f"o.{fmt}"
    result = CliRunner().invoke(app, ["create", "t-image", "-o", str(out)])
    assert result.exit_code == 2, result.output
    assert "photo.jpg" in result.stderr
    assert "Traceback" not in result.output
    assert not out.exists()


@pytest.mark.usefixtures("fake_photo_catalog")
def test_preview_with_non_image_template_photo_exits_two(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["preview", "t-image", "--no-open", "-o", str(tmp_path / "p.png")]
    )
    assert result.exit_code == 2, result.output
    assert "photo.jpg" in result.stderr
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Panel background_image (#153): resolved and contained exactly like images.
# ---------------------------------------------------------------------------


def _write_background(directory: Path, background_image: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    data = _template("unused.jpg")
    data["panels"][0]["image_elements"] = []
    data["panels"][0]["background_image"] = background_image
    path = directory / "t.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def test_background_image_resolves_against_template_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tdir = tmp_path / "tpl"
    path = _write_background(tdir, "art/bg.jpg")
    (tdir / "art").mkdir()
    shutil.copy(FIXTURE_IMAGE, tdir / "art" / "bg.jpg")
    monkeypatch.chdir(tmp_path)
    background = load_template_from_file(path).panels[0].background_image
    assert background == str((tdir / "art" / "bg.jpg").resolve())


@pytest.mark.parametrize(
    ("background_image", "match"),
    [("../bg.png", r"\.\."), ("/abs/bg.png", "absolute")],
)
def test_background_image_escape_is_load_error(
    tmp_path: Path, background_image: str, match: str
) -> None:
    path = _write_background(tmp_path / "tpl", background_image)
    with pytest.raises(TemplateLoadError, match=match) as exc_info:
        load_template_from_file(path)
    assert "panels[0].background_image" in str(exc_info.value)


def test_background_image_symlink_escape_is_load_error(tmp_path: Path) -> None:
    outside = tmp_path / "bg.png"
    shutil.copy(FIXTURE_IMAGE, outside)
    tdir = tmp_path / "tpl"
    path = _write_background(tdir, "bg.png")
    (tdir / "bg.png").symlink_to(outside)
    with pytest.raises(TemplateLoadError, match="outside") as exc_info:
        load_template_from_file(path)
    assert "panels[0].background_image" in str(exc_info.value)
