"""Integration tests for the PNG backend.

Renders every shipped template to PNG and verifies the output is a
valid image with the expected dimensions. Same shape as
``test_svg_backend.py`` — keep them in sync.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from holiday_card.cli.commands import app
from holiday_card.core.compiler import CompileContext, compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.utils.measurements import PageGeometry

PNG_TEMPLATES = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "christmas-festive-stripes",
    "christmas-holiday-masterpiece",
    "christmas-holly-wreath",
    "christmas-metallic-ornaments",
    "christmas-winter-sky",
    "christmas-photo-ornament",
    "christmas-family-photo",
    "birthday-balloons",
    "birthday-photo",
    "hanukkah-menorah",
    "generic-celebration",
    "mothers-day",
    "mothers-day-photo",
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
    """Letter is 8.5" × 11" with no bleed (D7, #59) → 612 × 792 pixels
    at 72 DPI.
    """
    out = tmp_path / f"{template_id}.png"
    _render_png(template_id, out, dpi=72)
    img = Image.open(out)
    assert img.size == (612, 792), (
        f"{template_id} PNG should be 612x792 (letter, no bleed) "
        f"at 72 DPI, got {img.size}"
    )


def test_preview_command_at_144_dpi_is_letter_sized(tmp_path: Path) -> None:
    """``preview --dpi 144`` is 8.5x11 at 144 px/in: exactly 1224x1584 (#59)."""
    out = tmp_path / "preview.png"
    result = CliRunner().invoke(
        app,
        ["preview", "christmas-classic", "--dpi", "144", "--no-open", "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert Image.open(out).size == (1224, 1584)


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

    The canvas is 612x792 at 72 DPI (no bleed, #59). We sample
    (391, 691) — well inside the front-panel red flood (bottom-right
    quadrant) and clear of the centered greeting text glyphs.
    """
    out = tmp_path / "christmas.png"
    _render_png("christmas-classic", out, dpi=72)
    img = Image.open(out).convert("RGB")
    r, g, b = img.getpixel((391, 691))
    assert r > 150, f"Expected red-dominant pixel; got rgb=({r},{g},{b})"
    assert r > g and r > b, f"Expected red-dominant pixel; got rgb=({r},{g},{b})"


def test_png_canvas_includes_bleed_pixels_on_every_side(tmp_path: Path) -> None:
    """With a bleed geometry the PNG canvas grows by ``2 * bleed_px`` on
    each axis; we expect
    the bleed border to be filled by the panel's background-color flood
    where the panel touches a page-trim edge. Sample a pixel in the
    bleed band right next to the trim corner — for christmas-classic's
    front panel (red bg, touches right + bottom of page), the
    bottom-right bleed strip should be red. The default letter page has
    no bleed (#59), so this compiles with an explicit 0.125" geometry.
    """
    out = tmp_path / "bleed_band.png"
    card = CardGenerator().create_card(template_id="christmas-classic")
    ctx = CompileContext(geometry=PageGeometry.us_letter(bleed_in=0.125))
    PNGRenderer(dpi=72).render(compile_card(card, ctx), out)
    img = Image.open(out).convert("RGB")
    # Canvas is 630 x 810 (letter trim 612x792 + 9pt bleed each side).
    # The bottom-right bleed strip (x: 621..629, y: 801..809) sits past
    # the trim edge of the front panel. Sample inside that strip.
    r, g, b = img.getpixel((625, 805))
    assert r > 150 and r > g and r > b, (
        "Bottom-right bleed strip should be red (front panel's bg flood "
        f"extending past trim); got rgb=({r},{g},{b})."
    )


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


def test_png_upscales_small_photo_to_fill_rect(tmp_path: Path) -> None:
    """#65: ``thumbnail`` never enlarges, so a 100 px source in a 2" rect
    at 300 DPI stayed 100 px. The fit scale must go up as well as down."""
    from holiday_card.core.models import (
        Card,
        FoldType,
        ImageElement,
        Panel,
        PanelPosition,
    )

    src = tmp_path / "small.png"
    Image.new("RGB", (100, 100), (0, 0, 255)).save(src)
    card = Card(
        name="upscale", template_id="t", fold_type=FoldType.HALF_FOLD,
        panels=[Panel(
            position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5,
            background_color={"r": 1, "g": 1, "b": 1},
            image_elements=[ImageElement(
                source_path=str(src), x=1.0, y=1.0, width=2.0, height=2.0,
            )],
        )],
    )
    out = tmp_path / "upscale.png"
    PNGRenderer(dpi=300).render(compile_card(card), out)
    with Image.open(out) as img:
        rgb = img.convert("RGB")
        blue = Image.eval(rgb.split()[2], lambda v: 255 if v > 200 else 0)
        red = Image.eval(rgb.split()[0], lambda v: 255 if v < 60 else 0)
        from PIL import ImageChops

        bbox = ImageChops.multiply(blue, red).getbbox()
    assert bbox is not None
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    assert w >= 590 and h >= 590, f"photo covers only {w}x{h} px"


def test_png_downscales_large_photo_to_fit_rect(tmp_path: Path) -> None:
    from holiday_card.core.models import (
        Card,
        FoldType,
        ImageElement,
        Panel,
        PanelPosition,
    )

    src = tmp_path / "wide.png"
    Image.new("RGB", (800, 400), (0, 0, 255)).save(src)
    card = Card(
        name="down", template_id="t", fold_type=FoldType.HALF_FOLD,
        panels=[Panel(
            position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5,
            image_elements=[ImageElement(
                source_path=str(src), x=1.0, y=1.0, width=2.0, height=2.0,
            )],
        )],
    )
    out = tmp_path / "down.png"
    PNGRenderer(dpi=72).render(compile_card(card), out)
    with Image.open(out) as img:
        rgb = img.convert("RGB")
        mask = Image.eval(rgb.split()[0], lambda v: 255 if v < 60 else 0)
        bbox = mask.getbbox()
    assert bbox is not None
    # 2" = 144 px wide; aspect 2:1 → 72 px tall, centred.
    assert abs((bbox[2] - bbox[0]) - 144) <= 1
    assert abs((bbox[3] - bbox[1]) - 72) <= 1


# ---------------------------------------------------------------------------
# Letter imposition (#58): inside panels land on the correct pages
# ---------------------------------------------------------------------------


def _four_colour_card() -> object:
    """A 4-panel card whose panels have distinct background colours plus a
    black marker in inside_left's panel-local top-left corner."""
    from holiday_card.core.models import (
        Card,
        FoldType,
        Panel,
        PanelPosition,
        Rectangle,
        ShapeType,
    )

    marker = Rectangle(
        type=ShapeType.RECTANGLE, x=0.05, y=5.25, width=0.2, height=0.2, fill_color="#000000"
    )
    colours = {
        PanelPosition.FRONT: {"r": 1, "g": 0, "b": 0},
        PanelPosition.BACK: {"r": 0, "g": 1, "b": 0},
        PanelPosition.INSIDE_LEFT: {"r": 0, "g": 0, "b": 1},
        PanelPosition.INSIDE_RIGHT: {"r": 1, "g": 1, "b": 0},
    }
    panels = [
        Panel(
            position=position,
            width=4.25,
            height=5.5,
            background_color=colour,
            shape_elements=[marker] if position is PanelPosition.INSIDE_LEFT else [],
        )
        for position, colour in colours.items()
    ]
    return Card(
        name="imposition", template_id="imposition", fold_type=FoldType.QUARTER_FOLD,
        bleed=0.0, panels=panels,
    )


_NO_BLEED = CompileContext(geometry=PageGeometry.us_letter(bleed_in=0.0))


def _sample(img: Image.Image, x_in: float, y_in: float, dpi: int) -> tuple[int, int, int]:
    """Sample the pixel at sheet coords (inches, bottom-left origin)."""
    px = int(x_in * dpi)
    py = img.height - 1 - int(y_in * dpi)
    r, g, b = img.getpixel((px, py))  # type: ignore[misc]
    return r, g, b


def test_png_inside_panels_land_in_the_correct_quadrants(tmp_path: Path) -> None:
    """After a quarter fold, inside_left is the top-right quadrant of the
    sheet and inside_right the top-left (#58)."""
    dpi = 36
    out = tmp_path / "imposition.png"
    PNGRenderer(dpi=dpi).render(compile_card(_four_colour_card(), _NO_BLEED), out)  # type: ignore[arg-type]
    img = Image.open(out).convert("RGB")
    assert img.size == (int(8.5 * dpi), int(11 * dpi))

    assert _sample(img, 6.375, 2.75, dpi) == (255, 0, 0), "front should be bottom-right"
    assert _sample(img, 2.125, 2.75, dpi) == (0, 255, 0), "back should be bottom-left"
    assert _sample(img, 6.375, 8.25, dpi) == (0, 0, 255), "inside_left should be top-right"
    assert _sample(img, 2.125, 8.25, dpi) == (255, 255, 0), "inside_right should be top-left"


def test_png_inside_left_prints_rotated_180(tmp_path: Path) -> None:
    """A marker in inside_left's panel-local top-left corner lands near the
    sheet point (8.5 - eps, 5.5 + eps): the panel prints upside down."""
    dpi = 36
    out = tmp_path / "rotation.png"
    PNGRenderer(dpi=dpi).render(compile_card(_four_colour_card(), _NO_BLEED), out)  # type: ignore[arg-type]
    img = Image.open(out).convert("RGB")

    assert _sample(img, 8.5 - 0.15, 5.5 + 0.15, dpi) == (0, 0, 0)
    # Where the marker would sit without the rotation: still plain blue.
    assert _sample(img, 4.25 + 0.15, 11.0 - 0.15, dpi) == (0, 0, 255)


def test_png_fill_only_rect_covers_exactly_its_pixels(tmp_path: Path) -> None:
    """Pillow's rectangle end is inclusive: a 2 px wide rect drew 3 px (#74,
    visible once patterns became thousands of 1 pt grid lines)."""
    from holiday_card.core.render_ir import (
        RGBA,
        BeginPage,
        DrawShape,
        EndPage,
        RectGeom,
        SolidPaint,
    )

    rect = DrawShape(geometry=RectGeom(x=10, y=10, width=1, height=20),
                     fill=SolidPaint(color=RGBA(r=0, g=0, b=1)))
    out = tmp_path / "line.png"
    PNGRenderer(dpi=144).render([BeginPage(width=40, height=40), rect, EndPage()], out)
    with Image.open(out) as img:
        rgb = img.convert("RGB")
        row = [rgb.getpixel((x, 40)) for x in range(18, 24)]
        col = [rgb.getpixel((21, y)) for y in range(18, 64)]
    blue = (0, 0, 255)
    assert [p == blue for p in row] == [False, False, True, True, False, False]
    assert sum(p == blue for p in col) == 40
