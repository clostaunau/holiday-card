"""Backend-neutral rendering intermediate representation (IR).

This module defines the eleven ``RenderCommand`` types — a frozen,
discriminated union — that sit between the domain model (``Card``) and any
rendering backend (ReportLab, future SVG/PNG/preview). The compiler
(see Wave 2 Step 2) lowers a ``Card`` to a ``list[RenderCommand]``;
backends consume that list with no further decisions.

Design notes:

* Coordinate space is **points** (1/72 inch) with the page origin at
  **bottom-left** (matching ReportLab and the PDF spec). The single
  inches→points conversion happens in the compiler, never here and never
  in a backend.
* All commands and value objects are **immutable** (Pydantic
  ``model_config = {"frozen": True}``). This lets backends safely cache,
  hash, or parallelize commands.
* Stateful effects (``saveState``/``restoreState``, clip paths, transforms)
  are modeled as **paired commands** — ``BeginGroup``/``EndGroup`` and
  ``BeginClip``/``EndClip``. ``assert_balanced`` enforces pairing so
  malformed nesting cannot ship.
* No backend imports allowed. No ReportLab, no Pillow, no YAML. This file
  is the contract; the contract has no dependencies.

This module has **no callers** in production code. It is the additive
first step (Wave 2 Step 1) of the migration plan in
``/tmp/wave2_architecture.md``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    # Value objects
    "Point",
    "RGBA",
    "Stroke",
    "Transform",
    "GradientStop",
    "TextRun",
    "ImageRef",
    # Paint variants and union
    "SolidPaint",
    "LinearGradientPaint",
    "RadialGradientPaint",
    "PatternPaint",
    "PaintU",
    # Geometry variants and union
    "RectGeom",
    "CircleGeom",
    "EllipseGeom",
    "PolygonGeom",
    "PolylineGeom",
    "PathGeom",
    "PathOp",
    "GeomU",
    # Commands and union
    "DrawShape",
    "DrawText",
    "DrawImage",
    "BeginGroup",
    "EndGroup",
    "BeginClip",
    "EndClip",
    "DrawFoldLine",
    "SetMetadata",
    "BeginPage",
    "EndPage",
    "RenderCommand",
    # Helpers
    "assert_balanced",
]


class _IRBase(BaseModel):
    """Base for every IR type: frozen, no extra fields tolerated."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class Point(_IRBase):
    """A 2D point in points (1/72 inch), origin at page bottom-left."""

    x: float
    y: float


class RGBA(_IRBase):
    """RGBA color, all channels in [0.0, 1.0]."""

    r: float = Field(ge=0.0, le=1.0)
    g: float = Field(ge=0.0, le=1.0)
    b: float = Field(ge=0.0, le=1.0)
    a: float = Field(default=1.0, ge=0.0, le=1.0)


class Stroke(_IRBase):
    """Stroke spec applied per-shape (no setter-state in the IR)."""

    color: RGBA
    width: float = Field(gt=0.0, description="Stroke width in points")
    dash: tuple[float, ...] = ()
    line_cap: Literal["butt", "round", "square"] = "butt"


class Transform(_IRBase):
    """Affine transform for ``BeginGroup``.

    The compiler is expected to resolve any "rotate around shape center"
    semantics into the explicit translate/rotate values stored here, so the
    backend never has to compute pivots.
    """

    translate_x: float = 0.0
    translate_y: float = 0.0
    rotate_deg: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0


# ---------------------------------------------------------------------------
# Paint (discriminated union)
# ---------------------------------------------------------------------------


class GradientStop(_IRBase):
    position: float = Field(ge=0.0, le=1.0)
    color: RGBA


class SolidPaint(_IRBase):
    kind: Literal["solid"] = "solid"
    color: RGBA


class LinearGradientPaint(_IRBase):
    kind: Literal["linear_gradient"] = "linear_gradient"
    start: Point
    end: Point
    stops: tuple[GradientStop, ...] = Field(min_length=2)


class RadialGradientPaint(_IRBase):
    kind: Literal["radial_gradient"] = "radial_gradient"
    center: Point
    radius: float = Field(gt=0.0)
    stops: tuple[GradientStop, ...] = Field(min_length=2)


