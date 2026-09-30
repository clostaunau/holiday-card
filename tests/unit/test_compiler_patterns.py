"""The compiler lowers pattern fills to a clip plus solid primitives (#74, D13).

``_lower_pattern_fill`` emits ``BeginClip(shape) → BeginGroup(rotation about
the bbox centre, shape opacity) → background → primitives → EndGroup →
EndClip → stroke``, so no backend tiles a pattern itself and there is no
pattern paint in the IR.
"""

from __future__ import annotations

import math

import pytest

from holiday_card.core.compiler import (
    CompileContext,
    UnsupportedFeatureError,
    _lower_pattern_fill,
    compile_card,
)
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import (
    Card,
    Circle,
    FoldType,
    Panel,
    PanelPosition,
    PatternFill,
    PatternType,
    Rectangle,
    SVGPath,
)
from holiday_card.core.render_ir import (
    RGBA,
    BeginClip,
    BeginGroup,
    CircleGeom,
    DrawShape,
    EndClip,
    EndGroup,
    PathGeom,
    RectGeom,
    RenderCommand,
    SolidPaint,
    Stroke,
    assert_balanced,
)

_CTX = CompileContext(impose=False, emit_fold_lines=False)
_BBOX = (100.0, 200.0, 100.0, 60.0)  # x, y, w, h in points
_GEOM = RectGeom(x=100, y=200, width=100, height=60)
_RED = "#FF0000"
_WHITE = "#FFFFFF"


def _fill(kind: str, *, spacing_in: float = 20 / 72, rotation: float = 0.0,
          colors: tuple[str, ...] = (_RED, _WHITE), scale: float = 1.0) -> PatternFill:
    return PatternFill(
        pattern_type=PatternType(kind), colors=list(colors),
        spacing=spacing_in, scale=scale, rotation=rotation,
    )


def _lower(fill: PatternFill, stroke: Stroke | None = None,
           opacity: float = 1.0) -> list[RenderCommand]:
    return _lower_pattern_fill(fill, _GEOM, _BBOX, stroke, opacity)


def _primitives(commands: list[RenderCommand]) -> list[DrawShape]:
    """Foreground primitives: every draw inside the group after the background."""
    start = next(i for i, c in enumerate(commands) if isinstance(c, BeginGroup))
    end = next(i for i, c in enumerate(commands) if isinstance(c, EndGroup))
    draws = [c for c in commands[start + 1:end] if isinstance(c, DrawShape)]
    return draws[1:]


def _colour(draw: DrawShape) -> RGBA:
    assert isinstance(draw.fill, SolidPaint)
    return draw.fill.color


class TestStructure:
    @pytest.mark.parametrize("kind", ["stripes", "dots", "grid", "checkerboard"])
    def test_clip_group_background_primitives_in_order(self, kind: str) -> None:
        out = _lower(_fill(kind))
        assert_balanced(out)
        assert isinstance(out[0], BeginClip) and out[0].geometry == _GEOM
        assert isinstance(out[1], BeginGroup)
        assert isinstance(out[-2], EndGroup) and isinstance(out[-1], EndClip)
        background = out[2]
        assert isinstance(background, DrawShape)
        assert _colour(background) == RGBA(r=1, g=0, b=0)
        assert background.geometry == _GEOM.model_copy()  # unrotated: the bbox
        prims = _primitives(out)
        assert prims, f"{kind} emitted no primitives"
        assert all(_colour(p) == RGBA(r=1, g=1, b=1) for p in prims)
        assert all(p.stroke is None and p.opacity == 1.0 for p in prims)

    def test_every_draw_is_a_solid_paint(self) -> None:
        out = _lower(_fill("dots"))
        assert all(isinstance(c.fill, SolidPaint) for c in out if isinstance(c, DrawShape))

    def test_stroke_is_drawn_after_the_clip(self) -> None:
        stroke = Stroke(color=RGBA(r=0, g=0, b=1), width=2)
        out = _lower(_fill("stripes"), stroke=stroke, opacity=0.5)
        last = out[-1]
        assert isinstance(out[-2], EndClip)
        assert isinstance(last, DrawShape)
        assert last.geometry == _GEOM and last.fill is None and last.stroke == stroke
        assert last.opacity == 0.5

    def test_opacity_goes_on_the_group_not_the_primitives(self) -> None:
        out = _lower(_fill("checkerboard"), opacity=0.4)
        group = out[1]
        assert isinstance(group, BeginGroup) and group.opacity == 0.4
        assert all(c.opacity == 1.0 for c in out if isinstance(c, DrawShape))

    def test_single_colour_pattern_is_the_background_alone(self) -> None:
        # colors[1] defaults to colors[0]: the primitives would be invisible.
        out = _lower(_fill("dots", colors=(_RED,)))
        assert [type(c) for c in out] == [BeginClip, BeginGroup, DrawShape, EndGroup, EndClip]


