"""Transparency flattening for PDF/X output (D10, #71).

PDF/X-1a forbids live transparency. When a target asks for it
(``CompileContext.flatten_transparency``), the compiler runs every panel's
draws through :class:`Flattener`, which removes alpha in the IR:

* The effective alpha of a paint is ``opacity × paint alpha × every
  enclosing group opacity``. Group opacity is pushed down into the
  children, and the groups are re-emitted with ``opacity = 1``.
* A draw with an effective alpha below 1 needs a **known solid** backdrop.
  Walking the earlier draws of the panel from the top down, the first one
  that paints inside the draw's bounding box must be an opaque solid fill
  whose geometry contains that whole box (rect: box containment;
  circle/ellipse: all four box corners inside). If nothing earlier paints
  there, the backdrop is the paper (white).
* Colours are composited in sRGB, ``out = a·src + (1−a)·backdrop``, the
  same result the SVG / PNG previews show, and emitted with ``a = 1``.
* An image cannot be pre-blended here, so a ``DrawImage`` that is
  translucent or carries an alpha channel records the solid backdrop on
  ``ImageRef.backdrop``; the PDF backend flattens its pixels against it.
* Every other case (gradient, clipped pattern primitive, image or text
  backdrop, partial overlap, a translucent group whose children overlap,
  which includes a translucent pattern) raises
  ``UnsupportedFeatureError`` naming the element and the backdrop found.

Bounding boxes are compared in the panel's frame: group transforms and
clip regions are applied to each box, conservatively, as axis-aligned
boxes.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from holiday_card.core.errors import UnsupportedFeatureError
from holiday_card.core.render_ir import (
    RGBA,
    BeginClip,
    BeginGroup,
    CircleGeom,
    DrawImage,
    DrawShape,
    DrawText,
    EllipseGeom,
    EndClip,
    EndGroup,
    GeomU,
    GradientStop,
    PaintU,
    PathGeom,
    PolygonGeom,
    PolylineGeom,
    RectGeom,
    RenderCommand,
    SolidPaint,
    Stroke,
)

__all__ = ["Flattener", "PAPER", "flatten_transparency"]

PAPER = RGBA(r=1.0, g=1.0, b=1.0)

# (x0, y0, x1, y1) in points, panel frame.
Box = tuple[float, float, float, float]
# Affine (a, b, c, d, e, f): (x, y) → (a·x + c·y + e, b·x + d·y + f).
Matrix = tuple[float, float, float, float, float, float]

_IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
# Overlap / containment slack in points (float drift from inch conversion).
_EPS = 1e-6
# Text box: descenders reach about this fraction of the size below the baseline.
_DESCENT = 0.3


def flatten_transparency(
    commands: Iterable[RenderCommand], *, where: str
) -> list[RenderCommand]:
    """Flatten one command list as a single element (see the module doc).

    The compiler uses :class:`Flattener` directly so each element gets its
    own ``where``; this entry point is for hand-built IR.
    """
    return Flattener().element(commands, where=where)


@dataclass(frozen=True)
class _Painted:
    """An earlier draw in the panel, as seen by the backdrop search."""

    box: Box
    kind: str
    hits: Callable[[Box], bool]
    # The opaque colour this draw leaves everywhere inside ``box``, or None.
    covers: Callable[[Box], RGBA | None]
    groups: frozenset[int]
    # An opaque solid fill: a backdrop wherever its geometry contains the box.
    solid: bool = False


@dataclass(frozen=True)
class _Clip:
    box: Box
    # The exact clip region when it is an untransformed rect, else None.
    exact: Box | None


class Flattener:
    """Backdrop-tracking alpha flattener for the draws of one panel."""

    def __init__(self) -> None:
        self._painted: list[_Painted] = []
        self._next_group = 0

    def element(self, commands: Iterable[RenderCommand], *, where: str) -> list[RenderCommand]:
        """Flatten one element's commands; ``where`` names it in errors."""
        out: list[RenderCommand] = []
        matrices: list[Matrix] = [_IDENTITY]
        clips: list[_Clip] = []
        # (group token or None, opacity) per open group.
        groups: list[tuple[int | None, float]] = []
        for cmd in commands:
            if isinstance(cmd, BeginGroup):
                opacity = cmd.opacity
                token = None
                if opacity < 1.0:
                    token = self._next_group
                    self._next_group += 1
                    cmd = cmd.model_copy(update={"opacity": 1.0})
                groups.append((token, opacity))
                matrices.append(_compose(matrices[-1], cmd.transform.to_matrix()))
            elif isinstance(cmd, EndGroup):
                groups.pop()
                matrices.pop()
            elif isinstance(cmd, BeginClip):
                clips.append(_clip_for(cmd.geometry, matrices[-1]))
            elif isinstance(cmd, EndClip):
                clips.pop()
            elif isinstance(cmd, (DrawShape, DrawText, DrawImage)):
                flat = self._draw(cmd, matrices[-1], clips, groups, where)
                if flat is None:
                    continue  # fully transparent or clipped away: paints nothing
                cmd = flat
            out.append(cmd)
        return out

    # ------------------------------------------------------------------

    def _draw(
        self,
        cmd: DrawShape | DrawText | DrawImage,
        matrix: Matrix,
        clips: list[_Clip],
        groups: list[tuple[int | None, float]],
        where: str,
    ) -> DrawShape | DrawText | DrawImage | None:
        group_alpha = math.prod(op for _t, op in groups)
        if all(a <= 0.0 for a in _alphas(cmd, group_alpha)):
            return None
        tokens = frozenset(t for t, _op in groups if t is not None)
        box = _clip_box(_transform_box(_local_box(cmd), matrix), clips)
        if box is None:
            return None  # clipped away entirely
        what = _describe(cmd)

        def backdrop(alpha: float) -> RGBA:
            return self._backdrop(box, tokens, where=where, what=what, alpha=alpha)

        flat: DrawShape | DrawText | DrawImage
        if isinstance(cmd, DrawShape):
            flat = _flatten_shape(cmd, group_alpha, backdrop)
        elif isinstance(cmd, DrawText):
            flat = _flatten_text(cmd, group_alpha, backdrop)
        else:
            flat = self._flatten_image(cmd, group_alpha, box, tokens, where)
        self._painted.append(_record(flat, box, matrix, clips, tokens))
        return flat

    def _flatten_image(
        self, cmd: DrawImage, group_alpha: float, box: Box, tokens: frozenset[int], where: str
    ) -> DrawImage:
        alpha = group_alpha * cmd.opacity
        needs = alpha < 1.0 or _image_has_alpha(cmd.image.source)
        try:
            colour: RGBA | None = self._backdrop(
                box, tokens, where=where, what="image", alpha=alpha
            )
        except UnsupportedFeatureError:
            if needs:
                raise
            colour = None
        return cmd.model_copy(update={
            "opacity": alpha,
            "image": cmd.image.model_copy(update={"backdrop": colour}),
        })

    def _backdrop(
        self, box: Box, tokens: frozenset[int], *, where: str, what: str, alpha: float
    ) -> RGBA:
        for painted in reversed(self._painted):
            if not painted.hits(box):
                continue
            if painted.groups & tokens:
                raise UnsupportedFeatureError(
                    f"{where}: group opacity cannot be pushed down into a {what} "
                    f"that overlaps an earlier {painted.kind} of the same group "
                    f"(PDF/X targets forbid live transparency)"
                )
            colour = painted.covers(box)
            if colour is None:
                below = painted.kind
                if painted.solid:
                    below += " that does not fully contain it"
                raise UnsupportedFeatureError(
                    f"{where}: translucent {what} (alpha {alpha:.2f}) sits over a "
                    f"{below}; PDF/X targets need a solid backdrop that "
                    f"fully contains it. Put it over a solid fill or give it an "
                    f"opaque pre-blended colour"
                )
            return colour
        return PAPER


