"""Compiler transparency flattening for PDF/X targets (#71, D10).

``CompileContext(flatten_transparency=True)`` resolves every draw whose
effective alpha (``opacity × paint alpha × enclosing group opacity``) is
below 1 against a *known solid* backdrop, composited in sRGB, and emits it
opaque. Anything else raises ``UnsupportedFeatureError`` naming the
element. Card-level tests use shapes (the only model elements that carry
opacity); IR-level tests cover what only hand-built IR can express
(gradient-stop alpha, text alpha, group opacity).
"""

from __future__ import annotations

import pytest

from holiday_card.core.compiler import (
    CompileContext,
    UnsupportedFeatureError,
    compile_card,
    flatten_transparency,
)
from holiday_card.core.data_paths import data_path
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import (
    Card,
    Circle,
    Color,
    ColorStop,
    FoldType,
    ImageElement,
    LinearGradientFill,
    Panel,
    PanelPosition,
    Rectangle,
    Star,
)
from holiday_card.core.render_ir import (
    RGBA,
    BeginClip,
    BeginGroup,
    CircleGeom,
    DrawImage,
    DrawShape,
    DrawText,
    EndClip,
    EndGroup,
    GradientStop,
    LinearGradientPaint,
    PatternPaint,
    Point,
    RectGeom,
    SolidPaint,
    Stroke,
    TextRun,
    Transform,
)

_FLAT = CompileContext(impose=False, emit_fold_lines=False, flatten_transparency=True)
_LIVE = CompileContext(impose=False, emit_fold_lines=False)

WHITE = RGBA(r=1, g=1, b=1)
RED = RGBA(r=1, g=0, b=0)


def _card(*shapes: object, background: Color | None = Color(r=1, g=1, b=1),
          images: list[ImageElement] | None = None) -> Card:
    panel = Panel(
        position=PanelPosition.FRONT, x=0, y=0, width=4, height=5,
        background_color=background,
        shape_elements=list(shapes),
        image_elements=images or [],
    )
    return Card(name="flatten", template_id="flatten-fixture",
                fold_type=FoldType.QUARTER_FOLD, panels=[panel])


def _shapes(commands: list[object]) -> list[DrawShape]:
    return [c for c in commands if isinstance(c, DrawShape)]


def _approx(color: RGBA, r: float, g: float, b: float) -> bool:
    return (color.a == 1.0 and abs(color.r - r) < 1e-9 and abs(color.g - g) < 1e-9
            and abs(color.b - b) < 1e-9)


