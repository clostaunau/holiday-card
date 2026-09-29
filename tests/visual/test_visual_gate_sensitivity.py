"""Locks the visual gate's sensitivity so it cannot quietly be loosened (#68).

Each calibration mutation from the issue is applied to ``christmas-classic``,
both sheets are rendered fresh, and the per-panel comparator must flag every
panel the mutation touches, on both gated backends. Raising
``MAX_PANEL_RATIO`` past the smallest real change makes this test fail.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image
from visual_gate import (
    BACKENDS,
    MAX_PANEL_RATIO,
    Backend,
    build_card,
    panel_crop_boxes,
    panel_ratios,
    render_sheet,
)

from holiday_card.core.models import Card, PanelPosition

pytestmark = pytest.mark.visual

TEMPLATE_ID = "christmas-classic"

# The smallest calibrated real change in the issue (text at 80%, inside_right).
SMALLEST_CALIBRATED_CHANGE = 0.0073

_INSIDE = {PanelPosition.INSIDE_LEFT, PanelPosition.INSIDE_RIGHT}


def _fonts_to_lato(card: Card) -> None:
    for panel in card.panels:
        for text in panel.text_elements:
            text.font_family = "Lato"


def _text_at_80_percent(card: Card) -> None:
    for panel in card.panels:
        for text in panel.text_elements:
            text.font_size = round(text.font_size * 0.8)


def _text_shift_2pt_x(card: Card) -> None:
    for panel in card.panels:
        for text in panel.text_elements:
            text.x += 2 / 72


def _inside_text_removed(card: Card) -> None:
    for panel in card.panels:
        if panel.position in _INSIDE:
            panel.text_elements = []


MUTATIONS: dict[str, Callable[[Card], None]] = {
    "fonts_to_lato": _fonts_to_lato,
    "text_at_80_percent": _text_at_80_percent,
    "text_shift_2pt_x": _text_shift_2pt_x,
    "inside_text_removed": _inside_text_removed,
}


def _touched_panels(before: Card, after: Card) -> set[str]:
    old = {p.position.value: p.model_dump() for p in before.panels}
    return {p.position.value for p in after.panels if p.model_dump() != old[p.position.value]}


@pytest.fixture(scope="module")
def baselines(tmp_path_factory: pytest.TempPathFactory) -> dict[Backend, Image.Image]:
    out = tmp_path_factory.mktemp("sensitivity-baseline")
    return {b: render_sheet(build_card(TEMPLATE_ID), b, out) for b in BACKENDS}


@pytest.mark.parametrize("backend", BACKENDS)
def test_identical_rerender_has_zero_ratio(
    backend: Backend, baselines: dict[Backend, Image.Image], tmp_path: Path
) -> None:
    card = build_card(TEMPLATE_ID)
    fresh = render_sheet(card, backend, tmp_path)

    ratios = panel_ratios(fresh, baselines[backend], panel_crop_boxes(card))

    assert ratios == dict.fromkeys(ratios, 0.0)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_mutation_trips_every_panel_it_touches(
    mutation: str, backend: Backend, baselines: dict[Backend, Image.Image], tmp_path: Path
) -> None:
    original = build_card(TEMPLATE_ID)
    card = build_card(TEMPLATE_ID)
    MUTATIONS[mutation](card)
    touched = _touched_panels(original, card)
    assert touched, f"{mutation} changed no panel of {TEMPLATE_ID}"

    ratios = panel_ratios(
        render_sheet(card, backend, tmp_path), baselines[backend], panel_crop_boxes(card)
    )

    missed = {p: ratios[p] for p in touched if ratios[p] <= MAX_PANEL_RATIO}
    assert not missed, (
        f"{mutation} on {backend} went undetected on {missed} "
        f"(MAX_PANEL_RATIO={MAX_PANEL_RATIO}); all ratios: {ratios}"
    )
    leaked = {p: ratios[p] for p in set(ratios) - touched if ratios[p] > MAX_PANEL_RATIO}
    assert not leaked, f"{mutation} tripped panels it does not touch: {leaked}"


def test_threshold_is_below_the_smallest_calibrated_change() -> None:
    assert MAX_PANEL_RATIO <= SMALLEST_CALIBRATED_CHANGE
