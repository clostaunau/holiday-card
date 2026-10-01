"""Panel ``background_image``: one cover-fit ``DrawImage`` under all panel content (#153).

The image covers exactly the rect the solid background uses (bleed-extended,
or the fitted bleed rect under ``panel_fit``), sits over ``background_color``
and under the border and every element whatever its ``z_index``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ai_fixtures import bake_fake_ai_asset
from holiday_card.core.ai_provenance import AIProvenanceError, sidecar_path_for
from holiday_card.core.compiler import CompileContext, compile_card, embedded_ai_assets
from holiday_card.core.images import ImageSourceError
from holiday_card.core.models import (
    Border,
    Card,
    Color,
    FoldType,
    Panel,
    PanelPosition,
    Rectangle,
)
from holiday_card.core.render_ir import (
    BeginClip,
    BeginGroup,
    DrawImage,
    DrawShape,
    EndClip,
    EndGroup,
    RectGeom,
    RenderCommand,
    SetMetadata,
)
from holiday_card.utils.measurements import PageGeometry

_RED = Color.from_hex("#FF0000")
_PANEL_W, _PANEL_H = 4.25, 5.5


def _png(path: Path, size: tuple[int, int], color: tuple[int, int, int] = (0, 90, 200)) -> Path:
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _panel(background_image: str | None, **kwargs: object) -> Panel:
    fields: dict[str, object] = {
        "id": "front-panel",
        "position": PanelPosition.FRONT,
        "x": 4.25,
        "y": 0.0,
        "width": _PANEL_W,
        "height": _PANEL_H,
        "background_image": background_image,
    }
    fields.update(kwargs)
    return Panel(**fields)  # type: ignore[arg-type]


def _card(*panels: Panel) -> Card:
    return Card(
        name="bg-fixture", template_id="bg-fixture",
        fold_type=FoldType.HALF_FOLD, panels=list(panels),
    )


def _rect_shape(z_index: int) -> Rectangle:
    return Rectangle(
        id="box", x=1.0, y=1.0, width=1.0, height=1.0, fill_color="#00FF00", z_index=z_index,
    )


_NO_IMPOSE = CompileContext(impose=False, emit_fold_lines=False)


def _panel_body(commands: list[RenderCommand]) -> list[RenderCommand]:
    """The commands between the panel's outer ``BeginGroup`` and its ``EndGroup``."""
    start = next(i for i, c in enumerate(commands) if isinstance(c, BeginGroup))
    end = max(i for i, c in enumerate(commands) if isinstance(c, EndGroup))
    return commands[start + 1:end]


def _background_colour_rect(commands: list[RenderCommand]) -> RectGeom:
    shape = next(c for c in _panel_body(commands) if isinstance(c, DrawShape))
    assert isinstance(shape.geometry, RectGeom)
    return shape.geometry


def _image_clip_rect(commands: list[RenderCommand]) -> RectGeom:
    body = _panel_body(commands)
    index = next(i for i, c in enumerate(body) if isinstance(c, DrawImage))
    before = body[index - 1]
    geometry = before.geometry if isinstance(before, BeginClip) else body[index].image.rect
    assert isinstance(geometry, RectGeom)
    return geometry


class TestOrder:
    def test_colour_then_image_then_border_then_elements(self, tmp_path: Path) -> None:
        image = _png(tmp_path / "bg.png", (1000, 1000))
        panel = _panel(
            str(image), background_color=_RED,
            border=Border(color=Color.from_hex("#000000"), width=2.0),
            shape_elements=[_rect_shape(z_index=-5)],
        )
        body = _panel_body(compile_card(_card(panel), _NO_IMPOSE))
        kinds = [type(c).__name__ for c in body]
        assert kinds == [
            "DrawShape",  # background_color
            "BeginClip", "DrawImage", "EndClip",  # cover-cropped background image
            "DrawShape",  # border
            "DrawShape",  # the z_index -5 element is still above the image
        ]
        border = body[4]
        assert isinstance(border, DrawShape) and border.fill is None

    def test_no_background_colour_puts_image_first(self, tmp_path: Path) -> None:
        image = _png(tmp_path / "bg.png", (1000, 1000))
        body = _panel_body(compile_card(_card(_panel(str(image))), _NO_IMPOSE))
        assert isinstance(body[0], BeginClip) and isinstance(body[1], DrawImage)


class TestRect:
    def test_letter_without_bleed_is_the_panel_rect(self, tmp_path: Path) -> None:
        image = _png(tmp_path / "bg.png", (1000, 1000))
        commands = compile_card(_card(_panel(str(image))), _NO_IMPOSE)
        assert _image_clip_rect(commands) == RectGeom(
            x=4.25 * 72, y=0.0, width=_PANEL_W * 72, height=_PANEL_H * 72,
        )

    def test_bleed_extended_like_the_background_colour(self, tmp_path: Path) -> None:
        image = _png(tmp_path / "bg.png", (1000, 1000))
        ctx = CompileContext(
            geometry=PageGeometry.us_letter(bleed_in=0.125), impose=False,
            emit_fold_lines=False,
        )
        commands = compile_card(_card(_panel(str(image), background_color=_RED)), ctx)
        rect = _image_clip_rect(commands)
        assert rect == _background_colour_rect(commands)
        assert rect.width == pytest.approx((_PANEL_W + 0.125) * 72)  # right + bottom edges

    def test_fitted_bleed_rect_under_moo_a6_fill(self, tmp_path: Path) -> None:
        image = _png(tmp_path / "bg.png", (1000, 1000))
        panel = _panel(str(image), background_color=_RED, x=0.0)
        ctx = CompileContext(
            geometry=PageGeometry.moo_a6(), impose=False, emit_fold_lines=False,
            panel_fit="fill",
        )
        commands = compile_card(_card(panel), ctx)
        rect = _image_clip_rect(commands)
        assert rect == _background_colour_rect(commands)
        assert rect.x < 0 and rect.y < 0  # extended on every edge under fill


