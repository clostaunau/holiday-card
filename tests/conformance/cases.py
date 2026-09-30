"""One-feature IR fixtures for the cross-backend conformance suite (#67, D12).

Each ``Case`` is a 144×144 pt page with ``bleed=0`` (except
``page_bleed_background``, which exercises bleed itself) that exercises
exactly one feature. Cases are built from ``core/render_ir.py`` types
directly, never via templates, so a failure points at one backend feature.
The pattern cases are the exception: patterns exist only as a compiler
lowering (#74, D13), so they come from ``_lower_pattern_fill``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from holiday_card.core.compiler import _lower_pattern_fill
from holiday_card.core.models import PatternFill, PatternType
from holiday_card.core.render_ir import (
    RGBA,
    BeginClip,
    BeginGroup,
    BeginPage,
    CircleGeom,
    DrawFoldLine,
    DrawImage,
    DrawShape,
    DrawText,
    EllipseGeom,
    EndClip,
    EndGroup,
    EndPage,
    GradientStop,
    ImageRef,
    LinearGradientPaint,
    PathGeom,
    PathOp,
    Point,
    PolygonGeom,
    PolylineGeom,
    RadialGradientPaint,
    RectGeom,
    RenderCommand,
    SolidPaint,
    Stroke,
    TextRun,
    Transform,
)

PAGE_PT = 144.0

PHOTO = Path(__file__).resolve().parent.parent / "fixtures" / "sample_photo.jpg"

RED = RGBA(r=1, g=0, b=0)
BLUE = RGBA(r=0, g=0, b=1)
GREEN = RGBA(r=0, g=0.6, b=0)
BLACK = RGBA(r=0, g=0, b=0)
GOLD = RGBA(r=0.9, g=0.7, b=0.1)


@dataclass(frozen=True)
class Case:
    """One conformance fixture: a single page exercising a single feature."""

    id: str
    commands: tuple[RenderCommand, ...]
    page_pt: float = PAGE_PT

    @property
    def is_text(self) -> bool:
        """Text cases compare ink bounding boxes, not pixel ratios."""
        return self.id.startswith("text_")


def _p(x: float, y: float) -> Point:
    return Point(x=x, y=y)


def _case(case_id: str, *body: RenderCommand, bleed: float = 0.0) -> Case:
    return Case(
        id=case_id,
        commands=(BeginPage(width=PAGE_PT, height=PAGE_PT, bleed=bleed), *body, EndPage()),
    )


def _fill(geometry: RectGeom | CircleGeom | EllipseGeom | PolygonGeom | PathGeom,
          color: RGBA = RED, opacity: float = 1.0) -> DrawShape:
    return DrawShape(geometry=geometry, fill=SolidPaint(color=color), opacity=opacity)


def _stroke_line(dash: tuple[float, ...]) -> DrawShape:
    return DrawShape(
        geometry=PolylineGeom(points=(_p(12, 72), _p(132, 72))),
        stroke=Stroke(color=BLACK, width=4, dash=dash),
    )


PATTERN_KINDS = ("stripes", "dots", "grid", "checkerboard")
PATTERN_ROTATIONS = (0, 45, 90)


def _pattern(kind: str, rotation: float) -> tuple[RenderCommand, ...]:
    fill = PatternFill(
        pattern_type=PatternType(kind), colors=["#FF0000", "#0000FF"],
        spacing=16 / 72, rotation=rotation,
    )
    geom = RectGeom(x=24, y=36, width=96, height=72)
    return tuple(_lower_pattern_fill(fill, geom, (24, 36, 96, 72), None, 1.0))


# #72 / D14: a 20×20 pt red square at (40, 40)-(60, 60) inside one or more
# nested groups. Outermost transform first.
GROUP_SQUARE = RectGeom(x=40, y=40, width=20, height=20)
GROUP_TRANSFORM_FIXTURES: dict[str, tuple[Transform, ...]] = {
    "group_square_scale2_pivot": (
        Transform(pivot_x=50, pivot_y=50, scale_x=2, scale_y=2),
    ),
    "group_square_scale2_rotate30": (
        Transform(pivot_x=50, pivot_y=50, rotate_deg=30, scale_x=2, scale_y=2),
    ),
    "group_square_scale2_offset": (
        Transform(pivot_x=50, pivot_y=50, scale_x=2, scale_y=2, offset_x=15, offset_y=-5),
    ),
    "group_square_nested_scale_in_rotate": (
        Transform(pivot_x=72, pivot_y=72, rotate_deg=30),
        Transform(pivot_x=50, pivot_y=50, scale_x=2, scale_y=1.5),
    ),
}


def _group_square(*transforms: Transform) -> tuple[RenderCommand, ...]:
    opens = tuple(BeginGroup(transform=t) for t in transforms)
    closes = tuple(EndGroup() for _ in transforms)
    return (*opens, _fill(GROUP_SQUARE), *closes)


def _text(case_id: str, align: str, font_id: str = "Lato", *,
          color: RGBA = BLACK, opacity: float = 1.0) -> Case:
    x = {"left": 12.0, "center": 72.0, "right": 132.0}[align]
    return _case(
        case_id,
        DrawText(
            run=TextRun(
                text="Hello", origin=_p(x, 60), font_id=font_id, size_pt=32,
                color=color, align=align,  # type: ignore[arg-type]
            ),
            opacity=opacity,
        ),
    )


def _photo(opacity: float = 1.0) -> DrawImage:
    with Image.open(PHOTO) as im:
        w, h = im.size
    return DrawImage(
        image=ImageRef(
            source=str(PHOTO),
            rect=RectGeom(x=12, y=12, width=120, height=120),
            format="jpeg",
            width_px=w,
            height_px=h,
            preserve_aspect=False,
        ),
        opacity=opacity,
    )


def _star(cx: float, cy: float, outer: float, inner: float) -> PolygonGeom:
    pts = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        a = math.pi / 2 + i * math.pi / 5
        pts.append(_p(cx + r * math.cos(a), cy + r * math.sin(a)))
    return PolygonGeom(points=tuple(pts))


_CENTER_RECT = RectGeom(x=36, y=36, width=72, height=72)
_CIRCLE_CLIP = BeginClip(geometry=CircleGeom(center=_p(72, 72), radius=48))
_RIGHT_HALF_CLIP = BeginClip(geometry=RectGeom(x=72, y=0, width=72, height=144))
_FULL_PAGE = RectGeom(x=0, y=0, width=144, height=144)

CASES: tuple[Case, ...] = (
    _case("rect_fill", _fill(_CENTER_RECT)),
    _case("rect_rounded", _fill(RectGeom(x=24, y=24, width=96, height=96, corner_radius=18))),
    _case("circle_fill", _fill(CircleGeom(center=_p(72, 72), radius=48))),
    _case("ellipse_fill", _fill(EllipseGeom(center=_p(72, 72), rx=60, ry=30))),
    _case("polygon_star", _fill(_star(72, 72, 60, 24))),
    _case(
        "polyline_stroke",
        DrawShape(
            geometry=PolylineGeom(points=(_p(12, 24), _p(72, 120), _p(132, 24))),
            stroke=Stroke(color=BLUE, width=6),
        ),
    ),
    _case(
        "path_cubic",
        _fill(PathGeom(ops=(
            PathOp(op="move", points=(_p(12, 24),)),
            PathOp(op="cubic", points=(_p(40, 140), _p(104, 140), _p(132, 24))),
            PathOp(op="close"),
        ))),
    ),
    _case(
        "path_quadratic",
        _fill(PathGeom(ops=(
            PathOp(op="move", points=(_p(12, 24),)),
            PathOp(op="quadratic", points=(_p(72, 140), _p(132, 24))),
            PathOp(op="close"),
        ))),
    ),
    _case(
        "stroke_rect_6pt",
        DrawShape(geometry=_CENTER_RECT, stroke=Stroke(color=BLACK, width=6)),
    ),
    _case("stroke_dash_line_2", _stroke_line((8, 4))),
    _case("stroke_dash_line_1", _stroke_line((4,))),
    _case("stroke_dash_line_4", _stroke_line((6, 2, 1, 2))),
    _case(
        "linear_gradient",
        DrawShape(
            geometry=RectGeom(x=12, y=36, width=120, height=72),
            fill=LinearGradientPaint(
                start=_p(12, 72), end=_p(132, 72),
                stops=(GradientStop(position=0, color=RED),
                       GradientStop(position=1, color=BLUE)),
            ),
        ),
    ),
    _case(
        "radial_gradient",
        DrawShape(
            geometry=CircleGeom(center=_p(72, 72), radius=60),
            fill=RadialGradientPaint(
                center=_p(72, 72), radius=60,
                stops=(GradientStop(position=0, color=GOLD),
                       GradientStop(position=1, color=GREEN)),
            ),
        ),
    ),
    *(
        _case(f"pattern_{kind}_{rotation}", *_pattern(kind, rotation))
        for kind in PATTERN_KINDS
        for rotation in PATTERN_ROTATIONS
    ),
    _case("clip_circle_over_rect", _CIRCLE_CLIP, _fill(_FULL_PAGE), EndClip()),
    _case(
        "clip_nested",
        _CIRCLE_CLIP, _RIGHT_HALF_CLIP, _fill(_FULL_PAGE), EndClip(), EndClip(),
    ),
    _case(
        "group_rotate_pivot",
        BeginGroup(transform=Transform(pivot_x=72, pivot_y=72, rotate_deg=30)),
        _fill(RectGeom(x=24, y=48, width=96, height=48)),
        EndGroup(),
    ),
    _case(
        "group_scale_pivot",
        BeginGroup(transform=Transform(pivot_x=72, pivot_y=72, scale_x=0.5, scale_y=0.5)),
        _fill(_FULL_PAGE),
        EndGroup(),
    ),
    *(
        _case(case_id, *_group_square(*transforms))
        for case_id, transforms in GROUP_TRANSFORM_FIXTURES.items()
    ),
    _case(
        "group_opacity",
        BeginGroup(opacity=0.5),
        _fill(_CENTER_RECT),
        EndGroup(),
    ),
    _case(
        "shape_opacity_times_color_alpha",
        _fill(_FULL_PAGE),
        _fill(_CENTER_RECT, color=RGBA(r=0, g=0, b=1, a=0.5), opacity=0.5),
    ),
    _case(
        "alpha_no_leak",
        _fill(RectGeom(x=12, y=36, width=56, height=72), color=RGBA(r=0, g=0, b=1, a=0.3)),
        _fill(RectGeom(x=76, y=36, width=56, height=72), color=BLUE),
    ),
    _text("text_lato_left", "left"),
    _text("text_lato_center", "center"),
    _text("text_lato_right", "right"),
    _text("text_curated_family", "center", font_id="Cormorant"),
    _text("text_opacity", "center", opacity=0.5),
    _case("image_jpeg", _photo()),
    _case("image_clipped_circle", _CIRCLE_CLIP, _photo(), EndClip()),
    _case("image_opacity", _fill(_FULL_PAGE), _photo(opacity=0.5)),
    _case("fold_line_dashed", DrawFoldLine(start=_p(72, 0), end=_p(72, 144), style="dashed")),
    _case(
        "page_bleed_background",
        _fill(RectGeom(x=-9, y=-9, width=162, height=162), color=GREEN),
        _fill(_CENTER_RECT),
        bleed=9,
    ),
)

CASES_BY_ID: dict[str, Case] = {c.id: c for c in CASES}