def _veil(**kwargs: object) -> Rectangle:
    base: dict[str, object] = {
        "id": "veil", "x": 1, "y": 1, "width": 1, "height": 1,
        "fill_color": "#FF0000", "opacity": 0.5,
    }
    base.update(kwargs)
    return Rectangle(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Card-level: shapes over solid backdrops
# ---------------------------------------------------------------------------


class TestSolidBackdrop:
    def test_half_red_rect_over_white_background_becomes_opaque_pink(self) -> None:
        veil = _shapes(compile_card(_card(_veil()), _FLAT))[-1]
        assert veil.opacity == 1.0
        assert isinstance(veil.fill, SolidPaint)
        assert _approx(veil.fill.color, 1.0, 0.5, 0.5)

    def test_backdrop_is_topmost_containing_solid_shape(self) -> None:
        green = Rectangle(x=0.5, y=0.5, width=3, height=3, fill_color="#00FF00")
        veil = _shapes(compile_card(_card(green, _veil(z_index=1)), _FLAT))[-1]
        assert isinstance(veil.fill, SolidPaint)
        assert _approx(veil.fill.color, 0.5, 0.5, 0.0)

    def test_circle_backdrop_containing_the_bbox_is_solid(self) -> None:
        disc = Circle(center_x=1.5, center_y=1.5, radius=1.0, fill_color="#0000FF")
        veil = _shapes(compile_card(_card(disc, _veil(z_index=1)), _FLAT))[-1]
        assert isinstance(veil.fill, SolidPaint)
        assert _approx(veil.fill.color, 0.5, 0.0, 0.5)

    def test_panel_without_background_composites_over_paper_white(self) -> None:
        veil = _shapes(compile_card(_card(_veil(), background=None), _FLAT))[-1]
        assert isinstance(veil.fill, SolidPaint)
        assert _approx(veil.fill.color, 1.0, 0.5, 0.5)

    def test_stroke_colour_is_preblended_too(self) -> None:
        veil = _shapes(compile_card(
            _card(_veil(stroke_color="#0000FF", stroke_width=2.0)), _FLAT))[-1]
        assert veil.stroke is not None
        assert _approx(veil.stroke.color, 0.5, 0.5, 1.0)

    def test_opaque_shapes_are_emitted_unchanged(self) -> None:
        card = _card(_veil(opacity=1.0))
        assert compile_card(card, _FLAT) == compile_card(card, _LIVE)

    def test_live_alpha_is_kept_when_not_flattening(self) -> None:
        veil = _shapes(compile_card(_card(_veil()), _LIVE))[-1]
        assert veil.opacity == 0.5
        assert isinstance(veil.fill, SolidPaint)
        assert veil.fill.color == RED

    def test_translucent_shape_becomes_a_backdrop_once_flattened(self) -> None:
        # The flattened veil is opaque pink; a second veil inside it blends with pink.
        inner = _veil(id="inner", x=1.25, y=1.25, width=0.5, height=0.5,
                      fill_color="#FFFFFF", z_index=1)
        draws = _shapes(compile_card(_card(_veil(), inner), _FLAT))
        assert isinstance(draws[-1].fill, SolidPaint)
        assert _approx(draws[-1].fill.color, 1.0, 0.75, 0.75)


class TestRefusals:
    def test_over_a_gradient_raises_naming_the_element(self) -> None:
        sky = Rectangle(x=0, y=0, width=4, height=5, fill=LinearGradientFill(
            angle=90, stops=[ColorStop(position=0, color="#000000"),
                             ColorStop(position=1, color="#FFFFFF")]))
        with pytest.raises(UnsupportedFeatureError) as err:
            compile_card(_card(sky, _veil(z_index=1)), _FLAT)
        message = str(err.value)
        assert "flatten-fixture" in message
        assert "front" in message
        assert "veil" in message
        assert "gradient" in message

    def test_partial_overlap_of_a_solid_shape_raises(self) -> None:
        half = Rectangle(id="half", x=0, y=0, width=1.5, height=5, fill_color="#00FF00")
        with pytest.raises(UnsupportedFeatureError, match="veil"):
            compile_card(_card(half, _veil(z_index=1)), _FLAT)

    def test_bbox_corner_outside_a_circle_backdrop_raises(self) -> None:
        disc = Circle(center_x=1.5, center_y=1.5, radius=0.6, fill_color="#0000FF")
        with pytest.raises(UnsupportedFeatureError, match="veil"):
            compile_card(_card(disc, _veil(z_index=1)), _FLAT)

    def test_over_a_polygon_raises(self) -> None:
        star = Star(center_x=1.5, center_y=1.5, outer_radius=1.5, inner_radius=1.0,
                    fill_color="#0000FF")
        with pytest.raises(UnsupportedFeatureError, match="veil"):
            compile_card(_card(star, _veil(z_index=1)), _FLAT)

    def test_translucent_star_over_a_gradient_raises(self) -> None:
        sky = Rectangle(x=0, y=0, width=4, height=5, fill=LinearGradientFill(
            angle=0, stops=[ColorStop(position=0, color="#000033"),
                            ColorStop(position=1, color="#333366")]))
        star = Star(id="twinkle", center_x=2, center_y=2, outer_radius=0.3,
                    inner_radius=0.15, fill_color="#FFFFFF", opacity=0.6, z_index=1)
        with pytest.raises(UnsupportedFeatureError, match="twinkle"):
            compile_card(_card(sky, star), _FLAT)

    def test_translucent_shape_over_an_image_raises(self) -> None:
        photo = ImageElement(
            id="photo", source_path=str(_placeholder()), x=0.5, y=0.5, width=3, height=3,
            z_index=0,
        )
        with pytest.raises(UnsupportedFeatureError, match="image"):
            compile_card(_card(_veil(z_index=5), images=[photo]), _FLAT)


# ---------------------------------------------------------------------------
# IR-level: gradient stops, text, group opacity, patterns, strokes-only
# ---------------------------------------------------------------------------


def _white_page() -> DrawShape:
    return DrawShape(geometry=RectGeom(x=0, y=0, width=300, height=300),
                     fill=SolidPaint(color=WHITE))


class TestIRFlattening:
    def test_gradient_stops_with_alpha_are_preblended(self) -> None:
        grad = DrawShape(
            geometry=RectGeom(x=10, y=10, width=50, height=50),
            fill=LinearGradientPaint(
                start=Point(x=10, y=10), end=Point(x=60, y=10),
                stops=(GradientStop(position=0, color=RGBA(r=0, g=0, b=0, a=0.5)),
                       GradientStop(position=1, color=RGBA(r=0, g=0, b=1, a=1.0))),
            ),
            opacity=0.5,
        )
        out = flatten_transparency([_white_page(), grad], where="t/front/grad")
        paint = out[-1].fill  # type: ignore[union-attr]
        assert isinstance(paint, LinearGradientPaint)
        assert out[-1].opacity == 1.0  # type: ignore[union-attr]
        assert _approx(paint.stops[0].color, 0.75, 0.75, 0.75)
        assert _approx(paint.stops[1].color, 0.5, 0.5, 1.0)

    def test_pattern_colours_are_preblended(self) -> None:
        pattern = DrawShape(
            geometry=RectGeom(x=10, y=10, width=50, height=50),
            fill=PatternPaint(pattern="dots", colors=(RED, RGBA(r=0, g=0, b=0)),
                              spacing=10),
            opacity=0.5,
        )
        out = flatten_transparency([_white_page(), pattern], where="t/front/p")
        paint = out[-1].fill  # type: ignore[union-attr]
        assert isinstance(paint, PatternPaint)
        assert _approx(paint.colors[0], 1.0, 0.5, 0.5)
        assert _approx(paint.colors[1], 0.5, 0.5, 0.5)

    def test_text_opacity_and_colour_alpha_are_preblended(self) -> None:
        text = DrawText(
            run=TextRun(text="Hi", origin=Point(x=50, y=50), font_id="Helvetica",
                        size_pt=12, color=RGBA(r=0, g=0, b=0, a=0.5)),
            opacity=0.5,
        )
        out = flatten_transparency([_white_page(), text], where="t/front/msg")
        flat = out[-1]
        assert isinstance(flat, DrawText)
        assert flat.opacity == 1.0
        assert _approx(flat.run.color, 0.75, 0.75, 0.75)

    def test_nested_group_opacity_is_multiplied_into_the_children(self) -> None:
        cmds = [
            _white_page(),
            BeginGroup(opacity=0.5),
            BeginGroup(opacity=0.5),
            DrawShape(geometry=RectGeom(x=10, y=10, width=20, height=20),
                      fill=SolidPaint(color=RGBA(r=0, g=0, b=0))),
            EndGroup(),
            EndGroup(),
        ]
        out = flatten_transparency(cmds, where="t/front/g")
        assert [c.opacity for c in out if isinstance(c, BeginGroup)] == [1.0, 1.0]
        shape = _shapes(out)[-1]
        assert isinstance(shape.fill, SolidPaint)
        assert _approx(shape.fill.color, 0.75, 0.75, 0.75)

    def test_group_opacity_over_overlapping_children_raises(self) -> None:
        cmds = [
            _white_page(),
            BeginGroup(opacity=0.5),
            DrawShape(geometry=RectGeom(x=10, y=10, width=40, height=40),
                      fill=SolidPaint(color=RED)),
            DrawShape(geometry=RectGeom(x=20, y=20, width=10, height=10),
                      fill=SolidPaint(color=RGBA(r=0, g=0, b=1))),
            EndGroup(),
        ]
        with pytest.raises(UnsupportedFeatureError, match="group opacity"):
            flatten_transparency(cmds, where="t/front/g")

    def test_rotated_element_bbox_is_found_in_the_panel_frame(self) -> None:
        # A 20×2 bar rotated 90° about (100, 100) spans y 90..110, so it
        # overlaps the half-panel green rect only after rotation.
        green = DrawShape(geometry=RectGeom(x=0, y=0, width=300, height=95),
                          fill=SolidPaint(color=RGBA(r=0, g=1, b=0)))
        cmds = [
            _white_page(), green,
            BeginGroup(transform=Transform(translate_x=100, translate_y=100, rotate_deg=90)),
            DrawShape(geometry=RectGeom(x=90, y=99, width=20, height=2),
                      fill=SolidPaint(color=RED), opacity=0.5),
            EndGroup(),
        ]
        with pytest.raises(UnsupportedFeatureError):
            flatten_transparency(cmds, where="t/front/bar")

    def test_clip_limits_the_region_that_needs_a_backdrop(self) -> None:
        # Only the clipped part (inside the green square) is painted.
        green = DrawShape(geometry=RectGeom(x=0, y=0, width=50, height=50),
                          fill=SolidPaint(color=RGBA(r=0, g=1, b=0)))
        cmds = [
            _white_page(), green,
            BeginClip(geometry=RectGeom(x=10, y=10, width=20, height=20)),
            DrawShape(geometry=RectGeom(x=0, y=0, width=200, height=200),
                      fill=SolidPaint(color=RED), opacity=0.5),
            EndClip(),
        ]
        out = flatten_transparency(cmds, where="t/front/clipped")
        shape = _shapes(out)[-1]
        assert isinstance(shape.fill, SolidPaint)
        assert _approx(shape.fill.color, 0.5, 0.5, 0.0)

    def test_stroke_only_border_is_not_a_backdrop_for_interior_elements(self) -> None:
        border = DrawShape(geometry=RectGeom(x=0, y=0, width=300, height=300),
                           stroke=Stroke(color=RED, width=4))
        veil = DrawShape(geometry=RectGeom(x=100, y=100, width=10, height=10),
                         fill=SolidPaint(color=RGBA(r=0, g=0, b=0)), opacity=0.5)
        out = flatten_transparency([_white_page(), border, veil], where="t/front/v")
        shape = _shapes(out)[-1]
        assert isinstance(shape.fill, SolidPaint)
        assert _approx(shape.fill.color, 0.5, 0.5, 0.5)

    def test_translucent_image_records_its_solid_backdrop(self) -> None:
        image = DrawImage(image=_image_ref(), opacity=0.5)
        out = flatten_transparency([_white_page(), image], where="t/front/photo")
        flat = out[-1]
        assert isinstance(flat, DrawImage)
        assert flat.image.backdrop == WHITE

    def test_translucent_image_over_a_gradient_raises(self) -> None:
        grad = DrawShape(
            geometry=RectGeom(x=0, y=0, width=300, height=300),
            fill=LinearGradientPaint(start=Point(x=0, y=0), end=Point(x=300, y=0),
                                     stops=(GradientStop(position=0, color=WHITE),
                                            GradientStop(position=1, color=RED))),
        )
        with pytest.raises(UnsupportedFeatureError, match="photo"):
            flatten_transparency([grad, DrawImage(image=_image_ref(), opacity=0.5)],
                                 where="t/front/photo")

    def test_opaque_image_over_a_gradient_passes_without_backdrop(self) -> None:
        grad = DrawShape(
            geometry=RectGeom(x=0, y=0, width=300, height=300),
            fill=LinearGradientPaint(start=Point(x=0, y=0), end=Point(x=300, y=0),
                                     stops=(GradientStop(position=0, color=WHITE),
                                            GradientStop(position=1, color=RED))),
        )
        out = flatten_transparency([grad, DrawImage(image=_image_ref())], where="t/f/p")
        assert isinstance(out[-1], DrawImage)
        assert out[-1].image.backdrop is None

    def test_circle_geometry_backdrop(self) -> None:
        disc = DrawShape(geometry=CircleGeom(center=Point(x=100, y=100), radius=50),
                         fill=SolidPaint(color=RGBA(r=0, g=0, b=1)))
        veil = DrawShape(geometry=RectGeom(x=90, y=90, width=20, height=20),
                         fill=SolidPaint(color=RED), opacity=0.5)
        out = flatten_transparency([_white_page(), disc, veil], where="t/f/v")
        shape = _shapes(out)[-1]
        assert isinstance(shape.fill, SolidPaint)
        assert _approx(shape.fill.color, 0.5, 0.0, 0.5)


# ---------------------------------------------------------------------------
# Shipped templates
# ---------------------------------------------------------------------------


def test_flattening_a_template_without_translucency_is_a_no_op() -> None:
    card = CardGenerator().create_card("christmas-classic")
    assert compile_card(card, CompileContext(flatten_transparency=True)) == compile_card(card)


def _placeholder() -> object:
    return data_path("templates") / "christmas" / "placeholder-photo.jpg"


def _image_ref() -> object:
    from holiday_card.core.render_ir import ImageRef

    return ImageRef(source=str(_placeholder()), rect=RectGeom(x=50, y=50, width=100, height=100),
                    format="jpeg", width_px=1200, height_px=1200)
