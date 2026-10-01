"""The compiler enforces AI-asset provenance and records it in the IR (#144).

``embedded_ai_assets(card)`` walks every image element; an AI asset (marked,
or legacy with a sibling sidecar) must have an intact sidecar and may not
sit in a photo slot (rail 8). ``compile_card`` then adds exactly one
``SetMetadata(key="ai_imagery")`` after the card metadata, and none at all
for a card without AI assets, so shipped snapshots stay byte-identical.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ai_fixtures import bake_fake_ai_asset
from holiday_card.core.ai_provenance import AIProvenanceError, sidecar_path_for
from holiday_card.core.compiler import CompileContext, compile_card, embedded_ai_assets
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import Card, FoldType, ImageElement, Panel, PanelPosition
from holiday_card.core.render_ir import AI_IMAGERY_METADATA_KEY, BeginGroup, SetMetadata
from holiday_card.core.templates import discover_templates

_NO_IMPOSE = CompileContext(impose=False)
_SMALL = (64, 96)


def _element(path: Path, element_id: str = "art", slot: str | None = None) -> ImageElement:
    return ImageElement(
        id=element_id, source_path=str(path), slot=slot,
        x=0.5, y=0.5, width=1.0, height=1.5,
    )


def _card(*panels: tuple[PanelPosition, list[ImageElement]]) -> Card:
    return Card(
        name="t", template_id="t", fold_type=FoldType.QUARTER_FOLD, theme_id="christmas-gold",
        panels=[
            Panel(position=pos, width=4.25, height=5.5, image_elements=elements)
            for pos, elements in panels
        ],
    )


def _ai_metadata(commands: list) -> list[SetMetadata]:  # type: ignore[type-arg]
    return [
        c for c in commands
        if isinstance(c, SetMetadata) and c.key == AI_IMAGERY_METADATA_KEY
    ]


def test_metadata_key_is_ai_imagery() -> None:
    assert AI_IMAGERY_METADATA_KEY == "ai_imagery"


def test_ai_asset_with_its_sidecar_compiles_and_is_recorded(tmp_path: Path) -> None:
    asset = bake_fake_ai_asset(tmp_path, size=_SMALL)
    commands = compile_card(_card((PanelPosition.FRONT, [_element(asset)])), _NO_IMPOSE)

    assert _ai_metadata(commands) == [
        SetMetadata(key=AI_IMAGERY_METADATA_KEY, value="gpt-image-2")
    ]
    keys = [c.key for c in commands if isinstance(c, SetMetadata)]
    assert keys == ["template_id", "fold_type", "theme_id", "ai_imagery"]
    ai_at = commands.index(_ai_metadata(commands)[0])
    first_group = next(i for i, c in enumerate(commands) if isinstance(c, BeginGroup))
    assert ai_at < first_group


def test_labels_are_sorted_and_deduplicated(tmp_path: Path) -> None:
    b = bake_fake_ai_asset(tmp_path, "b.png", model="b-model", size=_SMALL)
    a = bake_fake_ai_asset(tmp_path, "a.png", model="a-model", size=_SMALL)
    a2 = bake_fake_ai_asset(tmp_path, "a2.png", model="a-model", size=_SMALL)
    card = _card(
        (PanelPosition.FRONT, [_element(b, "b"), _element(a, "a")]),
        (PanelPosition.BACK, [_element(a2, "a2")]),
    )
    [meta] = _ai_metadata(compile_card(card, _NO_IMPOSE))
    assert meta.value == "a-model; b-model"


def test_missing_sidecar_is_refused_naming_the_element(tmp_path: Path) -> None:
    asset = bake_fake_ai_asset(tmp_path, size=_SMALL)
    sidecar_path_for(asset).unlink()
    with pytest.raises(AIProvenanceError) as exc:
        compile_card(_card((PanelPosition.FRONT, [_element(asset)])), _NO_IMPOSE)
    msg = str(exc.value)
    assert "t/front/image_elements[0]" in msg
    assert "'art'" in msg
    assert "art.license.yaml" in msg


def test_ai_asset_in_a_photo_slot_is_refused(tmp_path: Path) -> None:
    asset = bake_fake_ai_asset(tmp_path, size=_SMALL)
    with pytest.raises(AIProvenanceError, match="rail 8"):
        compile_card(
            _card((PanelPosition.FRONT, [_element(asset, slot="photo")])), _NO_IMPOSE,
        )


def test_legacy_asset_in_a_photo_slot_is_refused(tmp_path: Path) -> None:
    asset = bake_fake_ai_asset(tmp_path, size=_SMALL)
    legacy = tmp_path / "legacy.png"
    Image.open(asset).convert("RGB").save(legacy, "PNG")  # re-save drops the marker
    sidecar_path_for(asset).rename(sidecar_path_for(legacy))
    with pytest.raises(AIProvenanceError, match="rail 8"):
        compile_card(
            _card((PanelPosition.FRONT, [_element(legacy, slot="photo")])), _NO_IMPOSE,
        )


def test_embedded_ai_assets_lists_uses_in_panel_then_element_order(tmp_path: Path) -> None:
    a = bake_fake_ai_asset(tmp_path, "a.png", size=_SMALL)
    b = bake_fake_ai_asset(tmp_path, "b.png", size=_SMALL)
    c = bake_fake_ai_asset(tmp_path, "c.png", size=_SMALL)
    plain = tmp_path / "plain.png"
    Image.new("RGB", (8, 8)).save(plain, "PNG")
    card = _card(
        (PanelPosition.FRONT, [_element(b, "b"), _element(plain, "plain"), _element(a, "a")]),
        (PanelPosition.BACK, [_element(c, "c")]),
    )
    uses = embedded_ai_assets(card)
    assert [u.path for u in uses] == [b, a, c]
    assert all(u.path.is_absolute() for u in uses)
    assert [u.where for u in uses] == [
        "t/front/image_elements[0] (id 'b')",
        "t/front/image_elements[2] (id 'a')",
        "t/back/image_elements[0] (id 'c')",
    ]
    assert {u.record.model for u in uses} == {"gpt-image-2"}


def test_card_without_ai_assets_gets_no_ai_metadata(tmp_path: Path) -> None:
    plain = tmp_path / "plain.png"
    Image.new("RGB", (8, 8)).save(plain, "PNG")
    commands = compile_card(_card((PanelPosition.FRONT, [_element(plain)])), _NO_IMPOSE)
    assert _ai_metadata(commands) == []


@pytest.mark.parametrize("template_id", sorted(t["id"] for t in discover_templates()))
def test_shipped_templates_embed_no_ai_imagery(template_id: str) -> None:
    card = CardGenerator().create_card(template_id)
    assert _ai_metadata(compile_card(card)) == []
