"""Shape ``rotation`` is honoured for every shape type (#135).

``BaseShape.rotation`` loads for every shape, but only ``SVGPath`` read it;
rectangles, circles, triangles, stars and lines dropped it silently (D4).
Now each non-path shape's commands (a ``DrawShape``, or a pattern fill's
clip + group sequence) are wrapped in ``BeginGroup(Transform(pivot = bbox
centre, rotate_deg))`` / ``EndGroup``, the idiom SVG paths, images and text
already use.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.compiler import CompileContext, compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import (
    Card,
    Circle,
    FoldType,
    Line,
    Panel,
    PanelPosition,
    PatternFill,
    Rectangle,
    Star,
    Triangle,
)
from holiday_card.core.render_ir import (
    BeginClip,
    BeginGroup,
    DrawShape,
    EndGroup,
    Transform,
)
from holiday_card.core.template_checks import check_template
from holiday_card.core.templates import discover_templates, resolve_template
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from rasterize import rasterize_pdf

_NO_IMPOSE = CompileContext(impose=False, emit_fold_lines=False)

# Each shape with its bbox centre in panel inches.
_SHAPES: dict[str, tuple[dict[str, object], type, tuple[float, float]]] = {
    "rectangle": (
        {"x": 1.0, "y": 2.0, "width": 2.0, "height": 1.0, "fill_color": "#FF0000"},
        Rectangle, (2.0, 2.5),
    ),
    "circle": (
        {"center_x": 2.0, "center_y": 3.0, "radius": 0.5, "fill_color": "#FF0000"},
        Circle, (2.0, 3.0),
    ),
    "triangle": (
        {"x1": 1.0, "y1": 1.0, "x2": 3.0, "y2": 1.0, "x3": 2.0, "y3": 3.0,
         "fill_color": "#FF0000"},
        Triangle, (2.0, 2.0),
    ),
    "star": (
        {"center_x": 2.0, "center_y": 3.0, "outer_radius": 1.0, "inner_radius": 0.4,
         "points": 5, "fill_color": "#FF0000"},
        Star, (2.0, 3.0),
    ),
    "line": (
        {"start_x": 1.0, "start_y": 3.0, "end_x": 3.0, "end_y": 3.0,
         "stroke_color": "#000000", "stroke_width": 2.0},
        Line, (2.0, 3.0),
    ),
}


def _card(*shapes: object) -> Card:
    panel = Panel(
        position=PanelPosition.FRONT, width=4.25, height=5.5,
        shape_elements=list(shapes),
    )
    return Card(name="t", template_id="t", fold_type=FoldType.HALF_FOLD, panels=[panel])


def _shape_commands(shape: object) -> list:
    """The shape's commands: everything inside the panel group (no background)."""
    commands = compile_card(_card(shape), _NO_IMPOSE)
    panel_open = next(i for i, c in enumerate(commands) if isinstance(c, BeginGroup))
    panel_close = max(i for i, c in enumerate(commands) if isinstance(c, EndGroup))
    inner = commands[panel_open + 1:panel_close]
    assert inner and not any(
        isinstance(c, DrawShape) and c.geometry.kind == "rect" and c.geometry.width == 306.0
        for c in inner
    ), "unexpected panel background"
    return inner


@pytest.mark.parametrize("kind", sorted(_SHAPES))
def test_rotation_wraps_the_shape_in_a_pivot_rotate_group(kind: str) -> None:
    fields, cls, (cx, cy) = _SHAPES[kind]
    rotated = _shape_commands(cls(**fields, rotation=30.0))
    plain = _shape_commands(cls(**fields))
    assert isinstance(rotated[0], BeginGroup)
    assert rotated[0].transform == Transform(
        pivot_x=cx * 72, pivot_y=cy * 72, rotate_deg=30.0,
    )
    assert rotated[1:-1] == plain
    assert isinstance(rotated[-1], EndGroup)


@pytest.mark.parametrize("kind", sorted(_SHAPES))
def test_zero_rotation_emits_no_group(kind: str) -> None:
    fields, cls, _ = _SHAPES[kind]
    commands = _shape_commands(cls(**fields))
    assert not any(isinstance(c, BeginGroup) for c in commands)


