"""Unit tests for per-panel preparation helpers."""

from __future__ import annotations

from holiday_card.core.export_targets import get_target
from holiday_card.core.models import (
    Card,
    Circle,
    Color,
    FoldType,
    Panel,
    PanelPosition,
    Rectangle,
    ShapeType,
    TextElement,
)
from holiday_card.core.per_panel import (
    build_per_panel_card,
    build_per_panel_context,
    prepare_native_panel,
)


def _panel_with_content() -> Panel:
    """A 4.25x5.5 panel with one text element and one shape, both
    positioned in panel-local coords."""
    return Panel(
        position=PanelPosition.FRONT,
        x=4.25, y=0.0, width=4.25, height=5.5,
        rotation=180.0,  # imposition rotation we expect prepare_* to strip
        background_color=Color(r=1.0, g=0.0, b=0.0),
        text_elements=[
            TextElement(
                content="Hello",
                x=2.0, y=3.0, width=4.0,
                font_size=24, min_font_size=12,
            ),
        ],
        shape_elements=[
            Rectangle(
                type=ShapeType.RECTANGLE,
                x=0.5, y=0.5, width=2.0, height=1.0,
                fill_color="#00FF00",
            ),
            Circle(
                type=ShapeType.CIRCLE,
                center_x=3.0, center_y=4.0, radius=0.75,
                fill_color="#0000FF",
            ),
        ],
    )


def _card_for(panel: Panel) -> Card:
    return Card(
        name="t", template_id="t", fold_type=FoldType.HALF_FOLD, panels=[panel],
    )


class TestPrepareNativePanel:
    """``prepare_native_panel`` strips imposition position and rotation."""

    def test_position_is_zeroed(self) -> None:
        result = prepare_native_panel(_panel_with_content())
        assert result.x == 0.0
        assert result.y == 0.0

    def test_rotation_is_cleared(self) -> None:
        result = prepare_native_panel(_panel_with_content())
        assert result.rotation == 0.0

    def test_dimensions_are_preserved(self) -> None:
        result = prepare_native_panel(_panel_with_content())
        assert result.width == 4.25
        assert result.height == 5.5

    def test_content_is_preserved_unchanged(self) -> None:
        original = _panel_with_content()
        result = prepare_native_panel(original)
        # Text element coords and font sizes are panel-local, untouched.
        assert result.text_elements[0].x == original.text_elements[0].x
        assert result.text_elements[0].font_size == original.text_elements[0].font_size
        assert result.shape_elements[0] == original.shape_elements[0]


class TestBuildPerPanelCard:
    """``build_per_panel_card`` always keeps the panel's native dimensions:
    fitting to a fixed trim is one compiler-emitted scale group (#73), not
    a rewrite of the domain model."""

    def test_panel_is_placed_at_the_origin_with_native_content(self) -> None:
        panel = _panel_with_content()
        result = build_per_panel_card(_card_for(panel), panel)
        out_panel = result.panels[0]
        assert (out_panel.x, out_panel.y, out_panel.rotation) == (0.0, 0.0, 0.0)
        assert (out_panel.width, out_panel.height) == (4.25, 5.5)
        assert out_panel.text_elements == panel.text_elements
        assert out_panel.shape_elements == panel.shape_elements


class TestBuildPerPanelContext:
    """``build_per_panel_context`` produces the right ``CompileContext``."""

    def test_native_dim_target_uses_panel_geometry(self) -> None:
        panel = _panel_with_content()
        target = get_target("per-panel-pdf")
        ctx = build_per_panel_context(panel, target)
        assert ctx.geometry.trim_width_in == 4.25
        assert ctx.geometry.trim_height_in == 5.5
        assert ctx.geometry.bleed_in == 0.125
        # Per-panel mode: no fold-line emission.
        assert ctx.emit_fold_lines is False

    def test_scaled_target_uses_target_geometry(self) -> None:
        panel = _panel_with_content()
        target = get_target("moo-a6")
        ctx = build_per_panel_context(panel, target)
        assert ctx.geometry.trim_width_in == 4.13
        assert ctx.geometry.trim_height_in == 5.83
        assert ctx.geometry.bleed_in == 0.125
        assert ctx.emit_fold_lines is False
        assert ctx.impose is False
        assert ctx.panel_fit == "fill"

    def test_native_dim_target_passes_native_fit(self) -> None:
        ctx = build_per_panel_context(_panel_with_content(), get_target("per-panel-pdf"))
        assert ctx.panel_fit == "native"

    def test_letterbox_override_reaches_the_context(self) -> None:
        from dataclasses import replace

        target = replace(get_target("moo-a6"), panel_fit="letterbox")
        ctx = build_per_panel_context(_panel_with_content(), target)
        assert ctx.panel_fit == "letterbox"
