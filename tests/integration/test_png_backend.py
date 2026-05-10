"""Integration tests for the PNG backend.

Renders every Wave 2-supported template to PNG and verifies the output
is a valid image with the expected dimensions. Same shape as
``test_svg_backend.py`` — keep them in sync.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.renderers.png_backend import PNGRenderer

PNG_TEMPLATES = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "birthday-balloons",
    "hanukkah-menorah",
    "generic-celebration",
)


def _render_png(template_id: str, output_path: Path, dpi: int = 72) -> None:
    """Use 72 DPI by default in tests so files stay small and fast."""
    card = CardGenerator().create_card(template_id=template_id)
    commands = compile_card(card)
    PNGRenderer(dpi=dpi).render(commands, output_path)


@pytest.mark.parametrize("template_id", PNG_TEMPLATES)
def test_png_renders_valid_image(template_id: str, tmp_path: Path) -> None:
    out = tmp_path / f"{template_id}.png"
    _render_png(template_id, out)

    assert out.exists()
    assert out.stat().st_size > 200, "PNG output is suspiciously small"

    # Pillow can open it == valid PNG
    img = Image.open(out)
    img.verify()


@pytest.mark.parametrize("template_id", PNG_TEMPLATES)
def test_png_dimensions_match_letter_at_chosen_dpi(
    template_id: str, tmp_path: Path
) -> None:
    """Letter is 8.5" × 11" → at 72 DPI that's 612 × 792 pixels."""
    out = tmp_path / f"{template_id}.png"
    _render_png(template_id, out, dpi=72)
    img = Image.open(out)
    assert img.size == (612, 792), (
        f"{template_id} PNG should be 612x792 at 72 DPI, got {img.size}"
    )


def test_png_higher_dpi_produces_proportionally_larger_image(tmp_path: Path) -> None:
    """A 144 DPI PNG should be exactly 2× the dimensions of a 72 DPI one."""
    low = tmp_path / "low.png"
    high = tmp_path / "high.png"
    _render_png("christmas-classic", low, dpi=72)
    _render_png("christmas-classic", high, dpi=144)
    low_size = Image.open(low).size
    high_size = Image.open(high).size
    assert high_size == (low_size[0] * 2, low_size[1] * 2)


def test_png_christmas_classic_has_red_pixel_in_front_panel(tmp_path: Path) -> None:
    """christmas-classic has a red front panel background. Sample a pixel
    from the front-panel area and confirm the red channel dominates.
    """
    out = tmp_path / "christmas.png"
    _render_png("christmas-classic", out, dpi=72)
    img = Image.open(out).convert("RGB")
    # Front panel is the right half of the page (x: 4.25"-8.5", y: 0-5.5").
    # In Pillow pixel coords (top-left origin, 72 DPI), that's around
    # (450, 600) — well within the panel and well away from any text.
    r, g, b = img.getpixel((450, 600))
    assert r > 150, f"Expected red-dominant pixel; got rgb=({r},{g},{b})"
    assert r > g and r > b, f"Expected red-dominant pixel; got rgb=({r},{g},{b})"


def test_png_renderer_rejects_invalid_dpi() -> None:
    with pytest.raises(ValueError, match="dpi must be"):
        PNGRenderer(dpi=10)


def test_png_rotated_panel_renders_at_expected_position(tmp_path: Path) -> None:
    """christmas-geometric (and -modern, -artist) have a back panel rotated
    180° around its center. This test catches the bug where a backend
    misinterprets the IR's pivot-rotate Transform and ends up drawing the
    rotated content in the wrong place. We sample a pixel deep inside the
    back panel; it should not be the white default background.
    """
    out = tmp_path / "rotated.png"
    _render_png("christmas-geometric", out, dpi=72)
    img = Image.open(out).convert("RGB")
    # christmas-geometric back panel is at x=0..4.25, y=5.5..11
    # (top-left in the unfolded layout). A point well inside the panel
    # at IR (2.0, 8.0) is pixel (144, 216) at 72 DPI (Pillow top-left origin).
    r, g, b = img.getpixel((144, 216))
    is_white = (r, g, b) == (255, 255, 255)
    assert not is_white, (
        "Back panel at (144, 216) is white default — rotated-panel content "
        "appears to have rendered outside the expected area. "
        f"Got rgb=({r},{g},{b})."
    )
