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
and SVG paths are out of scope and will
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
from dataclasses import dataclass, field

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as _reportlab_canvas

from holiday_card.core.models import (
    Border,
    BorderStyle,
    Card,
    Circle,
    CircleClipMask,
    Color,
    EllipseClipMask,
    FoldType,
    ImageElement,
    Line,
    Panel,
    Rectangle,
    RectangleClipMask,
    Star,
    StarClipMask,
    SVGPath,
    TextElement,
    Triangle,
)
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
    GeomU,
    GradientStop,
    ImageRef,
    LinearGradientPaint,
    PaintU,
    PathGeom,
    PathOp,
    PatternPaint,
    Point,
    PolygonGeom,
    PolylineGeom,
    RadialGradientPaint,
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
    PageGeometry,
    inches_to_points,
)

__all__ = [
    "CompileContext",
    "compile_card",
    "UnsupportedFeatureError",
]


# Default fold-line styling — matches the legacy renderer.
_FOLD_LINE_GREY = RGBA(r=0.7, g=0.7, b=0.7)

# Tolerance for "panel edge touches page trim edge" comparisons. Inches
# come from YAML and may have small float drift after arithmetic; 0.001"
# is well below print precision (a typical inkjet dot is ~0.005").
_EDGE_TOUCH_EPSILON: float = 1e-3


class UnsupportedFeatureError(NotImplementedError):
    """Raised when the compiler encounters a Card feature not yet ported.

    The error message names the feature and the element for easy triage.
    """