class TestGeometry:
    PERIOD = 20.0

    def test_stripes_are_bands_half_a_period_tall(self) -> None:
        prims = _primitives(_lower(_fill("stripes")))
        assert all(isinstance(p.geometry, RectGeom) for p in prims)
        heights = {round(p.geometry.height, 6) for p in prims}  # type: ignore[union-attr]
        assert heights == {self.PERIOD / 2}
        tops = sorted(p.geometry.y + p.geometry.height for p in prims)  # type: ignore[union-attr]
        # First band hangs from the bbox top; one band per period.
        assert tops[-1] == pytest.approx(260.0)
        assert [b - a for a, b in zip(tops, tops[1:], strict=False)] == pytest.approx(
            [self.PERIOD] * (len(tops) - 1)
        )
        assert len(prims) == 3  # 60 pt tall / 20 pt period

    def test_dots_have_radius_a_quarter_period_at_tile_centres(self) -> None:
        prims = _primitives(_lower(_fill("dots")))
        assert all(isinstance(p.geometry, CircleGeom) for p in prims)
        assert {p.geometry.radius for p in prims} == {self.PERIOD / 4}  # type: ignore[union-attr]
        centres = {(p.geometry.center.x, p.geometry.center.y) for p in prims}  # type: ignore[union-attr]
        assert (110.0, 250.0) in centres  # first tile: top-left corner + period/2
        assert len(prims) == 5 * 3

    def test_grid_has_one_vertical_and_one_horizontal_line_per_period(self) -> None:
        prims = _primitives(_lower(_fill("grid")))
        geoms = [p.geometry for p in prims]
        assert all(isinstance(g, RectGeom) for g in geoms)
        vertical = [g for g in geoms if g.width == 1.0 and g.height > 1.0]  # type: ignore[union-attr]
        horizontal = [g for g in geoms if g.height == 1.0 and g.width > 1.0]  # type: ignore[union-attr]
        assert len(vertical) == 100 / self.PERIOD
        assert len(horizontal) == 60 / self.PERIOD
        assert len(vertical) + len(horizontal) == len(geoms)
        xs = sorted(g.x for g in vertical)  # type: ignore[union-attr]
        assert xs == pytest.approx([100, 120, 140, 160, 180])

    def test_checkerboard_squares_are_half_a_period(self) -> None:
        prims = _primitives(_lower(_fill("checkerboard")))
        assert all(isinstance(p.geometry, RectGeom) for p in prims)
        sides = {(p.geometry.width, p.geometry.height) for p in prims}  # type: ignore[union-attr]
        assert sides == {(self.PERIOD / 2, self.PERIOD / 2)}
        assert len(prims) == 2 * 5 * 3

    def test_scale_multiplies_the_period(self) -> None:
        prims = _primitives(_lower(_fill("dots", spacing_in=10 / 72, scale=2.0)))
        assert {p.geometry.radius for p in prims} == {self.PERIOD / 4}  # type: ignore[union-attr]


class TestRotation:
    def test_unrotated_group_is_identity(self) -> None:
        group = _lower(_fill("stripes"))[1]
        assert isinstance(group, BeginGroup) and group.transform.is_identity()

    @pytest.mark.parametrize("angle", [45.0, 90.0])
    def test_rotation_pivots_on_the_bbox_centre(self, angle: float) -> None:
        group = _lower(_fill("stripes", rotation=angle))[1]
        assert isinstance(group, BeginGroup)
        t = group.transform
        assert (t.pivot_x, t.pivot_y, t.rotate_deg) == (150.0, 230.0, angle)
        assert (t.offset_x, t.offset_y, t.scale_x, t.scale_y) == (0, 0, 1, 1)

    @pytest.mark.parametrize("kind", ["stripes", "dots", "grid", "checkerboard"])
    def test_rotated_pattern_covers_the_circumscribed_square(self, kind: str) -> None:
        out = _lower(_fill(kind, rotation=45))
        half = math.hypot(100, 60) / 2
        background = out[2]
        assert isinstance(background, DrawShape) and isinstance(background.geometry, RectGeom)
        g = background.geometry
        assert (g.x, g.y) == pytest.approx((150 - half, 230 - half))
        assert (g.width, g.height) == pytest.approx((2 * half, 2 * half))
        boxes = [_box(p.geometry) for p in _primitives(out)]
        assert min(b[0] for b in boxes) <= 150 - half + 20
        assert min(b[1] for b in boxes) <= 230 - half + 20
        assert max(b[2] for b in boxes) >= 150 + half - 20
        assert max(b[3] for b in boxes) >= 230 + half - 20


