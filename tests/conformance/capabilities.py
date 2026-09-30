"""Backend capability matrix for the conformance suite (#67, D12).

The SVG backend is the oracle and never appears here. Each entry says what
the PDF / PNG backend does for one case in ``cases.py``.

Regenerate the doc with::

    python -m tests.conformance.capabilities > docs/conformance-matrix.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Backend = Literal["pdf", "png"]  # svg is the oracle, never listed
Status = Literal["match", "raises", "known_diff"]


@dataclass(frozen=True)
class Cap:
    status: Status
    owner: str | None = None  # issue ref, required when status == "known_diff"



_M = Cap("match")
_R = Cap("raises")


def _both(cap: Cap) -> dict[Backend, Cap]:
    return {"pdf": cap, "png": cap}


# Filled from observed ratios on 2026-09-29 (see the PR for the table).
CAPABILITIES: dict[str, dict[Backend, Cap]] = {
    "rect_fill": _both(_M),
    "rect_rounded": _both(_M),
    "circle_fill": _both(_M),
    "ellipse_fill": _both(_M),
    "polygon_star": _both(_M),
    "polyline_stroke": _both(_M),
    "path_cubic": _both(_M),
    "path_quadratic": _both(_M),
    # PNG strokes inside the edge instead of centred on it.
    "stroke_rect_6pt": {"pdf": _M, "png": Cap("known_diff", "#77")},
    "stroke_dash_line_2": _both(_M),
    "stroke_dash_line_1": _both(_M),
    "stroke_dash_line_4": _both(_M),
    "linear_gradient": _both(_M),
    "radial_gradient": _both(_M),
    # Patterns are lowered to clip + solid primitives by the compiler (#74).
    **{
        f"pattern_{kind}_{rotation}": _both(_M)
        for kind in ("stripes", "dots", "grid", "checkerboard")
        for rotation in (0, 45, 90)
    },
    "clip_circle_over_rect": _both(_M),
    "clip_nested": _both(_M),
    "group_rotate_pivot": _both(_M),
    "group_scale_pivot": _both(_M),
    "group_square_scale2_pivot": _both(_M),
    "group_square_scale2_rotate30": _both(_M),
    "group_square_scale2_offset": _both(_M),
    "group_square_nested_scale_in_rotate": _both(_M),
    "group_opacity": _both(_R),
    "shape_opacity_times_color_alpha": _both(_M),
    "alpha_no_leak": _both(_M),
    "text_lato_left": _both(_M),
    "text_lato_center": _both(_M),
    "text_lato_right": _both(_M),
    # SVG names the font by font_id ("Cormorant"), which matches no font
    # family, so the oracle draws nothing until @font-face lands.
    "text_curated_family": _both(Cap("known_diff", "#76")),
    "text_opacity": _both(_M),
    "image_jpeg": _both(_M),
    "image_clipped_circle": _both(_M),
    "image_opacity": _both(_M),
    "fold_line_dashed": _both(_M),
    "page_bleed_background": _both(_M),
}


def _cell(cap: Cap) -> str:
    return f"{cap.status} ({cap.owner})" if cap.owner else cap.status


def render_markdown(capabilities: dict[str, dict[Backend, Cap]]) -> str:
    """Render the matrix as the Markdown table in ``docs/conformance-matrix.md``."""
    lines = [
        "# Backend conformance matrix",
        "",
        "<!-- Generated from tests/conformance/capabilities.py; do not edit by hand. -->",
        "<!-- Regenerate: python -m tests.conformance.capabilities > docs/conformance-matrix.md -->",
        "",
        "Each case in `tests/conformance/cases.py` is rendered by every backend and",
        "compared against the SVG backend (the oracle, D12) at 144 DPI.",
        "",
        "- `match`: within tolerance of the SVG raster.",
        "- `raises`: the backend raises `NotImplementedError` (D4).",
        "- `known_diff (#N)`: differs from SVG; issue #N owns the fix.",
        "",
        "| case | pdf | png |",
        "|---|---|---|",
    ]
    for case_id, row in capabilities.items():
        lines.append(f"| `{case_id}` | {_cell(row['pdf'])} | {_cell(row['png'])} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_markdown(CAPABILITIES), end="")
