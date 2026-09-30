"""``ImageElement.fit``: contain vs cover (#98).

A cover-fit image is scaled to fill its rect and cropped by a clip to that
rect, so a clip larger than the photo's contain box (mothers-day-photo's
2.6×3.4" ellipse over a square photo) is filled edge to edge. The compiler
lowers cover to a grown ``DrawImage`` rect inside a ``BeginClip`` of the
element rect, so no backend needs to crop. Slotted elements default to
cover; others default to contain.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from holiday_card.core.compiler import CompileContext, compile_card
from holiday_card.core.images import effective_ppi
from holiday_card.core.models import (
    Card,
    EllipseClipMask,
    FoldType,
    ImageElement,
    Panel,
    PanelPosition,
)
from holiday_card.core.render_ir import BeginClip, DrawImage, EndClip, RectGeom

_NO_IMPOSE = CompileContext(impose=False)


@pytest.fixture
def square_jpg(tmp_path: Path) -> Path:
    path = tmp_path / "square.jpg"
    Image.new("RGB", (400, 400), (200, 30, 30)).save(path)
    return path


@pytest.fixture
def wide_jpg(tmp_path: Path) -> Path:
    path = tmp_path / "wide.jpg"
    Image.new("RGB", (800, 400), (30, 30, 200)).save(path)
    return path


def _compile(image: ImageElement) -> list:
    panel = Panel(
        position=PanelPosition.FRONT, width=4.0, height=6.0,
        image_elements=[image],
    )
    card = Card(
        name="t", template_id="t", fold_type=FoldType.HALF_FOLD, panels=[panel],
    )
    return [
        c for c in compile_card(card, _NO_IMPOSE)
        if isinstance(c, (BeginClip, EndClip, DrawImage))
    ]


def _element(path: Path, **kw: object) -> ImageElement:
    fields: dict[str, object] = {
        "source_path": str(path), "x": 1.0, "y": 1.0, "width": 2.6, "height": 3.4,
    }
    fields.update(kw)
    return ImageElement(**fields)  # type: ignore[arg-type]


class TestFitModel:
    def test_unslotted_element_defaults_to_contain(self, square_jpg: Path) -> None:
        assert _element(square_jpg).resolved_fit == "contain"

    def test_slotted_element_defaults_to_cover(self, square_jpg: Path) -> None:
        assert _element(square_jpg, slot="photo").resolved_fit == "cover"

    def test_explicit_fit_wins_over_the_slot_default(self, square_jpg: Path) -> None:
        el = _element(square_jpg, slot="photo", fit="contain")
        assert el.resolved_fit == "contain"

    def test_stretch_element_resolves_to_stretch(self, square_jpg: Path) -> None:
        el = _element(square_jpg, slot="photo", preserve_aspect=False)
        assert el.resolved_fit == "stretch"

    def test_fit_with_preserve_aspect_false_is_refused(self, square_jpg: Path) -> None:
        with pytest.raises(ValidationError, match="preserve_aspect"):
            _element(square_jpg, fit="cover", preserve_aspect=False)

    def test_unknown_fit_is_refused(self, square_jpg: Path) -> None:
        with pytest.raises(ValidationError):
            _element(square_jpg, fit="fill")


class TestCoverLowering:
    def test_cover_grows_the_rect_to_the_photo_aspect_and_clips_to_the_slot(
        self, square_jpg: Path
    ) -> None:
        cmds = _compile(_element(square_jpg, fit="cover"))
        assert [type(c) for c in cmds] == [BeginClip, DrawImage, EndClip]
        slot = RectGeom(x=72.0, y=72.0, width=2.6 * 72, height=3.4 * 72)
        assert cmds[0].geometry == slot
        rect = cmds[1].image.rect
        # Square photo over a 2.6×3.4" slot: 3.4" square, centred on the slot.
        assert rect.width == pytest.approx(3.4 * 72)
        assert rect.height == pytest.approx(3.4 * 72)
        assert rect.x + rect.width / 2 == pytest.approx(72 + 1.3 * 72)
        assert rect.y + rect.height / 2 == pytest.approx(72 + 1.7 * 72)

    def test_wide_photo_in_a_tall_slot_is_cropped_left_and_right(
        self, wide_jpg: Path
    ) -> None:
        cmds = _compile(_element(wide_jpg, fit="cover"))
        rect = cmds[1].image.rect
        assert rect.height == pytest.approx(3.4 * 72)
        assert rect.width == pytest.approx(6.8 * 72)

    def test_slot_clip_wraps_the_clip_mask(self, square_jpg: Path) -> None:
        mask = EllipseClipMask(center_x=2.3, center_y=2.7, radius_x=1.0, radius_y=1.7)
        cmds = _compile(_element(square_jpg, slot="photo", clip_mask=mask))
        assert [type(c) for c in cmds] == [
            BeginClip, BeginClip, DrawImage, EndClip, EndClip,
        ]
        assert isinstance(cmds[0].geometry, RectGeom)

    def test_cover_with_matching_aspect_emits_no_extra_clip(
        self, square_jpg: Path
    ) -> None:
        cmds = _compile(_element(square_jpg, fit="cover", width=2.0, height=2.0))
        assert [type(c) for c in cmds] == [DrawImage]
        assert cmds[0].image.rect == RectGeom(x=72.0, y=72.0, width=144.0, height=144.0)

    def test_contain_keeps_the_element_rect(self, square_jpg: Path) -> None:
        cmds = _compile(_element(square_jpg, fit="contain"))
        assert [type(c) for c in cmds] == [DrawImage]
        assert cmds[0].image.rect == RectGeom(
            x=72.0, y=72.0, width=2.6 * 72, height=3.4 * 72,
        )
        assert cmds[0].image.preserve_aspect is True

    def test_stretch_keeps_the_element_rect(self, square_jpg: Path) -> None:
        cmds = _compile(_element(square_jpg, slot="photo", preserve_aspect=False))
        assert [type(c) for c in cmds] == [DrawImage]
        assert cmds[0].image.preserve_aspect is False

    def test_cover_ppi_is_the_scaled_up_resolution(self, square_jpg: Path) -> None:
        # 400 px over 3.4" (cover), not over 2.6" (contain).
        cmds = _compile(_element(square_jpg, fit="cover"))
        assert effective_ppi(cmds[1].image) == pytest.approx(400 / 3.4)
