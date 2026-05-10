"""Tests for ``core.compiler.compile_card``.

Two flavors:

* **Structural unit tests** assert specific properties of the emitted
  command list (page bounds are open, panels are wrapped in groups,
  fold lines match fold type, ``assert_balanced`` passes, unsupported
  features raise loudly).
* **Snapshot tests** for shipped templates that use only the supported
  feature subset. The snapshot file is committed; any compiler change
  shows up as a JSON diff for human review. Regenerate with
  ``UPDATE_COMPILER_SNAPSHOTS=1 pytest tests/unit/test_compiler.py``.

This PR's compiler covers backgrounds, borders, basic shapes
(Rectangle/Circle/Triangle/Star/Line with solid fills only), text via
``core.text_fitting``, and fold lines. Templates using images, gradients,
patterns, clip masks, SVG paths, or decorative elements raise
``UnsupportedFeatureError`` — that's by design (Wave 2 follow-up PRs lift
each one in turn).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from holiday_card.core.compiler import (
    CompileContext,
    UnsupportedFeatureError,
    compile_card,
)
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import (
    Card,
    Color,
    FoldType,
    Panel,
    PanelPosition,
)
from holiday_card.core.render_ir import (
    BeginGroup,
    BeginPage,
    DrawFoldLine,
    DrawShape,
    DrawText,
    EndGroup,
    EndPage,
    RectGeom,
    SetMetadata,
    assert_balanced,
)
from holiday_card.utils.measurements import PageGeometry

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
UPDATE_SNAPSHOTS = os.environ.get("UPDATE_COMPILER_SNAPSHOTS") == "1"

# Templates that compile cleanly with the Step 2b feature subset.
# When a follow-up PR adds support for images / gradients / etc., move
# the relevant template id from SUPPORTED_REJECTING_TEMPLATES to
# SUPPORTED_SNAPSHOT_TEMPLATES and regenerate the snapshot.
SUPPORTED_SNAPSHOT_TEMPLATES = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "birthday-balloons",
    "hanukkah-menorah",
    "generic-celebration",
    "mothers-day",
)

# Templates expected to raise UnsupportedFeatureError. Empty after the
# valentine/decorative-element removal — every shipped template now
# compiles via the IR. Kept as a hook so a future feature with partial
# coverage can re-enable the watch-dog without restructuring the test.
SUPPORTED_REJECTING_TEMPLATES: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Structural unit tests (don't require any specific template — build the
# Card directly via CardGenerator on a known-supported template)
# ---------------------------------------------------------------------------


@pytest.fixture
def classic_card() -> object:
    return CardGenerator().create_card(
        template_id="christmas-classic", message="Merry Christmas!"
    )


class TestStructure:
    def test_first_command_opens_a_page(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        assert isinstance(commands[0], BeginPage)
        assert commands[0].width > 0 and commands[0].height > 0

    def test_last_command_closes_the_page(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        assert isinstance(commands[-1], EndPage)

    def test_emits_metadata_for_template_and_fold(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        meta = [c for c in commands if isinstance(c, SetMetadata)]
        keys = {m.key for m in meta}
        assert "template_id" in keys
        assert "fold_type" in keys

    def test_each_panel_is_wrapped_in_a_group(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        begins = sum(1 for c in commands if isinstance(c, BeginGroup))
        ends = sum(1 for c in commands if isinstance(c, EndGroup))
        # christmas-classic is a half-fold card with 4 panels; the compiler
        # opens one group per panel.
        assert begins == ends == len(classic_card.panels)  # type: ignore[attr-defined]

    def test_half_fold_emits_one_horizontal_fold_line(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        folds = [c for c in commands if isinstance(c, DrawFoldLine)]
        assert len(folds) == 1
        assert folds[0].start.y == folds[0].end.y, "half-fold line should be horizontal"

    def test_assert_balanced_passes_on_compiled_output(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        assert_balanced(commands)  # would raise on imbalance

    def test_text_lines_get_drawn(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        texts = [c for c in commands if isinstance(c, DrawText)]
        # christmas-classic ships with at least the front greeting + the
        # inside message.
        assert len(texts) >= 2
        assert any("Merry Christmas" in t.run.text for t in texts)

    def test_panel_backgrounds_become_draw_shapes(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        # All four panels in christmas-classic declare a background_color.
        rect_fills = [
            c for c in commands
            if isinstance(c, DrawShape) and c.geometry.kind == "rect" and c.fill is not None
        ]
        assert len(rect_fills) >= 4


# ---------------------------------------------------------------------------
# Watch-dog: templates with unsupported features must raise loudly so we
# never silently ship a half-compiled PDF.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_id", SUPPORTED_REJECTING_TEMPLATES)
def test_unsupported_features_raise_loudly(template_id: str) -> None:
    card = CardGenerator().create_card(template_id=template_id)
    with pytest.raises(UnsupportedFeatureError):
        compile_card(card)


# ---------------------------------------------------------------------------
# Snapshot tests — golden JSON for templates that currently compile
# ---------------------------------------------------------------------------


def _snapshot_path(template_id: str) -> Path:
    return SNAPSHOT_DIR / f"compile_card__{template_id}.json"


def _serialize(commands: list[object]) -> str:
    """Dump commands to deterministic JSON for diff-friendly snapshots."""
    payload = [json.loads(c.model_dump_json()) for c in commands]  # type: ignore[attr-defined]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize("template_id", SUPPORTED_SNAPSHOT_TEMPLATES)
def test_compiler_snapshot(template_id: str) -> None:
    card = CardGenerator().create_card(template_id=template_id)
    commands = compile_card(card)
    actual = _serialize(commands)

    path = _snapshot_path(template_id)

    if UPDATE_SNAPSHOTS:
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        path.write_text(actual)
        pytest.skip(f"snapshot updated: {path.name}")

    if not path.exists():
        pytest.fail(
            f"Missing snapshot {path}. "
            f"Generate with: UPDATE_COMPILER_SNAPSHOTS=1 pytest {__file__}"
        )

    expected = path.read_text()
    assert actual == expected, (
        f"Compiler output for {template_id!r} differs from snapshot at {path}.\n"
        f"If the change is intentional, regenerate with:\n"
        f"  UPDATE_COMPILER_SNAPSHOTS=1 pytest {__file__}"
    )


# ---------------------------------------------------------------------------
# Bleed extension — edge-aware background expansion
# ---------------------------------------------------------------------------


def _single_panel_card(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    rotation: float = 0.0,
    panel_bleed: float | None = None,
    card_bleed: float = 0.125,
) -> Card:
    """Build a minimal 1-panel card whose only feature is a red background.

    The compiler then emits exactly one DrawShape (the background) per
    panel, which is what the bleed tests inspect.
    """
    panel = Panel(
        position=PanelPosition.FRONT,
        x=x, y=y, width=width, height=height,
        rotation=rotation,
        bleed=panel_bleed,
        background_color=Color(r=1.0, g=0.0, b=0.0),
    )
    return Card(
        name="bleed-fixture",
        template_id="bleed-fixture",
        fold_type=FoldType.HALF_FOLD,
        bleed=card_bleed,
        panels=[panel],
    )


def _bg_rect(commands: list[object]) -> RectGeom:
    """Locate the (single) panel-background DrawShape's RectGeom."""
    rects = [
        c.geometry for c in commands  # type: ignore[attr-defined]
        if isinstance(c, DrawShape)
        and isinstance(c.geometry, RectGeom)
        and c.fill is not None
    ]
    assert len(rects) == 1, f"expected exactly one bg rect, got {len(rects)}"
    return rects[0]


