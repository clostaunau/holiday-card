"""Shipped-template invariants (#65) and the template search path / resolver (#79)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.data_paths import data_path
from holiday_card.core.templates import (
    TemplateNotFoundError,
    discover_templates,
    load_template,
    resolve_template,
    template_search_path,
    templates_with_photo_slots,
    user_templates_dir,
)

_PHOTO_TEMPLATES = sorted(
    t["id"] for t in discover_templates()
    if any(p.image_elements for p in load_template(t["id"]).panels)
)


def test_the_five_photo_templates_are_discovered() -> None:
    assert _PHOTO_TEMPLATES == [
        "birthday-photo",
        "christmas-family-photo",
        "christmas-holiday-masterpiece",
        "christmas-photo-ornament",
        "mothers-day-photo",
    ]


@pytest.mark.parametrize("template_id", _PHOTO_TEMPLATES)
def test_photo_template_has_front_photo_slot(template_id: str) -> None:
    template = load_template(template_id)
    front = [p for p in template.panels if p.position.value == "front"]
    assert any(e.slot == "photo" for p in front for e in p.image_elements)


@pytest.mark.parametrize("template_id", _PHOTO_TEMPLATES)
def test_photo_slots_are_contiguous(template_id: str) -> None:
    slots = {
        e.slot for p in load_template(template_id).panels
        for e in p.image_elements if e.slot is not None
    }
    expected = {"photo"} | {f"photo-{k}" for k in range(2, len(slots) + 1)}
    assert slots == expected


@pytest.mark.parametrize("template_id", _PHOTO_TEMPLATES)
def test_photo_template_uses_the_placeholder(template_id: str) -> None:
    for panel in load_template(template_id).panels:
        for element in panel.image_elements:
            assert Path(element.source_path).name == "placeholder-photo.jpg"


def test_templates_with_photo_slots_lists_the_photo_templates() -> None:
    assert templates_with_photo_slots() == _PHOTO_TEMPLATES


def _placeholders() -> list[Path]:
    return sorted(data_path("templates").rglob("placeholder-photo.jpg"))


def test_every_placeholder_copy_is_byte_identical() -> None:
    copies = _placeholders()
    assert len(copies) == 3
    digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in copies}
    assert len(digests) == 1


def test_placeholder_is_at_least_300_ppi_at_the_largest_slot() -> None:
    with Image.open(_placeholders()[0]) as img:
        assert img.format == "JPEG"
        assert min(img.size) >= 1200


def test_old_400px_sample_photo_is_gone() -> None:
    assert list(data_path("templates").rglob("sample_photo.jpg")) == []


# ---------------------------------------------------------------------------
# Template search path and resolver (#79)
# ---------------------------------------------------------------------------

_CLASSIC = data_path("templates") / "christmas" / "classic.yaml"


def _write_template(directory: Path, filename: str, template_id: str) -> Path:
    """A copy of christmas-classic under ``directory`` with a new id."""
    directory.mkdir(parents=True, exist_ok=True)
    text = _CLASSIC.read_text().replace('id: "christmas-classic"', f'id: "{template_id}"', 1)
    assert f'id: "{template_id}"' in text
    path = directory / filename
    path.write_text(text)
    return path


@pytest.fixture
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated XDG data home and no env layer."""
    home = tmp_path / "xdg"
    home.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(home))
    monkeypatch.delenv("HOLIDAY_CARD_TEMPLATES", raising=False)
    return home


@pytest.mark.usefixtures("xdg")
class TestTemplateSearchPath:
    def test_default_layers_are_user_then_builtin(self, xdg: Path) -> None:
        assert template_search_path() == [
            ("user", xdg / "holiday-card" / "templates"),
            ("builtin", data_path("templates")),
        ]

    def test_user_dir_defaults_to_local_share(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert user_templates_dir() == tmp_path / ".local/share/holiday-card/templates"

    def test_empty_xdg_data_home_is_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", "")
        monkeypatch.setenv("HOME", str(tmp_path))
        assert user_templates_dir() == tmp_path / ".local/share/holiday-card/templates"

    def test_env_entries_come_first_split_on_pathsep(
        self, xdg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        a, b = tmp_path / "a", tmp_path / "b"
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", f"{a}{os.pathsep}{b}")
        assert template_search_path() == [
            ("env", a),
            ("env", b),
            ("user", xdg / "holiday-card" / "templates"),
            ("builtin", data_path("templates")),
        ]

    def test_env_entries_expand_user(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", "~/tpl")
        assert template_search_path()[0] == ("env", tmp_path / "tpl")


@pytest.mark.usefixtures("xdg")
class TestDiscoverLayers:
    def test_env_layer_adds_to_the_builtins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_template(tmp_path / "mine", "a.yaml", "my-card")
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path / "mine"))
        found = {t["id"]: t for t in discover_templates()}
        assert found["my-card"]["source"] == "env"
        assert found["christmas-classic"]["source"] == "builtin"
        assert sum(t["source"] == "builtin" for t in found.values()) == 21

    def test_missing_layers_are_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path / "nonexistent"))
        assert len(discover_templates()) == 21

    def test_user_template_shadows_builtin_and_is_listed_once(self, xdg: Path) -> None:
        _write_template(xdg / "holiday-card" / "templates", "classic.yaml", "christmas-classic")
        matches = [t for t in discover_templates() if t["id"] == "christmas-classic"]
        assert len(matches) == 1
        assert matches[0]["source"] == "user"
        assert matches[0]["shadows"] == "builtin"
        assert matches[0]["path"] == str(xdg / "holiday-card" / "templates" / "classic.yaml")

    def test_occasion_comes_from_the_yaml_not_the_directory(self, xdg: Path) -> None:
        # User dirs need no occasion subfolder.
        _write_template(xdg / "holiday-card" / "templates", "flat.yaml", "flat-card")
        found = {t["id"]: t for t in discover_templates()}
        assert found["flat-card"]["occasion"] == "christmas"

    def test_yml_extension_is_discovered(self, xdg: Path) -> None:
        _write_template(xdg / "holiday-card" / "templates" / "x", "y.yml", "yml-card")
        assert "yml-card" in {t["id"] for t in discover_templates()}

    def test_non_mapping_yaml_is_skipped(self, xdg: Path) -> None:
        user = xdg / "holiday-card" / "templates"
        user.mkdir(parents=True)
        (user / "empty.yaml").write_text("")
        (user / "list.yaml").write_text("- 1\n- 2\n")
        assert len(discover_templates()) == 21