# ---------------------------------------------------------------------------
# Per-command flattening
# ---------------------------------------------------------------------------


def _blend(src: RGBA, alpha: float, backdrop: RGBA) -> RGBA:
    a = alpha * src.a
    return RGBA(
        r=a * src.r + (1 - a) * backdrop.r,
        g=a * src.g + (1 - a) * backdrop.g,
        b=a * src.b + (1 - a) * backdrop.b,
    )


def _alphas(cmd: DrawShape | DrawText | DrawImage, group_alpha: float) -> list[float]:
    alpha = group_alpha * cmd.opacity
    if isinstance(cmd, DrawShape):
        colours = _paint_colours(cmd.fill) + ([cmd.stroke.color] if cmd.stroke else [])
        return [alpha * c.a for c in colours]
    if isinstance(cmd, DrawText):
        return [alpha * cmd.run.color.a]
    return [alpha]


def _paint_colours(paint: PaintU | None) -> list[RGBA]:
    if paint is None:
        return []
    if isinstance(paint, SolidPaint):
        return [paint.color]
    return [s.color for s in paint.stops]


def _flatten_shape(
    cmd: DrawShape, group_alpha: float, backdrop: Callable[[float], RGBA]
) -> DrawShape:
    alpha = group_alpha * cmd.opacity
    colours = _paint_colours(cmd.fill) + ([cmd.stroke.color] if cmd.stroke else [])
    if not colours:
        return cmd.model_copy(update={"opacity": 1.0})  # paints nothing
    if all(alpha * c.a >= 1.0 for c in colours):
        return cmd
    bd = backdrop(min((alpha * c.a for c in colours), default=alpha))
    fill = _blend_paint(cmd.fill, alpha, bd)
    stroke: Stroke | None = None
    if cmd.stroke is not None:
        stroke = cmd.stroke.model_copy(update={"color": _blend(cmd.stroke.color, alpha, bd)})
    return cmd.model_copy(update={"fill": fill, "stroke": stroke, "opacity": 1.0})