def test_rotated_pattern_fill_is_rotated_as_a_whole() -> None:
    rect = Rectangle(
        x=1.0, y=2.0, width=2.0, height=1.0, rotation=15.0,
        fill=PatternFill(pattern_type="stripes", spacing=0.2, colors=["#FF0000", "#FFFFFF"]),
    )
    commands = _shape_commands(rect)
    assert isinstance(commands[0], BeginGroup)
    assert commands[0].transform.rotate_deg == 15.0
    assert isinstance(commands[1], BeginClip)
    assert isinstance(commands[-1], EndGroup)


_ROTATED_SHIPPED = {
    "birthday-balloons": [30.0, 60.0],
    "birthday-photo": [30.0, 60.0],
    "christmas-holiday-masterpiece": [15.0],
}


def test_every_rotated_shipped_shape_is_listed() -> None:
    found: dict[str, list[float]] = {}
    for entry in discover_templates():
        template, _ = resolve_template(entry["id"])
        for panel in template.panels:
            for shape in panel.shape_elements:
                if shape.rotation and shape.type.value != "svg_path":
                    found.setdefault(entry["id"], []).append(shape.rotation)
    assert found == _ROTATED_SHIPPED


@pytest.mark.parametrize("template_id", sorted(_ROTATED_SHIPPED))
def test_shipped_rotated_shapes_compile_to_rotation_groups(template_id: str) -> None:
    card = CardGenerator().create_card(template_id=template_id)
    angles = [
        c.transform.rotate_deg for c in compile_card(card)
        if isinstance(c, BeginGroup)
    ]
    for rotation in _ROTATED_SHIPPED[template_id]:
        assert rotation in angles, f"{template_id}: no {rotation}° group in {angles}"


def test_check_template_uses_the_rotated_box() -> None:
    template, _ = resolve_template("christmas-classic")
    front = next(p for p in template.panels if p.position == PanelPosition.FRONT)
    # Unrotated this bar sits inside the panel (y 0..0.2); turned 90° about
    # its centre (1, 0.1) it spans y -0.9..1.1 and leaves the panel.
    bar = Rectangle(x=0.0, y=0.0, width=2.0, height=0.2, rotation=90.0, fill_color="#000000")
    front.shape_elements = [*front.shape_elements, bar]
    problems = check_template(template)
    assert any("rectangle bbox" in p.message for p in problems), problems


# --- pixels ---------------------------------------------------------------

DPI = 72
PAGE_H_IN = 11.0
# A 2×0.2" bar centred at (2, 3) turned 90°: vertical, x 1.9..2.1, y 2..4.
_BAR = Rectangle(x=1.0, y=2.9, width=2.0, height=0.2, rotation=90.0, fill_color="#FF0000")
_INSIDE_ONLY_WHEN_ROTATED = (2.0, 3.8)
_INSIDE_ONLY_WHEN_UNROTATED = (2.8, 3.0)


def _pixel(img: Image.Image, x_in: float, y_in: float) -> tuple[int, int, int]:
    px = img.convert("RGB").getpixel((round(x_in * DPI), round((PAGE_H_IN - y_in) * DPI)))
    return px  # type: ignore[return-value]


def _is_red(rgb: tuple[int, int, int]) -> bool:
    return rgb[0] > 200 and rgb[1] < 60 and rgb[2] < 60


@pytest.mark.parametrize("backend", ["png", "pdf"])
def test_rotated_rectangle_renders_rotated(backend: str, tmp_path: Path) -> None:
    commands = compile_card(_card(_BAR), _NO_IMPOSE)
    if backend == "png":
        out = tmp_path / "bar.png"
        PNGRenderer(dpi=DPI).render(commands, out)
        img = Image.open(out)
    else:
        out = tmp_path / "bar.pdf"
        IRReportLabRenderer().render(commands, out)
        img = rasterize_pdf(out, DPI)
    assert _is_red(_pixel(img, *_INSIDE_ONLY_WHEN_ROTATED))
    assert not _is_red(_pixel(img, *_INSIDE_ONLY_WHEN_UNROTATED))
