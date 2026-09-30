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
  lowered to clip + solid primitives by the compiler, #74); strokes
  centred on the edge with fractional widths, miter joins (SVG's limit
  of 4, then bevel) and butt caps; ``Stroke.dash`` with PDF/SVG
  semantics (odd-length arrays repeat, phase 0, restart per subpath). A
  ``line_cap`` other than ``butt`` raises: PDF and SVG draw butt only.
* Text with three alignments; effective alpha is
  ``DrawText.opacity × run.color.a``. Fonts resolve **only** through
  ``font_registry.ttf_path_for``; an id with no bundled TTF raises.
* Images (PNG/JPEG), with ``opacity``.
* ``BeginClip`` / ``EndClip`` for rect / circle / ellipse / polygon /
  path geometry. Nested clips intersect and apply to shapes, text,
  images and fold lines. A clip opened outside a rotated group applies
  to the group's composited result. ``PolylineGeom`` clips raise at
  ``BeginClip``.
* ``BeginGroup`` with any ``Transform`` (``to_matrix()``); group
  ``opacity != 1`` raises.

Anti-aliasing (#77)
-------------------
Every fill, stroke and clip is a per-shape ``"L"`` coverage mask
(``_coverage_mask``) drawn at ``SUPERSAMPLE`` (4)× inside the shape's
pixel box only and box-reduced, so edges carry fractional coverage.
Each supersample is painted when its centre is inside: rects, rounded
rects and ellipses through ``_pixel_span``, everything else through the
nonzero scanline filler ``_scan_fill`` (Pillow's polygon filler floors
vertices and fills both ends). The colour composites through the mask
on a layer the size of that box (text: its ink box; images: the image),
never a page-sized one. Gradients are evaluated without per-pixel
Python (``_draw_shape_with_complex_fill``). A group overlay is mapped
through its transform over the content's box only. ``antialias=False``
samples once per pixel instead: every pixel fully in or out, strokes at
least 1 px, for tests that need exact values.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageMath

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

    # Coverage masks are drawn at this many samples per pixel per axis.
    SUPERSAMPLE: int = 4

    def __init__(self, dpi: int = 144, antialias: bool = True) -> None:
        """Initialize the renderer.

        Args:
            dpi: Output resolution in dots per inch. 72 = 1px:1pt
                (smallest, fastest). 144 (the default) is a good preview
                quality. 288 for high-DPI display.
            antialias: Supersample shape, stroke and clip edges (the
                default). ``False`` draws them aliased, every pixel fully
                in or out, with strokes at least 1 px wide: for tests that
                need exact pixel values.
        """
        if dpi < 32:
            raise ValueError(f"dpi must be >= 32, got {dpi}")
        self.dpi = dpi
        self._scale = dpi / 72.0
        self._antialias = antialias
        self._supersample = self.SUPERSAMPLE if antialias else 1
        self._font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def render(self, commands: Iterable[RenderCommand], output: Path) -> None:
        """Consume ``commands`` and write a PNG at ``output``."""
        output.parent.mkdir(parents=True, exist_ok=True)

        # State accumulated across the visit
        self._page_height_pts: float = 0.0
        self._bleed_pts: float = 0.0
        self._image: Image.Image | None = None
        self._metadata: dict[str, str] = {}
        # Stack of (saved_image, transform). When a BeginGroup has a
        # non-identity transform we push the current target, redirect
        # drawing to a transparent overlay, and on EndGroup we map the
        # overlay through the transform and composite it back.
        self._group_stack: list[tuple[Image.Image, Transform] | None] = []
        # Open clips as (group level, mask). Each "L" canvas-sized mask
        # is already intersected with the enclosing clip at the same
        # level; clips from outer levels apply when the rotated group
        # overlay is composited back in ``_end_group``.
        self._clip_stack: list[tuple[int, Image.Image]] = []

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
        # The canvas starts opaque white and only ever takes source-over
        # composites, so it is opaque: dropping alpha is the RGB page.
        self._image.convert("RGB").save(output, "PNG", pnginfo=info)

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
        # RGBA so every draw composites source-over with
        # ``Image.alpha_composite``; ``render`` flattens it onto white
        # before writing, so the saved file is RGB.
        self._image = Image.new("RGBA", (width_px, height_px), (255, 255, 255, 255))

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
        assert self._image is not None
        saved_image = self._image
        self._image = Image.new("RGBA", saved_image.size, (0, 0, 0, 0))
        self._group_stack.append((saved_image, t))

    def _end_group(self) -> None:
        if not self._group_stack:
            raise RuntimeError("PNGRenderer: EndGroup with no open group")
        state = self._group_stack.pop()
        if state is None:
            return  # identity group; nothing to composite
        saved_image, transform = state
        overlay = self._image
        assert overlay is not None
        # Composite back onto the parent through the parent level's
        # clip, so a clip opened outside the group still applies.
        self._image = saved_image
        content = overlay.getbbox()
        if content is None:
            return
        if transform.is_identity():
            self._composite(overlay.crop(content), content[:2])
            return
        # Map only the output box the content lands in, not the whole page.
        forward = self._pixel_affine(transform)
        corners = [
            _apply(forward, x, y)
            for x in (content[0], content[2]) for y in (content[1], content[3])
        ]
        box = self._pixel_box(
            (min(p[0] for p in corners), min(p[1] for p in corners),
             max(p[0] for p in corners), max(p[1] for p in corners)),
            2.0,
        )
        if box is None:
            return
        a, b, c, d, e, f = _invert(forward)
        ox, oy = box[0], box[1]
        # Pillow wants x_in = a·x + c·y + e, y_in = b·x + d·y + f as (a, c, e, b, d, f),
        # with (x, y) relative to the output box.
        transformed = overlay.transform(
            (box[2] - ox, box[3] - oy),
            Image.Transform.AFFINE,
            (a, c, e + a * ox + c * oy, b, d, f + b * ox + d * oy),
            resample=Image.Resampling.BICUBIC,
        )
        self._composite(transformed, (ox, oy))

    def _pixel_affine(self, t: Transform) -> _Matrix:
        """``t`` as a canvas-pixel affine in PDF ``cm`` order (source → output).

        The forward map in pixel space is ``P · M · P⁻¹``, where ``M`` is
        ``t.to_matrix()`` and ``P`` is the IR → pixel map (bleed offset,
        DPI scale, y-flip) that ``_x`` / ``_y`` apply.
        """
        s, b, h = self._scale, self._bleed_pts, self._page_height_pts
        to_px = (s, 0.0, 0.0, -s, s * b, s * (h + b))
        from_px = (1 / s, 0.0, 0.0, -1 / s, -b, h + b)
        return _compose(to_px, _compose(t.to_matrix(), from_px))

    # ------------------------------------------------------------------
    # Clips and compositing
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
        geom = cmd.geometry
        if isinstance(geom, PolylineGeom):
            raise NotImplementedError(
                "PNGRenderer: clip geometry PolylineGeom is not supported "
                "(an open polyline has no interior)"
            )
        assert self._image is not None
        mask = Image.new("L", self._image.size, 0)
        box = self._pixel_box(self._geom_extent_px(geom), 1.0)
        if box is not None:
            mask.paste(self._coverage_mask(geom, box), box[:2])
        enclosing = self._active_mask()
        if enclosing is not None:
            mask = ImageChops.multiply(mask, enclosing)
        self._clip_stack.append((self._group_level(), mask))

    def _composite(
        self, layer: Image.Image, dest: tuple[int, int] = (0, 0), alpha: float = 1.0
    ) -> None:
        """Source-over ``layer`` at ``dest``, scaled by ``alpha`` and clipped.

        The layer may hang off the canvas; only the overlap is composited.
        """
        assert self._image is not None
        x, y = dest
        canvas_w, canvas_h = self._image.size
        left, top = max(0, x), max(0, y)
        right, bottom = min(canvas_w, x + layer.width), min(canvas_h, y + layer.height)
        if right <= left or bottom <= top:
            return
        if (left, top, right, bottom) != (x, y, x + layer.width, y + layer.height):
            layer = layer.crop((left - x, top - y, right - x, bottom - y))
        mask = self._active_mask()
        if mask is not None or alpha < 1.0:
            layer_alpha = layer.getchannel("A")
            if alpha < 1.0:
                layer_alpha = layer_alpha.point(_scale_lut(alpha))
            if mask is not None:
                layer_alpha = ImageChops.multiply(
                    layer_alpha, mask.crop((left, top, right, bottom))
                )
            layer.putalpha(layer_alpha)
        self._image.alpha_composite(layer, (left, top))

    def _paint_mask(
        self, mask: Image.Image, box: tuple[int, int, int, int], color: RGBA, opacity: float
    ) -> None:
        """Composite ``color`` × ``opacity`` through the coverage ``mask`` at ``box``."""
        alpha = color.a * opacity
        if alpha <= 0.0:
            return
        layer = Image.new("RGBA", mask.size, (*_rgb8(color), 0))
        layer.putalpha(mask if alpha >= 1.0 else mask.point(_scale_lut(alpha)))
        self._composite(layer, box[:2])

    # ------------------------------------------------------------------
    # Coverage masks
    # ------------------------------------------------------------------

    def _geom_extent_px(self, geom: GeomU) -> tuple[float, float, float, float]:
        """``(left, top, right, bottom)`` of ``geom`` in canvas pixels (unstroked)."""
        if isinstance(geom, RectGeom):
            return (
                self._x(geom.x), self._y(geom.y + geom.height),
                self._x(geom.x + geom.width), self._y(geom.y),
            )
        if isinstance(geom, (CircleGeom, EllipseGeom)):
            cx, cy = self._x(geom.center.x), self._y(geom.center.y)
            rx, ry = self._radii_px(geom)
            return (cx - rx, cy - ry, cx + rx, cy + ry)
        if isinstance(geom, PathGeom):
            pts = [p for sp in self._flatten_path(geom) for p in sp]
        else:
            pts = [(self._x(p.x), self._y(p.y)) for p in geom.points]
        if not pts:
            return (0.0, 0.0, 0.0, 0.0)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def _pixel_box(
        self, extent: tuple[float, float, float, float], pad: float
    ) -> tuple[int, int, int, int] | None:
        """Integer pixel box around ``extent`` + ``pad``, clamped to the canvas."""
        assert self._image is not None
        left = max(0, math.floor(extent[0] - pad))
        top = max(0, math.floor(extent[1] - pad))
        right = min(self._image.width, math.ceil(extent[2] + pad))
        bottom = min(self._image.height, math.ceil(extent[3] + pad))
        if right <= left or bottom <= top:
            return None
        return (left, top, right, bottom)

    def _radii_px(self, geom: CircleGeom | EllipseGeom) -> tuple[float, float]:
        if isinstance(geom, CircleGeom):
            return (self._len(geom.radius),) * 2
        return (self._len(geom.rx), self._len(geom.ry))

    def _coverage_mask(
        self,
        geom: GeomU,
        bbox_px: tuple[int, int, int, int],
        *,
        stroke_width_px: float | None = None,
        dash: Sequence[float] = (),
    ) -> Image.Image:
        """``"L"`` coverage of ``geom`` over ``bbox_px`` (canvas pixels).

        Drawn at ``self._supersample``× and box-reduced, so edges carry
        fractional coverage (anti-aliasing); every supersample is painted
        when its centre is inside. Without ``stroke_width_px`` it is the
        fill; with it, the stroke centred on the edge: rects, circles and
        ellipses as the shape grown by ``w/2`` minus the shape shrunk by
        ``w/2``, everything else as per-segment quads with miter joins and
        butt caps (``_stroke_polygons``). ``dash`` is in pixels, PDF/SVG
        semantics.
        """
        ss = self._supersample
        ox, oy = bbox_px[0], bbox_px[1]
        size = ((bbox_px[2] - ox) * ss, (bbox_px[3] - oy) * ss)
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)

        def to_ss(x: float, y: float) -> tuple[float, float]:
            return ((x - ox) * ss, (y - oy) * ss)

        if stroke_width_px is None:
            self._fill_coverage(draw, geom, to_ss, size)
        elif not dash and isinstance(geom, (RectGeom, CircleGeom, EllipseGeom)):
            self._stroke_coverage_exact(draw, geom, to_ss, stroke_width_px * ss / 2)
        else:
            half = stroke_width_px * ss / 2
            polys: list[list[_Pt]] = []
            for outline in self._outline_polylines(geom):
                pts = [to_ss(*p) for p in outline]
                if dash:
                    for run in _dash_runs(pts, [d * ss for d in dash]):
                        polys += _stroke_polygons(run, half, closed=False)
                else:
                    closed = len(pts) > 2 and pts[0] == pts[-1]
                    polys += _stroke_polygons(pts, half, closed=closed)
            _scan_fill(draw, polys, size)
        return mask.reduce(ss) if ss > 1 else mask

    def _fill_coverage(
        self,
        draw: ImageDraw.ImageDraw,
        geom: GeomU,
        to_ss: Callable[[float, float], tuple[float, float]],
        size: tuple[int, int],
    ) -> None:
        if isinstance(geom, (RectGeom, CircleGeom, EllipseGeom)):
            self._draw_box_shape(draw, geom, to_ss, 0.0, 255)
        elif isinstance(geom, PolygonGeom):
            _scan_fill(draw, [[to_ss(self._x(p.x), self._y(p.y)) for p in geom.points]], size)
        elif isinstance(geom, PathGeom):
            # One nonzero fill over all subpaths, each implicitly closed (PDF / SVG).
            _scan_fill(draw, [[to_ss(*p) for p in sp] for sp in self._flatten_path(geom)], size)
        # An open polyline has no interior: its fill paints nothing.

    def _stroke_coverage_exact(
        self,
        draw: ImageDraw.ImageDraw,
        geom: RectGeom | CircleGeom | EllipseGeom,
        to_ss: Callable[[float, float], tuple[float, float]],
        half: float,
    ) -> None:
        """Outer shape (grown by ``half``) minus inner shape (shrunk by ``half``)."""
        self._draw_box_shape(draw, geom, to_ss, half, 255)
        self._draw_box_shape(draw, geom, to_ss, -half, 0)

    def _draw_box_shape(
        self,
        draw: ImageDraw.ImageDraw,
        geom: RectGeom | CircleGeom | EllipseGeom,
        to_ss: Callable[[float, float], tuple[float, float]],
        grow: float,
        value: int,
    ) -> None:
        """Rect / rounded rect / ellipse grown by ``grow`` supersampled pixels.

        Pixels whose centres fall inside are painted (``_pixel_span``);
        a shape shrunk to nothing paints nothing.
        """
        ss = self._supersample
        left, top, right, bottom = self._geom_extent_px(geom)
        x0, y0 = to_ss(left, top)
        x1, y1 = to_ss(right, bottom)
        x0, y0, x1, y1 = x0 - grow, y0 - grow, x1 + grow, y1 + grow
        if x1 <= x0 or y1 <= y0:
            return
        left_px, right_px = _pixel_span(x0, x1)
        top_px, bottom_px = _pixel_span(y0, y1)
        box = (left_px, top_px, right_px, bottom_px)
        if isinstance(geom, RectGeom):
            radius = self._len(geom.corner_radius) * ss + grow if geom.corner_radius > 0 else 0.0
            if radius > 0:
                draw.rounded_rectangle(box, radius=radius, fill=value)
            else:
                draw.rectangle(box, fill=value)
        else:
            draw.ellipse(box, fill=value)

    # ------------------------------------------------------------------
    # Shape drawing
    # ------------------------------------------------------------------

    def _draw_shape(self, cmd: DrawShape) -> None:
        geom = cmd.geometry
        extent = self._geom_extent_px(geom)
        if cmd.fill is not None and not isinstance(geom, PolylineGeom):
            box = self._pixel_box(extent, 1.0)
            if box is not None:
                mask = self._coverage_mask(geom, box)
                if isinstance(cmd.fill, SolidPaint):
                    self._paint_mask(mask, box, cmd.fill.color, cmd.opacity)
                else:
                    self._draw_shape_with_complex_fill(cmd.fill, mask, box, cmd.opacity)
        if cmd.stroke is not None:
            self._draw_stroke(geom, cmd.stroke, cmd.stroke.color, cmd.opacity, extent)

    def _draw_stroke(
        self,
        geom: GeomU,
        stroke: Stroke,
        color: RGBA,
        opacity: float,
        extent: tuple[float, float, float, float] | None = None,
    ) -> None:
        if stroke.line_cap != "butt":
            # PDF and SVG draw butt caps only; drawing others here would
            # make the preview differ from the oracle (D4, D12).
            raise NotImplementedError(
                f"PNGRenderer: line_cap {stroke.line_cap!r} is not supported (butt only)"
            )
        width = self._len(stroke.width)
        if not self._antialias:
            width = max(1, round(width))
        box = self._pixel_box(extent or self._geom_extent_px(geom), width / 2 + 2.0)
        if box is None:
            return
        mask = self._coverage_mask(
            geom, box, stroke_width_px=width,
            dash=[self._len(d) for d in stroke.dash],
        )
        self._paint_mask(mask, box, color, opacity)

    # Polyline samples per Bezier curve segment: at least 16 (smooth for the
    # holly-wreath leaves at 144 DPI), and one per ``_BEZIER_STEP_PX`` of
    # control-polygon length so large curves keep short chords (at most
    # ``_BEZIER_MAX_SAMPLES``).
    _BEZIER_SAMPLES: int = 16
    _BEZIER_STEP_PX: float = 4.0
    _BEZIER_MAX_SAMPLES: int = 512

    def _curve_samples(self, *points: tuple[float, float]) -> int:
        length = sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False))
        steps = math.ceil(self._len(length) / self._BEZIER_STEP_PX)
        return max(self._BEZIER_SAMPLES, min(self._BEZIER_MAX_SAMPLES, steps))

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
        """Append ``_curve_samples`` sampled pixels of a cubic Bezier."""
        n = self._curve_samples(p0, p1, p2, p3)
        for k in range(1, n + 1):
            t = k / n
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
        """Append ``_curve_samples`` sampled pixels of a quadratic Bezier."""
        n = self._curve_samples(p0, p1, p2)
        for k in range(1, n + 1):
            t = k / n
            u = 1.0 - t
            x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            subpath.append((self._x(x), self._y(y)))

    # Minimum samples when flattening a circle / ellipse outline.
    _ELLIPSE_SAMPLES: int = 64

    def _outline_polylines(self, geom: GeomU) -> list[list[tuple[float, float]]]:
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
            rx, ry = self._radii_px(geom)
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
        return self._flatten_path(geom)

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def _draw_text(self, cmd: DrawText) -> None:
        """Draw the run on a layer the size of its ink box, then composite.

        Glyphs are opaque on a layer whose transparent pixels carry the
        text colour (AA edges don't blend toward black); the effective
        alpha ``opacity × color.a`` and any clip apply at composite time.
        """
        run = cmd.run
        size_px = max(1, int(round(run.size_pt * self._scale)))
        font = self._get_font(run.font_id, size_px)
        rgb = _rgb8(run.color)
        # Pillow anchor codes: l/m/r for x, t/m/s/b for y. Baseline ('s')
        # matches ReportLab's drawString origin convention.
        anchor = {"left": "ls", "center": "ms", "right": "rs"}[run.align]
        x, y = self._x(run.origin.x), self._y(run.origin.y)
        left, top, right, bottom = font.getbbox(run.text, anchor=anchor)
        bx, by = math.floor(x + left) - 1, math.floor(y + top) - 1
        size = (math.ceil(x + right) + 1 - bx, math.ceil(y + bottom) + 1 - by)
        if size[0] <= 0 or size[1] <= 0:
            return
        layer = Image.new("RGBA", size, (*rgb, 0))
        ImageDraw.Draw(layer).text(
            (x - bx, y - by), run.text, font=font, fill=(*rgb, 255), anchor=anchor,
        )
        self._composite(layer, (bx, by), cmd.opacity * run.color.a)

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
        """Composite an image, optionally through the active clip mask.

        Steps:

        1. Open source via Pillow; convert to RGBA so alpha compositing
           works regardless of the source format.
        2. Resize to the target rect's pixel dimensions. ``preserve_aspect``
           scales (up or down) to fit inside the box; otherwise stretches
           to fill.
        3. Compute pixel position from the IR rect (bottom-left origin
           → top-left origin; height inversion via ``_y``).
        4. Composite the image-sized layer through the active clip mask,
           scaled by ``cmd.opacity`` (``_composite``).
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

        # IR rect (x, y) is bottom-left; compute Pillow top-left.
        # Center the (possibly aspect-preserved) image within the
        # original target rect so off-axis letterboxing reads as
        # margin rather than a corner-stuck image.
        rect_left_px = int(round(self._x(rect.x)))
        rect_top_px = int(round(self._y(rect.y + rect.height)))
        paste_x = rect_left_px + (target_w_px - src.width) // 2
        paste_y = rect_top_px + (target_h_px - src.height) // 2
        self._composite(src, (paste_x, paste_y), cmd.opacity)

    # ------------------------------------------------------------------
    # Fold lines
    # ------------------------------------------------------------------

    # Fold guide: 0.5 pt of 0.7 grey, dashed 3 pt on / 3 pt off (PDF / SVG).
    _FOLD_STROKE = Stroke(color=RGBA(r=0.7, g=0.7, b=0.7), width=0.5)

    def _draw_fold_line(self, cmd: DrawFoldLine) -> None:
        stroke = self._FOLD_STROKE
        if cmd.style == "dashed":
            stroke = stroke.model_copy(update={"dash": (3.0, 3.0)})
        line = PolylineGeom(points=(cmd.start, cmd.end))
        self._draw_stroke(line, stroke, stroke.color, 1.0)

    # ------------------------------------------------------------------
    # Complex fills (gradients)
    # ------------------------------------------------------------------

    def _draw_shape_with_complex_fill(
        self,
        fill: LinearGradientPaint | RadialGradientPaint,
        mask: Image.Image,
        box: tuple[int, int, int, int],
        opacity: float,
    ) -> None:
        """Composite a gradient through the shape's coverage ``mask`` at ``box``.

        The gradient is evaluated without per-pixel Python: ``_gradient_t``
        builds the stop parameter ``t`` over the box as an 8-bit ``"L"``
        image with ``ImageMath`` (pixel centres, clamped to [0, 1]), and
        256-entry lookup tables from ``_interp_stops`` map it to R, G, B
        and A (× ``opacity``). Within ±1/255 per channel of evaluating
        ``_interp_stops`` per pixel; a 1000 × 1000 px fill takes ~50 ms.
        """
        t_map = self._gradient_t(fill, box)
        stops = [(s.position, s.color) for s in fill.stops]
        table = [_interp_stops(stops, i / 255) for i in range(256)]
        alpha_lut = [round(c[3] * max(0.0, min(1.0, opacity))) for c in table]
        bands = [t_map.point([c[k] for c in table]) for k in range(3)]
        alpha = ImageChops.multiply(t_map.point(alpha_lut), mask)
        self._composite(Image.merge("RGBA", (*bands, alpha)), box[:2])

    def _gradient_t(
        self, fill: LinearGradientPaint | RadialGradientPaint, box: tuple[int, int, int, int]
    ) -> Image.Image:
        """``"L"`` image of ``255 · t`` over ``box`` (canvas pixel centres)."""
        left, top, right, bottom = box
        w, h = right - left, bottom - top
        xs = Image.new("F", (w, 1))
        xs.putdata([left + i + 0.5 for i in range(w)])
        ys = Image.new("F", (1, h))
        ys.putdata([top + j + 0.5 for j in range(h)])
        grid_x = xs.resize((w, h), Image.Resampling.NEAREST)
        grid_y = ys.resize((w, h), Image.Resampling.NEAREST)
        if isinstance(fill, LinearGradientPaint):
            sx, sy = self._x(fill.start.x), self._y(fill.start.y)
            dx, dy = self._x(fill.end.x) - sx, self._y(fill.end.y) - sy
            length_sq = dx * dx + dy * dy
            if length_sq < 1e-6:
                length_sq = 1.0
            kx, ky = 255 * dx / length_sq, 255 * dy / length_sq

            def t255(a: dict[str, Any]) -> Any:
                return (a["x"] - sx) * kx + (a["y"] - sy) * ky
        else:
            cx, cy = self._x(fill.center.x), self._y(fill.center.y)
            k = 255 / max(self._len(fill.radius), 1e-6)

            def t255(a: dict[str, Any]) -> Any:
                return (((a["x"] - cx) ** 2 + (a["y"] - cy) ** 2) ** 0.5) * k

        # Clamp to [0, 255] and round (F → L conversion truncates).
        t_map: Image.Image = ImageMath.lambda_eval(
            lambda a: a["min"](a["max"](t255(a), 0.0), 255.0) + 0.5, x=grid_x, y=grid_y,
        )
        return t_map.convert("L")


def _rgb8(color: RGBA) -> tuple[int, int, int]:
    return (int(round(color.r * 255)), int(round(color.g * 255)), int(round(color.b * 255)))


def _scale_lut(alpha: float) -> list[int]:
    """``Image.point`` table multiplying an 8-bit channel by ``alpha``."""
    return [round(v * alpha) for v in range(256)]


_Pt = tuple[float, float]

# Miter joins longer than this many stroke widths fall back to bevels (SVG's
# default ``stroke-miterlimit``; the SVG backend is the oracle, D12).
_MITER_LIMIT = 4.0


def _scan_fill(draw: ImageDraw.ImageDraw, polygons: Iterable[list[_Pt]], size: tuple[int, int]) -> None:
    """Fill ``polygons`` (implicitly closed) with the nonzero rule, centre-sampled.

    A pixel is painted when its centre is inside, so a polygon on whole
    pixels has no partial edge (Pillow's filler floors vertices and fills
    both ends). One pass per row over the edges crossing it, not per pixel.
    """
    width, height = size
    edges: list[tuple[float, float, float, float, int]] = []  # y0, y1, x at y0, dx/dy, winding
    for poly in polygons:
        for (ax, ay), (bx, by) in zip(poly, [*poly[1:], poly[0]], strict=True):
            if ay == by:
                continue
            winding = 1 if by > ay else -1
            if ay > by:
                ax, ay, bx, by = bx, by, ax, ay
            edges.append((ay, by, ax, (bx - ax) / (by - ay), winding))
    if not edges:
        return
    edges.sort()
    first = max(0, math.ceil(edges[0][0] - 0.5))
    last = min(height - 1, math.ceil(max(e[1] for e in edges) - 0.5) - 1)
    active: list[tuple[float, float, float, float, int]] = []
    pending = 0
    for row in range(first, last + 1):
        yc = row + 0.5
        while pending < len(edges) and edges[pending][0] <= yc:
            active.append(edges[pending])
            pending += 1
        active = [e for e in active if e[1] > yc]
        crossings = sorted((e[2] + (yc - e[0]) * e[3], e[4]) for e in active if e[0] <= yc)
        winding = 0
        for (xa, wa), (xb, _) in zip(crossings, crossings[1:], strict=False):
            winding += wa
            if winding:
                left = max(0, math.ceil(xa - 0.5))
                right = min(width - 1, math.ceil(xb - 0.5) - 1)
                if right >= left:
                    draw.line((left, row, right, row), fill=255)


def _stroke_polygons(pts: list[_Pt], half: float, closed: bool) -> list[list[_Pt]]:
    """Outline of a ``2 · half`` stroke along ``pts``: butt caps, miter joins.

    One quad per segment plus one join polygon per corner, all wound the
    same way so ``_scan_fill``'s nonzero rule paints their union.
    """
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 2:
        return []
    segments = list(zip(pts, [*pts[1:], pts[0]] if closed else pts[1:], strict=False))
    normals = [_unit_normal(a, b) for a, b in segments]
    polys = [
        _oriented([(a[0] + nx * half, a[1] + ny * half), (b[0] + nx * half, b[1] + ny * half),
                   (b[0] - nx * half, b[1] - ny * half), (a[0] - nx * half, a[1] - ny * half)])
        for (a, b), (nx, ny) in zip(segments, normals, strict=True)
    ]
    corners = range(len(segments)) if closed else range(1, len(segments))
    for i in corners:
        join = _join_polygon(segments[i][0], normals[i - 1], normals[i], half)
        if join:
            polys.append(_oriented(join))
    return polys


def _unit_normal(a: _Pt, b: _Pt) -> _Pt:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    return (-dy / length, dx / length)


def _join_polygon(v: _Pt, n1: _Pt, n2: _Pt, half: float) -> list[_Pt] | None:
    """Miter (or, past ``_MITER_LIMIT``, bevel) wedge at corner ``v``."""
    cross = n1[0] * n2[1] - n1[1] * n2[0]
    if abs(cross) < 1e-9 and n1[0] * n2[0] + n1[1] * n2[1] > 0:
        return None  # straight on: the quads already meet
    # The gap opens on the side away from the turn.
    side = -1.0 if cross > 0 else 1.0
    c1 = (v[0] + side * n1[0] * half, v[1] + side * n1[1] * half)
    c2 = (v[0] + side * n2[0] * half, v[1] + side * n2[1] * half)
    bx, by = n1[0] + n2[0], n1[1] + n2[1]
    norm = math.hypot(bx, by)
    if norm > 1e-9:
        bx, by = bx / norm, by / norm
        cos_half = bx * n1[0] + by * n1[1]
        if cos_half > 1 / _MITER_LIMIT:
            m = (v[0] + side * bx * half / cos_half, v[1] + side * by * half / cos_half)
            return [v, c1, m, c2]
    return [v, c1, c2]


def _oriented(poly: list[_Pt]) -> list[_Pt]:
    """``poly`` with positive signed area, so overlapping pieces add up."""
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, [*poly[1:], poly[0]], strict=True))
    return poly if area >= 0 else poly[::-1]


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


def _apply(m: _Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _invert(m: _Matrix) -> _Matrix:
    a, b, c, d, e, f = m
    det = a * d - b * c
    return (
        d / det, -b / det, -c / det, a / det,
        (c * f - d * e) / det, (b * e - a * f) / det,
    )
