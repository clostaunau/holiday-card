"""Letter-sheet imposition is computed from the fold type (issue #58, D6).

Every shipped template is a 4-panel card printed 4-up on one side of a
letter sheet and folded twice (quarter fold). Where each panel lands on
the sheet is a property of the fold, not of the template, so the
compiler derives it from ``letter_slot`` and never trusts panel x/y.

The correct slots (origin bottom-left, quadrants as seen on the printed
side):

    front        -> BR (x 4.25, y 0)   upright
    back         -> BL (x 0,    y 0)   upright
    inside_left  -> TR (x 4.25, y 5.5) rotated 180
    inside_right -> TL (x 0,    y 5.5) rotated 180

The paper-fold simulator below re-derives that table from the physical
folds so the slot table has an oracle independent of the code.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from holiday_card.core.compiler import CompileContext, UnsupportedFeatureError, compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.imposition import (
    PanelPlacement,
    PanelSlot,
    impose_letter,
    letter_slot,
    panel_placements,
)
from holiday_card.core.models import Card, Color, FoldType, Panel, PanelPosition
from holiday_card.core.render_ir import BeginGroup, DrawShape, EndGroup, RectGeom
from holiday_card.core.templates import TemplateLoadError, load_template_from_file

LETTER_FOLDS = (FoldType.QUARTER_FOLD, FoldType.HALF_FOLD)
FOUR_PANELS = (
    PanelPosition.FRONT,
    PanelPosition.BACK,
    PanelPosition.INSIDE_LEFT,
    PanelPosition.INSIDE_RIGHT,
)

# (position) -> (quadrant, x_in, y_in, rotation_deg)
EXPECTED_SLOTS = {
    PanelPosition.FRONT: ("BR", 4.25, 0.0, 0.0),
    PanelPosition.BACK: ("BL", 0.0, 0.0, 0.0),
    PanelPosition.INSIDE_LEFT: ("TR", 4.25, 5.5, 180.0),
    PanelPosition.INSIDE_RIGHT: ("TL", 0.0, 5.5, 180.0),
}


# ---------------------------------------------------------------------------
# letter_slot
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fold_type", LETTER_FOLDS)
@pytest.mark.parametrize("position", FOUR_PANELS)
def test_letter_slot_matches_the_quarter_fold_table(
    fold_type: FoldType, position: PanelPosition
) -> None:
    quadrant, x_in, y_in, rotation = EXPECTED_SLOTS[position]
    slot = letter_slot(fold_type, position)
    assert slot == PanelSlot(
        quadrant=quadrant, x_in=x_in, y_in=y_in, rotation_deg=rotation
    )


@pytest.mark.parametrize("position", list(PanelPosition))
def test_tri_fold_has_no_letter_imposition(position: PanelPosition) -> None:
    with pytest.raises(UnsupportedFeatureError, match="tri_fold"):
        letter_slot(FoldType.TRI_FOLD, position)


@pytest.mark.parametrize("fold_type", LETTER_FOLDS)
def test_center_panel_has_no_letter_slot(fold_type: FoldType) -> None:
    with pytest.raises(UnsupportedFeatureError, match="center"):
        letter_slot(fold_type, PanelPosition.CENTER)


# ---------------------------------------------------------------------------
# Paper-fold simulator: an oracle independent of the slot table
# ---------------------------------------------------------------------------


def _fold_letter_sheet() -> list[tuple[str, float]]:
    """Fold a letter sheet the way a person does and return the layers.

    The sheet is portrait, printed side toward the viewer (+z). Each
    quadrant is a rigid layer described by its centre ``(x, y, z)`` and
    its facing normal ``nz``. Sheet thickness is 1 unit.

    Fold 1 folds the top half *back* (away from the viewer) along
    y = 5.5:  (x, y, z) -> (x, 11 - y, -z - 1); normals flip.
    Fold 2 folds the left half *back* along x = 4.25 about an axis just
    below the right-hand stack: (x, y, z) -> (8.5 - x, y, 2c - z);
    normals flip.

    Returns ``[(quadrant, nz), ...]`` ordered front (toward the viewer)
    to back.
    """
    layers: dict[str, tuple[float, float, float, float]] = {
        "BL": (2.125, 2.75, 0.0, 1.0),
        "BR": (6.375, 2.75, 0.0, 1.0),
        "TL": (2.125, 8.25, 0.0, 1.0),
        "TR": (6.375, 8.25, 0.0, 1.0),
    }

    # Fold 1: top half back over the horizontal centre line.
    for name, (x, y, z, nz) in layers.items():
        if y > 5.5:
            layers[name] = (x, 11.0 - y, -z - 1.0, -nz)

    # Fold 2: left half back over the vertical centre line. The axis sits
    # just below the lowest layer of the right-hand stack.
    right_stack_min_z = min(z for x, _, z, _ in layers.values() if x > 4.25)
    axis_z = right_stack_min_z - 0.5
    for name, (x, y, z, nz) in layers.items():
        if x < 4.25:
            layers[name] = (8.5 - x, y, 2 * axis_z - z, -nz)

    ordered = sorted(layers.items(), key=lambda kv: kv[1][2], reverse=True)
    return [(name, nz) for name, (_, _, _, nz) in ordered]


def test_paper_fold_simulator_puts_front_on_the_cover_and_inside_left_behind_it() -> None:
    layers = _fold_letter_sheet()
    quadrants = [name for name, _ in layers]
    assert quadrants == ["BR", "TR", "TL", "BL"]
    # Cover faces the viewer; the back cover faces away.
    assert layers[0][1] > 0
    assert layers[-1][1] < 0


@pytest.mark.parametrize("fold_type", LETTER_FOLDS)
def test_letter_slot_agrees_with_the_paper_fold_simulator(fold_type: FoldType) -> None:
    """Opening the folded card like a book: the cover leaf's back is the
    left inside page, the next layer is the right inside page."""
    quadrants = [name for name, _ in _fold_letter_sheet()]
    assert letter_slot(fold_type, PanelPosition.FRONT).quadrant == quadrants[0]
    assert letter_slot(fold_type, PanelPosition.INSIDE_LEFT).quadrant == quadrants[1]
    assert letter_slot(fold_type, PanelPosition.INSIDE_RIGHT).quadrant == quadrants[2]
    assert letter_slot(fold_type, PanelPosition.BACK).quadrant == quadrants[3]


# ---------------------------------------------------------------------------
# impose_letter
# ---------------------------------------------------------------------------


def _four_panel_card(fold_type: FoldType = FoldType.QUARTER_FOLD, bleed: float = 0.0) -> Card:
    panels = [
        Panel(
            position=position,
            width=4.25,
            height=5.5,
            background_color=Color(r=1.0, g=0.0, b=0.0),
        )
        for position in FOUR_PANELS
    ]
    return Card(
        name="imposition-fixture",
        template_id="imposition-fixture",
        fold_type=fold_type,
        bleed=bleed,
        panels=panels,
    )


def test_impose_letter_places_every_panel_in_its_slot() -> None:
    card = _four_panel_card()
    imposed = impose_letter(card.panels, card.fold_type)
    assert [p.position for p in imposed] == list(FOUR_PANELS)
    for panel in imposed:
        _, x_in, y_in, rotation = EXPECTED_SLOTS[panel.position]
        assert (panel.x, panel.y, panel.rotation) == (x_in, y_in, rotation)


def test_impose_letter_overrides_mirrored_coordinates() -> None:
    """Template x/y are never trusted (D6): the old mirrored layout is
    replaced, not preserved."""
    mirrored = Panel(
        position=PanelPosition.INSIDE_LEFT, x=0.0, y=5.5, rotation=180.0, width=4.25, height=5.5
    )
    (panel,) = impose_letter([mirrored], FoldType.HALF_FOLD)
    assert (panel.x, panel.y, panel.rotation) == (4.25, 5.5, 180.0)


def test_impose_letter_does_not_mutate_the_input() -> None:
    original = Panel(position=PanelPosition.INSIDE_LEFT, width=4.25, height=5.5)
    impose_letter([original], FoldType.QUARTER_FOLD)
    assert (original.x, original.y, original.rotation) == (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# panel_placements: the public placement API (#68 crops per panel with it)
# ---------------------------------------------------------------------------


@pytest.fixture
def classic_card() -> Card:
    return CardGenerator().create_card(template_id="christmas-classic")


def test_panel_placements_of_classic_has_four_entries(classic_card: Card) -> None:
    placements = panel_placements(classic_card)
    assert set(placements) == set(FOUR_PANELS)


def test_panel_placements_inside_left_lands_top_right_rotated(classic_card: Card) -> None:
    placement = panel_placements(classic_card)[PanelPosition.INSIDE_LEFT]
    assert placement == PanelPlacement(
        position=PanelPosition.INSIDE_LEFT,
        quadrant="TR",
        x_pt=306.0,
        y_pt=396.0,
        width_pt=306.0,
        height_pt=396.0,
        rotation_deg=180.0,
    )


def test_panel_placements_inside_right_lands_top_left_rotated(classic_card: Card) -> None:
    placement = panel_placements(classic_card)[PanelPosition.INSIDE_RIGHT]
    assert (placement.quadrant, placement.x_pt, placement.y_pt, placement.rotation_deg) == (
        "TL", 0.0, 396.0, 180.0
    )


def test_panel_placements_rejects_tri_fold(classic_card: Card) -> None:
    card = classic_card.model_copy(update={"fold_type": FoldType.TRI_FOLD})
    with pytest.raises(UnsupportedFeatureError):
        panel_placements(card)


def _background_rects_by_panel(card: Card) -> dict[PanelPosition, RectGeom]:
    """Map each panel to the RectGeom of its background DrawShape."""
    commands = compile_card(card, CompileContext(emit_fold_lines=False))
    rects: dict[PanelPosition, RectGeom] = {}
    panel_iter = iter(card.panels)
    depth = 0
    current: PanelPosition | None = None
    for cmd in commands:
        if isinstance(cmd, BeginGroup):
            depth += 1
            if depth == 1:
                current = next(panel_iter).position
        elif isinstance(cmd, EndGroup):
            depth -= 1
        elif (
            isinstance(cmd, DrawShape)
            and isinstance(cmd.geometry, RectGeom)
            and current is not None
            and current not in rects
        ):
            rects[current] = cmd.geometry
    return rects


@pytest.mark.parametrize("fold_type", LETTER_FOLDS)
def test_panel_placements_match_compiled_background_rects(fold_type: FoldType) -> None:
    """``compile_card`` and ``panel_placements`` share ``letter_slot``, so
    with bleed 0 every placement rect equals the compiled background rect."""
    card = _four_panel_card(fold_type=fold_type, bleed=0.0)
    rects = _background_rects_by_panel(card)
    for position, placement in panel_placements(card).items():
        rect = rects[position]
        assert (rect.x, rect.y, rect.width, rect.height) == (
            placement.x_pt,
            placement.y_pt,
            placement.width_pt,
            placement.height_pt,
        )


def test_compile_card_rotates_inside_panels_about_their_slot_centre() -> None:
    card = _four_panel_card()
    commands = compile_card(card, CompileContext(emit_fold_lines=False))
    groups = [c for c in commands if isinstance(c, BeginGroup)]
    by_position = dict(zip(FOUR_PANELS, groups, strict=True))
    left = by_position[PanelPosition.INSIDE_LEFT].transform
    right = by_position[PanelPosition.INSIDE_RIGHT].transform
    # TR centre = (4.25 + 2.125, 5.5 + 2.75) in; TL centre = (2.125, 8.25) in.
    assert (left.rotate_deg, left.pivot_x, left.pivot_y) == (180.0, 459.0, 594.0)
    assert (right.rotate_deg, right.pivot_x, right.pivot_y) == (180.0, 153.0, 594.0)


def test_compile_card_with_impose_off_keeps_panel_coordinates() -> None:
    panel = Panel(position=PanelPosition.FRONT, x=1.0, y=2.0, width=3.0, height=4.0,
                  background_color=Color(r=1.0, g=0.0, b=0.0))
    card = Card(name="raw", template_id="raw", fold_type=FoldType.QUARTER_FOLD, bleed=0.0,
                panels=[panel])
    commands = compile_card(card, CompileContext(impose=False, emit_fold_lines=False))
    (rect,) = [c.geometry for c in commands if isinstance(c, DrawShape)]
    assert (rect.x, rect.y) == (72.0, 144.0)


# ---------------------------------------------------------------------------
# Loader: panel coordinates are derived; stale ones fail loud
# ---------------------------------------------------------------------------


_BASE: dict[str, Any] = {
    "id": "t-impose",
    "name": "Impose",
    "occasion": "generic",
    "fold_type": "half_fold",
    "panels": [
        {"id": "front", "position": "front", "width": 4.25, "height": 5.5},
        {"id": "back", "position": "back", "width": 4.25, "height": 5.5},
        {"id": "inside_left", "position": "inside_left", "width": 4.25, "height": 5.5},
        {"id": "inside_right", "position": "inside_right", "width": 4.25, "height": 5.5},
    ],
}


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "t.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def _base() -> dict[str, Any]:
    return copy.deepcopy(_BASE)


def test_template_without_panel_coordinates_loads(tmp_path: Path) -> None:
    template = load_template_from_file(_write(tmp_path, _base()))
    assert [(p.x, p.y, p.rotation) for p in template.panels] == [(0.0, 0.0, 0.0)] * 4


def test_template_with_old_mirrored_coordinates_fails_loud(tmp_path: Path) -> None:
    data = _base()
    data["panels"][2].update({"x": 0, "y": 5.5, "rotation": 180})
    data["panels"][3].update({"x": 4.25, "y": 5.5, "rotation": 180})
    with pytest.raises(TemplateLoadError) as excinfo:
        load_template_from_file(_write(tmp_path, data))
    message = str(excinfo.value)
    assert "inside_left" in message
    assert "x=0.0" in message and "4.25" in message
    assert "delete x/y/rotation; imposition is computed from fold_type" in message


def test_template_with_matching_coordinates_is_accepted(tmp_path: Path) -> None:
    data = _base()
    data["panels"][2].update({"x": 4.25, "y": 5.5, "rotation": 180})
    data["panels"][3].update({"x": 0, "y": 5.5, "rotation": 180})
    data["panels"][0].update({"x": 4.25, "y": 0})
    template = load_template_from_file(_write(tmp_path, data))
    assert template.panels[2].x == 4.25


def test_template_with_wrong_rotation_only_fails_loud(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["rotation"] = 180
    with pytest.raises(TemplateLoadError, match=r"front.*rotation=180\.0.*0\.0"):
        load_template_from_file(_write(tmp_path, data))


# ---------------------------------------------------------------------------
# Acceptance: every shipped template imposes the same way
# ---------------------------------------------------------------------------


def _shipped_template_ids() -> list[str]:
    from holiday_card.core.templates import discover_templates

    return sorted(t["id"] for t in discover_templates())


@pytest.mark.parametrize("template_id", _shipped_template_ids())
def test_every_shipped_template_puts_inside_left_top_right(template_id: str) -> None:
    card = CardGenerator().create_card(template_id=template_id)
    placements = panel_placements(card)
    assert placements[PanelPosition.INSIDE_LEFT].quadrant == "TR"
    assert placements[PanelPosition.INSIDE_RIGHT].quadrant == "TL"
    assert placements[PanelPosition.FRONT].quadrant == "BR"
    assert placements[PanelPosition.BACK].quadrant == "BL"
