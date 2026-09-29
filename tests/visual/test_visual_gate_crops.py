"""The visual gate's per-panel crop boxes (#68).

Crops come from the compiler's imposition API (D6), never from template
``x``/``y``, so a panel is always compared where it actually lands on the
sheet.
"""

from __future__ import annotations

from itertools import combinations

import pytest
from visual_gate import CROP_INSET_PX, DPI, build_card, panel_crop_boxes

pytestmark = pytest.mark.visual

SHEET_PX = (1224, 1584)  # 8.5×11 in at 144 DPI; the letter target has no bleed (D7)


def _area(box: tuple[int, int, int, int]) -> int:
    left, top, right, bottom = box
    return (right - left) * (bottom - top)


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return max(width, 0) * max(height, 0)


def test_gate_runs_at_144_dpi() -> None:
    assert DPI == 144


def test_quarter_fold_panels_are_612_by_792_px_before_inset() -> None:
    boxes = panel_crop_boxes(build_card("christmas-classic"), inset=0)

    assert set(boxes) == {"front", "back", "inside_left", "inside_right"}
    for position, (left, top, right, bottom) in boxes.items():
        assert (right - left, bottom - top) == (612, 792), position


def test_panel_boxes_tile_the_sheet_without_overlap() -> None:
    boxes = panel_crop_boxes(build_card("christmas-classic"), inset=0)

    for (name_a, a), (name_b, b) in combinations(boxes.items(), 2):
        assert _overlap(a, b) == 0, (name_a, name_b)
    for box in boxes.values():
        assert 0 <= box[0] < box[2] <= SHEET_PX[0]
        assert 0 <= box[1] < box[3] <= SHEET_PX[1]
    assert sum(_area(b) for b in boxes.values()) == SHEET_PX[0] * SHEET_PX[1]


def test_boxes_follow_imposition_with_a_top_left_origin() -> None:
    boxes = panel_crop_boxes(build_card("christmas-classic"), inset=0)

    # front → bottom-right, back → bottom-left, inside_left → top-right,
    # inside_right → top-left (core/imposition.letter_slot).
    assert boxes["front"] == (612, 792, 1224, 1584)
    assert boxes["back"] == (0, 792, 612, 1584)
    assert boxes["inside_left"] == (612, 0, 1224, 792)
    assert boxes["inside_right"] == (0, 0, 612, 792)


def test_default_inset_drops_seam_pixels_on_every_edge() -> None:
    card = build_card("christmas-classic")
    raw = panel_crop_boxes(card, inset=0)
    inset = panel_crop_boxes(card)

    assert CROP_INSET_PX == 2
    for position, (left, top, right, bottom) in raw.items():
        assert inset[position] == (left + 2, top + 2, right - 2, bottom - 2)
