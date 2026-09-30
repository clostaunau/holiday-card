"""A photo slot's clip is filled edge to edge, not cut flat (#98).

mothers-day-photo clips its slot with a 2.0×3.1" ellipse inside a 2.6×3.4"
rect. Under contain, a square photo covered only the middle 2.6×2.6", so
the ellipse was flat at the top and bottom. The slot is cover-fit now:
pixels inside the ellipse but outside the old contain box are the photo on
every raster backend.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.compiler import CompileContext, compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.imposition import panel_placements
from holiday_card.core.models import PanelPosition
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from rasterize import rasterize_pdf

DPI = 72
PAGE_H_IN = 11.0
PHOTO_RGB = (20, 180, 40)

# Panel-relative inches on the front panel. The
# ellipse spans y 1.70..4.80 at x = 2.125; the contain box spanned 1.95..4.55.
INSIDE_ELLIPSE_OUTSIDE_CONTAIN = [(2.125, 4.70), (2.125, 1.80)]


def _render_commands(photo: Path) -> tuple[list, tuple[float, float]]:
    """The sheet's IR and the front panel's origin on it, in inches."""
    card = CardGenerator().create_card(template_id="mothers-day-photo", photos=[photo])
    front = panel_placements(card)[PanelPosition.FRONT]
    assert front.rotation_deg == 0
    commands = compile_card(card, CompileContext(emit_fold_lines=False))
    return commands, (front.x_pt / 72, front.y_pt / 72)


def _pixel(img: Image.Image, x_in: float, y_in: float) -> tuple[int, int, int]:
    px = img.convert("RGB").getpixel(
        (round(x_in * DPI), round((PAGE_H_IN - y_in) * DPI))
    )
    return px  # type: ignore[return-value]


def _is_photo(rgb: tuple[int, int, int]) -> bool:
    return all(abs(a - b) <= 12 for a, b in zip(rgb, PHOTO_RGB, strict=True))


@pytest.fixture
def green_photo(tmp_path: Path) -> Path:
    path = tmp_path / "green.jpg"
    Image.new("RGB", (1200, 1200), PHOTO_RGB).save(path, quality=95)
    return path


@pytest.mark.parametrize("backend", ["png", "pdf"])
def test_ellipse_is_filled_top_and_bottom(
    backend: str, green_photo: Path, tmp_path: Path
) -> None:
    commands, (ox, oy) = _render_commands(green_photo)
    if backend == "png":
        out = tmp_path / "card.png"
        PNGRenderer(dpi=DPI).render(commands, out)
        img = Image.open(out)
    else:
        out = tmp_path / "card.pdf"
        IRReportLabRenderer().render(commands, out)
        img = rasterize_pdf(out, DPI)
    for x_in, y_in in INSIDE_ELLIPSE_OUTSIDE_CONTAIN:
        rgb = _pixel(img, ox + x_in, oy + y_in)
        assert _is_photo(rgb), f"{backend}: ({x_in}, {y_in})\" is {rgb}, not the photo"
