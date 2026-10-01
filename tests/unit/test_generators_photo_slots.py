"""Tests for ``fill_photo_slots`` (issue #65): ``-i/--image`` fills template slots.

The k-th photo replaces ``source_path`` on every image element whose ``slot``
is the k-th slot name (``photo``, ``photo-2``, ...). Geometry, clip and z-order
stay the template's; unfilled slots keep the placeholder. Too many photos, or
any photo on a template without slots, raises ``PhotoSlotError`` (D4).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from holiday_card.core.generators import PhotoSlotError, fill_photo_slots
from holiday_card.core.images import ImageSourceError
from holiday_card.core.models import (
    Card,
    CircleClipMask,
    FoldType,
    ImageElement,
    Panel,
    PanelPosition,
)

PLACEHOLDER = "/templates/placeholder-photo.jpg"


def _img(slot: str | None, **kw: float) -> ImageElement:
    return ImageElement(
        source_path=PLACEHOLDER, slot=slot, x=kw.get("x", 0.5), y=0.5,
        width=1.0, height=1.0, z_index=int(kw.get("z", 100)),
        clip_mask=CircleClipMask(center_x=0.5, center_y=0.5, radius=0.5),
    )


def _card(*elements: ImageElement, template_id: str = "christmas-test") -> Card:
    return Card(
        name="slots",
        template_id=template_id,
        fold_type=FoldType.HALF_FOLD,
        panels=[
            Panel(
                position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5,
                image_elements=list(elements[:2]),
            ),
            Panel(
                position=PanelPosition.INSIDE_RIGHT, x=4.25, y=0, width=4.25,
                height=5.5, image_elements=list(elements[2:]),
            ),
        ],
    )


def _sources(card: Card) -> list[str]:
    return [e.source_path for p in card.panels for e in p.image_elements]


@pytest.fixture
def red_jpg(tmp_path: Path) -> Path:
    path = tmp_path / "red.jpg"
    Image.new("RGB", (40, 40), "red").save(path)
    return path


@pytest.fixture
def blue_png(tmp_path: Path) -> Path:
    path = tmp_path / "blue.png"
    Image.new("RGB", (40, 40), "blue").save(path)
    return path


class TestSlotField:
    @pytest.mark.parametrize("slot", ["photo", "photo-2", "photo-9"])
    def test_accepts_slot_names(self, slot: str) -> None:
        assert _img(slot).slot == slot

    @pytest.mark.parametrize("slot", ["photo-1", "photo-10", "Photo", "cover", ""])
    def test_rejects_other_names(self, slot: str) -> None:
        with pytest.raises(ValidationError):
            _img(slot)

    def test_defaults_to_none(self) -> None:
        assert _img(None).slot is None


class TestFillPhotoSlots:
    def test_first_photo_fills_every_element_in_photo_slot(self, red_jpg: Path) -> None:
        card = _card(_img("photo"), _img(None), _img("photo"), _img("photo-2"))
        fill_photo_slots(card, [red_jpg])
        assert _sources(card) == [
            str(red_jpg.resolve()), PLACEHOLDER, str(red_jpg.resolve()), PLACEHOLDER,
        ]

    def test_kth_photo_fills_kth_slot(self, red_jpg: Path, blue_png: Path) -> None:
        card = _card(_img("photo-2"), _img("photo"))
        fill_photo_slots(card, [red_jpg, blue_png])
        assert _sources(card) == [str(blue_png.resolve()), str(red_jpg.resolve())]

    def test_keeps_geometry_clip_and_z_order(self, red_jpg: Path) -> None:
        card = _card(_img("photo", x=1.25, z=7))
        before = card.panels[0].image_elements[0].model_dump(exclude={"source_path"})
        fill_photo_slots(card, [red_jpg])
        after = card.panels[0].image_elements[0].model_dump(exclude={"source_path"})
        assert after == before

    def test_no_photos_is_a_no_op(self) -> None:
        card = _card(_img("photo"))
        fill_photo_slots(card, [])
        assert _sources(card) == [PLACEHOLDER]

    def test_more_photos_than_slots_raises(self, red_jpg: Path, blue_png: Path) -> None:
        card = _card(_img("photo"), _img("photo"), template_id="christmas-family-photo")
        with pytest.raises(PhotoSlotError) as exc:
            fill_photo_slots(card, [red_jpg, blue_png])
        assert str(exc.value) == (
            "christmas-family-photo has 1 photo slot(s); got 2 --image values"
        )
        assert _sources(card) == [PLACEHOLDER, PLACEHOLDER]

    def test_template_without_slots_raises(self, red_jpg: Path) -> None:
        card = _card(_img(None), template_id="christmas-classic")
        with pytest.raises(PhotoSlotError, match="christmas-classic has no photo slot"):
            fill_photo_slots(card, [red_jpg])

    def test_photo_slot_error_is_a_value_error(self) -> None:
        assert issubclass(PhotoSlotError, ValueError)

    def test_non_image_content_raises_image_source_error(self, tmp_path: Path) -> None:
        fake = tmp_path / "notes.jpg"
        fake.write_text("not a photo")
        card = _card(_img("photo"))
        with pytest.raises(ImageSourceError):
            fill_photo_slots(card, [fake])
        assert _sources(card) == [PLACEHOLDER]

    def test_missing_file_raises_image_source_error(self, tmp_path: Path) -> None:
        card = _card(_img("photo"))
        with pytest.raises(ImageSourceError, match="not found"):
            fill_photo_slots(card, [tmp_path / "missing.jpg"])


class TestAIAssetRefused:
    """#144, rail 8: an AI asset never replaces a photo, and nothing changes."""

    def _card(self) -> Card:
        return _card(_img("photo"), _img("photo-2"))

    def test_marked_ai_asset_is_refused(self, tmp_path: Path) -> None:
        from ai_fixtures import bake_fake_ai_asset
        from holiday_card.core.ai_provenance import AIProvenanceError

        card = self._card()
        before = card.model_copy(deep=True)
        asset = bake_fake_ai_asset(tmp_path, size=(64, 96))
        with pytest.raises(AIProvenanceError) as exc:
            fill_photo_slots(card, [asset])
        msg = str(exc.value)
        assert "rail 8" in msg
        assert "model gpt-image-2" in msg
        assert card == before

    def test_legacy_sidecar_only_asset_is_refused(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import (
            AIProvenanceError,
            LicenseRecord,
            write_sidecar,
        )

        legacy = tmp_path / "legacy.png"
        Image.new("RGB", (40, 40), "green").save(legacy)
        write_sidecar(legacy, LicenseRecord(prompt="p", model="gpt-image-1", timestamp="t"))
        card = self._card()
        before = card.model_copy(deep=True)
        with pytest.raises(AIProvenanceError, match="rail 8"):
            fill_photo_slots(card, [legacy])
        assert card == before

    def test_marked_asset_without_its_sidecar_says_model_unknown(self, tmp_path: Path) -> None:
        from ai_fixtures import bake_fake_ai_asset
        from holiday_card.core.ai_provenance import AIProvenanceError, sidecar_path_for

        asset = bake_fake_ai_asset(tmp_path, size=(64, 96))
        sidecar_path_for(asset).unlink()
        with pytest.raises(AIProvenanceError, match="model unknown"):
            fill_photo_slots(self._card(), [asset])

    def test_ai_asset_as_second_photo_leaves_the_first_unapplied(
        self, tmp_path: Path, red_jpg: Path,
    ) -> None:
        from ai_fixtures import bake_fake_ai_asset
        from holiday_card.core.ai_provenance import AIProvenanceError

        card = self._card()
        before = card.model_copy(deep=True)
        asset = bake_fake_ai_asset(tmp_path, size=(64, 96))
        with pytest.raises(AIProvenanceError):
            fill_photo_slots(card, [red_jpg, asset])
        assert card == before
        assert _sources(card) == [PLACEHOLDER, PLACEHOLDER]
