"""Group transforms: scale about the pivot, rotate, offset, nesting (#72, D14).

The fixtures live in ``cases.GROUP_TRANSFORM_FIXTURES`` and are rendered by
every backend against the SVG oracle in ``test_conformance.py``. This module
checks the oracle itself: each grouped square must rasterize like a plain
polygon whose corners were moved by the ``Transform`` docstring formula,
applied step by step here (not through ``Transform.to_matrix``).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import pytest
from capabilities import CAPABILITIES
from cases import CASES_BY_ID, GROUP_SQUARE, GROUP_TRANSFORM_FIXTURES, PAGE_PT, RED
from PIL import Image

from holiday_card.core.render_ir import (
    BeginPage,
    DrawShape,
    EndPage,
    Point,
    PolygonGeom,
    SolidPaint,
    Transform,
)
from holiday_card.renderers.svg_backend import SVGRenderer

DPI = 144


def _step_by_step(t: Transform, x: float, y: float) -> tuple[float, float]:
    """p' = T(offset) · T(pivot) · R(rotate, CCW) · S(scale) · T(-pivot) · p."""
    x, y = x - t.pivot_x, y - t.pivot_y
    x, y = x * t.scale_x, y * t.scale_y
    rad = math.radians(t.rotate_deg)
    x, y = x * math.cos(rad) - y * math.sin(rad), x * math.sin(rad) + y * math.cos(rad)
    return x + t.pivot_x + t.offset_x, y + t.pivot_y + t.offset_y


def _expected_polygon(transforms: tuple[Transform, ...]) -> PolygonGeom:
    r = GROUP_SQUARE
    corners = [(r.x, r.y), (r.x + r.width, r.y),
               (r.x + r.width, r.y + r.height), (r.x, r.y + r.height)]
    points = []
    for x, y in corners:
        # Innermost group applies first.
        for t in reversed(transforms):
            x, y = _step_by_step(t, x, y)
        points.append(Point(x=x, y=y))
    return PolygonGeom(points=tuple(points))


@pytest.mark.parametrize("case_id", list(GROUP_TRANSFORM_FIXTURES))
def test_svg_oracle_follows_the_transform_formula(
    case_id: str,
    tmp_path: Path,
    rasterize_svg: Callable[[Path, int], Image.Image],
    raster_matches: Callable[[Image.Image, Image.Image, float], tuple[bool, str]],
    tolerance: dict[str, float],
) -> None:
    grouped = tmp_path / "grouped.svg"
    SVGRenderer().render(list(CASES_BY_ID[case_id].commands), grouped)

    flat = tmp_path / "flat.svg"
    SVGRenderer().render(
        [
            BeginPage(width=PAGE_PT, height=PAGE_PT, bleed=0),
            DrawShape(
                geometry=_expected_polygon(GROUP_TRANSFORM_FIXTURES[case_id]),
                fill=SolidPaint(color=RED),
            ),
            EndPage(),
        ],
        flat,
    )
    matched, detail = raster_matches(
        rasterize_svg(flat, DPI), rasterize_svg(grouped, DPI), tolerance["pdf"]
    )
    assert matched, f"{case_id}: SVG group transform disagrees with the formula: {detail}"


@pytest.mark.parametrize("case_id", [*GROUP_TRANSFORM_FIXTURES, "group_scale_pivot"])
def test_group_scale_is_supported_by_every_backend(case_id: str) -> None:
    assert {b: cap.status for b, cap in CAPABILITIES[case_id].items()} == {
        "pdf": "match", "png": "match",
    }
