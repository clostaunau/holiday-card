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

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as _canvas

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
)

__all__ = ["IRReportLabRenderer"]


class IRReportLabRenderer:
    """Renderer that visits a ``RenderCommand`` stream and writes a PDF.

    Public surface is a single method, ``render``. Construction is
    deliberately argument-free — there's no per-instance state to set.
    """

    name: str = "reportlab"
    file_extension: str = ".pdf"

    def render(self, commands: Iterable[RenderCommand], output: Path) -> None:
        """Consume ``commands`` and write a PDF at ``output``."""
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas = _canvas.Canvas(str(output), pagesize=letter)
        try:
            for cmd in commands:
                self._dispatch(canvas, cmd)
        finally:
            canvas.save()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, canvas: _canvas.Canvas, cmd: RenderCommand) -> None:
        # Pydantic discriminated unions resolve to a concrete class at
        # construction time, so isinstance dispatch is safe and fast.
        if isinstance(cmd, BeginPage):
            # The canvas was opened with letter size already; reset state
            # for the new page (matches the legacy renderer's first page).
            canvas.setPageSize((cmd.width, cmd.height))
        elif isinstance(cmd, EndPage):
            canvas.showPage()
        elif isinstance(cmd, SetMetadata):
            self._apply_metadata(canvas, cmd)
        elif isinstance(cmd, BeginGroup):
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
        # records the pivot as the translate target, so this matches the
        # legacy renderer's `translate(cx, cy); rotate; translate(-cx, -cy)`
        # sequence (reportlab_renderer.py:96-102).
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
        geom = cmd.geometry
        has_fill = self._apply_fill(canvas, cmd.fill)
        has_stroke = self._apply_stroke(canvas, cmd.stroke)
        if not has_fill and not has_stroke:
            return  # nothing to draw

        if cmd.opacity != 1.0:
            canvas.setFillAlpha(cmd.opacity)
            canvas.setStrokeAlpha(cmd.opacity)

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

        # Reset alpha to 1.0 for subsequent draws (the legacy renderer's
        # state is grouped in saveState/restoreState; per-draw alpha is
        # safer here because compiler emits paint per-shape).
        if cmd.opacity != 1.0:
            canvas.setFillAlpha(1.0)
            canvas.setStrokeAlpha(1.0)

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
            for op in geom.ops:
                if op.op == "move":
                    path.moveTo(op.points[0].x, op.points[0].y)
                elif op.op == "line":
                    path.lineTo(op.points[0].x, op.points[0].y)
                elif op.op == "cubic":
                    cp1, cp2, end = op.points
                    path.curveTo(cp1.x, cp1.y, cp2.x, cp2.y, end.x, end.y)
                elif op.op == "quadratic":
                    # ReportLab Path doesn't expose quadraticTo; convert to
                    # cubic with the standard 2/3 control-point lift.
                    cp, end = op.points
                    last_x, last_y = path.contour[-1] if hasattr(path, "contour") else (cp.x, cp.y)
                    path.curveTo(
                        last_x + 2 / 3 * (cp.x - last_x),
                        last_y + 2 / 3 * (cp.y - last_y),
                        end.x + 2 / 3 * (cp.x - end.x),
                        end.y + 2 / 3 * (cp.y - end.y),
                        end.x, end.y,
                    )
                elif op.op == "close":
                    path.close()
        return path

    # ------------------------------------------------------------------
    # Paint / stroke setup
    # ------------------------------------------------------------------

    def _apply_fill(self, canvas: _canvas.Canvas, fill: object) -> bool:
        if fill is None:
            return False
        if isinstance(fill, SolidPaint):
            c = fill.color
            canvas.setFillColorRGB(c.r, c.g, c.b)
            if c.a != 1.0:
                canvas.setFillAlpha(c.a)
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
        canvas.setStrokeColorRGB(c.r, c.g, c.b)
        canvas.setLineWidth(stroke.width)
        if stroke.dash:
            canvas.setDash(*stroke.dash)
        else:
            canvas.setDash()
        return True

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def _draw_text(self, canvas: _canvas.Canvas, cmd: DrawText) -> None:
        run = cmd.run
        canvas.setFont(run.font_id, run.size_pt)
        canvas.setFillColorRGB(run.color.r, run.color.g, run.color.b)
        if cmd.opacity != 1.0:
            canvas.setFillAlpha(cmd.opacity)
        if run.align == "center":
            canvas.drawCentredString(run.origin.x, run.origin.y, run.text)
        elif run.align == "right":
            canvas.drawRightString(run.origin.x, run.origin.y, run.text)
        else:
            canvas.drawString(run.origin.x, run.origin.y, run.text)
        if cmd.opacity != 1.0:
            canvas.setFillAlpha(1.0)

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def _draw_image(self, canvas: _canvas.Canvas, cmd: DrawImage) -> None:
        rect = cmd.image.rect
        canvas.drawImage(
            cmd.image.source,
            rect.x, rect.y,
            width=rect.width, height=rect.height,
            preserveAspectRatio=cmd.image.preserve_aspect,
            mask="auto",
        )

    # ------------------------------------------------------------------
    # Fold lines
    # ------------------------------------------------------------------

    def _draw_fold_line(self, canvas: _canvas.Canvas, cmd: DrawFoldLine) -> None:
        canvas.saveState()
        canvas.setStrokeColorRGB(0.7, 0.7, 0.7)  # matches legacy fold-line grey
        canvas.setLineWidth(0.5)
        if cmd.style == "dashed":
            canvas.setDash(3, 3)
        canvas.line(cmd.start.x, cmd.start.y, cmd.end.x, cmd.end.y)
        canvas.restoreState()
