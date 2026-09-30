"""PNG raster backend for the rendering IR.

The third backend on the IR seam (after PDF and SVG). Designed for
**fast preview** during template authoring — opens in any image viewer,
no PDF reader, no browser. Powers the ``holiday-card preview`` command.

Pillow is already a dependency, so no new install. Resolution is
configurable via ``__init__(dpi=...)``; the default of 144 DPI is the
sweet spot for screen preview (sharp on retina, fast to render).

Coordinate system note
----------------------
Pillow, like SVG, uses top-left pixel origin with y growing downward.
The IR uses bottom-left origin in **points** (1/72 inch). This backend
converts both at emit time:

    pixel_x = ir_x_pts * scale
    pixel_y = (page_height_pts - ir_y_pts) * scale

where ``scale = dpi / 72``.

Scope
-----
Every IR command is honoured or raises ``NotImplementedError`` (fail
loud, D4):

* Shapes (rect / rounded rect / circle / ellipse / polygon / polyline /
  path) with solid fills and linear + radial gradients (patterns are
  lowered to clip + solid primitives by the compiler, #74);
  strokes with ``Stroke.dash`` (PDF/SVG semantics: odd-length arrays
  repeat, phase 0, restart per subpath).
* Text with three alignments; effective alpha is
  ``DrawText.opacity × run.color.a``. Fonts resolve **only** through
  ``font_registry.ttf_path_for``; an id with no bundled TTF raises.
* Images (PNG/JPEG), with ``opacity``.
* ``BeginClip`` / ``EndClip`` for rect / circle / ellipse / polygon /
  path geometry. Nested clips intersect and apply to shapes, text,
  images and fold lines. A clip opened outside a rotated group applies
  to the group's composited result. ``PolylineGeom`` clips raise at
  ``BeginClip``.
* ``BeginGroup`` with identity or pivot-rotation transforms.

Not supported (raise): group ``opacity != 1``, group scale. Known
fidelity gaps (tracked elsewhere, not silent drops): no anti-aliasing
on shapes, strokes drawn inset rather than centred, ``line_cap``
ignored (#77).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from holiday_card.core.render_ir import (
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
    LinearGradientPaint,
    PathGeom,
    PolygonGeom,
    PolylineGeom,
    RadialGradientPaint,
    RectGeom,
    RenderCommand,
    SetMetadata,
    SolidPaint,
    Stroke,
    Transform,
)

__all__ = ["PNGRenderer"]


def _interp_stops(
    stops: list,
    t: float,
) -> tuple[int, int, int, int]:
    """Interpolate between two adjacent gradient stops at parameter ``t``.

    ``stops`` is a list of ``(position, RGBA)`` tuples in ascending
    position order (validated at the model layer). Returns an 8-bit
    RGBA tuple — alpha is sampled too so a gradient can fade in/out.
    """
    if t <= stops[0][0]:
        c = stops[0][1]
        return (
            int(round(c.r * 255)),
            int(round(c.g * 255)),
            int(round(c.b * 255)),
            int(round(c.a * 255)),
        )
    if t >= stops[-1][0]:
        c = stops[-1][1]
        return (
            int(round(c.r * 255)),
            int(round(c.g * 255)),
            int(round(c.b * 255)),
            int(round(c.a * 255)),
        )
    # Linear search is fine — gradients ship with 2–6 stops at most.
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            p0, c0 = stops[i - 1]
            p1, c1 = stops[i]
            span = p1 - p0
            local_t = (t - p0) / span if span > 0 else 0.0
            r = c0.r + (c1.r - c0.r) * local_t
            g = c0.g + (c1.g - c0.g) * local_t
            b = c0.b + (c1.b - c0.b) * local_t
            a = c0.a + (c1.a - c0.a) * local_t
            return (
                int(round(r * 255)),
                int(round(g * 255)),
                int(round(b * 255)),
                int(round(a * 255)),
            )
    c = stops[-1][1]
    return (
        int(round(c.r * 255)),
        int(round(c.g * 255)),
        int(round(c.b * 255)),
        int(round(c.a * 255)),
    )


def _pixel_span(start: float, end: float) -> tuple[int, int]:
    """Inclusive range of the pixels whose centres lie in ``[start, end)``.

    Never empty. Pillow treats a box end as inclusive, so a 2 px line drew
    3 px; the centre rule also gives abutting rects (checker cells) exactly
    one owner per pixel.
    """
    first = math.ceil(start - 0.5)
    return first, max(first, math.ceil(end - 0.5) - 1)


def _dash_runs(
    polyline: list[tuple[float, float]], pattern: list[float]
) -> list[list[tuple[float, float]]]:
    """Split ``polyline`` into its "on" runs under a dash ``pattern``.

    PDF/SVG semantics: an odd-length pattern repeats to even length,
    phase 0, the first entry is "on". An all-zero pattern means solid.
    """
    if len(polyline) < 2 or sum(pattern) <= 0:
        return [polyline]
    if len(pattern) % 2:
        pattern = pattern * 2
    runs: list[list[tuple[float, float]]] = []
    index, remaining, on = 0, pattern[0], True
    current = [polyline[0]]
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:], strict=False):
        seg = math.hypot(bx - ax, by - ay)
        pos = 0.0
        while seg - pos > remaining:
            pos += remaining
            pt = (ax + (bx - ax) * pos / seg, ay + (by - ay) * pos / seg)
            if on:
                current.append(pt)
                runs.append(current)
            current = [pt]
            on = not on
            index = (index + 1) % len(pattern)
            remaining = pattern[index]
        remaining -= seg - pos
        if on:
            current.append((bx, by))
    if on and len(current) >= 2:
        runs.append(current)
    return runs


class PNGRenderer:
    """Renderer that visits a ``RenderCommand`` stream and writes a PNG.

    Single-method public surface, like the other backends. Stateless
    across calls — every ``render()`` invocation builds a fresh image.
    """

    name: str = "png"
    file_extension: str = ".png"
    # sRGB only: a CMYK target never swaps this backend (core Renderer Protocol).
    color_space: str = "srgb"

    def __init__(self, dpi: int = 144) -> None:
        """Initialize the renderer.

        Args:
            dpi: Output resolution in dots per inch. 72 = 1px:1pt
                (smallest, fastest). 144 (the default) is a good preview
                quality. 288 for high-DPI display.
        """
        if dpi < 32:
            raise ValueError(f"dpi must be >= 32, got {dpi}")
        self.dpi = dpi
        self._scale = dpi / 72.0
        self._font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def render(self, commands: Iterable[RenderCommand], output: Path) -> None:
        """Consume ``commands`` and write a PNG at ``output``."""
        output.parent.mkdir(parents=True, exist_ok=True)

        # State accumulated across the visit
        self._page_height_pts: float = 0.0
        self._bleed_pts: float = 0.0
        self._image: Image.Image | None = None
        self._draw: ImageDraw.ImageDraw | None = None
        self._metadata: dict[str, str] = {}
        # Stack of (saved_image, saved_draw, transform). When a BeginGroup
        # has a non-identity transform we push the current target,
        # redirect drawing to a transparent overlay, and on EndGroup we
        # rotate the overlay around the pivot and paste back.
        self._group_stack: list[
            tuple[Image.Image, ImageDraw.ImageDraw, Transform] | None
        ] = []
        # Open clips as (group level, mask). Each "L" canvas-sized mask
        # is already intersected with the enclosing clip at the same
        # level; clips from outer levels apply when the rotated group
        # overlay is composited back in ``_end_group``.
        self._clip_stack: list[tuple[int, Image.Image]] = []
        # Recursion guard: ``_draw_in_layer`` redirects drawing to a temp
        # RGBA layer and re-enters the draw method, which must then take
        # the direct path instead of bouncing back into a layer.
        self._in_layer: bool = False

        for cmd in commands:
            self._dispatch(cmd)

        if self._image is None:
            raise RuntimeError("PNGRenderer.render: command stream had no BeginPage")
        if self._group_stack:
            raise RuntimeError(
                f"PNGRenderer: command stream ended with {len(self._group_stack)} "
                "open group(s); compiler invariant assert_balanced should have caught this."
            )

        # PNG textual metadata for the title; quiet best-effort.
        from PIL.PngImagePlugin import PngInfo
        info = PngInfo()
        for key, value in self._metadata.items():
            info.add_text(key, value)
        # Convert RGBA to RGB before saving (white background already in place)
        if self._image.mode == "RGBA":
            base = Image.new("RGB", self._image.size, (255, 255, 255))
            base.paste(self._image, mask=self._image.split()[3])
            base.save(output, "PNG", pnginfo=info)
        else:
            self._image.save(output, "PNG", pnginfo=info)

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _x(self, x: float) -> float:
        """IR x (trim-relative, points) → Pillow x (media-relative, pixels)."""
        return (x + self._bleed_pts) * self._scale

    def _y(self, y: float) -> float:
        """IR (bottom-left, points) → Pillow (top-left, pixels).

        Includes the bleed offset so IR ``(0, 0)`` lands at the trim
        corner of the media canvas, not the media corner itself.
        """
        return (self._page_height_pts - y + self._bleed_pts) * self._scale

    def _len(self, value: float) -> float:
        return value * self._scale

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, cmd: RenderCommand) -> None:
        if isinstance(cmd, BeginPage):
            self._begin_page(cmd)
        elif isinstance(cmd, EndPage):
            pass  # save happens in render()
        elif isinstance(cmd, SetMetadata):
            self._metadata[cmd.key] = cmd.value
        elif isinstance(cmd, BeginGroup):
            self._begin_group(cmd)
        elif isinstance(cmd, EndGroup):
            self._end_group()
        elif isinstance(cmd, BeginClip):
            self._begin_clip(cmd)
        elif isinstance(cmd, EndClip):
            if not self._clip_stack:
                raise RuntimeError("PNGRenderer: EndClip without matching BeginClip")
            self._clip_stack.pop()
        elif isinstance(cmd, DrawShape):
            self._draw_shape(cmd)
        elif isinstance(cmd, DrawText):
            self._draw_text(cmd)
        elif isinstance(cmd, DrawImage):
            self._draw_image(cmd)
        elif isinstance(cmd, DrawFoldLine):
            self._draw_fold_line(cmd)
        else:
            raise NotImplementedError(
                f"PNGRenderer does not know how to handle {type(cmd).__name__}"
            )

    # ------------------------------------------------------------------
    # Page
    # ------------------------------------------------------------------

    def _begin_page(self, cmd: BeginPage) -> None:
        # Trim height drives the y-flip math; bleed grows the canvas
        # outward by 2*bleed on each axis. The _x / _y helpers fold the
        # bleed into the IR-to-pixel transform so trim coords (0, 0)
        # land at the trim-corner of the media canvas.
        self._page_height_pts = cmd.height
        self._bleed_pts = cmd.bleed
        media_w = cmd.width + 2 * cmd.bleed
        media_h = cmd.height + 2 * cmd.bleed
        width_px = max(1, int(round(media_w * self._scale)))
        height_px = max(1, int(round(media_h * self._scale)))
        # Start with an opaque white canvas — matches a printed page.
        # RGBA mode (not RGB) so the ``_draw_shape_with_alpha_compositing``
        # path's ``Image.alpha_composite`` correctly blends semi-
        # transparent shapes onto the panel. The save path at the end
        # of ``render`` composites this RGBA canvas back onto opaque
        # white before writing PNG, so the saved file is still RGB.
        self._image = Image.new("RGBA", (width_px, height_px), (255, 255, 255, 255))
        self._draw = ImageDraw.Draw(self._image)

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def _begin_group(self, cmd: BeginGroup) -> None:
        t = cmd.transform
        if cmd.opacity != 1.0:
            # Group opacity would need a separate compositing layer with
            # alpha-multiply. Not exercised by the compiler today.
            raise NotImplementedError(
                "PNGRenderer does not yet handle BeginGroup with non-1.0 opacity"
            )
        if t.is_identity() and self._active_mask() is None:
            # No isolation needed; draw context unchanged.
            self._group_stack.append(None)
            return
        # Draw the group's content to a transparent overlay at canvas size,
        # then map the whole overlay through the transform on EndGroup. An
        # identity group under a clip is isolated too, so its draws go
        # straight onto one overlay that is clipped once (a lowered
        # pattern's thousands of primitives, #74) instead of one layer each.
        assert self._image is not None and self._draw is not None
        saved_image = self._image
        saved_draw = self._draw
        overlay = Image.new("RGBA", saved_image.size, (0, 0, 0, 0))
        self._image = overlay
        self._draw = ImageDraw.Draw(overlay)
        self._group_stack.append((saved_image, saved_draw, t))

    def _end_group(self) -> None:
        if not self._group_stack:
            raise RuntimeError("PNGRenderer: EndGroup with no open group")
        state = self._group_stack.pop()
        if state is None:
            return  # identity group; nothing to composite
        saved_image, saved_draw, transform = state
        overlay = self._image
        assert overlay is not None
        transformed = overlay if transform.is_identity() else overlay.transform(
            overlay.size,
            Image.Transform.AFFINE,
            self._inverse_pixel_affine(transform),
            resample=Image.Resampling.BICUBIC,
        )
        # Composite back onto the parent through the parent level's
        # clip, so a clip opened outside the group still applies.
        self._image = saved_image
        self._draw = saved_draw
        self._composite(transformed)

    def _inverse_pixel_affine(
        self, t: Transform
    ) -> tuple[float, float, float, float, float, float]:
        """Pillow AFFINE coefficients (output pixel → source pixel) for ``t``.

        The forward map in pixel space is ``P · M · P⁻¹``, where ``M`` is
        ``t.to_matrix()`` and ``P`` is the IR → pixel map (bleed offset,
        DPI scale, y-flip) that ``_x`` / ``_y`` apply.
        """
        s, b, h = self._scale, self._bleed_pts, self._page_height_pts
        to_px = (s, 0.0, 0.0, -s, s * b, s * (h + b))
        from_px = (1 / s, 0.0, 0.0, -1 / s, -b, h + b)
        a, bb, c, d, e, f = _invert(_compose(to_px, _compose(t.to_matrix(), from_px)))
        # Pillow wants x_in = a·x + c·y + e, y_in = b·x + d·y + f as (a, c, e, b, d, f).
        return (a, c, e, bb, d, f)

    # ------------------------------------------------------------------
    # Clips and compositing layers
    # ------------------------------------------------------------------

    def _group_level(self) -> int:
        """Number of open non-identity groups (each has its own overlay)."""
        return sum(1 for state in self._group_stack if state is not None)

    def _active_mask(self) -> Image.Image | None:
        """The clip mask for draws at the current group level, if any."""
        if self._clip_stack and self._clip_stack[-1][0] == self._group_level():
            return self._clip_stack[-1][1]
        return None

    def _begin_clip(self, cmd: BeginClip) -> None:
        mask = self._geom_mask(cmd.geometry)
        enclosing = self._active_mask()
        if enclosing is not None:
            mask = ImageChops.multiply(mask, enclosing)
        self._clip_stack.append((self._group_level(), mask))

    def _geom_mask(self, geom: object) -> Image.Image:
        """Canvas-sized "L" mask: 255 inside ``geom`` (IR coords), 0 outside."""
        assert self._image is not None
        mask = Image.new("L", self._image.size, 0)
        draw = ImageDraw.Draw(mask)
        if isinstance(geom, RectGeom):
            box = (
                self._x(geom.x), self._y(geom.y + geom.height),
                self._x(geom.x + geom.width), self._y(geom.y),
            )
            if geom.corner_radius > 0:
                draw.rounded_rectangle(box, radius=self._len(geom.corner_radius), fill=255)
            else:
                draw.rectangle(box, fill=255)
        elif isinstance(geom, (CircleGeom, EllipseGeom)):
            cx, cy = self._x(geom.center.x), self._y(geom.center.y)
            if isinstance(geom, CircleGeom):
                rx = ry = self._len(geom.radius)
            else:
                rx, ry = self._len(geom.rx), self._len(geom.ry)
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        elif isinstance(geom, PolygonGeom):
            draw.polygon([(self._x(p.x), self._y(p.y)) for p in geom.points], fill=255)
        elif isinstance(geom, PathGeom):
            for sp in self._flatten_path(geom):
                if len(sp) >= 3:
                    draw.polygon(sp, fill=255)
        else:
            raise NotImplementedError(
                f"PNGRenderer: clip geometry {type(geom).__name__} is not supported "
                "(an open polyline has no interior)"
            )
        return mask

    def _draw_in_layer(self, draw: Callable[[], None], alpha: float = 1.0) -> None:
        """Run ``draw`` against a transparent layer, then ``_composite`` it.

        Pillow's ``ImageDraw`` replaces pixels instead of blending, so
        anything translucent or clipped is drawn in isolation first.
        """
        assert self._image is not None
        saved_image, saved_draw = self._image, self._draw
        layer = Image.new("RGBA", saved_image.size, (0, 0, 0, 0))
        self._image, self._draw = layer, ImageDraw.Draw(layer)
        self._in_layer = True
        try:
            draw()
        finally:
            self._in_layer = False
            self._image, self._draw = saved_image, saved_draw
        self._composite(layer, alpha)

    def _composite(self, layer: Image.Image, alpha: float = 1.0) -> None:
        """Source-over ``layer`` onto the target, scaled by ``alpha`` and clipped."""
        assert self._image is not None
        mask = self._active_mask()
        if mask is not None or alpha < 1.0:
            layer_alpha = layer.getchannel("A")
            if alpha < 1.0:
                layer_alpha = layer_alpha.point(lambda a: round(a * alpha))
            if mask is not None:
                layer_alpha = ImageChops.multiply(layer_alpha, mask)
            layer.putalpha(layer_alpha)
        self._image.alpha_composite(layer)

    # ------------------------------------------------------------------
    # Shape drawing
    # ------------------------------------------------------------------

    def _draw_shape(self, cmd: DrawShape) -> None:
        assert self._draw is not None
        complex_fill = isinstance(
            cmd.fill,
            (LinearGradientPaint, RadialGradientPaint),
        )
        # Pillow's ImageDraw drops the alpha channel: a fill or stroke
        # with alpha < 255 *replaces* the pixel instead of compositing
        # with what's underneath. Translucent or clipped shapes are drawn
        # on a transparent layer and composited; the common opaque,
        # unclipped case still hits the fast direct-draw path. Complex
        # fills handle their own opacity, so only a clip redirects them.
        if not self._in_layer and (
            self._active_mask() is not None
            or (not complex_fill and self._shape_needs_alpha_compositing(cmd))
        ):
            self._draw_in_layer(lambda: self._draw_shape(cmd))
            return
        # Gradient fills need a separate rendering path —
        # they paint a 2D field rather than a single color, so the
        # ``ImageDraw.rectangle``/``ellipse`` calls below can't fill
        # them in one step. Dispatch and return.
        if complex_fill:
            self._draw_shape_with_complex_fill(cmd)
            return
        fill_rgba = self._fill_to_rgba(cmd.fill, cmd.opacity)
        stroke_rgba = self._stroke_to_rgba(cmd.stroke, cmd.opacity)
        dashed = cmd.stroke is not None and bool(cmd.stroke.dash)
        # A dashed stroke: the fast path fills only; ``_stroke_outline``
        # draws the dashes afterwards.
        dash_rgba = stroke_rgba if dashed else None
        if dashed:
            stroke_rgba = None
        stroke_width = max(1, int(round(self._len(cmd.stroke.width)))) if cmd.stroke else 0

        geom = cmd.geometry
        if isinstance(geom, RectGeom):
            x0 = self._x(geom.x)
            y1 = self._y(geom.y)
            x1 = self._x(geom.x + geom.width)
            y0 = self._y(geom.y + geom.height)
            if geom.corner_radius > 0:
                self._draw.rounded_rectangle(
                    (x0, y0, x1, y1),
                    radius=self._len(geom.corner_radius),
                    fill=fill_rgba, outline=stroke_rgba, width=stroke_width,
                )
            elif stroke_rgba is None:
                if fill_rgba is not None:
                    # Pillow's box end is inclusive (one pixel too many).
                    left, right = _pixel_span(x0, x1)
                    top, bottom = _pixel_span(y0, y1)
                    self._draw.rectangle((left, top, right, bottom), fill=fill_rgba)
            else:
                self._draw.rectangle(
                    (x0, y0, x1, y1),
                    fill=fill_rgba, outline=stroke_rgba, width=stroke_width,
                )
        elif isinstance(geom, CircleGeom):
            cx = self._x(geom.center.x)
            cy = self._y(geom.center.y)
            r = self._len(geom.radius)
            # Pillow's box end is inclusive; a fill-only disc insets it by
            # half a pixel each side so its diameter matches (#74).
            inset = 0.5 if stroke_rgba is None else 0.0
            self._draw.ellipse(
                (cx - r + inset, cy - r + inset, cx + r - inset, cy + r - inset),
                fill=fill_rgba, outline=stroke_rgba, width=stroke_width,
            )
        elif isinstance(geom, EllipseGeom):
            cx = self._x(geom.center.x)
            cy = self._y(geom.center.y)
            rx = self._len(geom.rx)
            ry = self._len(geom.ry)
            inset = 0.5 if stroke_rgba is None else 0.0
            self._draw.ellipse(
                (cx - rx + inset, cy - ry + inset, cx + rx - inset, cy + ry - inset),
                fill=fill_rgba, outline=stroke_rgba, width=stroke_width,
            )
        elif isinstance(geom, PolygonGeom):
            pts = [(self._x(p.x), self._y(p.y)) for p in geom.points]
            self._draw.polygon(pts, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif isinstance(geom, PolylineGeom):
            if not dashed:
                pts = [(self._x(p.x), self._y(p.y)) for p in geom.points]
                # Pillow's polygon doesn't fill open shapes the same way; for
                # an open polyline, draw as a line. Fill is ignored.
                self._draw.line(
                    pts, fill=stroke_rgba or (0, 0, 0, 255),
                    width=max(1, stroke_width), joint="curve",
                )
        elif isinstance(geom, PathGeom):
            self._draw_path(geom, fill_rgba, stroke_rgba, stroke_width)
        if cmd.stroke is not None and dash_rgba is not None:
            self._stroke_outline(geom, cmd.stroke, dash_rgba)

    @staticmethod
    def _shape_needs_alpha_compositing(cmd: DrawShape) -> bool:
        """Return True when ``cmd`` has any sub-unit alpha contribution.

        Triggers redirection to ``_draw_in_layer`` so the pixel actually blends with the underlying panel
        instead of replacing it (which is what Pillow's ImageDraw
        does on RGBA images when given a fill with alpha < 255).
        """
        if cmd.opacity < 1.0:
            return True
        if isinstance(cmd.fill, SolidPaint) and cmd.fill.color.a < 1.0:
            return True
        return cmd.stroke is not None and cmd.stroke.color.a < 1.0

    # Number of polyline samples per Bezier curve segment. 16 is a
    # sweet spot for the holly-wreath style organic curves we see in
    # shipped templates — visually smooth at 144 DPI and cheap to
    # generate. Bumping to 32 produces no perceptual difference at
    # preview resolution; dropping to 8 starts to show faceting.
    _BEZIER_SAMPLES: int = 16

    def _draw_path(
        self,
        geom: PathGeom,
        fill_rgba: tuple[int, int, int, int] | None,
        stroke_rgba: tuple[int, int, int, int] | None,
        stroke_width: int,
    ) -> None:
        """Flatten a PathGeom into one-or-more filled polygons + outlines.

        Cubic and quadratic Bezier curves are sampled into polyline
        segments (Pillow has no native bezier API). The sample count
        is fixed at :attr:`_BEZIER_SAMPLES` per segment; for the curves
        used in shipped templates (holly-wreath leaves, ornament
        outlines) this produces visually smooth output at preview DPI.
        """
        assert self._draw is not None
        subpaths = self._flatten_path(geom)
        for sp in subpaths:
            if len(sp) >= 2:
                # Closed subpath with fill → polygon; else stroke only.
                is_closed = sp[0] == sp[-1]
                if fill_rgba is not None and is_closed:
                    self._draw.polygon(
                        sp, fill=fill_rgba,
                        outline=stroke_rgba, width=stroke_width,
                    )
                elif stroke_rgba is not None:
                    self._draw.line(
                        sp, fill=stroke_rgba,
                        width=max(1, stroke_width), joint="curve",
                    )

    def _flatten_path(self, geom: PathGeom) -> list[list[tuple[float, float]]]:
        """Flatten ``geom`` into pixel-space subpaths (closed ones end on their start)."""
        # Walk ops, collect subpaths
        current_path = (0.0, 0.0)  # in IR coordinates
        subpath: list[tuple[float, float]] = []
        subpaths: list[list[tuple[float, float]]] = []

        def emit_px(x: float, y: float) -> None:
            subpath.append((self._x(x), self._y(y)))

        for op in geom.ops:
            if op.op == "move":
                if subpath:
                    subpaths.append(subpath)
                    subpath = []
                p = op.points[0]
                current_path = (p.x, p.y)
                emit_px(p.x, p.y)
            elif op.op == "line":
                p = op.points[0]
                emit_px(p.x, p.y)
                current_path = (p.x, p.y)
            elif op.op == "cubic":
                cp1, cp2, end = op.points
                self._sample_cubic_into(
                    subpath, current_path, (cp1.x, cp1.y),
                    (cp2.x, cp2.y), (end.x, end.y),
                )
                current_path = (end.x, end.y)
            elif op.op == "quadratic":
                cp, end = op.points
                self._sample_quadratic_into(
                    subpath, current_path, (cp.x, cp.y), (end.x, end.y),
                )
                current_path = (end.x, end.y)
            elif op.op == "close":
                if subpath:
                    subpath.append(subpath[0])

        if subpath:
            subpaths.append(subpath)
        return subpaths

    def _sample_cubic_into(
        self,
        subpath: list[tuple[float, float]],
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> None:
        """Append ``_BEZIER_SAMPLES`` sampled pixels of a cubic Bezier."""
        for k in range(1, self._BEZIER_SAMPLES + 1):
            t = k / self._BEZIER_SAMPLES
            u = 1.0 - t
            x = (u * u * u * p0[0] + 3 * u * u * t * p1[0]
                 + 3 * u * t * t * p2[0] + t * t * t * p3[0])
            y = (u * u * u * p0[1] + 3 * u * u * t * p1[1]
                 + 3 * u * t * t * p2[1] + t * t * t * p3[1])
            subpath.append((self._x(x), self._y(y)))

    def _sample_quadratic_into(
        self,
        subpath: list[tuple[float, float]],
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
    ) -> None:
        """Append ``_BEZIER_SAMPLES`` sampled pixels of a quadratic Bezier."""
        for k in range(1, self._BEZIER_SAMPLES + 1):
            t = k / self._BEZIER_SAMPLES
            u = 1.0 - t
            x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            subpath.append((self._x(x), self._y(y)))

    # ------------------------------------------------------------------
    # Dashed strokes
    # ------------------------------------------------------------------

    # Minimum samples when flattening a circle / ellipse outline.
    _ELLIPSE_SAMPLES: int = 64

    def _stroke_outline(
        self, geom: object, stroke: Stroke, rgba: tuple[int, int, int, int]
    ) -> None:
        """Draw ``geom``'s outline with ``stroke.dash`` (points) applied."""
        width = max(1, int(round(self._len(stroke.width))))
        pattern = [self._len(d) for d in stroke.dash]
        for polyline in self._outline_polylines(geom):
            self._draw_dashed_polyline(polyline, pattern, rgba, width)

    def _draw_dashed_polyline(
        self,
        polyline: list[tuple[float, float]],
        pattern: list[float],
        rgba: tuple[int, int, int, int] | tuple[int, int, int],
        width: int,
    ) -> None:
        assert self._draw is not None
        for run in _dash_runs(polyline, pattern):
            self._draw.line(run, fill=rgba, width=width, joint="curve")

    def _outline_polylines(self, geom: object) -> list[list[tuple[float, float]]]:
        """Pixel-space outline of ``geom``: closed shapes end on their start."""
        if isinstance(geom, RectGeom):
            left, top = self._x(geom.x), self._y(geom.y + geom.height)
            right, bottom = self._x(geom.x + geom.width), self._y(geom.y)
            r = min(self._len(geom.corner_radius), (right - left) / 2, (bottom - top) / 2)
            if r <= 0:
                pts = [(left, top), (right, top), (right, bottom), (left, bottom)]
            else:
                pts = []
                corners = [
                    (left + r, top + r, 180.0), (right - r, top + r, 270.0),
                    (right - r, bottom - r, 0.0), (left + r, bottom - r, 90.0),
                ]
                for cx, cy, start in corners:
                    for k in range(self._BEZIER_SAMPLES + 1):
                        a = math.radians(start + 90.0 * k / self._BEZIER_SAMPLES)
                        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            return [[*pts, pts[0]]]
        if isinstance(geom, (CircleGeom, EllipseGeom)):
            cx, cy = self._x(geom.center.x), self._y(geom.center.y)
            if isinstance(geom, CircleGeom):
                rx = ry = self._len(geom.radius)
            else:
                rx, ry = self._len(geom.rx), self._len(geom.ry)
            n = max(self._ELLIPSE_SAMPLES, int(math.pi * max(rx, ry)))
            pts = [
                (cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n))
                for k in range(n)
            ]
            return [[*pts, pts[0]]]
        if isinstance(geom, PolygonGeom):
            pts = [(self._x(p.x), self._y(p.y)) for p in geom.points]
            return [[*pts, pts[0]]]
        if isinstance(geom, PolylineGeom):
            return [[(self._x(p.x), self._y(p.y)) for p in geom.points]]
        if isinstance(geom, PathGeom):
            return self._flatten_path(geom)
        raise NotImplementedError(
            f"PNGRenderer: dashed stroke on {type(geom).__name__} is not supported"
        )

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def _draw_text(self, cmd: DrawText) -> None:
        assert self._draw is not None
        run = cmd.run
        size_px = max(1, int(round(run.size_pt * self._scale)))
        font = self._get_font(run.font_id, size_px)
        alpha = cmd.opacity * run.color.a
        rgb = (
            int(round(run.color.r * 255)),
            int(round(run.color.g * 255)),
            int(round(run.color.b * 255)),
        )
        # Translucent or clipped text is drawn opaque on a layer and
        # composited (ImageDraw replaces pixels instead of blending).
        if not self._in_layer and (alpha < 1.0 or self._active_mask() is not None):
            self._draw_text_in_layer(cmd, rgb, alpha)
            return
        # Pillow anchor codes: l/m/r for x, t/m/s/b for y. We want
        # baseline-aligned to match ReportLab's drawString origin
        # convention, so use 's' (baseline) for y.
        anchor_map = {"left": "ls", "center": "ms", "right": "rs"}
        self._draw.text(
            (self._x(run.origin.x), self._y(run.origin.y)),
            run.text,
            font=font,
            fill=(*rgb, 255),
            anchor=anchor_map[run.align],
        )

    def _draw_text_in_layer(
        self,
        cmd: DrawText,
        rgb: tuple[int, int, int],
        alpha: float,
    ) -> None:
        assert self._image is not None
        saved_image, saved_draw = self._image, self._draw
        # Transparent pixels carry the text colour so anti-aliased glyph
        # edges don't blend toward black.
        layer = Image.new("RGBA", saved_image.size, (*rgb, 0))
        self._image, self._draw = layer, ImageDraw.Draw(layer)
        self._in_layer = True
        try:
            self._draw_text(cmd)
        finally:
            self._in_layer = False
            self._image, self._draw = saved_image, saved_draw
        self._composite(layer, alpha)

    def _get_font(self, font_id: str, size_px: int) -> ImageFont.FreeTypeFont:
        """Resolve ``font_id`` + size to the bundled TTF, or raise.

        Only ``font_registry.ttf_path_for`` is consulted, so the preview
        uses the same font files as the PDF backend. There is no system
        font or bitmap fallback: an unknown id raises (fail loud, D4).
        """
        from holiday_card.renderers.font_registry import ttf_path_for

        key = (font_id, size_px)
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached
        path = ttf_path_for(font_id)
        if path is None:
            raise NotImplementedError(f"PNGRenderer: no bundled TTF for font_id {font_id!r}")
        font = ImageFont.truetype(str(path), size=size_px)
        self._font_cache[key] = font
        return font

    # ------------------------------------------------------------------
    # Images (with optional clip masking)
    # ------------------------------------------------------------------

    def _draw_image(self, cmd: DrawImage) -> None:
        """Paste an image onto the canvas, optionally through a clip mask.

        Steps:

        1. Open source via Pillow; convert to RGBA so alpha compositing
           works regardless of the source format.
        2. Resize to the target rect's pixel dimensions. ``preserve_aspect``
           scales (up or down) to fit inside the box; otherwise stretches
           to fill.
        3. Compute pixel position from the IR rect (bottom-left origin
           → top-left origin; height inversion via ``_y``).
        4. Composite through the active clip mask (``_composite``).
        5. Honor ``cmd.opacity`` by pre-multiplying the source's alpha
           channel.
        """
        assert self._image is not None
        rect = cmd.image.rect
        source_path = Path(cmd.image.source)
        if not source_path.is_file():
            raise FileNotFoundError(
                f"PNGRenderer: image source not found: {source_path}"
            )

        # Open + convert to RGBA (gives us a uniform alpha channel for
        # transparency-aware paste). Pillow auto-detects format.
        src = Image.open(source_path).convert("RGBA")

        target_w_px = max(1, int(round(self._len(rect.width))))
        target_h_px = max(1, int(round(self._len(rect.height))))
        if cmd.image.preserve_aspect:
            # Fit inside the target, scaling up as well as down
            # (``thumbnail`` never enlarges, so a small photo stayed
            # small). The off-axis may come out short; the centering
            # below puts the image in the middle of the intended rect.
            scale = min(target_w_px / src.width, target_h_px / src.height)
            fit = (
                max(1, min(target_w_px, round(src.width * scale))),
                max(1, min(target_h_px, round(src.height * scale))),
            )
            src = src.resize(fit, Image.Resampling.LANCZOS)
        else:
            src = src.resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)

        # Pre-multiply opacity into the alpha channel.
        if cmd.opacity != 1.0:
            alpha = src.split()[3]
            alpha = alpha.point(lambda a: int(a * cmd.opacity))
            src.putalpha(alpha)

        # IR rect (x, y) is bottom-left; compute Pillow top-left.
        # Center the (possibly aspect-preserved) image within the
        # original target rect so off-axis letterboxing reads as
        # margin rather than a corner-stuck image.
        rect_left_px = int(round(self._x(rect.x)))
        rect_top_px = int(round(self._y(rect.y + rect.height)))
        offset_x = (target_w_px - src.width) // 2
        offset_y = (target_h_px - src.height) // 2
        paste_x = rect_left_px + offset_x
        paste_y = rect_top_px + offset_y

        # Position on a transparent canvas-sized layer, then composite
        # through the active clip (if any).
        layer = Image.new("RGBA", self._image.size, (0, 0, 0, 0))
        layer.paste(src, (paste_x, paste_y))
        self._composite(layer)

    # ------------------------------------------------------------------
    # Fold lines
    # ------------------------------------------------------------------

    def _draw_fold_line(self, cmd: DrawFoldLine) -> None:
        """Draw a fold guide: 1 px grey, dashed 3 pt on / 3 pt off."""
        assert self._draw is not None
        if not self._in_layer and self._active_mask() is not None:
            self._draw_in_layer(lambda: self._draw_fold_line(cmd))
            return
        line = [(self._x(cmd.start.x), self._y(cmd.start.y)), (self._x(cmd.end.x), self._y(cmd.end.y))]
        pattern = [] if cmd.style == "solid" else [self._len(3.0)]
        self._draw_dashed_polyline(line, pattern, (178, 178, 178), 1)

    # ------------------------------------------------------------------
    # Paint helpers
    # ------------------------------------------------------------------

    def _fill_to_rgba(
        self, fill: object | None, opacity: float
    ) -> tuple[int, int, int, int] | None:
        if fill is None:
            return None
        if isinstance(fill, SolidPaint):
            c = fill.color
            return (
                int(round(c.r * 255)),
                int(round(c.g * 255)),
                int(round(c.b * 255)),
                int(round(c.a * opacity * 255)),
            )
        raise NotImplementedError(
            f"PNGRenderer does not yet handle paint type {type(fill).__name__} "
            "via _fill_to_rgba (use _draw_shape_with_complex_fill)"
        )

    # ------------------------------------------------------------------
    # Complex fills (gradients)
    # ------------------------------------------------------------------

    def _draw_shape_with_complex_fill(self, cmd: DrawShape) -> None:
        """Render a shape whose fill is a gradient.

        Pillow's ``ImageDraw`` only fills with a single color, so we
        build a small RGBA image sized to the shape's bounding box,
        render the fill into it pixel by pixel, build a mask for the
        shape's geometry in the same coord space, then composite.

        Stroke renders separately on top via the existing path.

        Performance: per-pixel Python iteration over the shape's bbox
        in pixels (~20-80K pixels per typical shape) takes ~50ms each.
        Acceptable for preview-quality PNG output; the PDF backend is
        the production-quality path.
        """
        assert self._image is not None
        bbox = self._geom_bbox_px(cmd.geometry)
        if bbox is None:
            raise NotImplementedError(
                f"PNGRenderer complex fill on geometry "
                f"{type(cmd.geometry).__name__} requires a bounding box."
            )
        bx, by, bw, bh = bbox
        # Clamp to canvas to avoid building enormous images for
        # offscreen geometry.
        canvas_w, canvas_h = self._image.size
        bx = max(0, bx)
        by = max(0, by)
        bw = max(1, min(bw, canvas_w - bx))
        bh = max(1, min(bh, canvas_h - by))

        # Build the fill image at shape-bbox size.
        fill_img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        self._render_complex_fill_into(
            fill_img, cmd.fill, cmd.opacity, bbox_origin=(bx, by),
        )

        # Build a mask matching the shape geometry, in shape-bbox coord
        # space (subtract bx/by from each coord).
        mask = Image.new("L", (bw, bh), 0)
        mask_draw = ImageDraw.Draw(mask)
        self._draw_geom_mask(mask_draw, cmd.geometry, offset=(bx, by))

        # AND the fill alpha with the shape mask so pixels outside the
        # shape stay transparent.
        fa = fill_img.split()[3]
        combined = ImageChops.multiply(fa, mask)
        fill_img.putalpha(combined)

        # Source-over onto the target at (bx, by); ``paste`` with the image
        # as its own mask would square the alpha on a transparent layer.
        self._image.alpha_composite(fill_img, (bx, by))

        # Stroke pass: draw the shape outline through the existing path.
        # Construct a tiny shim cmd with fill=None so the regular path
        # doesn't recurse back into complex-fill handling.
        if cmd.stroke is not None:
            stroke_cmd = cmd.model_copy(update={"fill": None})
            self._draw_shape(stroke_cmd)

    def _render_complex_fill_into(
        self,
        img: Image.Image,
        fill: object,
        opacity: float,
        bbox_origin: tuple[int, int],
    ) -> None:
        """Render gradient paint into the supplied small RGBA image.

        ``bbox_origin`` is the top-left of ``img`` in canvas pixels —
        used to translate IR-space gradient endpoints into image-local
        coords.
        """
        bx, by = bbox_origin
        w, h = img.size
        alpha_mult = max(0.0, min(1.0, opacity))

        if isinstance(fill, LinearGradientPaint):
            # Project each pixel onto the gradient axis and look up
            # the interpolated stop color.
            start_x_px = self._x(fill.start.x) - bx
            start_y_px = self._y(fill.start.y) - by
            end_x_px = self._x(fill.end.x) - bx
            end_y_px = self._y(fill.end.y) - by
            dx = end_x_px - start_x_px
            dy = end_y_px - start_y_px
            length_sq = dx * dx + dy * dy
            if length_sq < 1e-6:
                length_sq = 1.0
            stops = [(s.position, s.color) for s in fill.stops]
            data: list[tuple[int, int, int, int]] = []
            for y in range(h):
                for x in range(w):
                    # Projection parameter t in [0, 1]
                    t = ((x - start_x_px) * dx + (y - start_y_px) * dy) / length_sq
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                    r, g, b, a = _interp_stops(stops, t)
                    data.append((r, g, b, int(round(a * alpha_mult))))
            img.putdata(data)
        elif isinstance(fill, RadialGradientPaint):
            cx_px = self._x(fill.center.x) - bx
            cy_px = self._y(fill.center.y) - by
            r_px = self._len(fill.radius)
            if r_px < 1e-6:
                r_px = 1.0
            stops = [(s.position, s.color) for s in fill.stops]
            data = []
            for y in range(h):
                for x in range(w):
                    d = ((x - cx_px) ** 2 + (y - cy_px) ** 2) ** 0.5
                    t = d / r_px
                    if t > 1.0:
                        t = 1.0
                    elif t < 0.0:
                        t = 0.0
                    r, g, b, a = _interp_stops(stops, t)
                    data.append((r, g, b, int(round(a * alpha_mult))))
            img.putdata(data)

    def _geom_bbox_px(
        self, geom: object,
    ) -> tuple[int, int, int, int] | None:
        """Return geometry's bounding box in canvas pixels (top-left origin).

        Returns ``(x, y, width, height)`` where ``(x, y)`` is the
        top-left corner.
        """
        if isinstance(geom, RectGeom):
            x0 = self._x(geom.x)
            x1 = self._x(geom.x + geom.width)
            y0 = self._y(geom.y + geom.height)
            y1 = self._y(geom.y)
            return (
                int(round(min(x0, x1))),
                int(round(min(y0, y1))),
                int(round(abs(x1 - x0))) + 1,
                int(round(abs(y1 - y0))) + 1,
            )
        if isinstance(geom, CircleGeom):
            cx = self._x(geom.center.x)
            cy = self._y(geom.center.y)
            r = self._len(geom.radius)
            return (
                int(round(cx - r)),
                int(round(cy - r)),
                int(round(2 * r)) + 1,
                int(round(2 * r)) + 1,
            )
        if isinstance(geom, EllipseGeom):
            cx = self._x(geom.center.x)
            cy = self._y(geom.center.y)
            rx = self._len(geom.rx)
            ry = self._len(geom.ry)
            return (
                int(round(cx - rx)),
                int(round(cy - ry)),
                int(round(2 * rx)) + 1,
                int(round(2 * ry)) + 1,
            )
        if isinstance(geom, (PolygonGeom, PolylineGeom)):
            xs = [self._x(p.x) for p in geom.points]
            ys = [self._y(p.y) for p in geom.points]
            return (
                int(round(min(xs))),
                int(round(min(ys))),
                int(round(max(xs) - min(xs))) + 1,
                int(round(max(ys) - min(ys))) + 1,
            )
        return None

    def _draw_geom_mask(
        self,
        draw: ImageDraw.ImageDraw,
        geom: object,
        offset: tuple[int, int],
    ) -> None:
        """Stamp ``geom`` onto the given mask draw context at white.

        Coords are translated by ``-offset`` so the shape lands in the
        small bbox-local coord system used by complex-fill rendering.
        """
        ox, oy = offset
        if isinstance(geom, RectGeom):
            x0 = self._x(geom.x) - ox
            x1 = self._x(geom.x + geom.width) - ox
            y0 = self._y(geom.y + geom.height) - oy
            y1 = self._y(geom.y) - oy
            draw.rectangle((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), fill=255)
        elif isinstance(geom, CircleGeom):
            cx = self._x(geom.center.x) - ox
            cy = self._y(geom.center.y) - oy
            r = self._len(geom.radius)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        elif isinstance(geom, EllipseGeom):
            cx = self._x(geom.center.x) - ox
            cy = self._y(geom.center.y) - oy
            rx = self._len(geom.rx)
            ry = self._len(geom.ry)
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        elif isinstance(geom, (PolygonGeom, PolylineGeom)):
            pts = [(self._x(p.x) - ox, self._y(p.y) - oy) for p in geom.points]
            draw.polygon(pts, fill=255)
        else:
            raise NotImplementedError(
                f"PNGRenderer complex fill mask: {type(geom).__name__} unsupported"
            )

    def _stroke_to_rgba(
        self, stroke: Stroke | None, opacity: float
    ) -> tuple[int, int, int, int] | None:
        if stroke is None:
            return None
        c = stroke.color
        return (
            int(round(c.r * 255)),
            int(round(c.g * 255)),
            int(round(c.b * 255)),
            int(round(c.a * opacity * 255)),
        )


_Matrix = tuple[float, float, float, float, float, float]


def _compose(m: _Matrix, n: _Matrix) -> _Matrix:
    """``m ∘ n`` in PDF ``cm`` order: apply ``n`` first."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + c * b2, b * a2 + d * b2,
        a * c2 + c * d2, b * c2 + d * d2,
        a * e2 + c * f2 + e, b * e2 + d * f2 + f,
    )


def _invert(m: _Matrix) -> _Matrix:
    a, b, c, d, e, f = m
    det = a * d - b * c
    return (
        d / det, -b / det, -c / det, a / det,
        (c * f - d * e) / det, (b * e - a * f) / det,
    )
