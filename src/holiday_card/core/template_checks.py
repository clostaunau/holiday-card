"""Authoring checks that a loaded :class:`Template` needs beyond its schema (#57).

``Template.model_validate`` (D3) already refuses unknown keys and bad types.
:func:`check_template` adds what the schema can't express: font names the
backends can render, elements that stay inside their panel, a default theme
that exists, and a compile smoke test. Every problem is reported at once
(D4), so ``holiday-card validate`` is the one pre-flight check before
``create``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel

from holiday_card.core.compiler import UnknownFontError, _compile_svg_path, compile_card
from holiday_card.core.errors import UnsupportedFeatureError
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import (
    Circle,
    Line,
    Panel,
    Rectangle,
    Shape,
    Star,
    SVGPath,
    Template,
    Triangle,
)
from holiday_card.core.render_ir import BeginGroup, DrawShape, PathGeom
from holiday_card.core.text_measure import default_text_measurer
from holiday_card.core.themes import ThemeNotFoundError, load_theme
from holiday_card.utils.measurements import points_to_inches

# Bounds slack in inches, so authored values like 4.25 aren't refused by float noise.
_EPSILON = 1e-6

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class TemplateProblem:
    """One authoring problem: where it is and what is wrong."""

    path: str
    """E.g. ``panels[front].text_elements[greeting].font_family``."""
    message: str


def check_template(template: Template) -> list[TemplateProblem]:
    """Return every problem in ``template``, never just the first.

    Checks, in order: font names (``FONT_MAP`` ∪ ``CURATED_FONTS`` unless
    ``font_file`` is set), element bounds (text anchor, shape bbox, image
    rect inside ``[0, width] × [0, height]`` of the panel; SVG paths use
    their compiled bbox, other shapes their unrotated geometry), the
    ``default_theme_id``, and a compile smoke test that turns a
    compile-time refusal into a problem. Pure apart from theme and font
    lookups; ``[]`` means the template is valid.
    """
    font_problems = list(_check_fonts(template))
    problems = [
        *font_problems,
        *_check_bounds(template),
        *_check_theme(template),
    ]
    problems.extend(_check_compiles(template, fonts_reported=bool(font_problems)))
    return problems


def _element_path(panel: Panel, kind: str, index: int, element: BaseModel) -> str:
    # Authored ids read better than indexes; generated uuids don't.
    key = getattr(element, "id", None) if "id" in element.model_fields_set else index
    return f"panels[{panel.position.value}].{kind}[{key}]"


def _check_fonts(template: Template) -> Iterable[TemplateProblem]:
    known = default_text_measurer().known_font_ids()
    for panel in template.panels:
        for index, text in enumerate(panel.text_elements):
            if text.font_file is None and text.font_family not in known:
                yield TemplateProblem(
                    f"{_element_path(panel, 'text_elements', index, text)}.font_family",
                    f"unknown font {text.font_family!r}. Available: "
                    f"{', '.join(sorted(known))}",
                )


def _check_bounds(template: Template) -> Iterable[TemplateProblem]:
    for panel in template.panels:
        for index, text in enumerate(panel.text_elements):
            if not _inside(panel, (text.x, text.y, text.x, text.y)):
                yield TemplateProblem(
                    _element_path(panel, "text_elements", index, text),
                    f"text anchor ({text.x:g}, {text.y:g}) in is outside the "
                    f"{_panel_size(panel)} panel",
                )
        for index, shape in enumerate(panel.shape_elements):
            box = _shape_box(shape, panel)
            if not _inside(panel, box):
                yield TemplateProblem(
                    _element_path(panel, "shape_elements", index, shape),
                    f"{shape.type.value} bbox {_fmt_box(box)} in is outside the "
                    f"{_panel_size(panel)} panel",
                )
        for index, image in enumerate(panel.image_elements):
            if image.width is None or image.height is None:
                continue  # auto-sizing is a compile-time refusal
            box = (image.x, image.y, image.x + image.width, image.y + image.height)
            if not _inside(panel, box):
                yield TemplateProblem(
                    _element_path(panel, "image_elements", index, image),
                    f"image rect {_fmt_box(box)} in is outside the "
                    f"{_panel_size(panel)} panel",
                )


def _shape_box(shape: Shape, panel: Panel) -> Box:
    if isinstance(shape, Rectangle):
        return (shape.x, shape.y, shape.x + shape.width, shape.y + shape.height)
    if isinstance(shape, Circle):
        r = shape.radius
        return (shape.center_x - r, shape.center_y - r, shape.center_x + r, shape.center_y + r)
    if isinstance(shape, Star):
        r = shape.outer_radius
        return (shape.center_x - r, shape.center_y - r, shape.center_x + r, shape.center_y + r)
    if isinstance(shape, Triangle):
        return _points_box([(shape.x1, shape.y1), (shape.x2, shape.y2), (shape.x3, shape.y3)])
    if isinstance(shape, Line):
        return _points_box([(shape.start_x, shape.start_y), (shape.end_x, shape.end_y)])
    assert isinstance(shape, SVGPath)
    return _svg_path_box(shape, panel)


def _svg_path_box(shape: SVGPath, panel: Panel) -> Box:
    # The compiled path, through its rotation group, back in panel inches.
    commands = _compile_svg_path(shape, panel)
    draw = next(c for c in commands if isinstance(c, DrawShape))
    assert isinstance(draw.geometry, PathGeom)
    a, b, c, d, e, f = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    group = next((c for c in commands if isinstance(c, BeginGroup)), None)
    if group is not None:
        a, b, c, d, e, f = group.transform.to_matrix()
    return _points_box(
        [
            (
                points_to_inches(a * pt.x + c * pt.y + e) - panel.x,
                points_to_inches(b * pt.x + d * pt.y + f) - panel.y,
            )
            for op in draw.geometry.ops
            for pt in op.points
        ]
    )


def _points_box(points: list[tuple[float, float]]) -> Box:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _inside(panel: Panel, box: Box) -> bool:
    x0, y0, x1, y1 = box
    return (
        x0 >= -_EPSILON
        and y0 >= -_EPSILON
        and x1 <= panel.width + _EPSILON
        and y1 <= panel.height + _EPSILON
    )


def _panel_size(panel: Panel) -> str:
    return f"{panel.width:g}×{panel.height:g} in"


def _fmt_box(box: Box) -> str:
    x0, y0, x1, y1 = (round(v, 3) for v in box)
    return f"({x0:g}, {y0:g})–({x1:g}, {y1:g})"


def _check_theme(template: Template) -> Iterable[TemplateProblem]:
    if template.default_theme_id is None:
        return
    try:
        load_theme(template.default_theme_id)
    except ThemeNotFoundError:
        yield TemplateProblem(
            "default_theme_id", f"unknown theme {template.default_theme_id!r}"
        )


def _check_compiles(template: Template, *, fonts_reported: bool) -> Iterable[TemplateProblem]:
    try:
        compile_card(CardGenerator().create_card_from_template(template))
    except (UnsupportedFeatureError, KeyError, ValueError) as e:
        if not (fonts_reported and isinstance(e, UnknownFontError)):  # said once already
            yield TemplateProblem("<compile>", str(e))