@pytest.mark.usefixtures("xdg")
class TestResolveTemplate:
    def test_builtin_by_id(self) -> None:
        template, path = resolve_template("christmas-classic")
        assert template.id == "christmas-classic"
        assert path == _CLASSIC

    def test_by_filename_stem(self, xdg: Path) -> None:
        user = xdg / "holiday-card" / "templates"
        _write_template(user, "stemmy.yaml", "other-id")
        template, path = resolve_template("stemmy")
        assert template.id == "other-id"
        assert path == user / "stemmy.yaml"

    def test_id_beats_an_earlier_layers_stem(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_template(tmp_path / "env", "christmas-classic.yaml", "decoy")
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path / "env"))
        assert resolve_template("christmas-classic")[1] == _CLASSIC

    def test_user_shadows_builtin(self, xdg: Path) -> None:
        user = xdg / "holiday-card" / "templates" / "christmas"
        mine = _write_template(user, "classic.yaml", "christmas-classic")
        assert resolve_template("christmas-classic")[1] == mine

    def test_env_shadows_user(
        self, xdg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_template(xdg / "holiday-card" / "templates", "u.yaml", "dup")
        env = _write_template(tmp_path / "env", "e.yaml", "dup")
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path / "env"))
        assert resolve_template("dup")[1] == env

    def test_unknown_id_raises(self) -> None:
        with pytest.raises(TemplateNotFoundError, match="Template not found: nope"):
            resolve_template("nope")

    @pytest.mark.parametrize(
        "ref", ["./x.yaml", "sub/x.yaml", "x.yml", "x.yaml", ".hidden/x"]
    )
    def test_relative_path_refs_load_from_cwd(
        self, ref: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        work = tmp_path / "work"
        target = work / ref
        _write_template(target.parent, target.name, "path-card")
        monkeypatch.chdir(work)
        template, path = resolve_template(ref)
        assert template.id == "path-card"
        assert path == target.resolve()

    def test_absolute_path_ref(self, tmp_path: Path) -> None:
        target = _write_template(tmp_path / "abs", "x.yaml", "abs-card")
        assert resolve_template(str(target))[0].id == "abs-card"

    def test_tilde_path_ref(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_template(tmp_path, "x.yaml", "home-card")
        assert resolve_template("~/x.yaml")[0].id == "home-card"

    def test_path_ref_never_searches_the_layers(self) -> None:
        # "classic.yaml" is path-like, so the builtin with that filename is not found.
        with pytest.raises(TemplateNotFoundError, match="Template not found: classic.yaml"):
            resolve_template("classic.yaml")

    def test_missing_path_names_the_path(self) -> None:
        with pytest.raises(
            TemplateNotFoundError, match="^Template not found: does/not/exist.yaml$"
        ):
            resolve_template("does/not/exist.yaml")

    def test_directory_path_is_not_a_template(self, tmp_path: Path) -> None:
        with pytest.raises(TemplateNotFoundError):
            resolve_template(str(tmp_path) + "/")

    def test_path_loaded_template_images_resolve_against_the_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # D5: a relative ref still yields absolute image paths next to the YAML.
        src = data_path("templates") / "christmas"
        work = tmp_path / "work" / "tpl"
        work.mkdir(parents=True)
        (work / "p.yaml").write_text((src / "family-photo.yaml").read_text())
        (work / "placeholder-photo.jpg").write_bytes((src / "placeholder-photo.jpg").read_bytes())
        monkeypatch.chdir(tmp_path / "work")
        template, _ = resolve_template("tpl/p.yaml")
        sources = [e.source_path for p in template.panels for e in p.image_elements]
        assert sources == [str(work.resolve() / "placeholder-photo.jpg")]

    def test_load_template_keeps_an_explicit_dir(self, tmp_path: Path) -> None:
        _write_template(tmp_path / "only" / "generic", "a.yaml", "only-card")
        assert load_template("only-card", tmp_path / "only").id == "only-card"
        with pytest.raises(TemplateNotFoundError):
            load_template("christmas-classic", tmp_path / "only")