class TestBleedExtension:
    """The compiler's bleed pass extends panel backgrounds on edges that
    touch the page trim. Page edges interior to the imposition (the
    fold line, panel-to-panel borders) do not get extended.
    """

    def test_panel_touching_all_four_edges_extends_on_all_four(self) -> None:
        # A full-page panel at (0, 0, 8.5, 11) touches every page edge.
        card = _single_panel_card(x=0, y=0, width=8.5, height=11.0)
        commands = compile_card(card)
        rect = _bg_rect(commands)
        # 0.125" bleed = 9 pt extension on every side.
        assert rect.x == -9.0
        assert rect.y == -9.0
        assert rect.width == 612.0 + 18.0
        assert rect.height == 792.0 + 18.0

    def test_panel_touching_only_right_edge_extends_only_on_right(self) -> None:
        # Front panel of a half-fold: x=4.25, y=0 → touches right + bottom
        # but not left or top. Use a smaller height to drop the top touch.
        card = _single_panel_card(x=4.25, y=2.0, width=4.25, height=4.0)
        commands = compile_card(card)
        rect = _bg_rect(commands)
        # x unchanged (left does NOT touch trim), width grows by 9 pt.
        assert rect.x == 4.25 * 72  # 306
        assert rect.width == 4.25 * 72 + 9.0  # 315
        # y unchanged (bottom does NOT touch trim), height unchanged.
        assert rect.y == 2.0 * 72  # 144
        assert rect.height == 4.0 * 72  # 288

    def test_no_bleed_when_card_bleed_and_panel_bleed_both_zero(self) -> None:
        card = _single_panel_card(
            x=0, y=0, width=8.5, height=11.0, card_bleed=0.0, panel_bleed=None
        )
        rect = _bg_rect(compile_card(card))
        assert rect.x == 0.0 and rect.y == 0.0
        assert rect.width == 612.0 and rect.height == 792.0

    def test_panel_bleed_overrides_card_bleed_with_zero(self) -> None:
        # Card says 0.125 but panel says 0 — panel wins (explicit override).
        card = _single_panel_card(
            x=0, y=0, width=8.5, height=11.0, card_bleed=0.125, panel_bleed=0.0
        )
        rect = _bg_rect(compile_card(card))
        # No extension despite card-level default.
        assert rect.x == 0.0 and rect.y == 0.0
        assert rect.width == 612.0 and rect.height == 792.0

    def test_panel_bleed_overrides_card_bleed_with_larger_value(self) -> None:
        card = _single_panel_card(
            x=0, y=0, width=8.5, height=11.0, card_bleed=0.125, panel_bleed=0.25
        )
        rect = _bg_rect(compile_card(card))
        # 0.25" = 18 pt extension on every side.
        assert rect.x == -18.0 and rect.y == -18.0
        assert rect.width == 612.0 + 36.0
        assert rect.height == 792.0 + 36.0

    def test_rotated_180_panel_extends_on_swapped_local_edges(self) -> None:
        # Inside-left of a half-fold: x=0, y=5.5, w=4.25, h=5.5, rotation=180.
        # Page-touches: left, top. After 180° rotation, those map to
        # panel-local right + bottom — meaning the LOCAL rect drawn inside
        # the BeginGroup extends rightward (+9 width) and downward (-9 y,
        # +9 height).
        card = _single_panel_card(x=0, y=5.5, width=4.25, height=5.5, rotation=180.0)
        rect = _bg_rect(compile_card(card))
        # x stays 0 (local left edge does NOT touch); width grows by 9.
        assert rect.x == 0.0
        assert rect.width == 4.25 * 72 + 9.0  # 315
        # y drops by 9 (local bottom edge maps to page-top touch).
        assert rect.y == 5.5 * 72 - 9.0  # 387
        # height grows by 9 (local-bottom extension only; local-top did not).
        assert rect.height == 5.5 * 72 + 9.0  # 405

    def test_unsupported_rotation_with_bleed_fails_loudly(self) -> None:
        card = _single_panel_card(x=0, y=0, width=8.5, height=11.0, rotation=90.0)
        with pytest.raises(UnsupportedFeatureError, match="rotation"):
            compile_card(card)


class TestBeginPageBleedFields:
    """``BeginPage`` now carries the bleed and safe-margin in points."""

    def test_default_geometry_emits_industry_bleed(self) -> None:
        # Default CompileContext = PageGeometry.us_letter() with 0.125" bleed.
        card = CardGenerator().create_card(template_id="christmas-classic")
        commands = compile_card(card)
        bp = commands[0]
        assert isinstance(bp, BeginPage)
        assert bp.width == 612.0  # trim width unchanged
        assert bp.height == 792.0
        assert bp.bleed == 9.0  # 0.125" in points
        assert bp.safe_margin == 18.0  # 0.25" in points

    def test_zero_bleed_geometry_zeros_the_field(self) -> None:
        card = CardGenerator().create_card(template_id="christmas-classic")
        ctx = CompileContext(geometry=PageGeometry.us_letter(bleed_in=0.0))
        bp = compile_card(card, ctx)[0]
        assert isinstance(bp, BeginPage)
        assert bp.bleed == 0.0
