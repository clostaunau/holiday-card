"""Integration tests for full card generation workflow."""

import re
import tempfile
from pathlib import Path

import pytest

from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import FoldType


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

        card, pdf_path = generator.create_and_generate(
            template_id="christmas-classic",
            output_path=output_path,
            message="Merry Christmas!",
        )

        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0
        assert card.fold_type == FoldType.HALF_FOLD
        assert card.template_id == "christmas-classic"

    def test_create_card_with_theme(self, generator, temp_output):
        """Test creating a card with a color theme."""
        output_path = temp_output / "themed-card.pdf"

        card, pdf_path = generator.create_and_generate(
            template_id="christmas-classic",
            output_path=output_path,
            message="Season's Greetings!",
            theme_id="christmas-winter-blue",
        )

        assert pdf_path.exists()
        assert card.theme_id == "christmas-winter-blue"

    def test_create_card_with_fold_override(self, generator, temp_output):
        """Test creating a card with fold type override."""
        output_path = temp_output / "quarter-fold-card.pdf"

        card, pdf_path = generator.create_and_generate(
            template_id="christmas-classic",
            output_path=output_path,
            fold_type=FoldType.QUARTER_FOLD,
        )

        assert pdf_path.exists()
        assert card.fold_type == FoldType.QUARTER_FOLD

    def test_create_birthday_card(self, generator, temp_output):
        """Test creating a birthday card."""
        output_path = temp_output / "birthday-card.pdf"

        card, pdf_path = generator.create_and_generate(
            template_id="birthday-balloons",
            output_path=output_path,
            message="Happy Birthday!",
        )

        assert pdf_path.exists()
        assert "birthday" in card.template_id

    def test_create_modern_christmas_card(self, generator, temp_output):
        """Test creating a modern Christmas card (quarter fold)."""
        output_path = temp_output / "modern-christmas.pdf"

        card, pdf_path = generator.create_and_generate(
            template_id="christmas-modern",
            output_path=output_path,
            message="Happy Holidays!",
        )

        assert pdf_path.exists()
        assert card.fold_type == FoldType.QUARTER_FOLD

    def test_card_panels_are_populated(self, generator, temp_output):
        """Test that card panels are properly populated."""
        output_path = temp_output / "card.pdf"

        card, _ = generator.create_and_generate(
            template_id="christmas-classic",
            output_path=output_path,
            message="Test Message",
        )

        # Should have 4 panels for half-fold
        assert len(card.panels) == 4

        # Front panel should have the message
        front_panel = next(p for p in card.panels if p.position.value == "front")
        assert len(front_panel.text_elements) > 0

    def test_output_directory_created(self, generator, temp_output):
        """Test that output directory is created if it doesn't exist."""
        nested_path = temp_output / "nested" / "dir" / "card.pdf"

        _, pdf_path = generator.create_and_generate(
            template_id="christmas-classic",
            output_path=nested_path,
        )

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


class TestBleedInPDF:
    """The PDF must declare distinct MediaBox / TrimBox / BleedBox / ArtBox
    so downstream POD preflight tools accept the file. Until this PR
    landed they were all equal — the panel critique flagged this and
    every POD service rejects unbroken-box PDFs.
    """

    def test_pdf_declares_distinct_boxes(self, tmp_path: Path) -> None:
        """Render christmas-classic with the default 0.125\" bleed and
        confirm the PDF byte-stream contains distinct /MediaBox,
        /TrimBox, /BleedBox declarations with the expected dimensions.
        """
        out = tmp_path / "boxes.pdf"
        CardGenerator().create_and_generate(
            template_id="christmas-classic", output_path=out,
        )
        pdf_bytes = out.read_bytes()

        # ReportLab serializes box arrays as e.g. "/TrimBox [9 9 621 801]".
        # Numbers may have a trailing decimal in some ReportLab versions.
        def find_box(name: bytes) -> tuple[float, float, float, float]:
            match = re.search(
                rb"/" + name + rb"\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]",
                pdf_bytes,
            )
            assert match, f"PDF does not declare /{name.decode()}"
            return tuple(float(g) for g in match.groups())  # type: ignore[return-value]

        # MediaBox = letter + 9pt bleed on every side = 630 x 810
        media = find_box(b"MediaBox")
        assert media == (0.0, 0.0, 630.0, 810.0)
        # TrimBox sits inside MediaBox at (bleed, bleed) → top-right (621, 801)
        trim = find_box(b"TrimBox")
        assert trim == (9.0, 9.0, 621.0, 801.0)
        # BleedBox equals MediaBox until a slug area is added
        bleed = find_box(b"BleedBox")
        assert bleed == media
        # ArtBox is the safe area inside trim
        art = find_box(b"ArtBox")
        assert art == (27.0, 27.0, 603.0, 783.0)

    def test_media_and_trim_differ_for_bleed_aware_pdf(self, tmp_path: Path) -> None:
        """Regression watchdog for the previous defect: until this PR,
        every box equaled MediaBox. After the change, MediaBox != TrimBox.
        """
        out = tmp_path / "regress.pdf"
        CardGenerator().create_and_generate(
            template_id="christmas-classic", output_path=out,
        )
        pdf_bytes = out.read_bytes()
        # The exact serialized form of MediaBox should NOT also appear as
        # the entire content of TrimBox.
        media_match = re.search(rb"/MediaBox\s*\[\s*([^\]]+)\s*\]", pdf_bytes)
        trim_match = re.search(rb"/TrimBox\s*\[\s*([^\]]+)\s*\]", pdf_bytes)
        assert media_match and trim_match
        assert media_match.group(1).strip() != trim_match.group(1).strip(), (
            "MediaBox and TrimBox have identical contents — the bleed "
            "extension did not propagate to the PDF box declarations."
        )


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
