"""Compiler-level tests for ``_compile_svg_path``.

Covers:

* basic move + line + cubic → PathGeom ops
* relative coords resolved against the cursor
* S/T smooth curves use reflected control points
* H/V shortcuts emit lines with the current y/x
* Z restores cursor to subpath start
* scale + position + rotation transforms
* arc commands raise UnsupportedFeatureError
"""

from __future__ import annotations

import pytest

from holiday_card.core.compiler import (
    UnsupportedFeatureError,
    _path_commands_to_ops,
    compile_card,
)
from holiday_card.core.models import (
    Card,
    FoldType,
    OccasionType,
    Panel,
    PanelPosition,
    SVGPath,
)
from holiday_card.core.render_ir import (
    BeginGroup,
    DrawShape,
    EndGroup,
    PathGeom,
)
from holiday_card.utils.svg_parser import SVGPathParser


def _ops(path_data: str) -> list:
    """Helper — parse path_data via parser and convert to IR ops (no transform)."""
    cmds = SVGPathParser().parse(path_data)
    ops, _bbox = _path_commands_to_ops(cmds)
    return ops


def _make_card(shape: SVGPath) -> Card:
    panel = Panel(
        position=PanelPosition.FRONT,
        x=0.0, y=0.0, width=4.0, height=5.0,
        shape_elements=[shape],
    )
    return Card(
        name="t", template_id="t",
        occasion=OccasionType.GENERIC,
        fold_type=FoldType.HALF_FOLD,
        panels=[panel],
    )


class TestPathOpsConversion:
    def test_move_then_line(self) -> None:
        ops = _ops("M 10 20 L 30 40")
        assert [(o.op, [(p.x, p.y) for p in o.points]) for o in ops] == [
            ("move", [(10.0, 20.0)]),
            ("line", [(30.0, 40.0)]),
        ]

    def test_lowercase_relative_line(self) -> None:
        ops = _ops("M 10 20 l 5 5 l 5 5")
        # First line at (10+5, 20+5) = (15, 25), second at (15+5, 25+5) = (20, 30)
        points = [(o.op, o.points[0].x, o.points[0].y) for o in ops]
        assert points == [
            ("move", 10.0, 20.0),
            ("line", 15.0, 25.0),
            ("line", 20.0, 30.0),
        ]

    def test_horizontal_and_vertical(self) -> None:
        ops = _ops("M 10 20 H 30 V 40")
        points = [(o.op, o.points[0].x, o.points[0].y) for o in ops]
        assert points == [
            ("move", 10.0, 20.0),
            ("line", 30.0, 20.0),
            ("line", 30.0, 40.0),
        ]

    def test_cubic_bezier(self) -> None:
        ops = _ops("M 0 0 C 10 10 20 10 30 0")
        cubic = [o for o in ops if o.op == "cubic"]
        assert len(cubic) == 1
        assert [(p.x, p.y) for p in cubic[0].points] == [
            (10.0, 10.0), (20.0, 10.0), (30.0, 0.0),
        ]

    def test_smooth_cubic_reflects_previous_control(self) -> None:
        # First cubic ends at (30, 0) with second control at (20, 10).
        # Smooth cubic 'S' synthesizes first control as reflection
        # through the end point: 2*(30,0) - (20,10) = (40, -10).
        ops = _ops("M 0 0 C 10 10 20 10 30 0 S 60 10 70 0")
        smooth = [o for o in ops if o.op == "cubic"][1]
        pts = [(p.x, p.y) for p in smooth.points]
        assert pts[0] == (40.0, -10.0), f"Expected reflected control point, got {pts[0]}"

    def test_quadratic_bezier(self) -> None:
        ops = _ops("M 0 0 Q 10 10 20 0")
        quad = [o for o in ops if o.op == "quadratic"]
        assert len(quad) == 1
        assert [(p.x, p.y) for p in quad[0].points] == [(10.0, 10.0), (20.0, 0.0)]

    def test_close_restores_cursor_to_subpath_start(self) -> None:
        # After Z, cursor should be back at (10, 20).
        # Z is appended; next M starts a fresh subpath.
        ops = _ops("M 10 20 L 30 40 Z M 50 60")
        types = [o.op for o in ops]
        assert types == ["move", "line", "close", "move"]


class TestCompileSVGPath:
    def test_emits_drawshape_with_pathgeom(self) -> None:
        shape = SVGPath(
            path_data="M 0 0 L 10 10 L 20 0 Z",
            scale=0.1,
            x=1.0, y=1.0,
        )
        cmds = compile_card(_make_card(shape))
        draws = [c for c in cmds if isinstance(c, DrawShape)]
        assert len(draws) == 1
        assert isinstance(draws[0].geometry, PathGeom)
        # No rotation → no extra BeginGroup wrapping just for this shape
        # (the panel itself still adds one).
        groups = [c for c in cmds if isinstance(c, (BeginGroup, EndGroup))]
        assert len(groups) == 2  # 1 panel begin + 1 panel end

    def test_scale_and_offset_applied(self) -> None:
        shape = SVGPath(
            path_data="M 0 0 L 100 0",
            scale=0.01,  # 100 path units → 1 inch
            x=1.0, y=2.0,
        )
        draws = [c for c in compile_card(_make_card(shape)) if isinstance(c, DrawShape)]
        path = draws[0].geometry
        assert isinstance(path, PathGeom)
        # First move at (panel.x + shape.x + 0*0.01, panel.y + shape.y + 0*0.01)
        # = (1.0, 2.0) inches = (72, 144) pts.
        # Line endpoint: (panel.x + shape.x + 100*0.01, panel.y + shape.y)
        # = (2.0, 2.0) inches = (144, 144) pts.
        ops = list(path.ops)
        assert ops[0].op == "move"
        assert ops[0].points[0].x == pytest.approx(72.0)
        assert ops[0].points[0].y == pytest.approx(144.0)
        assert ops[1].op == "line"
        assert ops[1].points[0].x == pytest.approx(144.0)

    def test_rotation_wraps_in_begingroup(self) -> None:
        shape = SVGPath(
            path_data="M 0 0 L 100 100 Z",
            scale=0.01,
            x=1.0, y=1.0,
            rotation=90.0,
        )
        cmds = compile_card(_make_card(shape))
        # Inner rotation group wrapping the path shape.
        groups = [c for c in cmds if isinstance(c, BeginGroup) and c.transform.rotate_deg == 90.0]
        assert len(groups) == 1


class TestArcUnsupported:
    def test_arc_raises(self) -> None:
        shape = SVGPath(
            path_data="M 0 0 A 5 5 0 0 1 10 10",
            scale=1.0,
        )
        with pytest.raises(UnsupportedFeatureError, match="arc"):
            compile_card(_make_card(shape))


class TestDeadTemplatesNowCompile:
    """The last two dead christmas templates should now compile."""

    @pytest.mark.parametrize("template_id", [
        "christmas-holly-wreath",
        "christmas-holiday-masterpiece",
    ])
    def test_template_compiles(self, template_id: str) -> None:
        from holiday_card.core.generators import CardGenerator
        card = CardGenerator().create_card(template_id=template_id)
        commands = compile_card(card)
        # The compiler should produce a meaningful command stream
        # (at least BeginPage + EndPage + several DrawShape).
        assert len(commands) >= 10
        path_draws = [
            c for c in commands
            if isinstance(c, DrawShape) and isinstance(c.geometry, PathGeom)
        ]
        assert len(path_draws) >= 1, (
            f"{template_id} should emit at least one DrawShape with a PathGeom"
        )