class PatternPaint(_IRBase):
    kind: Literal["pattern"] = "pattern"
    pattern: Literal["stripes", "dots", "grid", "checkerboard"]
    colors: tuple[RGBA, ...] = Field(min_length=1)
    spacing: float = Field(gt=0.0, description="Pattern spacing in points")
    scale: float = Field(default=1.0, gt=0.0)
    rotation_deg: float = 0.0


PaintU = Annotated[
    SolidPaint | LinearGradientPaint | RadialGradientPaint | PatternPaint,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Geometry (discriminated union)
# ---------------------------------------------------------------------------


class RectGeom(_IRBase):
    kind: Literal["rect"] = "rect"
    x: float
    y: float
    width: float = Field(gt=0.0)
    height: float = Field(gt=0.0)
    corner_radius: float = Field(default=0.0, ge=0.0)


class CircleGeom(_IRBase):
    kind: Literal["circle"] = "circle"
    center: Point
    radius: float = Field(gt=0.0)


class EllipseGeom(_IRBase):
    kind: Literal["ellipse"] = "ellipse"
    center: Point
    rx: float = Field(gt=0.0)
    ry: float = Field(gt=0.0)


class PolygonGeom(_IRBase):
    """Closed polygon. Backends should auto-close if first != last."""

    kind: Literal["polygon"] = "polygon"
    points: tuple[Point, ...] = Field(min_length=3)


class PolylineGeom(_IRBase):
    """Open polyline (not auto-closed)."""

    kind: Literal["polyline"] = "polyline"
    points: tuple[Point, ...] = Field(min_length=2)


class PathOp(_IRBase):
    """One sub-operation of a ``PathGeom``.

    Point counts: ``move``=1, ``line``=1, ``cubic``=3 (cp1, cp2, end),
    ``quadratic``=2 (cp, end), ``close``=0.
    """

    op: Literal["move", "line", "cubic", "quadratic", "close"]
    points: tuple[Point, ...] = ()


class PathGeom(_IRBase):
    """Resolved absolute path. Star, triangle, SVG, decorative components,
    and clip masks all compile down to this when simpler primitives don't fit.
    """

    kind: Literal["path"] = "path"
    ops: tuple[PathOp, ...] = Field(min_length=1)


GeomU = Annotated[
    RectGeom | CircleGeom | EllipseGeom | PolygonGeom | PolylineGeom | PathGeom,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Resolved text / image (compiler has already chosen fonts and sizes)
# ---------------------------------------------------------------------------


class TextRun(_IRBase):
    """A single, already-wrapped, already-shrunk line of text at a point."""

    text: str
    origin: Point
    font_id: str = Field(min_length=1, description="Opaque id; backend resolves")
    size_pt: float = Field(gt=0.0)
    color: RGBA
    align: Literal["left", "center", "right"] = "left"


class ImageRef(_IRBase):
    """Reference to an image with its render rect already resolved.

    Image effects (grayscale/sepia/vignette/blur) are applied by the
    compiler before the IR is emitted; ``source`` may point to a temp file
    holding the post-effect bytes.
    """

    source: str = Field(min_length=1)
    rect: RectGeom
    preserve_aspect: bool = True


# ---------------------------------------------------------------------------
# The eleven commands
# ---------------------------------------------------------------------------


class DrawShape(_IRBase):
    cmd: Literal["draw_shape"] = "draw_shape"
    geometry: GeomU
    fill: PaintU | None = None
    stroke: Stroke | None = None
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class DrawText(_IRBase):
    cmd: Literal["draw_text"] = "draw_text"
    run: TextRun
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class DrawImage(_IRBase):
    cmd: Literal["draw_image"] = "draw_image"
    image: ImageRef
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class BeginGroup(_IRBase):
    """Push a graphics state with optional transform and group opacity."""

    cmd: Literal["begin_group"] = "begin_group"
    transform: Transform = Transform()
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class EndGroup(_IRBase):
    cmd: Literal["end_group"] = "end_group"


class BeginClip(_IRBase):
    """Push a clip region. Subsequent draws are clipped until ``EndClip``."""

    cmd: Literal["begin_clip"] = "begin_clip"
    geometry: GeomU


class EndClip(_IRBase):
    cmd: Literal["end_clip"] = "end_clip"


class DrawFoldLine(_IRBase):
    """Print-only construction guide. Backends without a print concept (e.g.
    a web preview) MAY ignore this, but should log a warning.
    """

    cmd: Literal["draw_fold_line"] = "draw_fold_line"
    start: Point
    end: Point
    style: Literal["dashed", "solid"] = "dashed"


class SetMetadata(_IRBase):
    """Attach producer metadata (template id, theme, fold type, ...).

    Backends MAY use this for PDF /Title or SVG <metadata>.
    """

    cmd: Literal["set_metadata"] = "set_metadata"
    key: str = Field(min_length=1)
    value: str


class BeginPage(_IRBase):
    """Begin a page. ``width`` / ``height`` are the **trim box** in points.

    The optional ``bleed`` extends the canvas (media box) past the trim
    edge by that many points on every side; backends are responsible for
    sizing their canvas to ``width + 2*bleed`` × ``height + 2*bleed`` and
    translating IR coordinates by ``+bleed`` so that IR ``(0, 0)`` lands
    at the trim box's bottom-left corner. ``safe_margin`` records the
    inset for the PDF /ArtBox; backends consume it metadata-only and do
    not enforce content placement against it (the compiler / templates do).
    """

    cmd: Literal["begin_page"] = "begin_page"
    width: float = Field(gt=0.0, description="Trim box width in points")
    height: float = Field(gt=0.0, description="Trim box height in points")
    bleed: float = Field(
        default=0.0, ge=0.0, description="Bleed extension past trim, in points"
    )
    safe_margin: float = Field(
        default=0.0, ge=0.0, description="Safe area inset from trim, in points"
    )


class EndPage(_IRBase):
    cmd: Literal["end_page"] = "end_page"


RenderCommand = Annotated[
    DrawShape
    | DrawText
    | DrawImage
    | BeginGroup
    | EndGroup
    | BeginClip
    | EndClip
    | DrawFoldLine
    | SetMetadata
    | BeginPage
    | EndPage,
    Field(discriminator="cmd"),
]


# ---------------------------------------------------------------------------
# Invariant checker
# ---------------------------------------------------------------------------

# Names used by assert_balanced. Pulled out so tests can reuse them.
_OPEN_TO_CLOSE: dict[str, str] = {
    "begin_group": "end_group",
    "begin_clip": "end_clip",
    "begin_page": "end_page",
}
_CLOSE_TO_OPEN: dict[str, str] = {v: k for k, v in _OPEN_TO_CLOSE.items()}


def assert_balanced(commands: Iterable[object]) -> None:
    """Verify ``BeginGroup``/``EndGroup``, ``BeginClip``/``EndClip``, and
    ``BeginPage``/``EndPage`` pairs are properly nested.

    Accepts any iterable of objects exposing a ``cmd`` attribute. Raises
    ``ValueError`` on the first imbalance, naming the offending command and
    the position in the list.

    Used as a free correctness gate at the end of the compile pass and in
    tests. Cheap (single linear scan, no backtracking).
    """
    stack: list[tuple[str, int]] = []
    for index, command in enumerate(commands):
        cmd = getattr(command, "cmd", None)
        if cmd is None:
            raise ValueError(
                f"command at index {index} is missing a `cmd` discriminator: {command!r}"
            )
        if cmd in _OPEN_TO_CLOSE:
            stack.append((cmd, index))
        elif cmd in _CLOSE_TO_OPEN:
            if not stack:
                raise ValueError(
                    f"unbalanced commands: {cmd!r} at index {index} has no matching open"
                )
            opened, opened_at = stack.pop()
            expected_close = _OPEN_TO_CLOSE[opened]
            if cmd != expected_close:
                raise ValueError(
                    f"unbalanced commands: {opened!r} at index {opened_at} "
                    f"closed by {cmd!r} at index {index} (expected {expected_close!r})"
                )
    if stack:
        opened, opened_at = stack[-1]
        raise ValueError(
            f"unbalanced commands: {opened!r} at index {opened_at} was never closed"
        )
