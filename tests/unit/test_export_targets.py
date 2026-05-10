"""Unit tests for the ExportTarget registry."""

from __future__ import annotations

import pytest

from holiday_card.core.export_targets import (
    REGISTRY,
    ExportTargetNotFoundError,
    get_target,
)


class TestRegistry:
    def test_letter_is_registered(self) -> None:
        target = get_target("letter")
        assert target.name == "letter"
        assert target.layout == "imposition"
        assert target.geometry is not None

    def test_per_panel_pdf_is_registered_and_native_dim(self) -> None:
        target = get_target("per-panel-pdf")
        assert target.layout == "per-panel"
        # Native-dim per-panel: no fixed geometry; uses the panel's own dims.
        assert target.geometry is None
        assert target.scale_panels_to_fit is False

    def test_moo_a6_is_registered_with_a6_geometry(self) -> None:
        target = get_target("moo-a6")
        assert target.layout == "per-panel"
        assert target.scale_panels_to_fit is True
        assert target.geometry is not None
        # A6 trim is approximately 4.13" x 5.83"
        assert target.geometry.trim_width_in == 4.13
        assert target.geometry.trim_height_in == 5.83
        # Bleed is 0.125" (industry standard)
        assert target.geometry.bleed_in == 0.125

    def test_unknown_target_raises_with_helpful_list(self) -> None:
        with pytest.raises(ExportTargetNotFoundError, match="unknown export target"):
            get_target("not-a-real-target")
        # Error message should list the registered targets so the caller
        # can recover.
        try:
            get_target("not-a-real-target")
        except ExportTargetNotFoundError as e:
            for name in REGISTRY:
                assert name in str(e)

    def test_default_bleed_is_industry_standard(self) -> None:
        # Both per-panel-pdf and letter target should default to 0.125".
        assert get_target("per-panel-pdf").bleed_in == 0.125
        assert get_target("letter").bleed_in == 0.125

    def test_target_is_frozen_dataclass(self) -> None:
        # Targets are immutable so accidental mutation can't change the
        # global registry's behavior at runtime.
        from dataclasses import FrozenInstanceError
        target = get_target("letter")
        with pytest.raises(FrozenInstanceError):
            target.name = "tampered"  # type: ignore[misc]
