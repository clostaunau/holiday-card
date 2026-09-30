"""Integration tests for scripts/build_microsite.py.

Builds the microsite into a temp directory and asserts the expected
file shape:

* ``site/index.html`` exists and references every per-template page
* ``site/templates/{id}.html`` exists for every discovered template
* ``site/thumbs/{id}.png`` exists for every template (non-empty PNG)
* per-template pages carry the expected form fields + JS scaffolding

The build runs the same code path as the production GH Action,
including thumbnail rendering. ~5-10s end to end.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_build_module():
    """Import scripts/build_microsite.py as a module.

    scripts/ isn't a package, so we load by file path via importlib.
    Done once per test session via the fixture below.
    """
    spec = importlib.util.spec_from_file_location(
        "build_microsite", REPO_ROOT / "scripts" / "build_microsite.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_microsite"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built_site(tmp_path_factory: pytest.TempPathFactory):
    """Run the build once per test module; reuse for individual assertions."""
    output = tmp_path_factory.mktemp("microsite")
    module = _load_build_module()
    # A user and an env template are on the search path (#79); the gallery
    # must still show only the built-ins.
    layers = tmp_path_factory.mktemp("layers")
    classic = (REPO_ROOT / "src/holiday_card/data/templates/christmas/classic.yaml").read_text()
    for layer, template_id in (
        ("xdg/holiday-card/templates", "user-only-card"),
        ("env", "env-only-card"),
    ):
        (layers / layer).mkdir(parents=True)
        (layers / layer / "t.yaml").write_text(
            classic.replace('id: "christmas-classic"', f'id: "{template_id}"', 1)
        )
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("XDG_DATA_HOME", str(layers / "xdg"))
        mp.setenv("HOLIDAY_CARD_TEMPLATES", str(layers / "env"))
        # Use a small DPI to keep the build fast; the structural assertions
        # don't care about thumbnail resolution.
        cards = module.build(output, dpi=72)
    return output, cards


class TestBuildShape:
    def test_index_exists(self, built_site) -> None:
        output, cards = built_site
        assert (output / "index.html").is_file()
        assert (output / "style.css").is_file()
        # Should produce all 14 templates currently in the repo.
        assert len(cards) >= 14, f"Expected 14+ templates rendered, got {len(cards)}"

    def test_gallery_shows_only_the_builtin_templates(self, built_site) -> None:
        from holiday_card.core.data_paths import data_path
        from holiday_card.core.templates import discover_templates

        _, cards = built_site
        builtin = {t["id"] for t in discover_templates(data_path("templates"))}
        assert {c.id for c in cards} == builtin

    def test_per_template_pages_exist(self, built_site) -> None:
        output, cards = built_site
        for card in cards:
            page = output / "templates" / f"{card.id}.html"
            assert page.is_file(), f"Missing per-template page for {card.id}"

    def test_thumbnails_exist_and_nonempty(self, built_site) -> None:
        output, cards = built_site
        for card in cards:
            thumb = output / "thumbs" / f"{card.id}.png"
            assert thumb.is_file(), f"Missing thumbnail for {card.id}"
            assert thumb.stat().st_size > 100, (
                f"Thumbnail too small for {card.id}: {thumb.stat().st_size} bytes"
            )

    def test_index_links_every_template(self, built_site) -> None:
        output, cards = built_site
        index_html = (output / "index.html").read_text()
        for card in cards:
            assert f'href="templates/{card.id}.html"' in index_html, (
                f"Gallery should link to templates/{card.id}.html"
            )


class TestTemplatePageContents:
    """Per-template page carries form fields + the copy-command script."""

    def test_form_fields_present(self, built_site) -> None:
        output, cards = built_site
        sample = output / "templates" / cards[0].id
        page = Path(str(sample) + ".html").read_text()
        # All the form field ids the JS references must exist.
        for field_id in (
            "f-message", "f-inside", "f-voice",
            "f-salutation", "f-signoff", "f-signature", "f-ps",
            "f-moo-a6",
        ):
            assert f'id="{field_id}"' in page, (
                f"Form field {field_id} should appear on template page"
            )

    def test_copy_command_script_present(self, built_site) -> None:
        output, cards = built_site
        page = (output / "templates" / f"{cards[0].id}.html").read_text()
        assert "function buildCommand" in page
        assert "holiday-card" in page
        assert "navigator.clipboard" in page

    def test_back_link_to_gallery(self, built_site) -> None:
        output, cards = built_site
        for card in cards:
            page = (output / "templates" / f"{card.id}.html").read_text()
            assert 'href="../index.html"' in page, (
                f"{card.id} page should link back to ../index.html"
            )

    def test_template_id_appears_in_command(self, built_site) -> None:
        output, cards = built_site
        for card in cards:
            page = (output / "templates" / f"{card.id}.html").read_text()
            # The page's JS hardcodes the template id into the
            # command — verify it's embedded correctly.
            assert f'"id": "{card.id}"' in page, (
                f"{card.id} page should embed its own id in the JS metadata"
            )


class TestOccasionGrouping:
    """Templates are grouped by occasion in the gallery."""

    def test_christmas_subsection_appears(self, built_site) -> None:
        output, _ = built_site
        index_html = (output / "index.html").read_text()
        assert "<h3>Christmas</h3>" in index_html

    def test_known_occasions_have_sections(self, built_site) -> None:
        output, cards = built_site
        index_html = (output / "index.html").read_text()
        occasions = {c.occasion for c in cards}
        # Every represented occasion should have a section header.
        for occ in occasions:
            # Section header is the human label; check the
            # corresponding badge class instead since it's invariant.
            assert f"badge-{occ}" in index_html, (
                f"Gallery should style occasion {occ!r} with a badge class"
            )


class TestCategorySeparation:
    """Sympathy-class occasions live in a visually separated category so
    a user looking for a sympathy card doesn't scroll past birthday and
    Christmas cards to get there."""

    def test_celebrations_category_renders(self, built_site) -> None:
        output, _ = built_site
        index_html = (output / "index.html").read_text()
        assert 'class="category category-celebrations"' in index_html
        assert "<h2>Celebrations</h2>" in index_html

    def test_sympathy_category_renders(self, built_site) -> None:
        output, _ = built_site
        index_html = (output / "index.html").read_text()
        assert 'class="category category-sympathy"' in index_html
        assert "<h2>With sympathy</h2>" in index_html

    def test_sympathy_class_cards_live_in_sympathy_category(
        self, built_site
    ) -> None:
        """A card linked from the sympathy category must be a
        sympathy-class template (not, say, a birthday card)."""
        output, _ = built_site
        index_html = (output / "index.html").read_text()
        sympathy_block = _between(
            index_html,
            'class="category category-sympathy"',
            "</section>\n  </main>",  # category end → main end
        )
        # Every sympathy-class template should appear in this block.
        for tmpl_id in (
            "sympathy-spare", "condolence-spare",
            "miscarriage-spare", "pet-loss-spare",
        ):
            assert f'href="templates/{tmpl_id}.html"' in sympathy_block, (
                f"{tmpl_id} should appear in the sympathy category section"
            )
        # And a celebration template should NOT.
        assert 'href="templates/christmas-classic.html"' not in sympathy_block

    def test_celebrations_cards_live_in_celebrations_category(
        self, built_site
    ) -> None:
        output, _ = built_site
        index_html = (output / "index.html").read_text()
        celebrations_block = _between(
            index_html,
            'class="category category-celebrations"',
            'class="category category-sympathy"',
        )
        for tmpl_id in (
            "christmas-classic", "birthday-balloons",
            "hanukkah-menorah", "mothers-day",
        ):
            assert f'href="templates/{tmpl_id}.html"' in celebrations_block, (
                f"{tmpl_id} should appear in the celebrations category"
            )
        # And a sympathy template should NOT.
        assert 'href="templates/sympathy-spare.html"' not in celebrations_block


def _between(haystack: str, start_marker: str, end_marker: str) -> str:
    """Return the substring of ``haystack`` between the first occurrence
    of ``start_marker`` and the next occurrence of ``end_marker``. Raises
    AssertionError with context if either marker is missing — keeps test
    failure modes loud."""
    i = haystack.find(start_marker)
    assert i != -1, f"start_marker not found: {start_marker!r}"
    j = haystack.find(end_marker, i + len(start_marker))
    assert j != -1, f"end_marker not found after start: {end_marker!r}"
    return haystack[i:j]


# ---------------------------------------------------------------------------
# #82: the gallery emits only commands the CLI accepts
# ---------------------------------------------------------------------------

SYMPATHY_CLASS_TEMPLATES = (
    "sympathy-spare", "condolence-spare", "miscarriage-spare", "pet-loss-spare",
)
PHOTO_SLOT_TEMPLATES = (
    "christmas-photo-ornament", "christmas-family-photo", "birthday-photo",
    "mothers-day-photo", "christmas-holiday-masterpiece",
)


def _page(output: Path, template_id: str) -> str:
    return (output / "templates" / f"{template_id}.html").read_text()


def _voice_options(page: str) -> list[str]:
    import re

    select = _between(page, '<select id="f-voice">', "</select>")
    return re.findall(r'<option value="([^"]*)">', select)


def _script_blocks(page: str) -> list[str]:
    import re

    return re.findall(r"<script>(.*?)</script>", page, flags=re.DOTALL)


class TestVoiceOptions:
    def test_sympathy_pages_offer_only_curated_voices(self, built_site) -> None:
        output, _ = built_site
        for template_id in SYMPATHY_CLASS_TEMPLATES:
            page = _page(output, template_id)
            assert "witty" not in page, template_id
            assert "irreverent" not in page, template_id

    def test_every_page_offers_exactly_its_occasions_voices(self, built_site) -> None:
        from holiday_card.core.sentiments import available_voices

        output, cards = built_site
        for card in cards:
            offered = _voice_options(_page(output, card.id))
            assert offered == ["", *available_voices(card.occasion)], card.id

    def test_pet_loss_offers_warm_and_spare(self, built_site) -> None:
        output, _ = built_site
        assert _voice_options(_page(output, "pet-loss-spare")) == ["", "warm", "spare"]

    def test_no_voice_select_when_the_occasion_ships_none(self) -> None:
        module = sys.modules.get("build_microsite") or _load_build_module()
        card = module.TemplateCard(
            id="x", name="X", occasion="no-such-occasion", fold_type="quarter_fold",
            description="", thumbnail_path="thumbs/x.png", has_photo_slot=False,
        )
        page = module._render_template_page(card)
        assert 'id="f-voice"' not in page
        assert "--voice" not in page


class TestPhotoField:
    def test_photo_templates_have_image_field(self, built_site) -> None:
        output, cards = built_site
        for template_id in PHOTO_SLOT_TEMPLATES:
            page = _page(output, template_id)
            assert page.count('id="f-image"') == 1, template_id
            assert "parts.push('-i'" in page, template_id
        assert 'id="f-image"' not in _page(output, "christmas-classic")
        # image_elements: [] is not a photo slot.
        assert 'id="f-image"' not in _page(output, "birthday-balloons")

    def test_has_photo_slot_matches_templates_with_photo_slots(self, built_site) -> None:
        from holiday_card.core.data_paths import data_path
        from holiday_card.core.templates import templates_with_photo_slots

        _, cards = built_site
        assert sorted(c.id for c in cards if c.has_photo_slot) == sorted(
            templates_with_photo_slots(data_path("templates"))
        )
        assert set(PHOTO_SLOT_TEMPLATES) <= {c.id for c in cards if c.has_photo_slot}

    def test_image_field_only_on_photo_pages(self, built_site) -> None:
        output, cards = built_site
        for card in cards:
            page = _page(output, card.id)
            assert ('id="f-image"' in page) == card.has_photo_slot, card.id


class TestScriptSafeJson:
    def test_script_json_escapes_closing_tag(self) -> None:
        import json

        module = sys.modules.get("build_microsite") or _load_build_module()
        out = module._script_json({"name": "</script><b>& "})
        assert "<" not in out
        assert ">" not in out
        assert "&" not in out
        assert " " not in out
        assert json.loads(out) == {"name": "</script><b>& "}

    def test_hostile_template_name_cannot_close_the_script(self) -> None:
        module = sys.modules.get("build_microsite") or _load_build_module()
        card = module.TemplateCard(
            id="x", name="</script><script>alert(1)</script>", occasion="christmas",
            fold_type="quarter_fold", description="", thumbnail_path="thumbs/x.png",
            has_photo_slot=False,
        )
        page = module._render_template_page(card)
        assert "<script>alert(1)" not in page
        for block in _script_blocks(page):
            assert "</" not in block.split("const TEMPLATE = ", 1)[-1].split(";", 1)[0]

    def test_no_script_block_has_a_raw_closing_sequence_in_json(self, built_site) -> None:
        output, cards = built_site
        for card in cards:
            for block in _script_blocks(_page(output, card.id)):
                literal = block.split("const TEMPLATE = ", 1)[-1].split(";\n", 1)[0]
                assert "</" not in literal, card.id


class TestFormFlags:
    def test_every_form_flag_is_a_create_option(self, built_site) -> None:
        import re

        import typer.main

        from holiday_card.cli.commands import app

        create = typer.main.get_command(app).commands["create"]  # type: ignore[attr-defined]
        options = {opt for p in create.params for opt in (*p.opts, *p.secondary_opts)}
        output, _ = built_site
        emitted: set[str] = set()
        for template_id in ("christmas-family-photo", "sympathy-spare", "christmas-classic"):
            page = _page(output, template_id)
            emitted |= set(re.findall(r"'(--?[a-z][a-z0-9-]*)'", _script_blocks(page)[0]))
        assert {"-i", "--voice", "-m", "--export-for", "-o"} <= emitted
        assert emitted - options == set()


class TestSharedPipeline:
    def test_thumbnails_are_built_through_build_card(self) -> None:
        source = (REPO_ROOT / "scripts" / "build_microsite.py").read_text()
        assert "contextlib.chdir" not in source
        assert "build_card(" in source
        assert "CardRequest(" in source
        assert "create_card(" not in source
        assert "_VOICES" not in source