class TestCover:
    def test_square_image_on_portrait_panel_overflows_vertically_centred(
        self, tmp_path: Path
    ) -> None:
        image = _png(tmp_path / "bg.png", (1000, 1000))
        commands = compile_card(_card(_panel(str(image))), _NO_IMPOSE)
        clip = _image_clip_rect(commands)
        draw = next(c for c in commands if isinstance(c, DrawImage))
        rect = draw.image.rect
        assert rect.height == pytest.approx(rect.width)
        assert rect.width == pytest.approx(clip.height)  # scaled to the taller side
        assert rect.width > clip.width
        assert rect.x + rect.width / 2 == pytest.approx(clip.x + clip.width / 2)
        assert rect.y + rect.height / 2 == pytest.approx(clip.y + clip.height / 2)
        assert draw.image.preserve_aspect is True
        assert draw.opacity == 1.0

    def test_matching_aspect_has_no_clip(self, tmp_path: Path) -> None:
        image = _png(tmp_path / "bg.png", (850, 1100))
        body = _panel_body(compile_card(_card(_panel(str(image))), _NO_IMPOSE))
        assert [type(c) for c in body] == [DrawImage]
        assert not any(isinstance(c, (BeginClip, EndClip)) for c in body)


class TestRefusals:
    def test_relative_path_names_field_and_panel(self) -> None:
        with pytest.raises(ImageSourceError) as exc:
            compile_card(_card(_panel("bg.png")), _NO_IMPOSE)
        assert "background_image" in str(exc.value)
        assert "front" in str(exc.value)

    def test_relative_path_has_no_cwd_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _png(tmp_path / "bg.png", (10, 10))
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ImageSourceError, match="background_image"):
            compile_card(_card(_panel("bg.png")), _NO_IMPOSE)

    def test_text_file_named_png(self, tmp_path: Path) -> None:
        fake = tmp_path / "bg.png"
        fake.write_text("not an image")
        with pytest.raises(ImageSourceError, match="background_image"):
            compile_card(_card(_panel(str(fake))), _NO_IMPOSE)

    def test_ai_asset_without_sidecar(self, tmp_path: Path) -> None:
        asset = bake_fake_ai_asset(tmp_path)
        sidecar_path_for(asset).unlink()
        with pytest.raises(AIProvenanceError) as exc:
            compile_card(_card(_panel(str(asset))), _NO_IMPOSE)
        assert "/front/background_image" in str(exc.value)


class TestProvenance:
    def test_background_ai_asset_is_recorded(self, tmp_path: Path) -> None:
        asset = bake_fake_ai_asset(tmp_path, model="gpt-image-2")
        card = _card(_panel(str(asset)))
        commands = compile_card(card, _NO_IMPOSE)
        metadata = {c.key: c.value for c in commands if isinstance(c, SetMetadata)}
        assert metadata["ai_imagery"] == "gpt-image-2"
        (use,) = embedded_ai_assets(card)
        assert use.where == "bg-fixture/front/background_image"
        assert use.path == asset.resolve()

    def test_hand_made_background_is_not_recorded(self, tmp_path: Path) -> None:
        image = _png(tmp_path / "bg.png", (10, 10))
        card = _card(_panel(str(image)))
        assert embedded_ai_assets(card) == []
        commands = compile_card(card, _NO_IMPOSE)
        assert not any(
            isinstance(c, SetMetadata) and c.key == "ai_imagery" for c in commands
        )


class TestSharedFitHelper:
    """The bake sizes against the compiler's own rect, so the two can't drift (#168)."""

    @pytest.mark.parametrize("fit", ["fill", "letterbox"])
    def test_helper_is_the_fitted_bleed_rect_times_scale(
        self, tmp_path: Path, fit: str
    ) -> None:
        from holiday_card.utils.measurements import fitted_panel_background_in

        image = _png(tmp_path / "bg.png", (1000, 1000))
        panel = _panel(str(image), background_color=_RED, x=0.0)
        geometry = PageGeometry.moo_a6()
        ctx = CompileContext(
            geometry=geometry, impose=False, emit_fold_lines=False,
            panel_fit=fit,  # type: ignore[arg-type]
        )
        commands = compile_card(_card(panel), ctx)
        group = next(c for c in commands if isinstance(c, BeginGroup))
        rect = _image_clip_rect(commands)
        placed = (
            rect.width * group.transform.scale_x / 72,
            rect.height * group.transform.scale_y / 72,
        )
        assert fitted_panel_background_in(
            _PANEL_W, _PANEL_H, geometry, fit, geometry.bleed_in,  # type: ignore[arg-type]
        ) == pytest.approx(placed)