def _blend_paint(paint: PaintU | None, alpha: float, bd: RGBA) -> PaintU | None:
    if paint is None:
        return None
    if isinstance(paint, SolidPaint):
        return paint.model_copy(update={"color": _blend(paint.color, alpha, bd)})
    stops = tuple(
        GradientStop(position=s.position, color=_blend(s.color, alpha, bd)) for s in paint.stops
    )
    return paint.model_copy(update={"stops": stops})


def _flatten_text(
    cmd: DrawText, group_alpha: float, backdrop: Callable[[float], RGBA]
) -> DrawText:
    alpha = group_alpha * cmd.opacity
    if alpha * cmd.run.color.a >= 1.0:
        return cmd
    colour = _blend(cmd.run.color, alpha, backdrop(alpha * cmd.run.color.a))
    return cmd.model_copy(update={
        "run": cmd.run.model_copy(update={"color": colour}),
        "opacity": 1.0,
    })


def _image_has_alpha(source: str) -> bool:
    with Image.open(Path(source)) as img:
        return img.mode in ("RGBA", "LA", "PA", "La", "RGBa") or "transparency" in img.info


# ---------------------------------------------------------------------------
# Records: what an earlier draw leaves behind
# ---------------------------------------------------------------------------


def _record(
    cmd: DrawShape | DrawText | DrawImage,
    box: Box,
    matrix: Matrix,
    clips: list[_Clip],
    tokens: frozenset[int],
) -> _Painted:
    def overlaps(other: Box) -> bool:
        return _overlap(box, other)

    def nothing(_other: Box) -> RGBA | None:
        return None

    if isinstance(cmd, DrawImage):
        return _Painted(box, "image", overlaps, nothing, tokens)
    if isinstance(cmd, DrawText):
        return _Painted(box, "text run", overlaps, nothing, tokens)

    geom = cmd.geometry
    kind = f"{_paint_kind(cmd.fill)} {geom.kind}"
    exact = matrix == _IDENTITY and all(c.exact is not None for c in clips)
    hits: Callable[[Box], bool] = overlaps
    if cmd.fill is None and cmd.stroke is not None and isinstance(geom, RectGeom) and exact:
        inner = _inset(_rect_box(geom), cmd.stroke.width / 2)

        def hits_band(other: Box) -> bool:
            return _overlap(box, other) and (inner is None or not _inside(other, inner))

        hits = hits_band

    fill = cmd.fill
    if not (exact and isinstance(fill, SolidPaint) and fill.color.a >= 1.0
            and cmd.opacity >= 1.0):
        return _Painted(box, kind, hits, nothing, tokens)
    colour = fill.color
    inset = cmd.stroke.width / 2 if cmd.stroke is not None else 0.0
    clip_boxes = [c.exact for c in clips if c.exact is not None]

    def covers(other: Box) -> RGBA | None:
        if not all(_inside(other, c) for c in clip_boxes):
            return None
        return colour if _geom_contains(geom, other, inset) else None

    return _Painted(box, kind, hits, covers, tokens, solid=True)


def _paint_kind(paint: PaintU | None) -> str:
    if paint is None:
        return "stroked"
    if isinstance(paint, SolidPaint):
        return "solid"
    return "gradient-filled"


def _describe(cmd: DrawShape | DrawText | DrawImage) -> str:
    if isinstance(cmd, DrawShape):
        return f"{cmd.geometry.kind} shape"
    if isinstance(cmd, DrawText):
        return f"text {cmd.run.text!r}"
    return "image"


def _geom_contains(geom: GeomU, box: Box, inset: float) -> bool:
    x0, y0, x1, y1 = box
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    if isinstance(geom, RectGeom):
        inner = _inset(_rect_box(geom), max(inset, 0.0))
        if inner is None or not _inside(box, inner):
            return False
        r = max(geom.corner_radius - inset, 0.0)
        if r == 0.0:
            return True
        ix0, iy0, ix1, iy1 = inner
        # Each corner must also clear the rounded corners' quarter circles.
        for px, py in corners:
            cx = min(max(px, ix0 + r), ix1 - r)
            cy = min(max(py, iy0 + r), iy1 - r)
            if math.hypot(px - cx, py - cy) > r + _EPS:
                return False
        return True
    if isinstance(geom, CircleGeom):
        r = geom.radius - inset
        return r > 0 and all(
            math.hypot(px - geom.center.x, py - geom.center.y) <= r + _EPS for px, py in corners
        )
    if isinstance(geom, EllipseGeom):
        rx, ry = geom.rx - inset, geom.ry - inset
        return rx > 0 and ry > 0 and all(
            ((px - geom.center.x) / rx) ** 2 + ((py - geom.center.y) / ry) ** 2 <= 1 + _EPS
            for px, py in corners
        )
    return False


