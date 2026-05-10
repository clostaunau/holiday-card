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
    UnsupportedFeatureError,
    compile_card,
)
from holiday_card.core.generators import CardGenerator
from holiday_card.core.render_ir import (
    BeginGroup,
    BeginPage,
    DrawFoldLine,
    DrawShape,
    DrawText,
    EndGroup,
    EndPage,
    SetMetadata,
    assert_balanced,
)

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
