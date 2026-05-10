"""Tests for the rendering IR contract.

The IR is the seam between the domain model and any rendering backend
(Wave 2 Step 1). These tests lock in:

- frozen-mutation enforcement (every IR type is immutable)
- JSON round-trip per command (so commands can be snapshot-tested in
  Step 2's compiler tests)
- ``assert_balanced`` correctly accepts well-nested groups/clips/pages and
  rejects each class of imbalance

There is no production caller of ``render_ir`` yet, so these are the only
guards on the contract until Step 2 lands the compiler.
"""

import json

import pytest
from pydantic import ValidationError

from holiday_card.core.render_ir import (
    RGBA,
    BeginClip,
    BeginGroup,
    BeginPage,
    CircleGeom,
    DrawFoldLine,
    DrawImage,
    DrawShape,
    DrawText,
    EndClip,
    EndGroup,
    EndPage,
    GradientStop,
    ImageRef,
    LinearGradientPaint,
    PathGeom,
    PathOp,
    PatternPaint,
    Point,
    PolygonGeom,
    RadialGradientPaint,
    RectGeom,
    SetMetadata,
    SolidPaint,
    Stroke,
    TextRun,
    Transform,
    assert_balanced,
)

# ---------------------------------------------------------------------------
# Frozen / immutability
# ---------------------------------------------------------------------------


