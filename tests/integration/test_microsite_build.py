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
