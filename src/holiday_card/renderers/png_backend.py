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
Mirrors the Wave 2 compiler's supported feature subset (PR #6) — the
same set the SVG backend covers. Backgrounds, borders, basic shapes
with solid fills, text with three alignments, fold lines (dashing
emulated by short segments since Pillow doesn't natively dash),
``BeginGroup`` honored when transform is identity (the only case the
compiler emits today). Gradients, patterns, images, ``BeginClip``, and
non-identity group transforms raise ``NotImplementedError`` — fail
loud, not silent.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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
    PathGeom,
    PolygonGeom,
    PolylineGeom,
    RectGeom,
    RenderCommand,
    SetMetadata,
    SolidPaint,
    Stroke,
    Transform,
)

__all__ = ["PNGRenderer"]

logger = logging.getLogger(__name__)

# Cross-platform font fallback chain. Tried in order; Pillow's
# truetype() does some name-based fuzzy matching on macOS, so the
# bare names ("Helvetica") often work directly.
_FONT_FALLBACKS: dict[str, tuple[str, ...]] = {
    "Helvetica": ("Helvetica", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"),
    "Helvetica-Bold": ("Helvetica-Bold", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"),
    "Times-Roman": ("Times-Roman", "Times.ttf", "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"),
    "Courier": ("Courier", "Courier.ttf", "DejaVuSansMono.ttf", "LiberationMono-Regular.ttf"),
}
# Generic last-resort fallback chain when font_id is unrecognized.
_GENERIC_FALLBACKS: tuple[str, ...] = (
    "Helvetica",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
)


class PNGRenderer:
    """Renderer that visits a ``RenderCommand`` stream and writes a PNG.

    Single-method public surface, like the other backends. Stateless
    across calls — every ``render()`` invocation builds a fresh image.
    """

    name: str = "png"
    file_extension: str = ".png"

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
        # The cache holds whatever Pillow returns from truetype()
        # (FreeTypeFont) or load_default() (ImageFont). Both expose the
        # subset of the API that ImageDraw.text() uses.
        self._font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

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
        # Active clip stack — geometries (in IR coords) for any open
        # BeginClip / EndClip pairs. Today only ``_draw_image`` reads
        # this; shapes and text inside a clip are not exercised by the
        # compiler. Push on BeginClip, pop on EndClip.
        self._clip_stack: list[object] = []

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
            self._clip_stack.append(cmd.geometry)
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
        self._image = Image.new("RGB", (width_px, height_px), (255, 255, 255))
        self._draw = ImageDraw.Draw(self._image)

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def _begin_group(self, cmd: BeginGroup) -> None:
        t = cmd.transform
        is_identity = (
            t.translate_x == 0 and t.translate_y == 0
            and t.rotate_deg == 0
            and t.scale_x == 1.0 and t.scale_y == 1.0
        )
        if cmd.opacity != 1.0:
            # Group opacity would need a separate compositing layer with
            # alpha-multiply. Not exercised by the compiler today.
            raise NotImplementedError(
                "PNGRenderer does not yet handle BeginGroup with non-1.0 opacity"
            )
        if is_identity:
            # No isolation needed; draw context unchanged.
            self._group_stack.append(None)
            return
        # The transform represents "rotate `rotate_deg` around the pivot
        # (translate_x, translate_y) in IR coords, with optional scale"
        # — the pivot-rotate-untranslate idiom from the legacy renderer
        # (reportlab_renderer.py:96-102) and matches the IR ReportLab
        # backend's _apply_transform. We render the group's content to a
        # transparent overlay at the same dimensions, then rotate the
        # whole overlay around the pivot when EndGroup arrives.
        if t.scale_x != 1.0 or t.scale_y != 1.0:
            raise NotImplementedError(
                "PNGRenderer does not yet handle BeginGroup with non-unit scale "
                "(compiler does not emit it)"
            )
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
        # Pivot in pixel space (IR is bottom-left, Pillow is top-left)
        pivot_px = (self._x(transform.translate_x), self._y(transform.translate_y))
        # Pillow's rotate angle is counter-clockwise in the y-down pixel
        # system, which matches the IR's CCW convention once we account
        # for the y-flip: the effective screen rotation direction is the
        # same.
        rotated = overlay.rotate(
            transform.rotate_deg,
            center=pivot_px,
            resample=Image.Resampling.BICUBIC,
        )
        # Composite back onto the parent using the rotated overlay's
        # alpha as a mask so the parent's content shows through gaps.
        if saved_image.mode == "RGB":
            saved_image.paste(rotated, (0, 0), rotated)
        else:
            saved_image.alpha_composite(rotated)
        self._image = saved_image
        self._draw = saved_draw

    # ------------------------------------------------------------------
    # Shape drawing
    # ------------------------------------------------------------------

    def _draw_shape(self, cmd: DrawShape) -> None:
        assert self._draw is not None
        fill_rgba = self._fill_to_rgba(cmd.fill, cmd.opacity)
        stroke_rgba = self._stroke_to_rgba(cmd.stroke, cmd.opacity)
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
            else:
                self._draw.rectangle(
                    (x0, y0, x1, y1),
                    fill=fill_rgba, outline=stroke_rgba, width=stroke_width,
                )
        elif isinstance(geom, CircleGeom):
            cx = self._x(geom.center.x)
            cy = self._y(geom.center.y)
            r = self._len(geom.radius)
            self._draw.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                fill=fill_rgba, outline=stroke_rgba, width=stroke_width,
            )
        elif isinstance(geom, EllipseGeom):
            cx = self._x(geom.center.x)
            cy = self._y(geom.center.y)
            rx = self._len(geom.rx)
            ry = self._len(geom.ry)
            self._draw.ellipse(
                (cx - rx, cy - ry, cx + rx, cy + ry),
                fill=fill_rgba, outline=stroke_rgba, width=stroke_width,
            )
        elif isinstance(geom, PolygonGeom):
            pts = [(self._x(p.x), self._y(p.y)) for p in geom.points]
            self._draw.polygon(pts, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif isinstance(geom, PolylineGeom):
            pts = [(self._x(p.x), self._y(p.y)) for p in geom.points]
            # Pillow's polygon doesn't fill open shapes the same way; for
            # an open polyline, draw as a line. Fill is ignored.
            self._draw.line(
                pts, fill=stroke_rgba or (0, 0, 0, 255),
                width=max(1, stroke_width), joint="curve",
            )
        elif isinstance(geom, PathGeom):
            # PathGeom is not exercised by the current compiler; flatten
            # to lines via the points and draw best-effort.
            self._draw_path(geom, fill_rgba, stroke_rgba, stroke_width)

    def _draw_path(
        self,
        geom: PathGeom,
        fill_rgba: tuple[int, int, int, int] | None,
        stroke_rgba: tuple[int, int, int, int] | None,
        stroke_width: int,
    ) -> None:
        """Best-effort path rendering: flatten cubic/quadratic curves into
        polylines for Pillow, which has no native bezier API. Currently
        the compiler emits no PathGeom commands, so this is defensive
        only.
        """
        assert self._draw is not None
        # Walk ops, collect subpaths
        current = (0.0, 0.0)
        subpath: list[tuple[float, float]] = []
        subpaths: list[list[tuple[float, float]]] = []
        for op in geom.ops:
            if op.op == "move":
                if subpath:
                    subpaths.append(subpath)
                p = op.points[0]
                current = (self._x(p.x), self._y(p.y))
                subpath = [current]
            elif op.op == "line":
                p = op.points[0]
                current = (self._x(p.x), self._y(p.y))
                subpath.append(current)
            elif op.op in ("cubic", "quadratic"):
                # Sample 8 points along the curve. Pillow has no native
                # bezier, so this is best-effort. Real bezier sampling
                # is left for a follow-up if/when needed.
                target = op.points[-1]
                current = (self._x(target.x), self._y(target.y))
                subpath.append(current)
            elif op.op == "close":
                if subpath:
                    subpath.append(subpath[0])
        if subpath:
            subpaths.append(subpath)
        for sp in subpaths:
            if len(sp) >= 2:
                if fill_rgba is not None and sp[0] == sp[-1]:
                    self._draw.polygon(sp, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
                else:
                    self._draw.line(sp, fill=stroke_rgba or (0, 0, 0, 255),
                                     width=max(1, stroke_width))

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def _draw_text(self, cmd: DrawText) -> None:
        assert self._draw is not None
        run = cmd.run
        size_px = max(1, int(round(run.size_pt * self._scale)))
        font = self._get_font(run.font_id, size_px)
        # Pillow anchor codes: l/m/r for x, t/m/s/b for y. We want
        # baseline-aligned to match ReportLab's drawString origin
        # convention, so use 's' (baseline) for y.
        anchor_map = {"left": "ls", "center": "ms", "right": "rs"}
        anchor = anchor_map[run.align]
        rgb = (
            int(round(run.color.r * 255)),
            int(round(run.color.g * 255)),
            int(round(run.color.b * 255)),
        )
        self._draw.text(
            (self._x(run.origin.x), self._y(run.origin.y)),
            run.text,
            font=font,
            fill=rgb,
            anchor=anchor,
        )

    def _get_font(
        self, font_id: str, size_px: int
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Resolve ``font_id`` + size to a Pillow font, with fallbacks.

        Prefers the bundled Liberation TTF for the default font_ids
        (Helvetica/Times-Roman/Courier and bold/italic variants), so the
        PNG preview matches what the PDF backend renders byte-for-byte.
        Falls back to system font lookup for custom font_ids.
        """
        from holiday_card.renderers.font_registry import ttf_path_for

        key = (font_id, size_px)
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached

        # Bundled Liberation TTF, if this font_id is one of the defaults
        bundled = ttf_path_for(font_id)
        if bundled is not None:
            try:
                font = ImageFont.truetype(str(bundled), size=size_px)
                self._font_cache[key] = font
                return font
            except OSError:
                pass  # fall through to fallback chain

        candidates = list(_FONT_FALLBACKS.get(font_id, ())) + list(_GENERIC_FALLBACKS)
        for candidate in candidates:
            try:
                font = ImageFont.truetype(candidate, size=size_px)
                self._font_cache[key] = font
                return font
            except OSError:
                continue

        logger.warning(
            "PNGRenderer: no truetype font found for %r; using Pillow's bitmap fallback. "
            "Install a system font for better preview quality.",
            font_id,
        )
        fallback = ImageFont.load_default()
        self._font_cache[key] = fallback
        return fallback

    # ------------------------------------------------------------------
    # Images (with optional clip masking)
    # ------------------------------------------------------------------

    def _draw_image(self, cmd: DrawImage) -> None:
        """Paste an image onto the canvas, optionally through a clip mask.

        Steps:

        1. Open source via Pillow; convert to RGBA so alpha compositing
           works regardless of the source format.
        2. Resize to the target rect's pixel dimensions. ``preserve_aspect``
           uses :meth:`PIL.Image.Image.thumbnail` (fits inside the box);
           otherwise stretches to fill.
        3. Compute pixel position from the IR rect (bottom-left origin
           → top-left origin; height inversion via ``_y``).
        4. If a clip is active, build a mask matching the clip geometry
           in pixel space and paste through it. Otherwise paste directly.
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
            # ``thumbnail`` resizes in place to fit *within* the target,
            # preserving aspect ratio. The result's actual dimensions
            # may be smaller than (target_w_px, target_h_px) on the
            # off-axis; the centering below compensates so the image
            # sits in the middle of the intended rect.
            src.thumbnail((target_w_px, target_h_px), Image.Resampling.LANCZOS)
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

        if not self._clip_stack:
            self._image.paste(src, (paste_x, paste_y), src)
            return

        # Active clip: build a mask matching the clip geometry in the
        # main canvas's pixel space, then composite the image through it.
        canvas_w, canvas_h = self._image.size
        mask = Image.new("L", (canvas_w, canvas_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        for geom in self._clip_stack:
            self._stamp_clip_geom(mask_draw, geom)
        # Build a composite image of the source positioned on a
        # transparent layer at canvas size, then apply the mask as
        # alpha. paste with mask=mask uses the mask's grayscale as the
        # alpha of the source pixels.
        positioned = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        positioned.paste(src, (paste_x, paste_y), src)
        # AND-combine the positioned image's alpha with the clip mask
        # so pixels outside the clip become transparent. Pillow's
        # ImageChops.multiply does per-pixel multiplication on
        # grayscale channels — exactly what mask intersection wants.
        from PIL import ImageChops
        src_alpha = positioned.split()[3]
        combined_alpha = ImageChops.multiply(src_alpha, mask)
        positioned.putalpha(combined_alpha)
        self._image.paste(positioned, (0, 0), positioned)

    def _stamp_clip_geom(
        self,
        mask_draw: ImageDraw.ImageDraw,
        geom: object,
    ) -> None:
        """Stamp ``geom`` (in IR coords) onto the mask at full white."""
        if isinstance(geom, CircleGeom):
            cx_px = self._x(geom.center.x)
            cy_px = self._y(geom.center.y)
            r_px = self._len(geom.radius)
            mask_draw.ellipse(
                (cx_px - r_px, cy_px - r_px, cx_px + r_px, cy_px + r_px),
                fill=255,
            )
        elif isinstance(geom, RectGeom):
            # IR rect: bottom-left origin. Pillow expects (left, top, right, bottom).
            left = self._x(geom.x)
            top = self._y(geom.y + geom.height)
            right = self._x(geom.x + geom.width)
            bottom = self._y(geom.y)
            mask_draw.rectangle((left, top, right, bottom), fill=255)
        elif isinstance(geom, EllipseGeom):
            cx_px = self._x(geom.center.x)
            cy_px = self._y(geom.center.y)
            rx_px = self._len(geom.rx)
            ry_px = self._len(geom.ry)
            mask_draw.ellipse(
                (cx_px - rx_px, cy_px - ry_px, cx_px + rx_px, cy_px + ry_px),
                fill=255,
            )
        elif isinstance(geom, PolygonGeom):
            mask_draw.polygon(
                [(self._x(p.x), self._y(p.y)) for p in geom.points],
                fill=255,
            )
        else:
            raise NotImplementedError(
                f"PNGRenderer: clip geometry {type(geom).__name__} not yet "
                "supported for image masking."
            )

    # ------------------------------------------------------------------
    # Fold lines
    # ------------------------------------------------------------------

    def _draw_fold_line(self, cmd: DrawFoldLine) -> None:
        """Draw a fold guide. Pillow has no native dash pattern, so
        emulate dashed style with short alternating segments.
        """
        assert self._draw is not None
        x0 = self._x(cmd.start.x)
        y0 = self._y(cmd.start.y)
        x1 = self._x(cmd.end.x)
        y1 = self._y(cmd.end.y)
        grey = (178, 178, 178)
        if cmd.style == "solid":
            self._draw.line((x0, y0, x1, y1), fill=grey, width=1)
            return
        # Dashed: 3pt on, 3pt off, scaled by DPI.
        dash_len = 3 * self._scale
        dx = x1 - x0
        dy = y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        if length == 0:
            return
        ux = dx / length
        uy = dy / length
        position = 0.0
        on = True
        while position < length:
            seg_end = min(position + dash_len, length)
            if on:
                self._draw.line(
                    (x0 + ux * position, y0 + uy * position,
                     x0 + ux * seg_end, y0 + uy * seg_end),
                    fill=grey, width=1,
                )
            position = seg_end
            on = not on

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
            f"PNGRenderer does not yet handle paint type {type(fill).__name__}"
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
