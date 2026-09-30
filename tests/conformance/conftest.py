"""Rasterizers and image metrics for the conformance suite (#67, D12).

The SVG backend is the oracle. PDF and SVG are rasterized with
host-independent, wheel-only libraries (``pypdfium2`` and ``resvg-py`` with
``skip_system_fonts=True``), so results do not depend on what the CI runner
has installed. resvg ignores ``@font-face``, so the SVG rasterizer loads the
font subsets embedded in the SVG itself (#76) and no other font: text in the
oracle is drawn only with what the file carries. The PNG backend rasterizes itself.
"""

from __future__ import annotations

import base64
import io
import re
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
import resvg_py
from capabilities import TOLERANCE
from PIL import Image, ImageChops

import rasterize
from holiday_card.core.render_ir import RenderCommand
from holiday_card.renderers.png_backend import PNGRenderer

# Every comparison runs at 144 DPI (2 px per point).
DPI = 144

# A pixel "mismatches" when any channel differs by more than this (0-255).
# 48 absorbs anti-aliasing and rasterizer rounding on edges; a real colour or
# geometry error moves channels by far more.
CHANNEL_DELTA = 48

# Maximum mismatched-pixel ratio per backend: ``capabilities.TOLERANCE``.

# A page-area ratio cannot see a thin feature: a 0.5 pt fold line is ~0.35%
# of the page, so it could change colour entirely and stay under 1%. Every
# comparison therefore also requires the mean colour of the non-white "ink"
# to agree within CHANNEL_DELTA per channel.

# Text is compared by ink bounding box (pixel ratios are too font-sensitive):
# each edge may move by at most this many pixels, and the mean ink colour may
# differ by at most CHANNEL_DELTA per channel.
BBOX_TOLERANCE_PX = 3

# Non-white threshold used to find "ink".
_INK_THRESHOLD = 16


# resvg falls back to its default families when a font-family matches nothing,
# and those defaults resolve differently per host (Linux picked a bundled
# serif, macOS drew nothing). Pointing every generic family at a name that is
# never installed makes an unmatched family draw nothing everywhere.
_NO_FALLBACK = "holiday-card-no-fallback-font"
_FAMILY_OPTIONS = (
    "font_family", "serif_family", "sans_serif_family",
    "cursive_family", "fantasy_family", "monospace_family",
)


_EMBEDDED_FONT = re.compile(rb"url\(data:font/ttf;base64,([A-Za-z0-9+/=]+)\)")


def _rasterize_svg(path: Path, dpi: int = DPI) -> Image.Image:
    with tempfile.TemporaryDirectory() as fonts_dir:
        font_files = []
        for i, data in enumerate(_EMBEDDED_FONT.findall(path.read_bytes())):
            font_file = Path(fonts_dir) / f"embedded-{i}.ttf"
            font_file.write_bytes(base64.b64decode(data))
            font_files.append(str(font_file))
        png = resvg_py.svg_to_bytes(
            svg_path=str(path),
            zoom=dpi / 72,
            background="#ffffff",
            skip_system_fonts=True,
            font_files=font_files,
            **dict.fromkeys(_FAMILY_OPTIONS, _NO_FALLBACK),
        )
    with Image.open(io.BytesIO(bytes(png))) as im:
        return rasterize.to_rgb_on_white(im)


def _rasterize_pdf(path: Path, dpi: int = DPI) -> Image.Image:
    return rasterize.rasterize_pdf(path, dpi)


def _mismatch_ratio(a: Image.Image, b: Image.Image, channel_delta: int = CHANNEL_DELTA) -> float:
    """Fraction of pixels whose max channel difference exceeds ``channel_delta``."""
    if a.size != b.size:
        raise AssertionError(f"image sizes differ: {a.size} vs {b.size}")
    r, g, bl = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).split()
    worst = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    bad = worst.point(lambda v: 255 if v > channel_delta else 0).histogram()[255]
    return bad / (a.size[0] * a.size[1])


