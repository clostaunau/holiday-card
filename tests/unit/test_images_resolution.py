"""Effective print resolution of placed images (#66, D4 / D8).

PPI is computed from the final IR, so any scale the compiler adds (e.g. the
moo-a6 fill group from #73) is counted.
"""

from __future__ import annotations

import pytest

from holiday_card.core.images import (
    MIN_PRINT_PPI,
    RECOMMENDED_PRINT_PPI,
    ResolutionFinding,
    check_print_resolution,
    effective_ppi,
)
from holiday_card.core.render_ir import (
    BeginGroup,
    DrawImage,
    EndGroup,
    ImageRef,
    RectGeom,
    RenderCommand,
    Transform,
)
from holiday_card.utils.measurements import MIN_DPI


def _ref(
    w_px: int, h_px: int, w_in: float, h_in: float, *,
    preserve_aspect: bool = True, source: str = "me.jpg",
) -> ImageRef:
    return ImageRef(
        source=source,
        rect=RectGeom(x=10, y=20, width=w_in * 72, height=h_in * 72),
        format="jpeg",
        width_px=w_px,
        height_px=h_px,
        preserve_aspect=preserve_aspect,
    )


class TestConstants:
    def test_thresholds(self) -> None:
        assert RECOMMENDED_PRINT_PPI == 300
        assert MIN_PRINT_PPI == 150

    def test_min_dpi_is_the_same_value(self) -> None:
        assert MIN_DPI == MIN_PRINT_PPI


class TestEffectivePpi:
    def test_400px_in_3_2_inch_square_is_125(self) -> None:
        assert effective_ppi(_ref(400, 400, 3.2, 3.2)) == pytest.approx(125.0)

    def test_960px_in_3_2_inch_square_is_300(self) -> None:
        assert effective_ppi(_ref(960, 960, 3.2, 3.2)) == pytest.approx(300.0)

    def test_meet_uses_the_larger_axis_ppi(self) -> None:
        # 1200x600 fitted into 2"x2": 2" wide by 1" tall -> 600 PPI.
        assert effective_ppi(_ref(1200, 600, 2, 2)) == pytest.approx(600.0)

    def test_stretch_uses_the_smaller_axis_ppi(self) -> None:
        ref = _ref(1200, 600, 2, 2, preserve_aspect=False)
        assert effective_ppi(ref) == pytest.approx(300.0)

    def test_group_scale_divides_ppi(self) -> None:
        assert effective_ppi(_ref(960, 960, 3.2, 3.2), 2.0) == pytest.approx(150.0)


def _draw(ref: ImageRef) -> DrawImage:
    return DrawImage(image=ref)


class TestCheckPrintResolution:
    def test_125_ppi_fails(self) -> None:
        findings = check_print_resolution([_draw(_ref(400, 400, 3.2, 3.2))])
        assert len(findings) == 1
        f = findings[0]
        assert f.level == "fail"
        assert f.source == "me.jpg"
        assert f.ppi == pytest.approx(125.0)

    def test_200_ppi_warns(self) -> None:
        findings = check_print_resolution([_draw(_ref(400, 400, 2, 2))])
        assert [f.level for f in findings] == ["warn"]
        assert findings[0].ppi == pytest.approx(200.0)

    def test_300_ppi_is_clean(self) -> None:
        assert check_print_resolution([_draw(_ref(600, 600, 2, 2))]) == []

    def test_finding_carries_pixels_needed_at_300_ppi(self) -> None:
        # 2.95" square at 300 PPI needs ceil(885) = 885 px per side.
        (f,) = check_print_resolution([_draw(_ref(700, 700, 2.95, 2.95))])
        assert (f.needed_width_px, f.needed_height_px) == (885, 885)

    def test_scaled_group_halves_the_ppi(self) -> None:
        commands: list[RenderCommand] = [
            BeginGroup(transform=Transform(scale_x=2, scale_y=2)),
            _draw(_ref(600, 600, 2, 2)),
            EndGroup(),
        ]
        (f,) = check_print_resolution(commands)
        assert f.ppi == pytest.approx(150.0)
        assert f.level == "warn"
        # The size needed is at the scaled (placed) size: 4" -> 1200 px.
        assert (f.needed_width_px, f.needed_height_px) == (1200, 1200)

    def test_nested_groups_multiply_and_pop(self) -> None:
        commands: list[RenderCommand] = [
            BeginGroup(transform=Transform(scale_x=2, scale_y=2)),
            BeginGroup(transform=Transform(scale_x=2, scale_y=2)),
            _draw(_ref(1200, 1200, 2, 2, source="inner.jpg")),  # 150 PPI
            EndGroup(),
            _draw(_ref(1200, 1200, 2, 2, source="outer.jpg")),  # 300 PPI
            EndGroup(),
            _draw(_ref(400, 400, 2, 2, source="top.jpg")),  # 200 PPI
        ]
        findings = check_print_resolution(commands)
        assert [(f.source, f.level) for f in findings] == [
            ("inner.jpg", "warn"), ("top.jpg", "warn"),
        ]

    def test_rotation_does_not_change_ppi(self) -> None:
        commands: list[RenderCommand] = [
            BeginGroup(transform=Transform(rotate_deg=37)),
            _draw(_ref(400, 400, 2, 2)),
            EndGroup(),
        ]
        (f,) = check_print_resolution(commands)
        assert f.ppi == pytest.approx(200.0)

    def test_anisotropic_scale_uses_geometric_mean(self) -> None:
        commands: list[RenderCommand] = [
            BeginGroup(transform=Transform(scale_x=4, scale_y=1)),
            _draw(_ref(1200, 1200, 2, 2)),  # 600 / sqrt(4) = 300
            EndGroup(),
        ]
        assert check_print_resolution(commands) == []

    def test_thresholds_are_parameters(self) -> None:
        findings = check_print_resolution(
            [_draw(_ref(400, 400, 2, 2))], warn_below=100, fail_below=50,
        )
        assert findings == []

    def test_finding_is_frozen(self) -> None:
        f = ResolutionFinding(
            source="a", ppi=1.0, level="fail", needed_width_px=1, needed_height_px=1,
        )
        with pytest.raises(AttributeError):
            f.ppi = 2.0  # type: ignore[misc]
