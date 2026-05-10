"""Per-panel rendering helpers for ``ExportTarget(layout='per-panel')``.

For per-panel export targets, each panel becomes its own page in its own
file. This module owns the two card-shape transforms that the generator
applies before compiling each per-panel single-page card:

* :func:`prepare_native_panel` — strip imposition position and rotation,
  giving the compiler a panel at the origin with no transform. Used by
  ``per-panel-pdf`` (and any other native-trim per-panel target).
* :func:`prepare_scaled_panel` — uniformly scale every panel-relative
  coordinate, font size, and panel dimension so the panel content fits
  inside a target trim, then center it (letterbox semantics). Used by
  ``moo-a6`` (and any future fixed-trim POD target).

These helpers operate at the **domain level** (Card / Panel / element
models) rather than the IR level so backends and the compiler don't
need any knowledge of per-panel rendering — by the time ``compile_card``
runs, the input is just a one-panel card at the desired trim.
"""

from __future__ import annotations

from holiday_card.core.compiler import CompileContext
from holiday_card.core.export_targets import ExportTarget
from holiday_card.core.models import (
    Card,
    Circle,
    DecorativeElement,
    Line,
    Panel,
    Rectangle,
    Star,
    SVGPath,
    TextElement,
    Triangle,
)
from holiday_card.utils.measurements import PageGeometry

__all__ = [
    "build_per_panel_card",
    "build_per_panel_context",
    "prepare_native_panel",
    "prepare_scaled_panel",
]


def build_per_panel_card(card: Card, panel: Panel, target: ExportTarget) -> Card:
    """Wrap a single panel into its own ``Card`` ready to be compiled
    into a per-panel output file.

    Dispatches on ``target.scale_panels_to_fit`` to either preserve the
    panel's native dimensions (just stripping imposition position +
    rotation) or scale-and-letterbox it into ``target.geometry``'s trim.
    """
    if target.scale_panels_to_fit:
        if target.geometry is None:
            raise ValueError(
                f"target {target.name!r} sets scale_panels_to_fit=True but "
                "has no geometry to scale into"
            )
        new_panel = prepare_scaled_panel(
            panel,
            target_width_in=target.geometry.trim_width_in,
            target_height_in=target.geometry.trim_height_in,
        )
    else:
        new_panel = prepare_native_panel(panel)
    return card.model_copy(update={"panels": [new_panel]})


def build_per_panel_context(panel: Panel, target: ExportTarget) -> CompileContext:
    """Build the ``CompileContext`` for compiling a per-panel card.

    For ``scale_panels_to_fit`` targets, the context geometry is the
    target trim. For native-dim targets, the context geometry is the
    panel's own dimensions (with the target's bleed and safe margin).
    Fold lines are always disabled in per-panel mode — each panel is a
    finished card, not part of an imposition.
    """
    if target.scale_panels_to_fit and target.geometry is not None:
        geometry = target.geometry
    else:
        geometry = PageGeometry(
            sheet_width_in=panel.width,
            sheet_height_in=panel.height,
            trim_width_in=panel.width,
            trim_height_in=panel.height,
            bleed_in=target.bleed_in,
            safe_margin_in=target.safe_margin_in,
        )
    return CompileContext(geometry=geometry, emit_fold_lines=False)


def prepare_native_panel(panel: Panel) -> Panel:
    """Return a copy of ``panel`` placed at the origin with no rotation.

    The imposition position (``panel.x``, ``panel.y``) and the
    imposition rotation (``panel.rotation``, typically 180° for inside
    panels) are both meaningful only when the panel is part of a
    folded sheet. For per-panel output, the panel becomes its own
    page; both are stripped.
    """
    return panel.model_copy(update={"x": 0.0, "y": 0.0, "rotation": 0.0})


def prepare_scaled_panel(
    panel: Panel,
    *,
    target_width_in: float,
    target_height_in: float,
) -> Panel:
    """Uniformly scale ``panel`` to fit ``(target_width_in, target_height_in)``,
    centered, and return a copy.

    Scale factor is ``min(target_w / panel.width, target_h / panel.height)``.
    The off-axis is letterboxed: empty space appears at the top/bottom
    or left/right of the target trim, in the target's background color
    (typically the page white).

    All recursive coordinates and font sizes are scaled. The panel is
    repositioned so the scaled content is centered inside the target
    trim. Imposition rotation is dropped (per-panel output never folds).
    """
    sx = target_width_in / panel.width
    sy = target_height_in / panel.height
    scale = min(sx, sy)
    new_width = panel.width * scale
    new_height = panel.height * scale
    offset_x = (target_width_in - new_width) / 2
    offset_y = (target_height_in - new_height) / 2

    return panel.model_copy(
        update={
            "x": offset_x,
            "y": offset_y,
            "width": new_width,
            "height": new_height,
            "rotation": 0.0,
            "text_elements": [_scale_text(t, scale) for t in panel.text_elements],
            "shape_elements": [_scale_shape(s, scale) for s in panel.shape_elements],
            # image_elements not yet supported by the compiler; preserve as-is.
        }
    )


# ---------------------------------------------------------------------------
# Element-level scaling
# ---------------------------------------------------------------------------


def _scale_text(text: TextElement, scale: float) -> TextElement:
    """Scale a text element's position, max-width, and font sizes."""
    updates: dict = {
        "x": text.x * scale,
        "y": text.y * scale,
        "font_size": max(6, int(round(text.font_size * scale))),
        "min_font_size": max(6, int(round(text.min_font_size * scale))),
    }
    if text.width is not None:
        updates["width"] = text.width * scale
    return text.model_copy(update=updates)


def _scale_shape(
    shape: Rectangle | Circle | Triangle | Star | Line | SVGPath | DecorativeElement,
    scale: float,
) -> Rectangle | Circle | Triangle | Star | Line | SVGPath | DecorativeElement:
    """Scale a shape's coordinates and size by ``scale``.

    Falls back to returning the shape unchanged for any type the
    compiler doesn't yet emit (notably ``DecorativeElement``); the
    compiler will raise ``UnsupportedFeatureError`` later if it
    encounters one, so we don't need to handle it here.
    """
    if isinstance(shape, Rectangle):
        return shape.model_copy(
            update={
                "x": shape.x * scale,
                "y": shape.y * scale,
                "width": shape.width * scale,
                "height": shape.height * scale,
            }
        )
    if isinstance(shape, Circle):
        return shape.model_copy(
            update={
                "center_x": shape.center_x * scale,
                "center_y": shape.center_y * scale,
                "radius": shape.radius * scale,
            }
        )
    if isinstance(shape, Triangle):
        return shape.model_copy(
            update={
                "x1": shape.x1 * scale, "y1": shape.y1 * scale,
                "x2": shape.x2 * scale, "y2": shape.y2 * scale,
                "x3": shape.x3 * scale, "y3": shape.y3 * scale,
            }
        )
    if isinstance(shape, Star):
        return shape.model_copy(
            update={
                "center_x": shape.center_x * scale,
                "center_y": shape.center_y * scale,
                "outer_radius": shape.outer_radius * scale,
                "inner_radius": shape.inner_radius * scale,
            }
        )
    if isinstance(shape, Line):
        return shape.model_copy(
            update={
                "start_x": shape.start_x * scale, "start_y": shape.start_y * scale,
                "end_x": shape.end_x * scale, "end_y": shape.end_y * scale,
            }
        )
    if isinstance(shape, SVGPath):
        # SVGPath uses a `scale` multiplier; compose.
        return shape.model_copy(update={"scale": shape.scale * scale})
    return shape  # other shapes (DecorativeElement) pass through; compiler rejects.