class TestFrozen:
    def test_value_objects_reject_mutation(self) -> None:
        p = Point(x=1.0, y=2.0)
        with pytest.raises(ValidationError):
            p.x = 99.0  # type: ignore[misc]

    def test_commands_reject_mutation(self) -> None:
        cmd = DrawText(
            run=TextRun(
                text="hi",
                origin=Point(x=0, y=0),
                font_id="Helvetica",
                size_pt=12,
                color=RGBA(r=0, g=0, b=0),
            )
        )
        with pytest.raises(ValidationError):
            cmd.opacity = 0.5  # type: ignore[misc]

    def test_extra_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Point(x=0, y=0, z=0)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Field-level validation (a few high-value cases — full Pydantic coverage
# is implicit through the constructors below)
# ---------------------------------------------------------------------------


class TestFieldValidation:
    def test_rgba_channels_must_be_in_unit_range(self) -> None:
        RGBA(r=0.0, g=1.0, b=0.5)  # ok
        with pytest.raises(ValidationError):
            RGBA(r=-0.01, g=0, b=0)
        with pytest.raises(ValidationError):
            RGBA(r=1.01, g=0, b=0)

    def test_rect_dimensions_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            RectGeom(x=0, y=0, width=0, height=10)
        with pytest.raises(ValidationError):
            RectGeom(x=0, y=0, width=10, height=-1)

    def test_polygon_requires_at_least_three_points(self) -> None:
        with pytest.raises(ValidationError):
            PolygonGeom(points=(Point(x=0, y=0), Point(x=1, y=1)))

    def test_begin_page_bleed_and_safe_default_to_zero(self) -> None:
        """Old-shape ``BeginPage(width=, height=)`` still works — the bleed
        and safe_margin fields default to 0 so callers that don't care
        about prepress aren't forced to supply them."""
        bp = BeginPage(width=612, height=792)
        assert bp.bleed == 0.0
        assert bp.safe_margin == 0.0

    def test_begin_page_accepts_bleed_and_safe_margin(self) -> None:
        bp = BeginPage(width=612, height=792, bleed=9.0, safe_margin=18.0)
        assert bp.bleed == 9.0
        assert bp.safe_margin == 18.0

    def test_begin_page_rejects_negative_bleed(self) -> None:
        with pytest.raises(ValidationError):
            BeginPage(width=612, height=792, bleed=-1.0)
        with pytest.raises(ValidationError):
            BeginPage(width=612, height=792, safe_margin=-1.0)

    def test_linear_gradient_requires_at_least_two_stops(self) -> None:
        with pytest.raises(ValidationError):
            LinearGradientPaint(
                start=Point(x=0, y=0),
                end=Point(x=10, y=0),
                stops=(GradientStop(position=0.5, color=RGBA(r=0, g=0, b=0)),),
            )


# ---------------------------------------------------------------------------
# JSON round-trip — proves every command is serializable for snapshot tests
# ---------------------------------------------------------------------------


def _all_command_fixtures() -> list[object]:
    """One representative instance of each of the 11 commands."""
    pt = Point(x=10.0, y=20.0)
    rgb = RGBA(r=0.1, g=0.2, b=0.3)
    rect = RectGeom(x=0, y=0, width=100, height=50)
    return [
        DrawShape(
            geometry=rect,
            fill=SolidPaint(color=rgb),
            stroke=Stroke(color=rgb, width=1.0),
            opacity=0.9,
        ),
        DrawText(
            run=TextRun(text="hi", origin=pt, font_id="Helvetica", size_pt=12, color=rgb),
            opacity=1.0,
        ),
        DrawImage(image=ImageRef(source="/tmp/x.png", rect=rect)),
        BeginGroup(transform=Transform(translate_x=5, rotate_deg=15), opacity=0.8),
        EndGroup(),
        BeginClip(geometry=CircleGeom(center=pt, radius=20)),
        EndClip(),
        DrawFoldLine(start=pt, end=Point(x=100, y=20), style="dashed"),
        SetMetadata(key="template_id", value="christmas-classic"),
        BeginPage(width=612.0, height=792.0),
        EndPage(),
    ]


@pytest.mark.parametrize("command", _all_command_fixtures())
def test_command_roundtrips_through_json(command: object) -> None:
    blob = command.model_dump_json()  # type: ignore[attr-defined]
    payload = json.loads(blob)
    assert "cmd" in payload, f"missing discriminator on {type(command).__name__}"
    revived = type(command).model_validate(payload)  # type: ignore[attr-defined]
    assert revived == command


def test_paint_variants_all_serialize_with_kind_discriminator() -> None:
    paints: list[object] = [
        SolidPaint(color=RGBA(r=1, g=0, b=0)),
        LinearGradientPaint(
            start=Point(x=0, y=0),
            end=Point(x=10, y=0),
            stops=(
                GradientStop(position=0.0, color=RGBA(r=0, g=0, b=0)),
                GradientStop(position=1.0, color=RGBA(r=1, g=1, b=1)),
            ),
        ),
        RadialGradientPaint(
            center=Point(x=5, y=5),
            radius=3.0,
            stops=(
                GradientStop(position=0.0, color=RGBA(r=0, g=0, b=0)),
                GradientStop(position=1.0, color=RGBA(r=1, g=1, b=1)),
            ),
        ),
        PatternPaint(
            pattern="stripes",
            colors=(RGBA(r=0, g=0, b=0),),
            spacing=4.0,
        ),
    ]
    for p in paints:
        blob = json.loads(p.model_dump_json())  # type: ignore[attr-defined]
        assert "kind" in blob


def test_path_geom_with_cubic_op_roundtrips() -> None:
    p = PathGeom(
        ops=(
            PathOp(op="move", points=(Point(x=0, y=0),)),
            PathOp(
                op="cubic",
                points=(Point(x=10, y=10), Point(x=20, y=10), Point(x=30, y=0)),
            ),
            PathOp(op="close"),
        )
    )
    revived = PathGeom.model_validate(json.loads(p.model_dump_json()))
    assert revived == p


# ---------------------------------------------------------------------------
# assert_balanced
# ---------------------------------------------------------------------------


class TestAssertBalanced:
    def test_empty_command_list_is_balanced(self) -> None:
        assert_balanced([])  # does not raise

    def test_well_nested_page_group_clip_is_balanced(self) -> None:
        cmds = [
            BeginPage(width=612, height=792),
            BeginGroup(),
            BeginClip(geometry=CircleGeom(center=Point(x=0, y=0), radius=10)),
            DrawShape(geometry=RectGeom(x=0, y=0, width=10, height=10)),
            EndClip(),
            EndGroup(),
            EndPage(),
        ]
        assert_balanced(cmds)

    def test_unmatched_open_raises(self) -> None:
        with pytest.raises(ValueError, match="never closed"):
            assert_balanced([BeginGroup()])

    def test_unmatched_close_raises(self) -> None:
        with pytest.raises(ValueError, match="no matching open"):
            assert_balanced([EndGroup()])

    def test_crossed_pairs_raise(self) -> None:
        # BeginGroup ... BeginClip ... EndGroup ... EndClip — illegal nesting
        with pytest.raises(ValueError, match="closed by"):
            assert_balanced([
                BeginGroup(),
                BeginClip(geometry=CircleGeom(center=Point(x=0, y=0), radius=1)),
                EndGroup(),
                EndClip(),
            ])

    def test_object_without_cmd_attribute_raises(self) -> None:
        with pytest.raises(ValueError, match="missing a `cmd` discriminator"):
            assert_balanced([object()])


# The "no production callers" guard from Step 1 has been removed: Step 2b
# (core/compiler.py) is the first production caller of render_ir, which is
# the moment the guard told future authors to retire it.
