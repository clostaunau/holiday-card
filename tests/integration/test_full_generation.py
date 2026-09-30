"""Integration tests for full card generation workflow."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pikepdf
import pytest

from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import FoldType
from holiday_card.renderers.svg_backend import SVGRenderer


class TestFullGeneration:
    """Integration tests for the complete card generation workflow."""

    @pytest.fixture
    def generator(self):
        """Create a card generator instance."""
        return CardGenerator()

    @pytest.fixture
    def temp_output(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_create_christmas_classic_card(self, generator, temp_output):
        """Test creating a Christmas classic card."""
        output_path = temp_output / "christmas-card.pdf"

        card = generator.create_card(
            template_id="christmas-classic",
            output_path=output_path,
            message="Merry Christmas!",
        )
        pdf_path = generator.generate(card, output_path)[0]

        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0
        assert card.fold_type == FoldType.QUARTER_FOLD
        assert card.template_id == "christmas-classic"

    def test_create_card_with_theme(self, generator, temp_output):
        """Test creating a card with a color theme."""
        output_path = temp_output / "themed-card.pdf"

        card = generator.create_card(
            template_id="christmas-classic",
            output_path=output_path,
            message="Season's Greetings!",
            theme_id="christmas-winter-blue",
        )
        pdf_path = generator.generate(card, output_path)[0]

        assert pdf_path.exists()
        assert card.theme_id == "christmas-winter-blue"

    def test_create_card_with_fold_override(self, generator, temp_output):
        """Test creating a card with fold type override."""
        output_path = temp_output / "quarter-fold-card.pdf"

        card = generator.create_card(
            template_id="christmas-classic",
            output_path=output_path,
            fold_type=FoldType.QUARTER_FOLD,
        )
        pdf_path = generator.generate(card, output_path)[0]

        assert pdf_path.exists()
        assert card.fold_type == FoldType.QUARTER_FOLD

    def test_create_birthday_card(self, generator, temp_output):
        """Test creating a birthday card."""
        output_path = temp_output / "birthday-card.pdf"

        card = generator.create_card(
            template_id="birthday-balloons",
            output_path=output_path,
            message="Happy Birthday!",
        )
        pdf_path = generator.generate(card, output_path)[0]

        assert pdf_path.exists()
        assert "birthday" in card.template_id

    def test_create_modern_christmas_card(self, generator, temp_output):
        """Test creating a modern Christmas card (quarter fold)."""
        output_path = temp_output / "modern-christmas.pdf"

        card = generator.create_card(
            template_id="christmas-modern",
            output_path=output_path,
            message="Happy Holidays!",
        )
        pdf_path = generator.generate(card, output_path)[0]

        assert pdf_path.exists()
        assert card.fold_type == FoldType.QUARTER_FOLD

    def test_card_panels_are_populated(self, generator, temp_output):
        """Test that card panels are properly populated."""
        output_path = temp_output / "card.pdf"

        card = generator.create_card(
            template_id="christmas-classic",
            output_path=output_path,
            message="Test Message",
        )
        generator.generate(card, output_path)

        # Should have 4 panels for half-fold
        assert len(card.panels) == 4

        # Front panel should have the message
        front_panel = next(p for p in card.panels if p.position.value == "front")
        assert len(front_panel.text_elements) > 0

    def test_output_directory_created(self, generator, temp_output):
        """Test that output directory is created if it doesn't exist."""
        nested_path = temp_output / "nested" / "dir" / "card.pdf"

        card = generator.create_card(
            template_id="christmas-classic",
            output_path=nested_path,
        )
        pdf_path = generator.generate(card, nested_path)[0]

        assert pdf_path.exists()
        assert pdf_path.parent.exists()


class TestTemplateDiscovery:
    """Tests for template discovery functionality."""

    def test_discover_templates(self):
        """Test that templates can be discovered."""
        from holiday_card.core.templates import discover_templates

        templates = discover_templates()

        # Should find at least the Christmas templates
        assert len(templates) > 0

        # Check template structure
        template = templates[0]
        assert "id" in template
        assert "name" in template
        assert "occasion" in template
        assert "fold_type" in template


class TestLetterPageBoxes:
    """The default ``letter`` target is for home printers: a true US
    Letter page with no bleed (D7, #59). Every PDF box is the same
    8.5x11 rectangle, so a print dialog never has to "fit to page" and
    shrink the sheet (which used to move the fold lines off centre).
    """

    def test_pdf_boxes_are_all_us_letter(self, tmp_path: Path) -> None:
        out = tmp_path / "boxes.pdf"
        generator = CardGenerator()
        card = generator.create_card(
            template_id="christmas-classic", output_path=out,
        )
        generator.generate(card, out)
        with pikepdf.open(out) as pdf:
            page = pdf.pages[0]
            letter = [0.0, 0.0, 612.0, 792.0]
            assert [float(v) for v in page.MediaBox] == letter
            assert [float(v) for v in page.CropBox] == letter
            assert [float(v) for v in page.TrimBox] == letter
            assert [float(v) for v in page.BleedBox] == letter
            # ArtBox is the safe area inset 0.25" from the trim.
            assert [float(v) for v in page.ArtBox] == [18.0, 18.0, 594.0, 774.0]

    def test_svg_canvas_is_us_letter(self, tmp_path: Path) -> None:
        out = tmp_path / "letter.svg"
        generator = CardGenerator(renderer=SVGRenderer())
        card = generator.create_card(
            template_id="christmas-classic", output_path=out,
        )
        generator.generate(card, out)
        root = ET.parse(out).getroot()
        assert root.get("width") == "612"
        assert root.get("height") == "792"
        assert root.get("viewBox") == "0 0 612 792"


class TestThemeDiscovery:
    """Tests for theme discovery functionality."""

    def test_discover_themes(self):
        """Test that themes can be discovered."""
        from holiday_card.core.themes import discover_themes

        themes = discover_themes()

        # Should find the themes we created
        assert len(themes) > 0

        # Check theme structure
        theme = themes[0]
        assert "id" in theme
        assert "name" in theme
        assert "occasion" in theme


def _shipped_template_ids() -> list[str]:
    from holiday_card.core.templates import discover_templates

    return sorted(t["id"] for t in discover_templates())


class TestShippedTemplatesPrintResolution:
    """#66: every shipped template (placeholder photos included) prints at
    ≥ 300 PPI on every print target, so `create` to PDF has no findings."""

    @pytest.mark.parametrize("template_id", _shipped_template_ids())
    @pytest.mark.parametrize("target_name", ["letter", "per-panel-pdf", "moo-a6"])
    def test_no_resolution_findings(self, template_id: str, target_name: str) -> None:
        from holiday_card.core.compiler import CompileContext, compile_card
        from holiday_card.core.export_targets import get_target
        from holiday_card.core.images import check_print_resolution
        from holiday_card.core.per_panel import build_per_panel_card, build_per_panel_context

        card = CardGenerator().create_card(template_id=template_id)
        target = get_target(target_name)
        if target.layout == "imposition":
            assert target.geometry is not None
            commands = compile_card(card, CompileContext(geometry=target.geometry))
        else:
            commands = [
                cmd
                for panel in card.panels
                for cmd in compile_card(
                    build_per_panel_card(card, panel), build_per_panel_context(panel, target),
                )
            ]
        assert check_print_resolution(commands) == []

    def test_placeholder_photo_card_writes_pdf_without_warnings(self, tmp_path: Path) -> None:
        import warnings

        generator = CardGenerator()
        card = generator.create_card(template_id="christmas-photo-ornament")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            (out,) = generator.generate(card, tmp_path / "c.pdf")
        assert out.exists()