@dataclass(frozen=True)
class CompileContext:
    """Optional context for compilation.

    Holds the :class:`PageGeometry` that tells the compiler the trim
    dimensions, the bleed extension, and the safe margin. Defaults to
    ``PageGeometry.us_letter()`` with the industry-standard 0.125" bleed.
    Tests that need byte-stable, no-bleed output construct the context
    with ``PageGeometry.us_letter(bleed_in=0.0)``.
    """

    geometry: PageGeometry = field(default_factory=PageGeometry.us_letter)
    emit_fold_lines: bool = True

    @property
    def page_width_inches(self) -> float:
        """Backwards-compat alias for ``geometry.trim_width_in``."""
        return self.geometry.trim_width_in

    @property
    def page_height_inches(self) -> float:
        """Backwards-compat alias for ``geometry.trim_height_in``."""
        return self.geometry.trim_height_in


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
    clip masks, SVG paths). Step 2b deliberately
    refuses rather than silently dropping content.
    """
    ctx = ctx or CompileContext()
    measurer = _make_measurer()
    geometry = ctx.geometry

    commands: list[RenderCommand] = []
    commands.append(BeginPage(
        width=geometry.trim_width_pts,
        height=geometry.trim_height_pts,
        bleed=geometry.bleed_pts,
        safe_margin=geometry.safe_margin_pts,
    ))
    commands.extend(_emit_metadata(card))

    for panel in card.panels:
        commands.extend(_compile_panel(panel, card, geometry, measurer))

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
    card: Card,
    geometry: PageGeometry,
    measurer: _reportlab_canvas.Canvas,
) -> list[RenderCommand]:
    out: list[RenderCommand] = []

    # Panel rotation is around its center (matches the legacy renderer's
    # translate/rotate/translate sequence at reportlab_renderer.py:96-102).
    # We materialize the pivot here so backends never compute it.
    transform = _panel_transform(panel)
    out.append(BeginGroup(transform=transform))

    out.extend(_emit_panel_background(panel, card, geometry))
    out.extend(_emit_panel_border(panel))

    for kind, element in _flatten_and_sort(panel):
        if kind == "shape":
            out.extend(_compile_shape(element, panel))
        elif kind == "text":
            assert isinstance(element, TextElement)  # narrowed via _flatten_and_sort
            out.extend(_compile_text(element, panel, measurer))
        elif kind == "image":
            assert isinstance(element, ImageElement)  # narrowed via _flatten_and_sort
            out.extend(_compile_image(element, panel))

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


def _emit_panel_background(
    panel: Panel, card: Card, geometry: PageGeometry
) -> list[RenderCommand]:
    """Emit the panel's solid-color background, extended by bleed on
    edges that touch the page trim.

    Effective bleed resolves as ``panel.bleed if panel.bleed is not None
    else card.bleed``. Per-panel ``None`` is the inherit signal; an
    explicit ``Panel(bleed=0.0)`` overrides the card default to zero.

    Edge-detection is in **page coords** (panel.x, .y, .width, .height
    are page-coords already). For each page-edge the panel touches, the
    background extends outward by the bleed amount in **panel-local
    coords** — the mapping accounts for panel rotation so that a 180°
    rotated panel still bleeds in the correct page direction.
    """
    if panel.background_color is None:
        return []
    rect = _bleed_extended_panel_rect(panel, card, geometry)
    return [
        DrawShape(
            geometry=rect,
            fill=SolidPaint(color=_color_to_rgba(panel.background_color)),
        ),
    ]


def _bleed_extended_panel_rect(
    panel: Panel, card: Card, geometry: PageGeometry
) -> RectGeom:
    """Compute the panel-background ``RectGeom`` with bleed applied on
    panel-local edges that map to page-trim edges.

    Returns coordinates in **points**, in the panel's local frame
    (i.e. inside the BeginGroup that applies ``_panel_transform``).
    """
    effective_bleed_in = panel.bleed if panel.bleed is not None else card.bleed
    if effective_bleed_in == 0.0:
        return RectGeom(
            x=inches_to_points(panel.x),
            y=inches_to_points(panel.y),
            width=inches_to_points(panel.width),
            height=inches_to_points(panel.height),
        )

    # Page-coord trim-edge touches.
    eps = _EDGE_TOUCH_EPSILON
    touches_left = abs(panel.x) <= eps
    touches_right = abs((panel.x + panel.width) - geometry.trim_width_in) <= eps
    touches_bottom = abs(panel.y) <= eps
    touches_top = abs((panel.y + panel.height) - geometry.trim_height_in) <= eps

    # Map page-touches to panel-local edges. The panel's transform rotates
    # the local rect around the panel center; for the rect we draw inside
    # the group, "extend leftward in panel-local" maps to "extend rightward
    # in page" under a 180° rotation. Compose the page-edge touches into
    # panel-local touches accordingly.
    if panel.rotation == 0:
        local_left, local_right = touches_left, touches_right
        local_bottom, local_top = touches_bottom, touches_top
    elif panel.rotation in (180.0, -180.0):
        # Page L↔panel-local R, page B↔panel-local T.
        local_left, local_right = touches_right, touches_left
        local_bottom, local_top = touches_top, touches_bottom
    else:
        raise UnsupportedFeatureError(
            f"Bleed extension is only implemented for panel rotations "
            f"of 0° or 180°; panel {panel.position.value!r} has rotation "
            f"{panel.rotation}°. Set Panel.bleed=0 to opt out, or extend "
            f"_bleed_extended_panel_rect to map page-edges through arbitrary "
            f"rotations."
        )

    bleed_pt = inches_to_points(effective_bleed_in)
    x_pt = inches_to_points(panel.x) - (bleed_pt if local_left else 0.0)
    y_pt = inches_to_points(panel.y) - (bleed_pt if local_bottom else 0.0)
    width_pt = (
        inches_to_points(panel.width)
        + (bleed_pt if local_left else 0.0)
        + (bleed_pt if local_right else 0.0)
    )
    height_pt = (
        inches_to_points(panel.height)
        + (bleed_pt if local_bottom else 0.0)
        + (bleed_pt if local_top else 0.0)
    )
    return RectGeom(x=x_pt, y=y_pt, width=width_pt, height=height_pt)


def _emit_panel_border(panel: Panel) -> list[RenderCommand]:
    if panel.border is None:
        return []
    border = panel.border
    if border.style == BorderStyle.DECORATIVE:
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
    if isinstance(shape, SVGPath):
        return _compile_svg_path(shape, panel)
    raise UnsupportedFeatureError(
        f"Shape type {type(shape).__name__} is not yet supported by the compiler."
    )


def _compile_rectangle(shape: Rectangle, panel: Panel) -> RenderCommand:
    fill, stroke = _resolve_paint_and_stroke(shape, _shape_bbox_pts(shape, panel), panel=panel)
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
    fill, stroke = _resolve_paint_and_stroke(shape, _shape_bbox_pts(shape, panel), panel=panel)
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
    fill, stroke = _resolve_paint_and_stroke(shape, _shape_bbox_pts(shape, panel), panel=panel)
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

    fill, stroke = _resolve_paint_and_stroke(shape, _shape_bbox_pts(shape, panel), panel=panel)
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


def _compile_svg_path(shape: SVGPath, panel: Panel) -> list[RenderCommand]:
    """Convert an ``SVGPath`` shape to IR commands.

    Pipeline:

    1. Parse the path's ``d`` string via :class:`SVGPathParser` into a
       flat list of :class:`PathCommand`.
    2. Translate each command into one or more :class:`PathOp` entries
       on the IR side — resolving relative coordinates against the
       running cursor, reflecting control points for ``S`` and ``T``,
       and re-emitting move-to-subpath-start on ``Z``.
    3. Apply ``shape.scale`` (path units → inches) and translate by
       ``shape.x + panel.x``, ``shape.y + panel.y`` (panel-relative
       inches), then convert to page-absolute points.
    4. If ``shape.rotation`` is non-zero, wrap the ``DrawShape`` in a
       ``BeginGroup`` carrying a pivot-rotate transform around the
       path's bounding-box center (matching the idiom used for image
       rotation in ``_compile_image``).

    Arcs (``A`` / ``a``) are not yet supported and raise
    :class:`UnsupportedFeatureError`. Real templates ship cubic +
    quadratic Beziers only; arc support is a follow-up.
    """
    from holiday_card.utils.svg_parser import SVGCommand, SVGPathParser

    parser = SVGPathParser()
    raw_commands = parser.parse(shape.path_data)

    ops_local, bbox_local = _path_commands_to_ops(raw_commands)
    if not ops_local:
        return []

    # Apply scale + translate + inches → points to each emitted point.
    offset_x_in = panel.x + shape.x
    offset_y_in = panel.y + shape.y
    scale = shape.scale

    def transform(px: float, py: float) -> Point:
        x_in = offset_x_in + px * scale
        y_in = offset_y_in + py * scale
        return Point(x=inches_to_points(x_in), y=inches_to_points(y_in))

    transformed_ops: list[PathOp] = []
    for op in ops_local:
        if op.op == "close":
            transformed_ops.append(op)
            continue
        new_points = tuple(transform(p.x, p.y) for p in op.points)
        transformed_ops.append(PathOp(op=op.op, points=new_points))

    fill, stroke = _resolve_paint_and_stroke(shape)
    draw = DrawShape(
        geometry=PathGeom(ops=tuple(transformed_ops)),
        fill=fill,
        stroke=stroke,
        opacity=shape.opacity,
    )

    if shape.rotation != 0:
        # Pivot at the bbox center, in absolute page-points.
        x_min, y_min, x_max, y_max = bbox_local
        cx_in = offset_x_in + (x_min + x_max) / 2 * scale
        cy_in = offset_y_in + (y_min + y_max) / 2 * scale
        transform_ir = Transform(
            translate_x=inches_to_points(cx_in),
            translate_y=inches_to_points(cy_in),
            rotate_deg=shape.rotation,
        )
        return [BeginGroup(transform=transform_ir), draw, EndGroup()]
    # Silence unused import if SVGCommand isn't referenced elsewhere.
    _ = SVGCommand
    return [draw]


def _path_commands_to_ops(
    raw: list,
) -> tuple[list[PathOp], tuple[float, float, float, float]]:
    """Convert parsed ``PathCommand`` list into IR ``PathOp`` list.

    Resolves relative commands, ``H``/``V`` shortcuts, ``S``/``T``
    smooth-curve control-point reflection, and ``Z`` close-with-implicit-
    move. Returns the ops plus a bounding box ``(x_min, y_min, x_max,
    y_max)`` in path-internal coords (useful for computing a rotation
    pivot before scale/translate are applied).
    """
    from holiday_card.utils.svg_parser import SVGCommand

    cx, cy = 0.0, 0.0  # current cursor
    sx, sy = 0.0, 0.0  # subpath start (for Z close)
    last_cubic_control: tuple[float, float] | None = None
    last_quad_control: tuple[float, float] | None = None
    ops: list[PathOp] = []
    seen_xs: list[float] = []
    seen_ys: list[float] = []

    def add_point(x: float, y: float) -> Point:
        seen_xs.append(x)
        seen_ys.append(y)
        return Point(x=x, y=y)

    for cmd in raw:
        c = cmd.command
        params = cmd.params

        if c in (SVGCommand.MOVE, SVGCommand.MOVE_REL):
            # M/m takes pairs: first pair is move, subsequent are line-tos.
            rel = c == SVGCommand.MOVE_REL
            for i in range(0, len(params), 2):
                x, y = params[i], params[i + 1]
                if rel:
                    x += cx
                    y += cy
                if i == 0:
                    ops.append(PathOp(op="move", points=(add_point(x, y),)))
                    sx, sy = x, y
                else:
                    ops.append(PathOp(op="line", points=(add_point(x, y),)))
                cx, cy = x, y
            last_cubic_control = None
            last_quad_control = None

        elif c in (SVGCommand.LINE, SVGCommand.LINE_REL):
            rel = c == SVGCommand.LINE_REL
            for i in range(0, len(params), 2):
                x, y = params[i], params[i + 1]
                if rel:
                    x += cx
                    y += cy
                ops.append(PathOp(op="line", points=(add_point(x, y),)))
                cx, cy = x, y
            last_cubic_control = None
            last_quad_control = None

        elif c in (SVGCommand.HORIZONTAL, SVGCommand.HORIZONTAL_REL):
            rel = c == SVGCommand.HORIZONTAL_REL
            for x in params:
                if rel:
                    x = cx + x
                ops.append(PathOp(op="line", points=(add_point(x, cy),)))
                cx = x
            last_cubic_control = None
            last_quad_control = None

        elif c in (SVGCommand.VERTICAL, SVGCommand.VERTICAL_REL):
            rel = c == SVGCommand.VERTICAL_REL
            for y in params:
                if rel:
                    y = cy + y
                ops.append(PathOp(op="line", points=(add_point(cx, y),)))
                cy = y
            last_cubic_control = None
            last_quad_control = None

        elif c in (SVGCommand.CUBIC_BEZIER, SVGCommand.CUBIC_BEZIER_REL):
            rel = c == SVGCommand.CUBIC_BEZIER_REL
            for i in range(0, len(params), 6):
                x1, y1, x2, y2, x, y = params[i:i + 6]
                if rel:
                    x1 += cx
                    y1 += cy
                    x2 += cx
                    y2 += cy
                    x += cx
                    y += cy
                ops.append(PathOp(op="cubic", points=(
                    add_point(x1, y1),
                    add_point(x2, y2),
                    add_point(x, y),
                )))
                cx, cy = x, y
                last_cubic_control = (x2, y2)
            last_quad_control = None

        elif c in (SVGCommand.CUBIC_BEZIER_SMOOTH, SVGCommand.CUBIC_BEZIER_SMOOTH_REL):
            rel = c == SVGCommand.CUBIC_BEZIER_SMOOTH_REL
            for i in range(0, len(params), 4):
                x2, y2, x, y = params[i:i + 4]
                if rel:
                    x2 += cx
                    y2 += cy
                    x += cx
                    y += cy
                # First control point: reflection of previous cubic's
                # second control point through the current point (per
                # SVG spec). If previous wasn't a cubic, reuse current.
                if last_cubic_control is None:
                    x1, y1 = cx, cy
                else:
                    x1 = 2 * cx - last_cubic_control[0]
                    y1 = 2 * cy - last_cubic_control[1]
                ops.append(PathOp(op="cubic", points=(
                    add_point(x1, y1),
                    add_point(x2, y2),
                    add_point(x, y),
                )))
                cx, cy = x, y
                last_cubic_control = (x2, y2)
            last_quad_control = None

        elif c in (SVGCommand.QUADRATIC_BEZIER, SVGCommand.QUADRATIC_BEZIER_REL):
            rel = c == SVGCommand.QUADRATIC_BEZIER_REL
            for i in range(0, len(params), 4):
                x1, y1, x, y = params[i:i + 4]
                if rel:
                    x1 += cx
                    y1 += cy
                    x += cx
                    y += cy
                ops.append(PathOp(op="quadratic", points=(
                    add_point(x1, y1),
                    add_point(x, y),
                )))
                cx, cy = x, y
                last_quad_control = (x1, y1)
            last_cubic_control = None

        elif c in (SVGCommand.QUADRATIC_BEZIER_SMOOTH, SVGCommand.QUADRATIC_BEZIER_SMOOTH_REL):
            rel = c == SVGCommand.QUADRATIC_BEZIER_SMOOTH_REL
            for i in range(0, len(params), 2):
                x, y = params[i:i + 2]
                if rel:
                    x += cx
                    y += cy
                if last_quad_control is None:
                    x1, y1 = cx, cy
                else:
                    x1 = 2 * cx - last_quad_control[0]
                    y1 = 2 * cy - last_quad_control[1]
                ops.append(PathOp(op="quadratic", points=(
                    add_point(x1, y1),
                    add_point(x, y),
                )))
                cx, cy = x, y
                last_quad_control = (x1, y1)
            last_cubic_control = None

        elif c in (SVGCommand.ARC, SVGCommand.ARC_REL):
            raise UnsupportedFeatureError(
                "SVG path arc commands (A/a) are not yet supported by the "
                "compiler. No shipped template uses arcs; raising rather "
                "than silently dropping. Track: follow-up PR."
            )

        elif c in (SVGCommand.CLOSE, SVGCommand.CLOSE_REL):
            ops.append(PathOp(op="close"))
            cx, cy = sx, sy
            last_cubic_control = None
            last_quad_control = None

    bbox = (
        min(seen_xs) if seen_xs else 0.0,
        min(seen_ys) if seen_ys else 0.0,
        max(seen_xs) if seen_xs else 0.0,
        max(seen_ys) if seen_ys else 0.0,
    )
    return ops, bbox


def _resolve_paint_and_stroke(
    shape: object,
    bbox_pts: tuple[float, float, float, float] | None = None,
    panel: Panel | None = None,
) -> tuple[PaintU | None, Stroke | None]:
    """Convert ``shape.fill`` / ``shape.fill_color`` / ``shape.stroke_*`` into
    IR paint (``PaintU``) + ``Stroke`` (or ``None`` for no fill/stroke).

    Solid, linear-gradient, radial-gradient, and pattern fills all
    convert to their corresponding ``PaintU`` member. Gradients need
    the shape's bounding box (in points, page-absolute) to resolve
    relative gradient coordinates into absolute ones — callers that
    intend to use a gradient/pattern fill must pass ``bbox_pts``.
    Solid-only shapes (lines, things without a fill) can omit it.
    """
    fill_attr = getattr(shape, "fill", None)
    fill_color_attr = getattr(shape, "fill_color", None)
    stroke_color_attr = getattr(shape, "stroke_color", None)
    stroke_width_attr = getattr(shape, "stroke_width", 0.0)

    fill: PaintU | None
    if fill_attr is not None:
        from holiday_card.core.models import (  # local: keep top-of-file tidy
            LinearGradientFill,
            PatternFill,
            RadialGradientFill,
            SolidFill,
        )

        if isinstance(fill_attr, SolidFill):
            fill = SolidPaint(color=_hex_to_rgba(fill_attr.color))
        elif isinstance(fill_attr, LinearGradientFill):
            if bbox_pts is None:
                raise UnsupportedFeatureError(
                    "LinearGradientFill requires a bounding box from the caller "
                    f"(shape {type(shape).__name__})"
                )
            fill = _linear_gradient_to_paint(fill_attr, bbox_pts)
        elif isinstance(fill_attr, RadialGradientFill):
            if panel is None:
                raise UnsupportedFeatureError(
                    "RadialGradientFill requires panel context from the caller "
                    f"(shape {type(shape).__name__})"
                )
            fill = _radial_gradient_to_paint(fill_attr, panel)
        elif isinstance(fill_attr, PatternFill):
            fill = _pattern_to_paint(fill_attr)
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


def _linear_gradient_to_paint(
    fill: object,
    bbox_pts: tuple[float, float, float, float],
) -> LinearGradientPaint:
    """Convert a ``LinearGradientFill`` (model) to ``LinearGradientPaint`` (IR).

    The model carries an *angle in degrees* (0° = horizontal,
    pointing right; 90° = vertical, pointing up). The IR carries
    explicit ``start`` and ``end`` points in absolute page-points.
    We resolve the angle against the shape's bounding box: the
    gradient line crosses the center of the bbox at the given
    angle, with the endpoints at the bbox edges along that axis.
    """
    import math

    from holiday_card.core.models import LinearGradientFill
    assert isinstance(fill, LinearGradientFill)
    x, y, w, h = bbox_pts
    cx = x + w / 2
    cy = y + h / 2
    # Half-diagonal projected onto the gradient axis — gives the
    # endpoints as the points where the perpendicular to the
    # gradient line tangent to the bbox would be.
    rad = math.radians(fill.angle)
    half_w = w / 2
    half_h = h / 2
    # Project the bbox half-extents onto the gradient direction.
    dx = math.cos(rad)
    dy = math.sin(rad)
    extent = abs(dx) * half_w + abs(dy) * half_h
    start = Point(x=cx - dx * extent, y=cy - dy * extent)
    end = Point(x=cx + dx * extent, y=cy + dy * extent)
    stops = tuple(
        GradientStop(position=s.position, color=_hex_to_rgba(s.color))
        for s in fill.stops
    )
    return LinearGradientPaint(start=start, end=end, stops=stops)


def _radial_gradient_to_paint(
    fill: object,
    panel: Panel,
) -> RadialGradientPaint:
    """Convert a ``RadialGradientFill`` (model) to ``RadialGradientPaint`` (IR).

    The model carries ``center_x`` / ``center_y`` / ``radius`` in
    panel-relative inches (the convention shipped templates use).
    The compiler translates to page-absolute points by adding the
    panel offset and converting inches → points.
    """
    from holiday_card.core.models import RadialGradientFill
    assert isinstance(fill, RadialGradientFill)
    cx_pt = inches_to_points(panel.x + fill.center_x)
    cy_pt = inches_to_points(panel.y + fill.center_y)
    radius_pt = inches_to_points(fill.radius)
    stops = tuple(
        GradientStop(position=s.position, color=_hex_to_rgba(s.color))
        for s in fill.stops
    )
    return RadialGradientPaint(
        center=Point(x=cx_pt, y=cy_pt), radius=radius_pt, stops=stops
    )


def _pattern_to_paint(fill: object) -> PatternPaint:
    """Convert a ``PatternFill`` (model, spacing in inches) to ``PatternPaint``
    (IR, spacing in points)."""
    from holiday_card.core.models import PatternFill
    assert isinstance(fill, PatternFill)
    return PatternPaint(
        pattern=fill.pattern_type.value,
        colors=tuple(_hex_to_rgba(c) for c in fill.colors),
        spacing=inches_to_points(fill.spacing),
        scale=fill.scale,
        rotation_deg=fill.rotation,
    )


def _shape_bbox_pts(
    shape: object, panel: Panel,
) -> tuple[float, float, float, float]:
    """Return the shape's bounding box in page-absolute points.

    Used by gradient resolution so the compiler can compute absolute
    gradient endpoints / radial centers without re-implementing each
    shape's geometry in the paint converter.

    Returns ``(x, y, width, height)`` where ``(x, y)`` is the
    bottom-left corner.
    """
    if isinstance(shape, Rectangle):
        return (
            inches_to_points(panel.x + shape.x),
            inches_to_points(panel.y + shape.y),
            inches_to_points(shape.width),
            inches_to_points(shape.height),
        )
    if isinstance(shape, Circle):
        cx_pt = inches_to_points(panel.x + shape.center_x)
        cy_pt = inches_to_points(panel.y + shape.center_y)
        r_pt = inches_to_points(shape.radius)
        return (cx_pt - r_pt, cy_pt - r_pt, 2 * r_pt, 2 * r_pt)
    if isinstance(shape, Triangle):
        xs = [
            inches_to_points(panel.x + shape.x1),
            inches_to_points(panel.x + shape.x2),
            inches_to_points(panel.x + shape.x3),
        ]
        ys = [
            inches_to_points(panel.y + shape.y1),
            inches_to_points(panel.y + shape.y2),
            inches_to_points(panel.y + shape.y3),
        ]
        return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    if isinstance(shape, Star):
        cx_pt = inches_to_points(panel.x + shape.center_x)
        cy_pt = inches_to_points(panel.y + shape.center_y)
        outer_pt = inches_to_points(shape.outer_radius)
        return (cx_pt - outer_pt, cy_pt - outer_pt, 2 * outer_pt, 2 * outer_pt)
    if isinstance(shape, Line):
        x1 = inches_to_points(panel.x + shape.start_x)
        x2 = inches_to_points(panel.x + shape.end_x)
        y1 = inches_to_points(panel.y + shape.start_y)
        y2 = inches_to_points(panel.y + shape.end_y)
        return (
            min(x1, x2), min(y1, y2),
            max(abs(x2 - x1), 1.0), max(abs(y2 - y1), 1.0),
        )
    raise UnsupportedFeatureError(
        f"_shape_bbox_pts: unknown shape type {type(shape).__name__}"
    )


# ---------------------------------------------------------------------------
# Text compilation
# ---------------------------------------------------------------------------


def _compile_text(
    text: TextElement,
    panel: Panel,
    measurer: _reportlab_canvas.Canvas,
) -> list[RenderCommand]:
    """Run the overflow strategy and emit one ``DrawText`` per resulting line.

    Hard line breaks (``\\n`` in ``text.content``) split into separate
    visual lines before any width-based wrapping runs — so a poem or
    address keeps its author-intended structure even inside a width
    constraint. Empty content emits no commands (supports blank-inside
    cards).

    When ``text.rich_content`` is set, dispatch to the dedicated rich-
    text layout pass (``--inside-message-md`` / Christmas-letter mode).
    Rich content takes priority over ``text.content`` per the model's
    docstring contract.

    Uses ``Helvetica`` as the font_id when no custom font is registered,
    matching the legacy renderer's default. Backends are responsible for
    resolving the font_id to a real font.
    """
    from holiday_card.core.text_utils import calculate_line_height  # local: small module

    if text.letter_content is not None and not text.letter_content.is_empty():
        return _compile_letter_content(text, panel, measurer)

    if text.rich_content is not None:
        return _compile_rich_text(text, panel, measurer)

    if not text.content:
        return []  # blank-inside

    font_id = text.font_family or "Helvetica"
    color = _color_to_rgba(text.color) if text.color else RGBA(r=0, g=0, b=0)
    align = text.alignment.value  # already "left"/"center"/"right" by enum

    # Hard line breaks first; width-based wrapping happens per-segment.
    hard_segments = text.content.split("\n")

    if text.width:
        final_size = text.font_size
        all_lines: list[str] = []
        for segment in hard_segments:
            if not segment:
                all_lines.append("")  # preserve blank lines for stanza spacing
                continue
            # Run the overflow strategy on this segment alone. We use a
            # transient TextElement so fit_text_element doesn't see the
            # joined-by-newline string.
            seg_element = text.model_copy(update={"content": segment})
            seg_size, seg_lines, _ = fit_text_element(measurer, seg_element, panel, font_id)
            # If any segment shrinks, the smallest size wins for the whole
            # block (avoids per-line size jitter in a stanza).
            final_size = min(final_size, seg_size)
            all_lines.extend(seg_lines)
        lines = all_lines
    else:
        final_size = text.font_size
        lines = hard_segments

    abs_x = inches_to_points(panel.x + text.x)
    abs_y = inches_to_points(panel.y + text.y)
    line_height = calculate_line_height(final_size)

    commands: list[RenderCommand] = []
    for i, line in enumerate(lines):
        if not line:
            continue  # blank line consumes vertical space below but emits nothing
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
# Rich-text compilation (Markdown / Christmas-letter mode)
# ---------------------------------------------------------------------------


def _compile_rich_text(
    text: TextElement,
    panel: Panel,
    measurer: _reportlab_canvas.Canvas,
) -> list[RenderCommand]:
    """Lay out a ``RichTextContent`` block into ``DrawText`` commands.

    Walks paragraphs → hard lines → wrapped lines → styled segments,
    emitting one ``DrawText`` per styled segment with an x-offset
    that places it after the previous segment on the same wrapped
    line. Bold runs use the bold font_id (``font_id_for_run``).

    Wrapping is greedy by word against ``text.width``. Hard line
    breaks (single newlines in the source) split inside paragraphs;
    blank lines in the source separate paragraphs and add
    ``text.paragraph_spacing * line_height`` of vertical space.
    """
    from holiday_card.core.markdown import font_id_for_run
    from holiday_card.core.text_utils import calculate_line_height

    assert text.rich_content is not None
    color = _color_to_rgba(text.color) if text.color else RGBA(r=0, g=0, b=0)
    align = text.alignment.value
    font_family = text.font_family or "Helvetica"
    font_size = text.font_size
    line_height = calculate_line_height(font_size)
    paragraph_gap = line_height * text.paragraph_spacing

    abs_x = inches_to_points(panel.x + text.x)
    abs_y = inches_to_points(panel.y + text.y)
    max_width_pt = (
        inches_to_points(text.width) if text.width else float("inf")
    )

    commands: list[RenderCommand] = []
    cursor_y = abs_y
    for p_index, paragraph in enumerate(text.rich_content.paragraphs):
        if p_index > 0:
            cursor_y -= paragraph_gap
        for hard_line in paragraph.hard_lines:
            wrapped_lines = _wrap_styled_runs(
                hard_line, max_width_pt, font_family, font_size, measurer,
            )
            for wrapped in wrapped_lines:
                # Emit one DrawText per styled segment on this line,
                # x-offset by the cumulative width of preceding segments.
                offset = 0.0
                for run in wrapped:
                    font_id = font_id_for_run(font_family, bold=run.bold)
                    seg_width = measurer.stringWidth(
                        run.text, font_id, font_size,
                    )
                    commands.append(
                        DrawText(
                            run=TextRun(
                                text=run.text,
                                origin=Point(x=abs_x + offset, y=cursor_y),
                                font_id=font_id,
                                size_pt=float(font_size),
                                color=color,
                                align=align,  # type: ignore[arg-type]
                            ),
                        )
                    )
                    offset += seg_width
                cursor_y -= line_height
    return commands


def _wrap_styled_runs(
    runs: list,
    max_width_pt: float,
    font_family: str,
    font_size: int,
    measurer: _reportlab_canvas.Canvas,
) -> list[list]:
    """Greedy word-wrap a sequence of styled runs into lines.

    Each input run carries its own ``bold`` flag; the wrapping
    measures each word in its own font (regular vs bold) so the
    wrap point is correct even when a long bold span shoves text
    onto the next line.

    Output is a list of lines; each line is a list of styled runs
    (the input runs may be split further if a single word starts a
    new line). Empty lines are filtered.
    """
    from holiday_card.core.markdown import StyledRun, font_id_for_run

    if max_width_pt == float("inf"):
        return [runs]  # unconstrained — emit as one line

    lines: list[list] = []
    current_line: list = []
    current_width = 0.0

    for run in runs:
        font_id = font_id_for_run(font_family, bold=run.bold)
        # Split on whitespace but keep visible spacing — reassemble
        # with a space between words.
        words = run.text.split(" ")
        # Track whether we're at a "word boundary" inside the run
        # (the first word doesn't need a leading space; subsequent
        # words do, IF there's already content on the current line).
        for i, word in enumerate(words):
            if word == "":
                continue  # collapsed multi-space; skip
            # Build the candidate text including the inter-word space
            # if this isn't the very first thing on the line.
            needs_leading_space = bool(current_line) or i > 0
            candidate = (" " + word) if needs_leading_space else word
            candidate_width = measurer.stringWidth(candidate, font_id, font_size)

            if current_width + candidate_width > max_width_pt and current_line:
                # Wrap: flush the current line and start a new one
                # with this word at column 0.
                lines.append(current_line)
                current_line = []
                current_width = 0.0
                candidate = word
                candidate_width = measurer.stringWidth(candidate, font_id, font_size)

            # Append: merge with the previous run if same style, else
            # start a new styled segment on this line.
            if current_line and current_line[-1].bold == run.bold:
                merged = StyledRun(
                    text=current_line[-1].text + candidate, bold=run.bold,
                )
                current_line[-1] = merged
            else:
                current_line.append(StyledRun(text=candidate, bold=run.bold))
            current_width += candidate_width

    if current_line:
        lines.append(current_line)
    return lines


# ---------------------------------------------------------------------------
# Letter compilation (structured salutation / body / signoff / signature / P.S.)
# ---------------------------------------------------------------------------


# Vertical-spacing conventions for the inside-letter layout. Each is
# expressed as a multiple of the *body* line height so layout scales
# with the TextElement's font_size without per-call constants leaking
# out. The values match handwritten-letter visual rhythm:
#
# * Salutation → body: one blank line (paragraph break).
# * Body → signoff: one and a half blank lines (signoff lands lower
#   than a normal paragraph break to read as a closing).
# * Signoff → signature: tight, like a real handwritten letter where
#   "Love," and the name almost touch.
# * Signature → P.S.: two blank lines (P.S. is its own visual block).
#
# P.S. renders at 85% of the body font size — the conventional
# greeting-card "afterthought" feel.
_LETTER_GAP_AFTER_SALUTATION = 1.0
_LETTER_GAP_AFTER_BODY = 1.5
_LETTER_GAP_AFTER_SIGNOFF = 0.4
_LETTER_GAP_AFTER_SIGNATURE = 2.0
_POSTSCRIPT_SIZE_RATIO = 0.85


def _compile_letter_content(
    text: TextElement,
    panel: Panel,
    measurer: _reportlab_canvas.Canvas,
) -> list[RenderCommand]:
    """Lay out a ``LetterContent`` instance into ``DrawText`` commands.

    The five parts (salutation, body, signoff, signature, postscript)
    are stacked top-to-bottom from the text element's origin with
    conventional gaps (see the ``_LETTER_GAP_*`` constants above).
    Every part respects ``text.width`` for greedy word-wrapping;
    embedded newlines in ``body`` split into hard line breaks before
    width-wrapping runs. Empty parts are skipped (no command emitted,
    no vertical space consumed) so the layout naturally collapses
    around whichever parts the user supplied.

    Font handling: every part uses ``text.font_family`` and
    ``text.font_size`` *except*:

    * The signature line uses
      ``letter.signature_font_family or text.font_family`` — the
      override exists for the handwritten-feel convention
      (``Caveat`` is the curated choice).
    * The P.S. renders at ``font_size * 0.85`` (rounded) in
      ``text.font_family``.
    """
    from holiday_card.core.text_utils import calculate_line_height, wrap_text

    assert text.letter_content is not None
    letter = text.letter_content
    color = _color_to_rgba(text.color) if text.color else RGBA(r=0, g=0, b=0)
    align = text.alignment.value
    font_family = text.font_family or "Helvetica"
    body_size = text.font_size
    body_line_height = calculate_line_height(body_size)

    abs_x = inches_to_points(panel.x + text.x)
    abs_y = inches_to_points(panel.y + text.y)
    max_width_pt = inches_to_points(text.width) if text.width else float("inf")

    commands: list[RenderCommand] = []
    cursor_y = abs_y
    previous_emitted = False

    def emit_block(
        content: str,
        *,
        font_id: str,
        size: int,
        gap_before_lines: float,
    ) -> None:
        """Emit one logical letter part (possibly multi-line)."""
        nonlocal cursor_y, previous_emitted
        if not content:
            return
        if previous_emitted:
            cursor_y -= body_line_height * gap_before_lines
        line_height = calculate_line_height(size)
        # Hard line breaks split first; width-wrap each segment.
        hard_segments = content.split("\n")
        rendered_lines: list[str] = []
        for segment in hard_segments:
            if not segment.strip():
                rendered_lines.append("")
                continue
            if max_width_pt == float("inf"):
                rendered_lines.append(segment)
            else:
                rendered_lines.extend(
                    wrap_text(measurer, segment, font_id, size, max_width_pt)
                )
        for line in rendered_lines:
            if line:
                commands.append(
                    DrawText(
                        run=TextRun(
                            text=line,
                            origin=Point(x=abs_x, y=cursor_y),
                            font_id=font_id,
                            size_pt=float(size),
                            color=color,
                            align=align,  # type: ignore[arg-type]
                        ),
                    )
                )
            cursor_y -= line_height
        previous_emitted = True

    # Salutation
    emit_block(
        letter.salutation,
        font_id=font_family,
        size=body_size,
        gap_before_lines=0.0,  # first block, no gap above
    )
    # Body
    emit_block(
        letter.body,
        font_id=font_family,
        size=body_size,
        gap_before_lines=_LETTER_GAP_AFTER_SALUTATION,
    )
    # Signoff
    emit_block(
        letter.signoff,
        font_id=font_family,
        size=body_size,
        gap_before_lines=_LETTER_GAP_AFTER_BODY,
    )
    # Signature — distinct font allowed
    signature_font = letter.signature_font_family or font_family
    emit_block(
        letter.signature,
        font_id=signature_font,
        size=body_size,
        gap_before_lines=_LETTER_GAP_AFTER_SIGNOFF,
    )
    # P.S. at 85% size
    postscript_size = max(6, round(body_size * _POSTSCRIPT_SIZE_RATIO))
    emit_block(
        letter.postscript,
        font_id=font_family,
        size=postscript_size,
        gap_before_lines=_LETTER_GAP_AFTER_SIGNATURE,
    )

    return commands


# ---------------------------------------------------------------------------
# Image compilation (ImageElement → DrawImage with optional clip + rotation)
# ---------------------------------------------------------------------------


def _compile_image(image: ImageElement, panel: Panel) -> list[RenderCommand]:
    """Convert an ``ImageElement`` to IR commands.

    Layout sequence (outer → inner):

    * If ``image.rotation`` is non-zero, wrap everything in a
      ``BeginGroup`` / ``EndGroup`` carrying a pivot-rotate transform
      around the image center (same idiom as panel rotation; see the
      ``Transform`` semantics in ``render_ir.py``).
    * If ``image.clip_mask`` is set, wrap the ``DrawImage`` in
      ``BeginClip`` / ``EndClip`` with the geometry resolved from
      the ClipMask type. Clip-mask coords are panel-relative inches
      (matching the convention real templates ship — see
      ``templates/christmas/photo-ornament.yaml``).
    * Emit the ``DrawImage`` carrying an ``ImageRef`` with the
      resolved absolute file path and the rectangle in page-points.

    Deferred for v1 (raise ``UnsupportedFeatureError`` if encountered):

    * ``image.effects`` — Pillow image effects (sepia / grayscale /
      vignette / blur). Need a pre-rendering pass on the source bytes.
    * ``image.frame_style`` != ``PhotoFrameStyle.NONE`` — frame
      treatments need an outline pass.
    * ``image.width`` or ``image.height`` is ``None`` — auto-sizing
      from the source image's natural dimensions needs a Pillow probe.
    * Clip mask types ``heart`` and ``svg_path`` — Heart needs synthesis
      to a path; SVGPath needs the parser wired to ``PathGeom``.
    """
    from holiday_card.core.models import PhotoFrameStyle  # local: enum only used here

    if image.effects is not None:
        raise UnsupportedFeatureError(
            f"ImageElement.effects (sepia/grayscale/vignette/blur) not yet "
            f"supported by the compiler (element id {image.id!r}). "
            f"Track: Wave 2 follow-up PR (image effects)."
        )
    if image.frame_style != PhotoFrameStyle.NONE:
        raise UnsupportedFeatureError(
            f"ImageElement.frame_style={image.frame_style.value!r} not yet "
            f"supported by the compiler (element id {image.id!r}). "
            f"Track: Wave 2 follow-up PR (image frames)."
        )
    if image.width is None or image.height is None:
        raise UnsupportedFeatureError(
            f"ImageElement requires explicit width and height in v1 "
            f"(element id {image.id!r}). "
            f"Auto-sizing from natural image dimensions is a follow-up."
        )

    # Resolve relative paths against CWD so the IR carries an absolute
    # path the backends can pass to drawImage/embed unchanged.
    from pathlib import Path as _Path
    source_abs = str(_Path(image.source_path).resolve())

    # Image rect in page-points (panel-relative inches → absolute points).
    x_pt = inches_to_points(panel.x + image.x)
    y_pt = inches_to_points(panel.y + image.y)
    width_pt = inches_to_points(image.width)
    height_pt = inches_to_points(image.height)

    image_ref = ImageRef(
        source=source_abs,
        rect=RectGeom(x=x_pt, y=y_pt, width=width_pt, height=height_pt),
        preserve_aspect=image.preserve_aspect,
    )
    draw = DrawImage(image=image_ref, opacity=image.opacity)

    # Inner layer: optional clip wrapping the DrawImage.
    inner: list[RenderCommand] = []
    if image.clip_mask is not None:
        inner.append(BeginClip(geometry=_clip_mask_to_geom(image.clip_mask, panel)))
    inner.append(draw)
    if image.clip_mask is not None:
        inner.append(EndClip())

    # Outer layer: optional rotation group around the image center.
    if image.rotation != 0:
        cx_pt = x_pt + width_pt / 2
        cy_pt = y_pt + height_pt / 2
        transform = Transform(
            translate_x=cx_pt,
            translate_y=cy_pt,
            rotate_deg=image.rotation,
        )
        return [BeginGroup(transform=transform), *inner, EndGroup()]
    return inner


def _clip_mask_to_geom(
    clip: CircleClipMask | RectangleClipMask | EllipseClipMask | StarClipMask,
    panel: Panel,
) -> GeomU:
    """Convert a :class:`ClipMask` discriminated-union member to IR geometry.

    Coordinate convention: shipped templates put clip-mask coords in
    panel-relative inches (verified against
    ``templates/christmas/photo-ornament.yaml`` and
    ``holiday-masterpiece.yaml``). The model's docstring says "relative
    to image" but no shipped template uses it that way; following the
    template behavior is the load-bearing constraint.

    Returns one of ``CircleGeom`` / ``RectGeom`` / ``EllipseGeom`` /
    ``PolygonGeom``.
    """
    import math

    if isinstance(clip, CircleClipMask):
        return CircleGeom(
            center=Point(
                x=inches_to_points(panel.x + clip.center_x),
                y=inches_to_points(panel.y + clip.center_y),
            ),
            radius=inches_to_points(clip.radius),
        )
    if isinstance(clip, RectangleClipMask):
        return RectGeom(
            x=inches_to_points(panel.x + clip.x),
            y=inches_to_points(panel.y + clip.y),
            width=inches_to_points(clip.width),
            height=inches_to_points(clip.height),
        )
    if isinstance(clip, EllipseClipMask):
        return EllipseGeom(
            center=Point(
                x=inches_to_points(panel.x + clip.center_x),
                y=inches_to_points(panel.y + clip.center_y),
            ),
            rx=inches_to_points(clip.radius_x),
            ry=inches_to_points(clip.radius_y),
        )
    if isinstance(clip, StarClipMask):
        cx_pt = inches_to_points(panel.x + clip.center_x)
        cy_pt = inches_to_points(panel.y + clip.center_y)
        outer_pt = inches_to_points(clip.outer_radius)
        inner_pt = inches_to_points(clip.inner_radius)
        n = clip.points
        # Match ``_compile_star``'s angular convention (π/2 + i*π/n)
        # so a clip-mask star and a Star shape with the same params
        # render in the same orientation.
        points: list[Point] = []
        for i in range(n * 2):
            angle = math.pi / 2 + i * math.pi / n
            radius = outer_pt if i % 2 == 0 else inner_pt
            points.append(Point(
                x=cx_pt + radius * math.cos(angle),
                y=cy_pt + radius * math.sin(angle),
            ))
        return PolygonGeom(points=tuple(points))
    raise UnsupportedFeatureError(
        f"Unknown ClipMask type {type(clip).__name__}."
    )


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

    Registers the embedded default + curated font chains so
    ``canvas.stringWidth`` works on any font_id those chains expose
    (Helvetica/Times/Courier for backwards-compat, plus the curated
    PlayfairDisplay/Cormorant/Lato/Inter/Caveat/Comfortaa). The text-
    fitting code calls ``stringWidth`` to size lines; without
    registration, ReportLab raises ``KeyError`` on any unrecognized
    font name.

    Reusing this single canvas across one ``compile_card`` call is
    safe because the canvas is stateless w.r.t. measurement, and font
    registration is process-global and idempotent.
    """
    from holiday_card.renderers.font_registry import ensure_default_fonts_registered
    ensure_default_fonts_registered()
    return _reportlab_canvas.Canvas(io.BytesIO(), pagesize=letter)