def _ink_mask(img: Image.Image) -> Image.Image:
    white = Image.new("RGB", img.size, (255, 255, 255))
    r, g, b = ImageChops.difference(img.convert("RGB"), white).split()
    worst = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return worst.point(lambda v: 255 if v > _INK_THRESHOLD else 0)


def _ink_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Bounding box of non-white pixels, or ``None`` for a blank image."""
    return _ink_mask(img).getbbox()


def _ink_mean_color(img: Image.Image) -> tuple[float, float, float] | None:
    """Mean RGB of the non-white pixels, or ``None`` for a blank image."""
    mask = _ink_mask(img)
    count = mask.histogram()[255]
    if count == 0:
        return None
    rgb = img.convert("RGB")
    sums = [sum(i * n for i, n in enumerate(rgb.getchannel(c).histogram(mask))) for c in range(3)]
    return (sums[0] / count, sums[1] / count, sums[2] / count)


def _ink_color_delta(a: Image.Image, b: Image.Image) -> float:
    """Largest per-channel difference of the mean ink colours (255 if one is blank)."""
    col_a, col_b = _ink_mean_color(a), _ink_mean_color(b)
    if col_a is None or col_b is None:
        return 0.0 if col_a is col_b else 255.0
    return max(abs(p - q) for p, q in zip(col_a, col_b, strict=True))


def _raster_matches(a: Image.Image, b: Image.Image, tolerance: float) -> tuple[bool, str]:
    """Compare two non-text renderings by mismatch ratio and mean ink colour."""
    ratio = _mismatch_ratio(a, b)
    ink = _ink_color_delta(a, b)
    detail = f"mismatch ratio {ratio:.2%} (tolerance {tolerance:.1%}), ink colour delta {ink:.1f}"
    return ratio <= tolerance and ink <= CHANNEL_DELTA, detail


def _text_matches(a: Image.Image, b: Image.Image) -> tuple[bool, str]:
    """Compare two text renderings by ink bbox (±px per edge) and mean ink colour."""
    box_a, box_b = _ink_bbox(a), _ink_bbox(b)
    col_a, col_b = _ink_mean_color(a), _ink_mean_color(b)
    detail = f"bbox {box_a} vs {box_b}, ink colour {col_a} vs {col_b}"
    if box_a is None or box_b is None or col_a is None or col_b is None:
        return (box_a is None and box_b is None), detail
    bbox_ok = all(abs(p - q) <= BBOX_TOLERANCE_PX for p, q in zip(box_a, box_b, strict=True))
    colour_ok = all(abs(p - q) <= CHANNEL_DELTA for p, q in zip(col_a, col_b, strict=True))
    return bbox_ok and colour_ok, detail


@pytest.fixture(scope="session")
def rasterize_svg() -> Callable[[Path, int], Image.Image]:
    return _rasterize_svg


@pytest.fixture(scope="session")
def rasterize_pdf() -> Callable[[Path, int], Image.Image]:
    return _rasterize_pdf


@pytest.fixture(scope="session")
def render_png(tmp_path_factory: pytest.TempPathFactory) -> Callable[..., Image.Image]:
    out_dir = tmp_path_factory.mktemp("conformance-png")

    def _render(commands: Iterable[RenderCommand], dpi: int = DPI, name: str = "out") -> Image.Image:
        out = out_dir / f"{name}.png"
        PNGRenderer(dpi=dpi).render(list(commands), out)
        with Image.open(out) as im:
            return rasterize.to_rgb_on_white(im)

    return _render


@pytest.fixture(scope="session")
def mismatch_ratio() -> Callable[..., float]:
    """``mismatch_ratio(a, b, channel_delta=48) -> float``."""
    return _mismatch_ratio


@pytest.fixture(scope="session")
def raster_matches() -> Callable[[Image.Image, Image.Image, float], tuple[bool, str]]:
    return _raster_matches


@pytest.fixture(scope="session")
def text_matches() -> Callable[[Image.Image, Image.Image], tuple[bool, str]]:
    return _text_matches


@pytest.fixture(scope="session")
def tolerance() -> dict[str, float]:
    return TOLERANCE
