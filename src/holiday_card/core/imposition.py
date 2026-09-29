"""Letter-sheet imposition: where each panel lands on the printed sheet.

Every shipped template is a 4-panel card printed 4-up on one side of a
US Letter sheet and folded twice (a quarter fold). Which quadrant each
panel occupies, and whether it prints upside down, is a property of the
fold, not of the template. The compiler therefore derives panel
placement from ``letter_slot`` and never trusts template ``x``/``y``
(standing decision D6).

Derivation (hold a portrait sheet, printed side toward you):

1. Fold the top half *back* along y = 5.5. The top-right quadrant now
   sits behind the bottom-right one, facing away.
2. Fold the left half *back* along x = 4.25. Front to back the stack is
   now BR, TR, TL, BL.

So the cover is BR, the left inside page (the back of the cover leaf) is
TR, the right inside page is TL and the back cover is BL. The top-half
panels were flipped over the horizontal fold, so they print rotated 180°
to read upright once folded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from holiday_card.core.errors import UnsupportedFeatureError
from holiday_card.core.models import Card, FoldType, Panel, PanelPosition
from holiday_card.utils.measurements import inches_to_points

Quadrant = Literal["BL", "BR", "TL", "TR"]

# US Letter, portrait: quadrant origins in inches (bottom-left origin).
_LETTER_WIDTH_IN = 8.5
_LETTER_HEIGHT_IN = 11.0
_HALF_WIDTH_IN = _LETTER_WIDTH_IN / 2
_HALF_HEIGHT_IN = _LETTER_HEIGHT_IN / 2


@dataclass(frozen=True)
class PanelSlot:
    """A panel's quadrant on the letter sheet, in inches."""

    quadrant: Quadrant
    x_in: float
    y_in: float
    rotation_deg: float


@dataclass(frozen=True)
class PanelPlacement:
    """Where a panel lands on the letter sheet after imposition.

    The rect is in IR points with a bottom-left origin, trim-relative
    (it excludes bleed). ``rotation_deg`` is applied about the rect's
    centre, so the rect itself is the same before and after rotation.
    """

    position: PanelPosition
    quadrant: Quadrant
    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float
    rotation_deg: float


# Both letter fold types are the same 4-up single-sided quarter fold;
# ``half_fold`` is a legacy alias (see FoldType).
_LETTER_FOLD_TYPES = frozenset({FoldType.QUARTER_FOLD, FoldType.HALF_FOLD})

_LETTER_SLOTS: dict[PanelPosition, PanelSlot] = {
    PanelPosition.FRONT: PanelSlot("BR", _HALF_WIDTH_IN, 0.0, 0.0),
    PanelPosition.BACK: PanelSlot("BL", 0.0, 0.0, 0.0),
    PanelPosition.INSIDE_LEFT: PanelSlot("TR", _HALF_WIDTH_IN, _HALF_HEIGHT_IN, 180.0),
    PanelPosition.INSIDE_RIGHT: PanelSlot("TL", 0.0, _HALF_HEIGHT_IN, 180.0),
}


def letter_slot(fold_type: FoldType, position: PanelPosition) -> PanelSlot:
    """Return the letter-sheet slot for ``position`` under ``fold_type``.

    Raises ``UnsupportedFeatureError`` for fold types without a letter
    imposition (``tri_fold``) and for positions outside the 4-panel set.
    """
    if fold_type not in _LETTER_FOLD_TYPES:
        raise UnsupportedFeatureError(
            f"no letter imposition for fold type {fold_type.value!r}; "
            f"only quarter_fold (and its legacy alias half_fold) is supported"
        )
    slot = _LETTER_SLOTS.get(position)
    if slot is None:
        raise UnsupportedFeatureError(
            f"panel position {position.value!r} has no slot in the "
            f"{fold_type.value} letter imposition; expected one of "
            f"{', '.join(p.value for p in _LETTER_SLOTS)}"
        )
    return slot


def impose_letter(panels: list[Panel], fold_type: FoldType) -> list[Panel]:
    """Return copies of ``panels`` placed in their letter-sheet slots.

    Only ``x``, ``y`` and ``rotation`` change; the input panels are not
    mutated.
    """
    imposed: list[Panel] = []
    for panel in panels:
        slot = letter_slot(fold_type, panel.position)
        imposed.append(
            panel.model_copy(
                update={"x": slot.x_in, "y": slot.y_in, "rotation": slot.rotation_deg}
            )
        )
    return imposed


def panel_placements(card: Card) -> dict[PanelPosition, PanelPlacement]:
    """Where each panel of ``card`` lands on the letter sheet after imposition.

    Pure; derived from ``letter_slot`` plus each panel's width/height.
    Raises ``UnsupportedFeatureError`` for fold types without a letter
    imposition.
    """
    placements: dict[PanelPosition, PanelPlacement] = {}
    for panel in card.panels:
        slot = letter_slot(card.fold_type, panel.position)
        placements[panel.position] = PanelPlacement(
            position=panel.position,
            quadrant=slot.quadrant,
            x_pt=inches_to_points(slot.x_in),
            y_pt=inches_to_points(slot.y_in),
            width_pt=inches_to_points(panel.width),
            height_pt=inches_to_points(panel.height),
            rotation_deg=slot.rotation_deg,
        )
    return placements
