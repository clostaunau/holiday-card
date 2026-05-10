"""Unit tests for per-panel preparation and scaling helpers."""

from __future__ import annotations

import pytest

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
    prepare_scaled_panel,
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


class TestPrepareScaledPanel:
    """``prepare_scaled_panel`` scales every coordinate and font size to
    fit the target trim, with letterbox semantics on the off-axis."""

    def test_scale_factor_is_uniform_min(self) -> None:
        # 4.25x5.5 panel into 4.13x5.83 A6:
        # sx = 4.13/4.25 = 0.9718; sy = 5.83/5.5 = 1.06
        # uniform = min = 0.9718
        result = prepare_scaled_panel(
            _panel_with_content(), target_width_in=4.13, target_height_in=5.83,
        )
        # Width fills target (the constrained axis).
        assert result.width == pytest.approx(4.13, rel=1e-6)
        # Height is shorter than target (letterbox top + bottom).
        assert result.height == pytest.approx(5.5 * (4.13 / 4.25), rel=1e-6)

    def test_offset_centers_on_letterbox_axis(self) -> None:
        result = prepare_scaled_panel(
            _panel_with_content(), target_width_in=4.13, target_height_in=5.83,
        )
        # x=0 (no letterbox on width — fills the target).
        assert result.x == pytest.approx(0.0, abs=1e-9)
        # y centered: (5.83 - scaled_height) / 2.
        scaled_h = 5.5 * (4.13 / 4.25)
        assert result.y == pytest.approx((5.83 - scaled_h) / 2, rel=1e-6)

    def test_text_element_position_and_size_scaled(self) -> None:
        result = prepare_scaled_panel(
            _panel_with_content(), target_width_in=4.13, target_height_in=5.83,
        )
        scale = 4.13 / 4.25
        text = result.text_elements[0]
        assert text.x == pytest.approx(2.0 * scale, rel=1e-6)
        assert text.y == pytest.approx(3.0 * scale, rel=1e-6)
        assert text.width == pytest.approx(4.0 * scale, rel=1e-6)
        # Font size: round(24 * 0.9718) = 23
        assert text.font_size == 23
        assert text.min_font_size == max(6, round(12 * scale))

    def test_rectangle_shape_scaled(self) -> None:
        result = prepare_scaled_panel(
            _panel_with_content(), target_width_in=4.13, target_height_in=5.83,
        )
        scale = 4.13 / 4.25
        rect = result.shape_elements[0]
        assert isinstance(rect, Rectangle)
        assert rect.x == pytest.approx(0.5 * scale, rel=1e-6)
        assert rect.y == pytest.approx(0.5 * scale, rel=1e-6)
        assert rect.width == pytest.approx(2.0 * scale, rel=1e-6)
        assert rect.height == pytest.approx(1.0 * scale, rel=1e-6)

    def test_circle_shape_scaled(self) -> None:
        result = prepare_scaled_panel(
            _panel_with_content(), target_width_in=4.13, target_height_in=5.83,
        )
        scale = 4.13 / 4.25
        circle = result.shape_elements[1]
        assert isinstance(circle, Circle)
        assert circle.center_x == pytest.approx(3.0 * scale, rel=1e-6)
        assert circle.center_y == pytest.approx(4.0 * scale, rel=1e-6)
        assert circle.radius == pytest.approx(0.75 * scale, rel=1e-6)

    def test_rotation_is_dropped(self) -> None:
        # Even though source panel had rotation=180 (imposition), the
        # scaled per-panel output never folds.
        result = prepare_scaled_panel(
            _panel_with_content(), target_width_in=4.13, target_height_in=5.83,
        )
        assert result.rotation == 0.0


class TestBuildPerPanelCard:
    """``build_per_panel_card`` dispatches on ``target.scale_panels_to_fit``."""

    def test_per_panel_pdf_uses_native_dims(self) -> None:
        panel = _panel_with_content()
        card = _card_for(panel)
        target = get_target("per-panel-pdf")
        result = build_per_panel_card(card, panel, target)
        out_panel = result.panels[0]
        assert out_panel.x == 0.0 and out_panel.y == 0.0
        assert out_panel.width == 4.25 and out_panel.height == 5.5
        assert out_panel.rotation == 0.0

    def test_moo_a6_scales_into_a6(self) -> None:
        panel = _panel_with_content()
        card = _card_for(panel)
        target = get_target("moo-a6")
        result = build_per_panel_card(card, panel, target)
        out_panel = result.panels[0]
        # Width fills A6 (the constrained axis).
        assert out_panel.width == pytest.approx(4.13, rel=1e-6)


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
