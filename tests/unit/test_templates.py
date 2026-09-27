"""Shipped-template invariants for photo slots and the placeholder photo (#65)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.data_paths import data_path
from holiday_card.core.templates import (
    discover_templates,
    load_template,
    templates_with_photo_slots,
)

_PHOTO_TEMPLATES = sorted(
    t["id"] for t in discover_templates()
    if any(p.image_elements for p in load_template(t["id"]).panels)
)


def test_the_five_photo_templates_are_discovered() -> None:
    assert _PHOTO_TEMPLATES == [
        "birthday-photo",
        "christmas-family-photo",
        "christmas-holiday-masterpiece",
        "christmas-photo-ornament",
        "mothers-day-photo",
    ]


@pytest.mark.parametrize("template_id", _PHOTO_TEMPLATES)
def test_photo_template_has_front_photo_slot(template_id: str) -> None:
    template = load_template(template_id)
    front = [p for p in template.panels if p.position.value == "front"]
    assert any(e.slot == "photo" for p in front for e in p.image_elements)


@pytest.mark.parametrize("template_id", _PHOTO_TEMPLATES)
def test_photo_slots_are_contiguous(template_id: str) -> None:
    slots = {
        e.slot for p in load_template(template_id).panels
        for e in p.image_elements if e.slot is not None
    }
    expected = {"photo"} | {f"photo-{k}" for k in range(2, len(slots) + 1)}
    assert slots == expected


@pytest.mark.parametrize("template_id", _PHOTO_TEMPLATES)
def test_photo_template_uses_the_placeholder(template_id: str) -> None:
    for panel in load_template(template_id).panels:
        for element in panel.image_elements:
            assert Path(element.source_path).name == "placeholder-photo.jpg"


def test_templates_with_photo_slots_lists_the_photo_templates() -> None:
    assert templates_with_photo_slots() == _PHOTO_TEMPLATES


def _placeholders() -> list[Path]:
    return sorted(data_path("templates").rglob("placeholder-photo.jpg"))


def test_every_placeholder_copy_is_byte_identical() -> None:
    copies = _placeholders()
    assert len(copies) == 3
    digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in copies}
    assert len(digests) == 1


def test_placeholder_is_at_least_300_ppi_at_the_largest_slot() -> None:
    with Image.open(_placeholders()[0]) as img:
        assert img.format == "JPEG"
        assert min(img.size) >= 1200


def test_old_400px_sample_photo_is_gone() -> None:
    assert list(data_path("templates").rglob("sample_photo.jpg")) == []
