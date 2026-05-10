"""SVG backend for the rendering IR.

Consumes a ``list[RenderCommand]`` and writes an SVG file. The first
non-PDF backend to use the Wave 2 IR seam — proves the architecture by
shipping a second renderer in ~1 PR.

Coordinate system note
----------------------
The IR uses **points (1/72 inch) with origin at page bottom-left** —
matching ReportLab and the PDF spec. SVG's native coordinate system has
**origin at top-left, y growing downward**. We convert per element at
emit time rather than wrapping the whole document in a y-flip ``<g>``,
because a global flip mirrors text and complicates the
``BeginGroup`` transform handling. Per-element conversion is verbose
but keeps the math local and the output trivially debuggable.

Helper:  ``svg_y = page_height - ir_y - element_height_if_top_origin``.

Scope
-----
Mirrors the Wave 2 compiler's supported feature subset (PR #6):
backgrounds, borders, basic shapes (Rect/Circle/Triangle/Star/Line)
with solid fills, text with three alignments, fold lines. ``BeginGroup``
is honored when the transform is identity (the only case the compiler
currently emits — panel rotations are zero in every shipped template).
``BeginClip`` is implemented via SVG ``<clipPath>``. Gradients,
patterns, images, and non-identity group transforms raise
``NotImplementedError`` for the same reason the IR ReportLab backend
does — fail loud, not silent.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

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

__all__ = ["SVGRenderer"]

_SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", _SVG_NS)


class SVGRenderer:
    """Renderer that visits a ``RenderCommand`` stream and writes an SVG.

    Single-method public surface, like the ReportLab backend. Stateless
    across calls — every ``render()`` invocation builds a fresh element
    tree from scratch.
    """

    name: str = "svg"
    file_extension: str = ".svg"

    def render(self, commands: Iterable[RenderCommand], output: Path) -> None:
        """Consume ``commands`` and write an SVG at ``output``."""
        output.parent.mkdir(parents=True, exist_ok=True)

        # State accumulated across the visit
        self._page_height: float = 0.0
        self._page_width: float = 0.0
        self._root: ET.Element | None = None
        self._defs: ET.Element | None = None
        self._stack: list[ET.Element] = []
        self._clip_counter: int = 0
        self._metadata: list[tuple[str, str]] = []

        for cmd in commands:
            self._dispatch(cmd)

        if self._root is None:
            raise RuntimeError(
                "SVGRenderer.render: command stream had no BeginPage"
            )

        # Pretty-print and write
        ET.indent(self._root, space="  ")
        tree = ET.ElementTree(self._root)
        # Use xml_declaration + utf-8 so the file opens cleanly in any browser
        tree.write(output, encoding="utf-8", xml_declaration=True)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, cmd: RenderCommand) -> None:
        if isinstance(cmd, BeginPage):
            self._begin_page(cmd)
        elif isinstance(cmd, EndPage):
            self._end_page()
        elif isinstance(cmd, SetMetadata):
            self._metadata.append((cmd.key, cmd.value))
            # Title only emits once we close the page (the SVG <title>
            # element must come after <defs> conventionally; we collect
            # and flush here for determinism).
        elif isinstance(cmd, BeginGroup):
            self._begin_group(cmd)
        elif isinstance(cmd, EndGroup):
            self._end_group()
        elif isinstance(cmd, BeginClip):
            self._begin_clip(cmd)
        elif isinstance(cmd, EndClip):
            self._end_group()  # clip group is just a regular group
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
                f"SVGRenderer does not know how to handle {type(cmd).__name__}"
            )

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def _begin_page(self, cmd: BeginPage) -> None:
        # Trim dimensions drive the per-element y-flip math (page_height
        # below is the trim height); the bleed extension is folded into
        # the SVG viewBox so IR coords (origin at trim corner) land
        # naturally without a per-element translate. The viewBox starts
        # at ``-bleed`` so element ``(0, 0)`` is the trim corner; the
        # outer ``width``/``height`` attributes report the media box so
        # browsers and SVG-to-PDF tools render the bleed area.
        self._page_width = cmd.width
        self._page_height = cmd.height
        bleed = cmd.bleed
        media_w = cmd.width + 2 * bleed
        media_h = cmd.height + 2 * bleed
        self._root = ET.Element(
            "svg",
            attrib={
                "xmlns": _SVG_NS,
                "width": _fmt(media_w),
                "height": _fmt(media_h),
                "viewBox": (
                    f"{_fmt(-bleed)} {_fmt(-bleed)} "
                    f"{_fmt(media_w)} {_fmt(media_h)}"
                ),
            },
        )
        self._defs = ET.SubElement(self._root, "defs")
        self._stack = [self._root]

    def _end_page(self) -> None:
        # Flush metadata as <title>/<desc>. Place after <defs> per convention.
        if self._metadata and self._root is not None:
            for key, value in self._metadata:
                if key == "template_id":
                    title = ET.Element("title")
                    title.text = value
                    self._root.insert(1, title)  # after <defs>
                elif key == "theme_id":
                    desc = ET.Element("desc")
                    desc.text = f"theme: {value}"
                    self._root.insert(1, desc)

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def _begin_group(self, cmd: BeginGroup) -> None:
        attrib: dict[str, str] = {}
        transform = self._format_transform(cmd.transform)
        if transform:
            attrib["transform"] = transform
        if cmd.opacity != 1.0:
            attrib["opacity"] = _fmt(cmd.opacity)
        g = ET.SubElement(self._stack[-1], "g", attrib=attrib)
        self._stack.append(g)

    def _format_transform(self, t: Transform) -> str:
        """Build the SVG ``transform`` value matching the IR's pivot-rotate
        semantics.

        The IR's ``Transform`` represents "rotate ``rotate_deg`` around
        the pivot ``(translate_x, translate_y)`` in IR coords, with
        optional uniform scale" — the same idiom the legacy renderer
        used (``translate; rotate; untranslate``). We emit the SVG
        equivalent in SVG coordinate space (top-left origin), converting
        the pivot via ``y_svg = page_height - y_ir`` and negating the
        rotation to compensate for SVG's y-down direction.

        Returns the empty string for identity transforms so the caller
        can omit the attribute.
        """
        is_identity = (
            t.translate_x == 0 and t.translate_y == 0
            and t.rotate_deg == 0
            and t.scale_x == 1.0 and t.scale_y == 1.0
        )
        if is_identity:
            return ""
        parts: list[str] = []
        pivot_x_svg = t.translate_x
        pivot_y_svg = self._page_height - t.translate_y
        if t.translate_x != 0 or t.translate_y != 0:
            parts.append(
                f"translate({_fmt(pivot_x_svg)} {_fmt(pivot_y_svg)})"
            )
        if t.rotate_deg != 0:
            # SVG positive rotation is CW in screen-space; the IR uses
            # math convention (CCW positive). Negate.
            parts.append(f"rotate({_fmt(-t.rotate_deg)})")
        if t.scale_x != 1.0 or t.scale_y != 1.0:
            parts.append(f"scale({_fmt(t.scale_x)} {_fmt(t.scale_y)})")
        if t.translate_x != 0 or t.translate_y != 0:
            parts.append(
                f"translate({_fmt(-pivot_x_svg)} {_fmt(-pivot_y_svg)})"
            )
        return " ".join(parts)

    def _end_group(self) -> None:
        if len(self._stack) <= 1:
            raise RuntimeError("SVGRenderer: EndGroup with no open group")
        self._stack.pop()

    def _begin_clip(self, cmd: BeginClip) -> None:
        # Define the clip path in <defs>, then push a <g clip-path="url(#id)">
        if self._defs is None:
            raise RuntimeError("SVGRenderer: BeginClip with no open page")
        self._clip_counter += 1
        clip_id = f"clip{self._clip_counter}"
        clip_path = ET.SubElement(self._defs, "clipPath", attrib={"id": clip_id})
        clip_path.append(self._geometry_element(cmd.geometry, fill=None, stroke=None, opacity=1.0))
        g = ET.SubElement(self._stack[-1], "g", attrib={"clip-path": f"url(#{clip_id})"})
        self._stack.append(g)

    # ------------------------------------------------------------------
    # Shape drawing
    # ------------------------------------------------------------------

    def _draw_shape(self, cmd: DrawShape) -> None:
        elem = self._geometry_element(cmd.geometry, fill=cmd.fill, stroke=cmd.stroke, opacity=cmd.opacity)
        self._stack[-1].append(elem)

    def _geometry_element(
        self,
        geom: object,
        fill: object | None,
        stroke: Stroke | None,
        opacity: float,
    ) -> ET.Element:
        if isinstance(geom, RectGeom):
            return self._rect_element(geom, fill, stroke, opacity)
        if isinstance(geom, CircleGeom):
            return self._circle_element(geom, fill, stroke, opacity)
        if isinstance(geom, EllipseGeom):
            return self._ellipse_element(geom, fill, stroke, opacity)
        if isinstance(geom, PolygonGeom):
            return self._polygon_element(geom, fill, stroke, opacity, closed=True)
        if isinstance(geom, PolylineGeom):
            return self._polygon_element(geom, fill, stroke, opacity, closed=False)
        if isinstance(geom, PathGeom):
            return self._path_element(geom, fill, stroke, opacity)
        raise NotImplementedError(
            f"SVGRenderer does not know how to handle geometry {type(geom).__name__}"
        )

    def _rect_element(
        self, geom: RectGeom, fill: object | None, stroke: Stroke | None, opacity: float
    ) -> ET.Element:
        # IR rect has bottom-left origin; SVG rect has top-left origin.
        attrib = {
            "x": _fmt(geom.x),
            "y": _fmt(self._page_height - geom.y - geom.height),
            "width": _fmt(geom.width),
            "height": _fmt(geom.height),
        }
        if geom.corner_radius > 0:
            attrib["rx"] = _fmt(geom.corner_radius)
            attrib["ry"] = _fmt(geom.corner_radius)
        _apply_paint_and_stroke(attrib, fill, stroke, opacity)
        return ET.Element("rect", attrib=attrib)

    def _circle_element(
        self, geom: CircleGeom, fill: object | None, stroke: Stroke | None, opacity: float
    ) -> ET.Element:
        attrib = {
            "cx": _fmt(geom.center.x),
            "cy": _fmt(self._page_height - geom.center.y),
            "r": _fmt(geom.radius),
        }
        _apply_paint_and_stroke(attrib, fill, stroke, opacity)
        return ET.Element("circle", attrib=attrib)

    def _ellipse_element(
        self, geom: EllipseGeom, fill: object | None, stroke: Stroke | None, opacity: float
    ) -> ET.Element:
        attrib = {
            "cx": _fmt(geom.center.x),
            "cy": _fmt(self._page_height - geom.center.y),
            "rx": _fmt(geom.rx),
            "ry": _fmt(geom.ry),
        }
        _apply_paint_and_stroke(attrib, fill, stroke, opacity)
        return ET.Element("ellipse", attrib=attrib)

    def _polygon_element(
        self,
        geom: PolygonGeom | PolylineGeom,
        fill: object | None,
        stroke: Stroke | None,
        opacity: float,
        *,
        closed: bool,
    ) -> ET.Element:
        points = " ".join(f"{_fmt(p.x)},{_fmt(self._page_height - p.y)}" for p in geom.points)
        attrib = {"points": points}
        # SVG polyline doesn't fill by default; if we have a fill on a polyline,
        # silently treat it as a polygon (the IR's PolylineGeom is "open" but
        # rendering the fill of an open shape requires implicit closing — match
        # SVG's default behavior).
        _apply_paint_and_stroke(attrib, fill, stroke, opacity)
        tag = "polygon" if closed else "polyline"
        if not closed:
            # An unfilled polyline by convention has no fill; force fill=none
            # so SVG doesn't apply the inherited fill.
            attrib.setdefault("fill", "none")
        return ET.Element(tag, attrib=attrib)

    def _path_element(
        self, geom: PathGeom, fill: object | None, stroke: Stroke | None, opacity: float
    ) -> ET.Element:
        d_parts: list[str] = []
        for op in geom.ops:
            if op.op == "move":
                p = op.points[0]
                d_parts.append(f"M {_fmt(p.x)} {_fmt(self._page_height - p.y)}")
            elif op.op == "line":
                p = op.points[0]
                d_parts.append(f"L {_fmt(p.x)} {_fmt(self._page_height - p.y)}")
            elif op.op == "cubic":
                cp1, cp2, end = op.points
                d_parts.append(
                    f"C {_fmt(cp1.x)} {_fmt(self._page_height - cp1.y)} "
                    f"{_fmt(cp2.x)} {_fmt(self._page_height - cp2.y)} "
                    f"{_fmt(end.x)} {_fmt(self._page_height - end.y)}"
                )
            elif op.op == "quadratic":
                cp, end = op.points
                d_parts.append(
                    f"Q {_fmt(cp.x)} {_fmt(self._page_height - cp.y)} "
                    f"{_fmt(end.x)} {_fmt(self._page_height - end.y)}"
                )
            elif op.op == "close":
                d_parts.append("Z")
        attrib = {"d": " ".join(d_parts)}
        _apply_paint_and_stroke(attrib, fill, stroke, opacity)
        return ET.Element("path", attrib=attrib)

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    def _draw_text(self, cmd: DrawText) -> None:
        run = cmd.run
        attrib = {
            "x": _fmt(run.origin.x),
            "y": _fmt(self._page_height - run.origin.y),
            "font-family": run.font_id,
            "font-size": _fmt(run.size_pt),
            "fill": _rgba_to_css(run.color),
        }
        # Match ReportLab's drawString / drawCentredString / drawRightString
        # alignment behavior via SVG's text-anchor.
        anchor_map = {"left": "start", "center": "middle", "right": "end"}
        attrib["text-anchor"] = anchor_map[run.align]
        if run.color.a != 1.0:
            attrib["fill-opacity"] = _fmt(run.color.a)
        if cmd.opacity != 1.0:
            attrib["opacity"] = _fmt(cmd.opacity)
        text_elem = ET.Element("text", attrib=attrib)
        text_elem.text = run.text
        self._stack[-1].append(text_elem)

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def _draw_image(self, cmd: DrawImage) -> None:
        # Image support requires either base64-embedding the image data or
        # writing a side-by-side image and href-ing it. Neither path is
        # currently exercised by the compiler (ImageElement raises
        # UnsupportedFeatureError). Until that lands, fail loud.
        raise NotImplementedError(
            "SVGRenderer does not yet handle DrawImage (compiler does not emit it)"
        )

    # ------------------------------------------------------------------
    # Fold lines
    # ------------------------------------------------------------------

    def _draw_fold_line(self, cmd: DrawFoldLine) -> None:
        attrib = {
            "x1": _fmt(cmd.start.x),
            "y1": _fmt(self._page_height - cmd.start.y),
            "x2": _fmt(cmd.end.x),
            "y2": _fmt(self._page_height - cmd.end.y),
            "stroke": "rgb(178,178,178)",  # 0.7 grey — matches ReportLab backend
            "stroke-width": "0.5",
        }
        if cmd.style == "dashed":
            attrib["stroke-dasharray"] = "3 3"
        ET.SubElement(self._stack[-1], "line", attrib=attrib)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    """Compact numeric formatting for SVG attributes.

    Matches what most SVG editors emit: at most 4 decimal places, no
    trailing zeros.
    """
    formatted = f"{value:.4f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _rgba_to_css(color: object) -> str:
    """Convert an RGBA value object to a CSS rgb() string.

    Alpha is emitted separately via ``fill-opacity`` for readability.
    """
    r = int(round(color.r * 255))  # type: ignore[attr-defined]
    g = int(round(color.g * 255))  # type: ignore[attr-defined]
    b = int(round(color.b * 255))  # type: ignore[attr-defined]
    return f"rgb({r},{g},{b})"


def _apply_paint_and_stroke(
    attrib: dict[str, str], fill: object | None, stroke: Stroke | None, opacity: float
) -> None:
    """Add fill/stroke/opacity attributes to an element, in place."""
    if fill is None:
        attrib["fill"] = "none"
    elif isinstance(fill, SolidPaint):
        attrib["fill"] = _rgba_to_css(fill.color)
        if fill.color.a != 1.0:
            attrib["fill-opacity"] = _fmt(fill.color.a)
    else:
        # Gradient/pattern paints aren't emitted by the compiler today.
        raise NotImplementedError(
            f"SVGRenderer does not yet handle paint type {type(fill).__name__}"
        )
    if stroke is not None:
        attrib["stroke"] = _rgba_to_css(stroke.color)
        attrib["stroke-width"] = _fmt(stroke.width)
        if stroke.dash:
            attrib["stroke-dasharray"] = " ".join(_fmt(d) for d in stroke.dash)
    if opacity != 1.0:
        attrib["opacity"] = _fmt(opacity)