# ---------------------------------------------------------------------------
# Boxes and transforms
# ---------------------------------------------------------------------------


def _rect_box(geom: RectGeom) -> Box:
    return (geom.x, geom.y, geom.x + geom.width, geom.y + geom.height)


def _geom_box(geom: GeomU) -> Box:
    if isinstance(geom, RectGeom):
        return _rect_box(geom)
    if isinstance(geom, CircleGeom):
        c, r = geom.center, geom.radius
        return (c.x - r, c.y - r, c.x + r, c.y + r)
    if isinstance(geom, EllipseGeom):
        c = geom.center
        return (c.x - geom.rx, c.y - geom.ry, c.x + geom.rx, c.y + geom.ry)
    if isinstance(geom, (PolygonGeom, PolylineGeom)):
        xs = [p.x for p in geom.points]
        ys = [p.y for p in geom.points]
    else:
        assert isinstance(geom, PathGeom)
        # Bézier curves stay inside their control points' hull.
        xs = [p.x for op in geom.ops for p in op.points]
        ys = [p.y for op in geom.ops for p in op.points]
    return (min(xs), min(ys), max(xs), max(ys))


def _local_box(cmd: DrawShape | DrawText | DrawImage) -> Box:
    if isinstance(cmd, DrawShape):
        x0, y0, x1, y1 = _geom_box(cmd.geometry)
        pad = cmd.stroke.width / 2 if cmd.stroke is not None else 0.0
        return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    if isinstance(cmd, DrawImage):
        return _rect_box(cmd.image.rect)
    from reportlab.pdfbase.pdfmetrics import stringWidth

    from holiday_card.renderers.font_registry import (
        ensure_default_fonts_registered,
        resolve_font_id,
    )

    ensure_default_fonts_registered()
    run = cmd.run
    width = stringWidth(run.text, resolve_font_id(run.font_id), run.size_pt)
    left = {"left": 0.0, "center": width / 2, "right": width}[run.align]
    x0 = run.origin.x - left
    return (x0, run.origin.y - _DESCENT * run.size_pt, x0 + width, run.origin.y + run.size_pt)


def _compose(m: Matrix, n: Matrix) -> Matrix:
    """``m ∘ n``: apply ``n`` first."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + c * b2, b * a2 + d * b2,
        a * c2 + c * d2, b * c2 + d * d2,
        a * e2 + c * f2 + e, b * e2 + d * f2 + f,
    )


def _transform_box(box: Box, m: Matrix) -> Box:
    if m == _IDENTITY:
        return box
    a, b, c, d, e, f = m
    x0, y0, x1, y1 = box
    xs, ys = [], []
    for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        xs.append(a * x + c * y + e)
        ys.append(b * x + d * y + f)
    return (min(xs), min(ys), max(xs), max(ys))


def _clip_for(geom: GeomU, m: Matrix) -> _Clip:
    box = _transform_box(_geom_box(geom), m)
    exact = box if isinstance(geom, RectGeom) and m == _IDENTITY else None
    return _Clip(box=box, exact=exact)


def _clip_box(box: Box, clips: list[_Clip]) -> Box | None:
    x0, y0, x1, y1 = box
    for clip in clips:
        cx0, cy0, cx1, cy1 = clip.box
        x0, y0, x1, y1 = max(x0, cx0), max(y0, cy0), min(x1, cx1), min(y1, cy1)
    if x1 - x0 <= _EPS or y1 - y0 <= _EPS:
        return None
    return (x0, y0, x1, y1)


def _overlap(a: Box, b: Box) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) > _EPS
            and min(a[3], b[3]) - max(a[1], b[1]) > _EPS)


def _inside(inner: Box, outer: Box) -> bool:
    return (inner[0] >= outer[0] - _EPS and inner[1] >= outer[1] - _EPS
            and inner[2] <= outer[2] + _EPS and inner[3] <= outer[3] + _EPS)


def _inset(box: Box, d: float) -> Box | None:
    x0, y0, x1, y1 = box[0] + d, box[1] + d, box[2] - d, box[3] - d
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None
