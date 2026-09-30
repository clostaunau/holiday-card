"""Vectorized PNG gradients (#77): same colours as the per-pixel reference, fast.

The reference is the per-pixel computation the backend used before #77:
project the pixel centre onto the gradient (linear) or measure its distance
from the centre (radial), clamp ``t`` to [0, 1] and interpolate the stops
with ``_interp_stops``. The vectorized fill quantizes ``t`` to 8 bits, so
each channel may differ by at most 1.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.render_ir import (
    RGBA,
    BeginPage,
    DrawShape,
    EndPage,
    GradientStop,
    LinearGradientPaint,
    Point,
    RadialGradientPaint,
    RectGeom,
)
from holiday_card.renderers.png_backend import PNGRenderer, _interp_stops

# 72 DPI: one pixel per point; y grows downward in the image.
SIZE = 400
STOPS = (
    GradientStop(position=0.0, color=RGBA(r=1.0, g=0.0, b=0.2)),
    GradientStop(position=0.35, color=RGBA(r=0.1, g=0.8, b=0.3)),
    GradientStop(position=1.0, color=RGBA(r=0.0, g=0.1, b=1.0)),
)
SAMPLES = ((5, 7), (60, 333), (200, 200), (321, 45), (390, 388))


def _render(paint: object, tmp_path: Path, size: int = SIZE) -> Image.Image:
    shape = DrawShape(geometry=RectGeom(x=0, y=0, width=size, height=size), fill=paint)
    out = tmp_path / "g.png"
    PNGRenderer(dpi=72).render([BeginPage(width=size, height=size), shape, EndPage()], out)
    with Image.open(out) as img:
        return img.convert("RGB")


def _expected(t: float) -> tuple[int, int, int]:
    r, g, b, _ = _interp_stops([(s.position, s.color) for s in STOPS], max(0.0, min(1.0, t)))
    return (r, g, b)


def _assert_close(actual: tuple[int, ...], expected: tuple[int, ...], where: object) -> None:
    assert all(abs(a - e) <= 1 for a, e in zip(actual, expected, strict=True)), (
        where, actual, expected,
    )


def test_linear_gradient_matches_the_per_pixel_reference(tmp_path: Path) -> None:
    # IR start (40, 360) → pixel (40, 40); end (350, 80) → pixel (350, 320).
    paint = LinearGradientPaint(start=Point(x=40, y=360), end=Point(x=350, y=80), stops=STOPS)
    img = _render(paint, tmp_path)
    sx, sy, ex, ey = 40.0, 40.0, 350.0, 320.0
    dx, dy = ex - sx, ey - sy
    for x, y in SAMPLES:
        t = ((x + 0.5 - sx) * dx + (y + 0.5 - sy) * dy) / (dx * dx + dy * dy)
        _assert_close(img.getpixel((x, y)), _expected(t), (x, y))


def test_radial_gradient_matches_the_per_pixel_reference(tmp_path: Path) -> None:
    # IR centre (180, 230) → pixel (180, 170).
    paint = RadialGradientPaint(center=Point(x=180, y=230), radius=210, stops=STOPS)
    img = _render(paint, tmp_path)
    for x, y in SAMPLES:
        t = math.hypot(x + 0.5 - 180, y + 0.5 - 170) / 210
        _assert_close(img.getpixel((x, y)), _expected(t), (x, y))


@pytest.mark.parametrize("kind", ["linear", "radial"])
def test_a_million_pixel_gradient_fills_in_under_half_a_second(kind: str, tmp_path: Path) -> None:
    paint: object = (
        LinearGradientPaint(start=Point(x=0, y=0), end=Point(x=1000, y=1000), stops=STOPS)
        if kind == "linear"
        else RadialGradientPaint(center=Point(x=500, y=500), radius=600, stops=STOPS)
    )
    start = time.perf_counter()
    _render(paint, tmp_path, size=1000)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, f"{kind} 1000x1000 gradient took {elapsed:.2f}s"


def test_no_per_pixel_loops_remain() -> None:
    source = Path(__import__("holiday_card.renderers.png_backend").renderers.png_backend.__file__)
    assert "for y in range(h)" not in source.read_text()
