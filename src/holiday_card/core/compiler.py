"""Card → list[RenderCommand] compiler.

This is the *decision* layer of the rendering pipeline (Wave 2 Step 2b in
``/tmp/wave2_architecture.md``). It owns:

* the single inches→points conversion (the IR is in points)
* z-index sorting of panel elements
* text-overflow strategy selection (delegated to ``core.text_fitting``)
* fold-line emission per ``FoldType``
* invariant checking via ``assert_balanced``

It is intentionally pure: ``compile_card(card)`` is a function from a
domain object to a deterministic command list, with no I/O except text
measurement (which uses a throwaway in-memory ReportLab Canvas — the same
dependency ``core.text_fitting`` already has).

**Scope of this PR (Wave 2 Step 2b):** only the structural shell plus
basic shapes and text. Image elements, gradients, patterns, clip masks,
SVG paths, and decorative-element expansion are out of scope and will
raise ``NotImplementedError`` if encountered. This is deliberate — silent
feature drop would let half-supported templates ship as broken PDFs in
Step 4. Subsequent PRs lift each feature into the compiler, gated behind
its own snapshot test.

The compiler has **no production callers** in this PR. It is reachable
only from ``tests/unit/test_compiler.py`` and the hidden CLI flag
``holiday-card create --debug-emit-ir``. Step 4 of the migration plan
flips ``CardGenerator`` over.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as _reportlab_canvas

from holiday_card.core.models import (
    Border,
    BorderStyle,
    Card,
    Circle,
    Color,
    FoldType,
    ImageElement,
    Line,
    Panel,
    Rectangle,
    Star,
    TextElement,
    Triangle,
)
from holiday_card.core.render_ir import (
    RGBA,
    BeginGroup,
    BeginPage,
    CircleGeom,
    DrawFoldLine,
    DrawShape,
    DrawText,
    EndGroup,
    EndPage,
    Point,
    PolygonGeom,
    PolylineGeom,
    RectGeom,
    RenderCommand,
    SetMetadata,
    SolidPaint,
    Stroke,
    TextRun,
    Transform,
    assert_balanced,
)
from holiday_card.core.text_fitting import fit_text_element
from holiday_card.utils.measurements import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
    inches_to_points,
)

__all__ = [
    "CompileContext",
    "compile_card",
    "UnsupportedFeatureError",
]


# Default fold-line styling — matches the legacy renderer.
_FOLD_LINE_GREY = RGBA(r=0.7, g=0.7, b=0.7)


class UnsupportedFeatureError(NotImplementedError):
    """Raised when the compiler encounters a Card feature not yet ported.

    The error message names the feature and the element for easy triage.
    """


@dataclass(frozen=True)
class CompileContext:
    """Optional context for compilation.

    Defaults are derived from ``utils.measurements`` — the simplest call is
    ``compile_card(card)`` with no context.
    """

    page_width_inches: float = PAGE_WIDTH
    page_height_inches: float = PAGE_HEIGHT
    emit_fold_lines: bool = True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compile_card(card: Card, ctx: CompileContext | None = None) -> list[RenderCommand]:
    """Lower a ``Card`` to a flat, ordered, balanced list of ``RenderCommand``.

    The returned list is fully self-describing: every coordinate is in
    points, every paint is resolved, every text run is at its final size.
    Backends can render it without consulting the original ``Card``.

    Raises ``UnsupportedFeatureError`` if the card uses features not yet
    implemented by the compiler (e.g. image elements, gradient fills,
    clip masks, SVG paths, decorative elements). Step 2b deliberately
    refuses rather than silently dropping content.
    """
    ctx = ctx or CompileContext()
    measurer = _make_measurer()

    commands: list[RenderCommand] = []
    commands.append(BeginPage(
        width=inches_to_points(ctx.page_width_inches),
        height=inches_to_points(ctx.page_height_inches),
    ))
    commands.extend(_emit_metadata(card))

    for panel in card.panels:
        commands.extend(_compile_panel(panel, measurer))

    if ctx.emit_fold_lines:
        commands.extend(_emit_fold_lines(card.fold_type, ctx))

    commands.append(EndPage())

    assert_balanced(commands)
    return commands


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def _emit_metadata(card: Card) -> list[RenderCommand]:
    out: list[RenderCommand] = [
        SetMetadata(key="template_id", value=card.template_id),
        SetMetadata(key="fold_type", value=card.fold_type.value),
    ]
    if card.theme_id:
        out.append(SetMetadata(key="theme_id", value=card.theme_id))
    return out


# ---------------------------------------------------------------------------
# Panel compilation
# ---------------------------------------------------------------------------


def _compile_panel(
    panel: Panel,
    measurer: _reportlab_canvas.Canvas,
) -> list[RenderCommand]:
    out: list[RenderCommand] = []

    # Panel rotation is around its center (matches the legacy renderer's
    # translate/rotate/translate sequence at reportlab_renderer.py:96-102).
    # We materialize the pivot here so backends never compute it.
    transform = _panel_transform(panel)
    out.append(BeginGroup(transform=transform))

    out.extend(_emit_panel_background(panel))
    out.extend(_emit_panel_border(panel))

    for kind, element in _flatten_and_sort(panel):
        if kind == "shape":
            out.extend(_compile_shape(element, panel))
        elif kind == "text":
            assert isinstance(element, TextElement)  # narrowed via _flatten_and_sort
            out.extend(_compile_text(element, panel, measurer))
        elif kind == "image":
            assert isinstance(element, ImageElement)  # narrowed via _flatten_and_sort
            raise UnsupportedFeatureError(
                f"ImageElement is not yet supported by the compiler "
                f"(panel {panel.position.value!r}, element id {element.id!r}). "
                f"Track: Wave 2 follow-up PR."
            )

    out.append(EndGroup())
    return out


def _panel_transform(panel: Panel) -> Transform:
    """Resolve panel rotation around its center to an explicit translate+rotate."""
    if panel.rotation == 0:
        return Transform()
    cx_pt = inches_to_points(panel.x + panel.width / 2)
    cy_pt = inches_to_points(panel.y + panel.height / 2)
    # Compose: translate(cx, cy) ∘ rotate(deg) ∘ translate(-cx, -cy).
    # Backends apply translate then rotate then scale; for now we collapse
    # the pivot into a translate+rotate by recording the center as the
    # translate target. Backends interpret Transform.translate_* as
    # post-rotation translate and rotate_deg as rotation about the local
    # origin — this is a known TODO; the legacy renderer encodes it
    # implicitly. For non-rotated panels (the common case) it's a no-op.
    return Transform(translate_x=cx_pt, translate_y=cy_pt, rotate_deg=panel.rotation)


def _emit_panel_background(panel: Panel) -> list[RenderCommand]:
    if panel.background_color is None:
        return []
    return [
        DrawShape(
            geometry=RectGeom(
                x=inches_to_points(panel.x),
                y=inches_to_points(panel.y),
                width=inches_to_points(panel.width),
                height=inches_to_points(panel.height),
            ),
            fill=SolidPaint(color=_color_to_rgba(panel.background_color)),
        ),
    ]


def _emit_panel_border(panel: Panel) -> list[RenderCommand]:
    if panel.border is None:
        return []
    border = panel.border
    if border.style == BorderStyle.DECORATIVE:
        # Decorative borders draw shapes rather than a stroked rect; not
        # ported yet (would require the decorative library).
        raise UnsupportedFeatureError(
            f"Border style {border.style.value!r} not yet supported by the compiler."
        )
    return [
        DrawShape(
            geometry=RectGeom(
                x=inches_to_points(panel.x),
                y=inches_to_points(panel.y),
                width=inches_to_points(panel.width),
                height=inches_to_points(panel.height),
                corner_radius=inches_to_points(border.corner_radius / 72.0)
                if border.corner_radius
                else 0.0,
            ),
            stroke=_border_to_stroke(border),
        ),
    ]


def _border_to_stroke(border: Border) -> Stroke:
    dash: tuple[float, ...]
    if border.style == BorderStyle.DASHED:
        dash = (3.0, 3.0)
    elif border.style == BorderStyle.DOTTED:
        dash = (1.0, 2.0)
    else:
        dash = ()
    return Stroke(color=_color_to_rgba(border.color), width=border.width, dash=dash)


# ---------------------------------------------------------------------------
# Element ordering — replaces the heterogeneous list[tuple[str, Any, int]]
# at reportlab_renderer.py:118-138 (source of 6 mypy errors)
# ---------------------------------------------------------------------------


def _flatten_and_sort(
    panel: Panel,
) -> list[tuple[str, object]]:
    """Merge shapes/images/text into one z-sorted list with stable secondary
    ordering by definition order.

    Returns ``(kind, element)`` tuples where ``kind`` is ``"shape"``,
    ``"image"``, or ``"text"``.
    """
    enumerated: list[tuple[int, int, str, object]] = []  # (z, order, kind, elem)
    order = 0
    for shape in panel.shape_elements:
        enumerated.append((getattr(shape, "z_index", 0), order, "shape", shape))
        order += 1
    for image in panel.image_elements:
        enumerated.append((getattr(image, "z_index", 100), order, "image", image))
        order += 1
    for text in panel.text_elements:
        enumerated.append((getattr(text, "z_index", 100), order, "text", text))
        order += 1
    enumerated.sort(key=lambda t: (t[0], t[1]))
    return [(kind, elem) for _z, _order, kind, elem in enumerated]


# ---------------------------------------------------------------------------
# Shape compilation
# ---------------------------------------------------------------------------


def _compile_shape(shape: object, panel: Panel) -> list[RenderCommand]:
    if isinstance(shape, Rectangle):
        return [_compile_rectangle(shape, panel)]
    if isinstance(shape, Circle):
        return [_compile_circle(shape, panel)]
    if isinstance(shape, Triangle):
        return [_compile_triangle(shape, panel)]
    if isinstance(shape, Star):
        return [_compile_star(shape, panel)]
    if isinstance(shape, Line):
        return [_compile_line(shape, panel)]
    raise UnsupportedFeatureError(
        f"Shape type {type(shape).__name__} is not yet supported by the compiler. "
        f"Track: Wave 2 follow-up PR (gradients, patterns, SVGPath, decorative elements)."
    )


def _compile_rectangle(shape: Rectangle, panel: Panel) -> RenderCommand:
    fill, stroke = _resolve_paint_and_stroke(shape)
    return DrawShape(
        geometry=RectGeom(
            x=inches_to_points(panel.x + shape.x),
            y=inches_to_points(panel.y + shape.y),
            width=inches_to_points(shape.width),
            height=inches_to_points(shape.height),
        ),
        fill=fill,
        stroke=stroke,
        opacity=shape.opacity,
    )


def _compile_circle(shape: Circle, panel: Panel) -> RenderCommand:
    fill, stroke = _resolve_paint_and_stroke(shape)
    return DrawShape(
        geometry=CircleGeom(
            center=Point(
                x=inches_to_points(panel.x + shape.center_x),
                y=inches_to_points(panel.y + shape.center_y),
            ),
            radius=inches_to_points(shape.radius),
        ),
        fill=fill,
        stroke=stroke,
        opacity=shape.opacity,
    )


def _compile_triangle(shape: Triangle, panel: Panel) -> RenderCommand:
    fill, stroke = _resolve_paint_and_stroke(shape)
    return DrawShape(
        geometry=PolygonGeom(
            points=(
                Point(x=inches_to_points(panel.x + shape.x1), y=inches_to_points(panel.y + shape.y1)),
                Point(x=inches_to_points(panel.x + shape.x2), y=inches_to_points(panel.y + shape.y2)),
                Point(x=inches_to_points(panel.x + shape.x3), y=inches_to_points(panel.y + shape.y3)),
            ),
        ),
        fill=fill,
        stroke=stroke,
        opacity=shape.opacity,
    )


def _compile_star(shape: Star, panel: Panel) -> RenderCommand:
    """Compute star vertices once, in the compiler.

    Mirrors the math in shape_renderer.py's render_star but emits a
    PolygonGeom with the resolved points so the backend never computes
    star geometry.
    """
    import math

    cx_pt = inches_to_points(panel.x + shape.center_x)
    cy_pt = inches_to_points(panel.y + shape.center_y)
    outer_pt = inches_to_points(shape.outer_radius)
    inner_pt = inches_to_points(shape.inner_radius)

    points: list[Point] = []
    n = shape.points
    for i in range(n * 2):
        angle = math.pi / 2 + i * math.pi / n
        radius = outer_pt if i % 2 == 0 else inner_pt
        points.append(Point(x=cx_pt + radius * math.cos(angle), y=cy_pt + radius * math.sin(angle)))

    fill, stroke = _resolve_paint_and_stroke(shape)
    return DrawShape(
        geometry=PolygonGeom(points=tuple(points)),
        fill=fill,
        stroke=stroke,
        opacity=shape.opacity,
    )


def _compile_line(shape: Line, panel: Panel) -> RenderCommand:
    _, stroke = _resolve_paint_and_stroke(shape)
    if stroke is None:
        # A line with no stroke is invisible; skip silently isn't an option,
        # so synthesize a 1-pt black stroke (matches the legacy default).
        stroke = Stroke(color=RGBA(r=0, g=0, b=0), width=1.0)
    return DrawShape(
        geometry=PolylineGeom(
            points=(
                Point(x=inches_to_points(panel.x + shape.start_x), y=inches_to_points(panel.y + shape.start_y)),
                Point(x=inches_to_points(panel.x + shape.end_x), y=inches_to_points(panel.y + shape.end_y)),
            ),
        ),
        stroke=stroke,
        opacity=shape.opacity,
    )


def _resolve_paint_and_stroke(
    shape: object,
) -> tuple[SolidPaint | None, Stroke | None]:
    """Convert ``shape.fill`` / ``shape.fill_color`` / ``shape.stroke_*`` into
    IR ``SolidPaint`` + ``Stroke`` (or ``None`` for no fill/stroke).

    Only solid fills are supported in this PR. Gradient and pattern fills
    raise ``UnsupportedFeatureError`` so the snapshot test surfaces them.
    """
    fill_attr = getattr(shape, "fill", None)
    fill_color_attr = getattr(shape, "fill_color", None)
    stroke_color_attr = getattr(shape, "stroke_color", None)
    stroke_width_attr = getattr(shape, "stroke_width", 0.0)

    if fill_attr is not None:
        # The discriminated FillStyle union — only SolidFill ports cleanly here.
        from holiday_card.core.models import SolidFill  # local import to keep top tidy

        if isinstance(fill_attr, SolidFill):
            fill: SolidPaint | None = SolidPaint(color=_hex_to_rgba(fill_attr.color))
        else:
            raise UnsupportedFeatureError(
                f"Fill style {type(fill_attr).__name__} is not yet supported by the compiler."
            )
    elif fill_color_attr:
        fill = SolidPaint(color=_hex_to_rgba(fill_color_attr))
    else:
        fill = None

    stroke: Stroke | None
    if stroke_color_attr and stroke_width_attr > 0:
        stroke = Stroke(color=_hex_to_rgba(stroke_color_attr), width=stroke_width_attr)
    else:
        stroke = None

    return (fill, stroke)


# ---------------------------------------------------------------------------
# Text compilation
# ---------------------------------------------------------------------------


def _compile_text(
    text: TextElement,
    panel: Panel,
    measurer: _reportlab_canvas.Canvas,
) -> list[RenderCommand]:
    """Run the overflow strategy and emit one ``DrawText`` per resulting line.

    Uses ``Helvetica`` as the font_id when no custom font is registered,
    matching the legacy renderer's default. Backends are responsible for
    resolving the font_id to a real font.
    """
    from holiday_card.core.text_utils import calculate_line_height  # local: small module

    font_id = text.font_family or "Helvetica"
    color = _color_to_rgba(text.color) if text.color else RGBA(r=0, g=0, b=0)
    align = text.alignment.value  # already "left"/"center"/"right" by enum

    if text.width:
        final_size, lines, _ = fit_text_element(measurer, text, panel, font_id)
    else:
        final_size = text.font_size
        lines = [text.content]

    abs_x = inches_to_points(panel.x + text.x)
    abs_y = inches_to_points(panel.y + text.y)
    line_height = calculate_line_height(final_size)

    commands: list[RenderCommand] = []
    for i, line in enumerate(lines):
        line_y = abs_y - (i * line_height)
        commands.append(
            DrawText(
                run=TextRun(
                    text=line,
                    origin=Point(x=abs_x, y=line_y),
                    font_id=font_id,
                    size_pt=float(final_size),
                    color=color,
                    align=align,  # type: ignore[arg-type]
                ),
            )
        )
    return commands


# ---------------------------------------------------------------------------
# Fold lines
# ---------------------------------------------------------------------------


def _emit_fold_lines(fold_type: FoldType, ctx: CompileContext) -> list[RenderCommand]:
    width = inches_to_points(ctx.page_width_inches)
    height = inches_to_points(ctx.page_height_inches)
    if fold_type == FoldType.HALF_FOLD:
        mid_y = height / 2
        return [DrawFoldLine(start=Point(x=0, y=mid_y), end=Point(x=width, y=mid_y))]
    if fold_type == FoldType.QUARTER_FOLD:
        mid_x = width / 2
        mid_y = height / 2
        return [
            DrawFoldLine(start=Point(x=0, y=mid_y), end=Point(x=width, y=mid_y)),
            DrawFoldLine(start=Point(x=mid_x, y=0), end=Point(x=mid_x, y=height)),
        ]
    if fold_type == FoldType.TRI_FOLD:
        third_x = width / 3
        return [
            DrawFoldLine(start=Point(x=third_x, y=0), end=Point(x=third_x, y=height)),
            DrawFoldLine(start=Point(x=2 * third_x, y=0), end=Point(x=2 * third_x, y=height)),
        ]
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _color_to_rgba(color: Color) -> RGBA:
    return RGBA(r=color.r, g=color.g, b=color.b)


def _hex_to_rgba(hex_color: str) -> RGBA:
    color = Color.from_hex(hex_color)
    return _color_to_rgba(color)


def _make_measurer() -> _reportlab_canvas.Canvas:
    """Return a throwaway in-memory ReportLab canvas for text measurement.

    The text-fitting code calls ``canvas.stringWidth`` to size lines; it
    does not draw or write the output. Reusing this single canvas across
    one ``compile_card`` call is safe because the canvas is stateless w.r.t.
    measurement.
    """
    return _reportlab_canvas.Canvas(io.BytesIO(), pagesize=letter)