def _box(geom: object) -> tuple[float, float, float, float]:
    if isinstance(geom, RectGeom):
        return (geom.x, geom.y, geom.x + geom.width, geom.y + geom.height)
    assert isinstance(geom, CircleGeom)
    c, r = geom.center, geom.radius
    return (c.x - r, c.y - r, c.x + r, c.y + r)


class TestFailLoud:
    def test_period_below_two_points_raises(self) -> None:
        with pytest.raises(UnsupportedFeatureError, match=r"1\.44 pt.*2 pt"):
            _lower(_fill("dots", spacing_in=0.02))

    def test_too_many_primitives_raises(self) -> None:
        geom = RectGeom(x=0, y=0, width=576, height=576)
        with pytest.raises(UnsupportedFeatureError, match=r"20000"):
            _lower_pattern_fill(
                _fill("checkerboard", spacing_in=0.03), geom, (0, 0, 576, 576), None, 1.0,
            )

    def test_error_names_the_shape(self) -> None:
        card = _card(Rectangle(
            id="ribbon", x=0.5, y=0.5, width=2, height=2, fill=_fill("dots", spacing_in=0.02),
        ))
        with pytest.raises(UnsupportedFeatureError, match="ribbon"):
            compile_card(card, _CTX)


def _card(*shapes: object) -> Card:
    panel = Panel(
        position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5,
        shape_elements=list(shapes),  # type: ignore[arg-type]
    )
    return Card(name="t", template_id="t", fold_type=FoldType.QUARTER_FOLD, panels=[panel])


class TestCompileCard:
    def test_rectangle_is_lowered(self) -> None:
        out = compile_card(_card(Rectangle(x=1, y=1, width=2, height=1, fill=_fill("grid"))), _CTX)
        assert_balanced(out)
        clips = [c for c in out if isinstance(c, BeginClip)]
        assert clips == [BeginClip(geometry=RectGeom(x=72, y=72, width=144, height=72))]

    def test_circle_clips_to_the_circle(self) -> None:
        out = compile_card(
            _card(Circle(center_x=2, center_y=2, radius=1, fill=_fill("stripes", rotation=45))),
            _CTX,
        )
        clip = next(c for c in out if isinstance(c, BeginClip))
        assert isinstance(clip.geometry, CircleGeom)
        group = out[out.index(clip) + 1]
        assert isinstance(group, BeginGroup)
        assert (group.transform.pivot_x, group.transform.pivot_y) == (144, 144)

    def test_svg_path_clips_to_the_path(self) -> None:
        path = SVGPath(path_data="M 0 0 L 1 0 L 1 1 Z", x=1, y=1, fill=_fill("dots"))
        out = compile_card(_card(path), _CTX)
        assert_balanced(out)
        clip = next(c for c in out if isinstance(c, BeginClip))
        assert isinstance(clip.geometry, PathGeom)
        assert not any(isinstance(c, DrawShape) and c.geometry == clip.geometry
                       and c.fill is not None for c in out)

    @pytest.mark.parametrize("template_id", [
        "christmas-festive-stripes", "christmas-holiday-masterpiece",
    ])
    def test_shipped_pattern_templates_emit_only_solid_paint(self, template_id: str) -> None:
        out = compile_card(CardGenerator().create_card(template_id=template_id))
        assert_balanced(out)
        fills = [c.fill for c in out if isinstance(c, DrawShape) and c.fill is not None]
        assert all(f.kind != "pattern" for f in fills)
        assert sum(isinstance(c, BeginClip) for c in out) >= 5
