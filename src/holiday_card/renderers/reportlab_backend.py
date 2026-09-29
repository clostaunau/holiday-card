"""ReportLab backend for the rendering IR.

Consumes a ``list[RenderCommand]`` (built by ``core.compiler.compile_card``)
and writes a PDF. Wave 2 Step 3 in ``/tmp/wave2_architecture.md``.

Design properties:

* **Stateless across calls.** ``render(commands, output)`` opens a fresh
  canvas, dispatches over the discriminated union, and saves. No instance
  state survives a call.
* **No semantic decisions.** Every command has exactly one obvious
  ReportLab translation. Things like z-order, font choice, text wrapping,
  unit conversion, and decorative-element expansion already happened in
  the compiler.
* **Strict.** Any command this backend can't handle (e.g. an
  ``UnsupportedFeatureError`` was bypassed somehow) raises immediately
  rather than rendering a partial PDF.

This backend lives **alongside** the legacy ``ReportLabRenderer`` in this
PR. ``CardGenerator`` still uses the legacy path; Step 4 is the cutover.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as _canvas

from holiday_card.core.color_management import rgb_to_cmyk
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
    PatternPaint,
    PolygonGeom,
    PolylineGeom,
    RadialGradientPaint,
    RectGeom,
    RenderCommand,
    SetMetadata,
    SolidPaint,
    Stroke,
)
from holiday_card.renderers.font_registry import (
    ensure_default_fonts_registered,
    resolve_font_id,
)

__all__ = ["IRReportLabRenderer"]


class IRReportLabRenderer:
    """Renderer that visits a ``RenderCommand`` stream and writes a PDF.

    Public surface is a single method, ``render``. The renderer's color
    space is fixed at construction:

    * ``color_space="srgb"`` (default) — today's behavior; emits RGB
      color operators (rg/RG) suitable for home-printer / browser
      / on-screen consumption.
    * ``color_space="cmyk"`` — emits DeviceCMYK operators (k/K) using a
      naive sRGB→CMYK conversion at the boundary. Intended to be paired
      with a PDF/X-1a post-processor that attaches the destination
      OutputIntent ICC profile; the colorimetric work happens on the
      printer's RIP. See ``core/color_management.py``.
    """

    name: str = "reportlab"
    file_extension: str = ".pdf"

    def __init__(self, color_space: Literal["srgb", "cmyk"] = "srgb") -> None:
        self.color_space: Literal["srgb", "cmyk"] = color_space

    def render(self, commands: Iterable[RenderCommand], output: Path) -> None:
        """Consume ``commands`` and write a PDF at ``output``."""
        output.parent.mkdir(parents=True, exist_ok=True)
        # Register the embedded Liberation default-font chain. Idempotent
        # — called every render so a fresh process picks up the fonts;
        # subsequent calls are no-ops.
        ensure_default_fonts_registered()
        # ReportLab's default initial font is base-14 Helvetica, which it
        # never embeds; every page's opening ``/F1 12 Tf`` then references
        # an unembedded font (PDF/X-1a forbids it, #69).
        canvas = _canvas.Canvas(
            str(output), pagesize=letter, initialFontName=resolve_font_id("Helvetica")
        )
        try:
            for cmd in commands:
                self._dispatch(canvas, cmd)
        finally:
            canvas.save()

    # ------------------------------------------------------------------
    # Color emission helpers (color-space-aware)
    # ------------------------------------------------------------------

    def _set_fill(self, canvas: _canvas.Canvas, r: float, g: float, b: float) -> None:
        if self.color_space == "cmyk":
            c, m, y, k = rgb_to_cmyk(r, g, b)
            canvas.setFillColorCMYK(c, m, y, k)
        else:
            canvas.setFillColorRGB(r, g, b)

    def _set_stroke(self, canvas: _canvas.Canvas, r: float, g: float, b: float) -> None:
        if self.color_space == "cmyk":
            c, m, y, k = rgb_to_cmyk(r, g, b)
            canvas.setStrokeColorCMYK(c, m, y, k)
        else:
            canvas.setStrokeColorRGB(r, g, b)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, canvas: _canvas.Canvas, cmd: RenderCommand) -> None:
        # Pydantic discriminated unions resolve to a concrete class at
        # construction time, so isinstance dispatch is safe and fast.
        if isinstance(cmd, BeginPage):
            # ReportLab's MediaBox is set implicitly via setPageSize.
            # TrimBox marks the cut line; BleedBox equals MediaBox until
            # we add a slug area; ArtBox is the safe-content rectangle.
            # IR coordinates are in trim-relative coords with bottom-left
            # origin, so we translate the canvas by +bleed to align IR
            # (0, 0) with the trim corner of the larger media canvas.
            bleed = cmd.bleed
            safe = cmd.safe_margin
            media_w = cmd.width + 2 * bleed
            media_h = cmd.height + 2 * bleed
            canvas.setPageSize((media_w, media_h))
            canvas.setTrimBox((bleed, bleed, bleed + cmd.width, bleed + cmd.height))
            canvas.setBleedBox((0, 0, media_w, media_h))
            canvas.setArtBox(
                (bleed + safe, bleed + safe, bleed + cmd.width - safe, bleed + cmd.height - safe)
            )
            canvas.setCropBox((0, 0, media_w, media_h))
            if bleed:
                canvas.translate(bleed, bleed)
        elif isinstance(cmd, EndPage):
            canvas.showPage()
        elif isinstance(cmd, SetMetadata):
            self._apply_metadata(canvas, cmd)
        elif isinstance(cmd, BeginGroup):
            if cmd.opacity != 1.0:
                raise NotImplementedError(
                    "IRReportLabRenderer does not support group opacity "
                    "(needs a transparency-group XObject)"
                )
            canvas.saveState()
            self._apply_transform(canvas, cmd)
        elif isinstance(cmd, EndGroup):
            canvas.restoreState()
        elif isinstance(cmd, BeginClip):
            canvas.saveState()
            self._apply_clip(canvas, cmd)
        elif isinstance(cmd, EndClip):
            canvas.restoreState()
        elif isinstance(cmd, DrawShape):
            self._draw_shape(canvas, cmd)
        elif isinstance(cmd, DrawText):
            self._draw_text(canvas, cmd)
        elif isinstance(cmd, DrawImage):
            self._draw_image(canvas, cmd)
        elif isinstance(cmd, DrawFoldLine):
            self._draw_fold_line(canvas, cmd)
        else:
            # Discriminated union should make this unreachable.
            raise NotImplementedError(
                f"IRReportLabRenderer does not know how to handle {type(cmd).__name__}"
            )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _apply_metadata(self, canvas: _canvas.Canvas, cmd: SetMetadata) -> None:
        # Map known keys onto PDF metadata. Unknown keys are ignored —
        # SetMetadata is intended as a free-form annotation channel.
        if cmd.key == "template_id":
            canvas.setTitle(cmd.value)
        elif cmd.key == "theme_id":
            canvas.setSubject(cmd.value)

    # ------------------------------------------------------------------
    # Group transform / clipping
    # ------------------------------------------------------------------

    def _apply_transform(self, canvas: _canvas.Canvas, cmd: BeginGroup) -> None:
        t = cmd.transform
        # No-op transform is the common case (panel rotation == 0); skip
        # the canvas calls so the output is byte-stable.
        if t.translate_x == 0 and t.translate_y == 0 and t.rotate_deg == 0 \
                and t.scale_x == 1.0 and t.scale_y == 1.0:
            return
        # Order: translate to pivot, rotate, translate back. The compiler
        # records the pivot as the translate target.
        if t.translate_x or t.translate_y:
            canvas.translate(t.translate_x, t.translate_y)
        if t.rotate_deg:
            canvas.rotate(t.rotate_deg)
        if t.translate_x or t.translate_y:
            canvas.translate(-t.translate_x, -t.translate_y)
        if t.scale_x != 1.0 or t.scale_y != 1.0:
            canvas.scale(t.scale_x, t.scale_y)

    def _apply_clip(self, canvas: _canvas.Canvas, cmd: BeginClip) -> None:
        path = self._geometry_to_path(canvas, cmd.geometry)
        canvas.clipPath(path, stroke=0, fill=0)

    # ------------------------------------------------------------------
    # Shape drawing
    # ------------------------------------------------------------------

    def _draw_shape(self, canvas: _canvas.Canvas, cmd: DrawShape) -> None:
        # Gradient and pattern fills need a different drawing flow:
        # clip to the shape, paint the gradient/pattern inside the clip,
        # then draw the stroke separately on top. ReportLab's
        # ``canvas.rect`` / ``circle`` / ``drawPath`` only accept a
        # single solid fill.
        if isinstance(
            cmd.fill,
            (LinearGradientPaint, RadialGradientPaint, PatternPaint),
        ):
            self._draw_shape_with_complex_fill(canvas, cmd)
            return

        if cmd.fill is None and cmd.stroke is None:
            return  # nothing to draw
        # Effective alpha = command opacity x paint alpha. Any alpha < 1 is
        # scoped with q/Q so it can never leak into later draws.
        fill_a = cmd.opacity * (cmd.fill.color.a if isinstance(cmd.fill, SolidPaint) else 1.0)
        stroke_a = cmd.opacity * (cmd.stroke.color.a if cmd.stroke is not None else 1.0)
        scoped = fill_a < 1.0 or stroke_a < 1.0
        if scoped:
            canvas.saveState()
            self._set_alpha(canvas, fill=fill_a, stroke=stroke_a)
        self._draw_solid_shape(canvas, cmd)
        if scoped:
            canvas.restoreState()

    def _draw_solid_shape(self, canvas: _canvas.Canvas, cmd: DrawShape) -> None:
        geom = cmd.geometry
        has_fill = self._apply_fill(canvas, cmd.fill)
        has_stroke = self._apply_stroke(canvas, cmd.stroke)

        if isinstance(geom, RectGeom):
            if geom.corner_radius > 0:
                canvas.roundRect(
                    geom.x, geom.y, geom.width, geom.height,
                    geom.corner_radius,
                    stroke=int(has_stroke), fill=int(has_fill),
                )
            else:
                canvas.rect(
                    geom.x, geom.y, geom.width, geom.height,
                    stroke=int(has_stroke), fill=int(has_fill),
                )
        elif isinstance(geom, CircleGeom):
            canvas.circle(
                geom.center.x, geom.center.y, geom.radius,
                stroke=int(has_stroke), fill=int(has_fill),
            )
        elif isinstance(geom, EllipseGeom):
            canvas.ellipse(
                geom.center.x - geom.rx, geom.center.y - geom.ry,
                geom.center.x + geom.rx, geom.center.y + geom.ry,
                stroke=int(has_stroke), fill=int(has_fill),
            )
        elif isinstance(geom, (PolygonGeom, PolylineGeom, PathGeom)):
            path = self._geometry_to_path(canvas, geom)
            canvas.drawPath(path, stroke=int(has_stroke), fill=int(has_fill))

    @staticmethod
    def _set_alpha(
        canvas: _canvas.Canvas, *, fill: float = 1.0, stroke: float = 1.0
    ) -> None:
        # Caller owns the enclosing saveState/restoreState.
        if fill < 1.0:
            canvas.setFillAlpha(fill)
        if stroke < 1.0:
            canvas.setStrokeAlpha(stroke)

    def _draw_shape_with_complex_fill(
        self,
        canvas: _canvas.Canvas,
        cmd: DrawShape,
    ) -> None:
        """Draw a shape whose fill is a gradient or pattern.

        ReportLab's ``canvas.linearGradient`` and ``canvas.radialGradient``
        paint inside the current clip region — so the flow is:
        ``saveState → clipPath(shape) → emit gradient → restoreState``.
        Patterns aren't a first-class ReportLab primitive; we tile the
        chosen pattern's primitive (lines for stripes, circles for dots,
        etc.) across the shape's bounding box inside the clip.

        After the fill, the stroke is drawn separately in a second pass
        so the outline lands on top of the fill. Opacity wraps the
        whole operation.
        """
        from reportlab.lib import colors as _rl_colors

        fill = cmd.fill
        # Compute the bounding box for pattern tiling and gradient
        # extent fallbacks.
        bbox = self._shape_bbox(cmd.geometry)
        if bbox is None:
            raise NotImplementedError(
                f"Complex fill on geometry {type(cmd.geometry).__name__} "
                "requires a bounding box; not supported."
            )

        canvas.saveState()
        # Pattern tiles paint with both fills and strokes (grid lines).
        self._set_alpha(canvas, fill=cmd.opacity, stroke=cmd.opacity)

        # Clip to the shape so the gradient/pattern only paints inside.
        clip_path = self._geometry_to_path(canvas, cmd.geometry)
        canvas.clipPath(clip_path, stroke=0, fill=0)

        # Convert each RGB stop / color to a ReportLab color, honoring
        # the renderer's color_space mode so CMYK PDFs emit CMYK gradients.
        def to_rl_color(rgba: object) -> object:
            r, g, b = rgba.r, rgba.g, rgba.b  # type: ignore[attr-defined]
            a = rgba.a  # type: ignore[attr-defined]
            if self.color_space == "cmyk":
                from holiday_card.core.color_management import rgb_to_cmyk
                c, m, y, k = rgb_to_cmyk(r, g, b)
                return _rl_colors.CMYKColor(c, m, y, k, alpha=a)
            return _rl_colors.Color(r, g, b, alpha=a)

        if isinstance(fill, LinearGradientPaint):
            canvas.linearGradient(
                fill.start.x, fill.start.y,
                fill.end.x, fill.end.y,
                colors=[to_rl_color(s.color) for s in fill.stops],
                positions=[s.position for s in fill.stops],
                extend=True,
            )
        elif isinstance(fill, RadialGradientPaint):
            canvas.radialGradient(
                fill.center.x, fill.center.y, fill.radius,
                colors=[to_rl_color(s.color) for s in fill.stops],
                positions=[s.position for s in fill.stops],
                extend=True,
            )
        elif isinstance(fill, PatternPaint):
            self._draw_pattern_tile(canvas, fill, bbox)

        canvas.restoreState()

        # Stroke pass on top of the fill (if any).
        if cmd.stroke is not None:
            canvas.saveState()
            self._set_alpha(canvas, stroke=cmd.opacity * cmd.stroke.color.a)
            self._apply_stroke(canvas, cmd.stroke)
            stroke_path = self._geometry_to_path(canvas, cmd.geometry)
            canvas.drawPath(stroke_path, stroke=1, fill=0)
            canvas.restoreState()

    def _draw_pattern_tile(
        self,
        canvas: _canvas.Canvas,
        pattern: PatternPaint,
        bbox: tuple[float, float, float, float],
    ) -> None:
        """Tile a pattern primitive across the bbox inside the active clip.

        First lays down ``pattern.colors[0]`` as the background, then
        repeats the pattern primitive (``stripes`` / ``dots`` / ``grid``
        / ``checkerboard``) using ``pattern.colors[1]`` (or the same
        color if only one is supplied). ``rotation_deg`` rotates the
        entire pattern around the bbox center.
        """
        from reportlab.lib import colors as _rl_colors

        x, y, w, h = bbox
        spacing = pattern.spacing * pattern.scale
        if spacing < 0.1:
            spacing = 0.1
        c0 = pattern.colors[0]
        c1 = pattern.colors[1] if len(pattern.colors) > 1 else c0

        def rl(rgba: object) -> object:
            r, g, b = rgba.r, rgba.g, rgba.b  # type: ignore[attr-defined]
            a = rgba.a  # type: ignore[attr-defined]
            if self.color_space == "cmyk":
                from holiday_card.core.color_management import rgb_to_cmyk
                c, m, y_, k = rgb_to_cmyk(r, g, b)
                return _rl_colors.CMYKColor(c, m, y_, k, alpha=a)
            return _rl_colors.Color(r, g, b, alpha=a)

        # Background fill (color 0).
        canvas.setFillColor(rl(c0))
        canvas.rect(x, y, w, h, stroke=0, fill=1)

        # Rotate around bbox center if requested.
        if pattern.rotation_deg:
            canvas.saveState()
            cx, cy = x + w / 2, y + h / 2
            canvas.translate(cx, cy)
            canvas.rotate(pattern.rotation_deg)
            canvas.translate(-cx, -cy)

        canvas.setFillColor(rl(c1))
        canvas.setStrokeColor(rl(c1))

        if pattern.pattern == "stripes":
            # Horizontal stripes — alternate rows at half-spacing height.
            half = spacing / 2
            row_y = y - half
            while row_y < y + h + spacing:
                canvas.rect(x - spacing, row_y, w + 2 * spacing, half, stroke=0, fill=1)
                row_y += spacing
        elif pattern.pattern == "dots":
            radius = spacing / 4
            cy = y
            while cy < y + h + spacing:
                cx = x
                while cx < x + w + spacing:
                    canvas.circle(cx, cy, radius, stroke=0, fill=1)
                    cx += spacing
                cy += spacing
        elif pattern.pattern == "grid":
            # Vertical lines
            line_x = x
            while line_x < x + w + spacing:
                canvas.setLineWidth(1.0)
                canvas.line(line_x, y - spacing, line_x, y + h + spacing)
                line_x += spacing
            # Horizontal lines
            line_y = y
            while line_y < y + h + spacing:
                canvas.line(x - spacing, line_y, x + w + spacing, line_y)
                line_y += spacing
        elif pattern.pattern == "checkerboard":
            half = spacing
            grid_y = y - half
            row = 0
            while grid_y < y + h + half:
                offset = half if row % 2 else 0
                gx = x - half + offset
                while gx < x + w + half:
                    canvas.rect(gx, grid_y, half, half, stroke=0, fill=1)
                    gx += 2 * half
                grid_y += half
                row += 1

        if pattern.rotation_deg:
            canvas.restoreState()

    def _shape_bbox(self, geom: object) -> tuple[float, float, float, float] | None:
        """Bounding box of an IR geometry in page-points.

        Returns ``(x, y, width, height)`` with bottom-left origin (the
        IR convention). Used by pattern tiling and as a fallback when
        a complex fill needs a target rect.
        """
        if isinstance(geom, RectGeom):
            return (geom.x, geom.y, geom.width, geom.height)
        if isinstance(geom, CircleGeom):
            return (
                geom.center.x - geom.radius,
                geom.center.y - geom.radius,
                2 * geom.radius, 2 * geom.radius,
            )
        if isinstance(geom, EllipseGeom):
            return (
                geom.center.x - geom.rx, geom.center.y - geom.ry,
                2 * geom.rx, 2 * geom.ry,
            )
        if isinstance(geom, (PolygonGeom, PolylineGeom)):
            xs = [p.x for p in geom.points]
            ys = [p.y for p in geom.points]
            return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        return None

    def _geometry_to_path(self, canvas: _canvas.Canvas, geom: object) -> object:
        path = canvas.beginPath()
        if isinstance(geom, RectGeom):
            path.rect(geom.x, geom.y, geom.width, geom.height)
        elif isinstance(geom, CircleGeom):
            # Approximate a circle via an ellipse (ReportLab's Path doesn't
            # have a native circle primitive but ellipse takes diameter box).
            path.ellipse(
                geom.center.x - geom.radius, geom.center.y - geom.radius,
                geom.radius * 2, geom.radius * 2,
            )
        elif isinstance(geom, EllipseGeom):
            path.ellipse(
                geom.center.x - geom.rx, geom.center.y - geom.ry,
                geom.rx * 2, geom.ry * 2,
            )
        elif isinstance(geom, PolygonGeom):
            pts = list(geom.points)
            path.moveTo(pts[0].x, pts[0].y)
            for p in pts[1:]:
                path.lineTo(p.x, p.y)
            path.close()
        elif isinstance(geom, PolylineGeom):
            pts = list(geom.points)
            path.moveTo(pts[0].x, pts[0].y)
            for p in pts[1:]:
                path.lineTo(p.x, p.y)
        elif isinstance(geom, PathGeom):
            # ReportLab's path object doesn't expose its current point, so
            # track it (and the subpath start ``close`` returns to) here.
            current: tuple[float, float] | None = None
            start: tuple[float, float] | None = None
            for op in geom.ops:
                if op.op == "move":
                    p = op.points[0]
                    path.moveTo(p.x, p.y)
                    current = start = (p.x, p.y)
                elif op.op == "line":
                    p = op.points[0]
                    path.lineTo(p.x, p.y)
                    current = (p.x, p.y)
                elif op.op == "cubic":
                    cp1, cp2, end = op.points
                    path.curveTo(cp1.x, cp1.y, cp2.x, cp2.y, end.x, end.y)
                    current = (end.x, end.y)
                elif op.op == "quadratic":
                    if current is None:
                        raise ValueError(
                            "quadratic path op has no current point; "
                            "the path must start with a move"
                        )
                    # ReportLab Path has no quadraticTo; elevate (P0, cp, P3)
                    # to a cubic with the standard 2/3 control-point lift.
                    cp, end = op.points
                    x0, y0 = current
                    path.curveTo(
                        x0 + 2 / 3 * (cp.x - x0),
                        y0 + 2 / 3 * (cp.y - y0),
                        end.x + 2 / 3 * (cp.x - end.x),
                        end.y + 2 / 3 * (cp.y - end.y),
                        end.x, end.y,
                    )
                    current = (end.x, end.y)
                elif op.op == "close":
                    path.close()
                    current = start
        return path

    # ------------------------------------------------------------------
    # Paint / stroke setup
    # ------------------------------------------------------------------

    def _apply_fill(self, canvas: _canvas.Canvas, fill: object) -> bool:
        if fill is None:
            return False
        if isinstance(fill, SolidPaint):
            c = fill.color
            self._set_fill(canvas, c.r, c.g, c.b)
            return True
        # Gradient + pattern paints aren't emitted by the compiler yet.
        # If they slip through, fail loud rather than silently drop.
        raise NotImplementedError(
            f"IRReportLabRenderer does not yet handle paint type {type(fill).__name__}"
        )

    def _apply_stroke(self, canvas: _canvas.Canvas, stroke: Stroke | None) -> bool:
        if stroke is None:
            return False
        c = stroke.color
        self._set_stroke(canvas, c.r, c.g, c.b)
        canvas.setLineWidth(stroke.width)
        if stroke.dash:
            # setDash(array, phase): a bare number would become (array, phase).
            canvas.setDash(list(stroke.dash), 0)
        else:
            canvas.setDash()
        return True

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def _draw_text(self, canvas: _canvas.Canvas, cmd: DrawText) -> None:
        run = cmd.run
        alpha = cmd.opacity * run.color.a
        if alpha < 1.0:
            canvas.saveState()
            self._set_alpha(canvas, fill=alpha)
        # font_id is canonicalized (e.g. "Helvetica" → "LiberationSans")
        # so the default base-14 names map to the embedded TTFs.
        canvas.setFont(resolve_font_id(run.font_id), run.size_pt)
        self._set_fill(canvas, run.color.r, run.color.g, run.color.b)
        if run.align == "center":
            canvas.drawCentredString(run.origin.x, run.origin.y, run.text)
        elif run.align == "right":
            canvas.drawRightString(run.origin.x, run.origin.y, run.text)
        else:
            canvas.drawString(run.origin.x, run.origin.y, run.text)
        if alpha < 1.0:
            canvas.restoreState()

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def _draw_image(self, canvas: _canvas.Canvas, cmd: DrawImage) -> None:
        rect = cmd.image.rect
        # Image XObjects paint with the non-stroking alpha (/ca).
        if cmd.opacity < 1.0:
            canvas.saveState()
            self._set_alpha(canvas, fill=cmd.opacity)
        canvas.drawImage(
            cmd.image.source,
            rect.x, rect.y,
            width=rect.width, height=rect.height,
            preserveAspectRatio=cmd.image.preserve_aspect,
            mask="auto",
        )
        if cmd.opacity < 1.0:
            canvas.restoreState()

    # ------------------------------------------------------------------
    # Fold lines
    # ------------------------------------------------------------------

    def _draw_fold_line(self, canvas: _canvas.Canvas, cmd: DrawFoldLine) -> None:
        canvas.saveState()
        self._set_stroke(canvas, 0.7, 0.7, 0.7)  # matches legacy fold-line grey
        canvas.setLineWidth(0.5)
        if cmd.style == "dashed":
            canvas.setDash(3, 3)
        canvas.line(cmd.start.x, cmd.start.y, cmd.end.x, cmd.end.y)
        canvas.restoreState()
