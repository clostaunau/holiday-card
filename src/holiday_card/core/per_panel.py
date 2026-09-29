"""Per-panel rendering helpers for ``ExportTarget(layout='per-panel')``.

For per-panel export targets, each panel becomes its own page in its own
file. The generator wraps each panel into a one-panel card with
:func:`build_per_panel_card` and compiles it with the context from
:func:`build_per_panel_context`.

The panel always keeps its native dimensions and content: fitting it to
a fixed trim (``moo-a6``) is one compiler-emitted scale group, selected by
``CompileContext.panel_fit`` (D8, #73), so every element type (images,
strokes, gradients, patterns, text) scales the same way.
"""

from __future__ import annotations

from holiday_card.core.compiler import CompileContext
from holiday_card.core.export_targets import ExportTarget
from holiday_card.core.models import Card, Panel
from holiday_card.utils.measurements import PageGeometry

__all__ = [
    "build_per_panel_card",
    "build_per_panel_context",
    "prepare_native_panel",
]


def build_per_panel_card(card: Card, panel: Panel) -> Card:
    """Wrap a single panel, placed at the origin, into its own ``Card``."""
    return card.model_copy(update={"panels": [prepare_native_panel(panel)]})


def build_per_panel_context(panel: Panel, target: ExportTarget) -> CompileContext:
    """Build the ``CompileContext`` for compiling a per-panel card.

    A fitting target (``panel_fit != "native"``) compiles onto its own
    trim and passes its fit mode to the compiler. A native target uses the
    panel's own dimensions (with the target's bleed and safe margin).
    Fold lines and letter imposition are always disabled in per-panel
    mode — each panel is a finished card, not part of a folded sheet.
    PDF/X targets flatten transparency in the compiler (D10).
    """
    if target.panel_fit != "native":
        if target.geometry is None:
            raise ValueError(
                f"target {target.name!r} sets panel_fit={target.panel_fit!r} but "
                "has no geometry to fit into"
            )
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
    return CompileContext(
        geometry=geometry,
        emit_fold_lines=False,
        impose=False,
        flatten_transparency=target.pdfx is not None,
        panel_fit=target.panel_fit,
    )


def prepare_native_panel(panel: Panel) -> Panel:
    """Return a copy of ``panel`` placed at the origin with no rotation.

    The imposition position (``panel.x``, ``panel.y``) and the
    imposition rotation (``panel.rotation``, typically 180° for inside
    panels) are both meaningful only when the panel is part of a
    folded sheet. For per-panel output, the panel becomes its own
    page; both are stripped.
    """
    return panel.model_copy(update={"x": 0.0, "y": 0.0, "rotation": 0.0})
