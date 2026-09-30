"""No shipped template draws text outside its own panel (#134).

christmas-photo-ornament centred its inside-left caption on ``x: 0.5"``, so
about half the line hung off the panel on every target; only moo-a6's
safe-zone warning (#73) ever said so. This compiles every panel of every
shipped template natively (per-panel-pdf: one panel at the origin, IR in
trim-relative points) and requires each text run's measured box (advance
width × ascent/descent, through any group such as text rotation) to stay
inside the panel's trim.
"""

from __future__ import annotations

import pytest

from holiday_card.core.compiler import compile_card
from holiday_card.core.export_targets import get_target
from holiday_card.core.generators import CardGenerator
from holiday_card.core.per_panel import build_per_panel_card, build_per_panel_context
from holiday_card.core.render_ir import BeginGroup, DrawText, EndGroup
from holiday_card.core.templates import discover_templates
from holiday_card.core.text_measure import default_text_measurer

_TOLERANCE_PT = 0.01
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

Matrix = tuple[float, float, float, float, float, float]


def _compose(outer: Matrix, inner: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1,
    )


def _overhangs(template_id: str) -> list[str]:
    """``panel: 'text' overhangs by N pt`` for every run leaving its panel trim."""
    measurer = default_text_measurer()
    card = CardGenerator().create_card(template_id=template_id)
    target = get_target("per-panel-pdf")
    found: list[str] = []
    for panel in card.panels:
        commands = compile_card(
            build_per_panel_card(card, panel), build_per_panel_context(panel, target),
        )
        width_pt, height_pt = panel.width * 72, panel.height * 72
        stack: list[Matrix] = [_IDENTITY]
        for cmd in commands:
            if isinstance(cmd, BeginGroup):
                stack.append(_compose(stack[-1], cmd.transform.to_matrix()))
            elif isinstance(cmd, EndGroup):
                stack.pop()
            elif isinstance(cmd, DrawText) and cmd.run.text.strip():
                run = cmd.run
                advance = measurer.string_width(run.text, run.font_id, run.size_pt)
                ascent, descent = measurer.ascent_descent(run.font_id, run.size_pt)
                x0 = run.origin.x - {"left": 0.0, "center": advance / 2, "right": advance}[run.align]
                a, b, c, d, e, f = stack[-1]
                corners = [
                    (a * x + c * y + e, b * x + d * y + f)
                    for x in (x0, x0 + advance)
                    for y in (run.origin.y + descent, run.origin.y + ascent)
                ]
                xs = [p[0] for p in corners]
                ys = [p[1] for p in corners]
                over = max(-min(xs), -min(ys), max(xs) - width_pt, max(ys) - height_pt)
                if over > _TOLERANCE_PT:
                    found.append(
                        f"{panel.position.value}: {run.text!r} overhangs by {over:.1f} pt"
                    )
    return found


@pytest.mark.parametrize(
    "template_id", sorted(t["id"] for t in discover_templates()),
)
def test_every_text_run_stays_inside_its_panel(template_id: str) -> None:
    assert _overhangs(template_id) == []
