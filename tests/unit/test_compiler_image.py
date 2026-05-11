"""Compiler-level tests for ``_compile_image`` (ImageElement → IR).

Asserts the emitted ``RenderCommand`` sequence shape for:

* plain image (no clip, no rotation)
* image with each supported clip-mask type
* image with rotation (BeginGroup wrapping)
* image with opacity passthrough
* unsupported feature combinations (effects / frame_style / Heart / SVGPath)

Path resolution is checked in passing — the compiler emits an
absolute path so backends don't have to know about CWD.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from holiday_card.core.compiler import UnsupportedFeatureError, compile_card
from holiday_card.core.models import (
    Card,
    CircleClipMask,
    EllipseClipMask,
    FoldType,
    HeartClipMask,
    ImageEffects,
    ImageElement,
    OccasionType,
    Panel,
    PanelPosition,
    PhotoFrameStyle,
    RectangleClipMask,
    StarClipMask,
    SVGPathClipMask,
)
from holiday_card.core.render_ir import (
    BeginClip,
    BeginGroup,
    CircleGeom,
    DrawImage,
    EllipseGeom,
    EndClip,
    EndGroup,
    PolygonGeom,
    RectGeom,
)

FIXTURE_IMAGE = Path(__file__).parent.parent / "fixtures" / "sample_photo.jpg"


def _make_card(image: ImageElement) -> Card:
    panel = Panel(
        position=PanelPosition.FRONT,
        width=4.0,
        height=6.0,
        x=0.0,
        y=0.0,
        image_elements=[image],
    )
    return Card(
        name="t",
        template_id="t",
        occasion=OccasionType.GENERIC,
        fold_type=FoldType.HALF_FOLD,
        panels=[panel],
    )


def _images(commands: list) -> list[DrawImage]:
    return [c for c in commands if isinstance(c, DrawImage)]


class TestCompileImage:
    def test_plain_image_emits_one_drawimage(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.5, y=1.0, width=2.0, height=2.0,
        )
        draws = _images(compile_card(_make_card(img)))
        assert len(draws) == 1
        d = draws[0]
        assert d.image.source == str(FIXTURE_IMAGE.resolve())
        assert d.image.preserve_aspect is True
        # Panel at (0,0) + image at (0.5, 1.0) → 36, 72 pts
        assert d.image.rect.x == pytest.approx(36.0)
        assert d.image.rect.y == pytest.approx(72.0)
        # Dimensions: 2.0" × 72 = 144 pts
        assert d.image.rect.width == pytest.approx(144.0)
        assert d.image.rect.height == pytest.approx(144.0)

    def test_image_with_opacity_passes_through(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=1.0, height=1.0,
            opacity=0.5,
        )
        draws = _images(compile_card(_make_card(img)))
        assert draws[0].opacity == 0.5

    def test_image_with_rotation_wraps_in_group(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=1.0, y=1.0, width=2.0, height=2.0,
            rotation=45.0,
        )
        commands = compile_card(_make_card(img))
        # Find the image-related commands inside the panel's group
        # (every panel itself is wrapped in a group, so image rotation
        # adds a *nested* BeginGroup/EndGroup pair).
        groups = [c for c in commands if isinstance(c, (BeginGroup, EndGroup))]
        # 1 panel group (begin+end) + 1 image rotation group (begin+end) = 4
        assert len(groups) == 4
        # The image's rotation group transform should encode 45° around
        # the image center.
        # Image center: x=1.0 + 1.0 = 2.0", y=1.0 + 1.0 = 2.0"
        # → (144, 144) pts
        inner_begin = [c for c in commands if isinstance(c, BeginGroup) and c.transform.rotate_deg == 45.0]
        assert len(inner_begin) == 1
        t = inner_begin[0].transform
        assert t.translate_x == pytest.approx(144.0)
        assert t.translate_y == pytest.approx(144.0)


class TestClipMaskConversion:
    """Each ClipMask subtype converts to the expected IR Geometry."""

    def test_circle_clip(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            clip_mask=CircleClipMask(center_x=1.0, center_y=1.0, radius=0.5),
        )
        commands = compile_card(_make_card(img))
        clips = [c for c in commands if isinstance(c, BeginClip)]
        assert len(clips) == 1
        assert isinstance(clips[0].geometry, CircleGeom)
        g = clips[0].geometry
        assert g.center.x == pytest.approx(72.0)
        assert g.center.y == pytest.approx(72.0)
        assert g.radius == pytest.approx(36.0)
        # Clip pairs balance
        ends = [c for c in commands if isinstance(c, EndClip)]
        assert len(ends) == 1

    def test_rectangle_clip(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            clip_mask=RectangleClipMask(x=0.1, y=0.2, width=1.5, height=1.6),
        )
        clips = [c for c in compile_card(_make_card(img)) if isinstance(c, BeginClip)]
        assert isinstance(clips[0].geometry, RectGeom)
        g = clips[0].geometry
        assert g.x == pytest.approx(7.2)
        assert g.y == pytest.approx(14.4)
        assert g.width == pytest.approx(108.0)
        assert g.height == pytest.approx(115.2)

    def test_ellipse_clip(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            clip_mask=EllipseClipMask(
                center_x=1.0, center_y=1.0, radius_x=0.8, radius_y=0.5,
            ),
        )
        clips = [c for c in compile_card(_make_card(img)) if isinstance(c, BeginClip)]
        assert isinstance(clips[0].geometry, EllipseGeom)
        g = clips[0].geometry
        assert g.rx == pytest.approx(57.6)
        assert g.ry == pytest.approx(36.0)

    def test_star_clip_produces_polygon(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            clip_mask=StarClipMask(
                center_x=1.0, center_y=1.0,
                outer_radius=0.8, inner_radius=0.4, points=5,
            ),
        )
        clips = [c for c in compile_card(_make_card(img)) if isinstance(c, BeginClip)]
        assert isinstance(clips[0].geometry, PolygonGeom)
        # 5-pointed star = 10 polygon vertices (alternating outer/inner)
        assert len(clips[0].geometry.points) == 10

    def test_heart_clip_unsupported(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            clip_mask=HeartClipMask(center_x=1.0, center_y=1.0, size=0.5),
        )
        with pytest.raises(UnsupportedFeatureError, match="Heart"):
            compile_card(_make_card(img))

    def test_svg_path_clip_unsupported(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            clip_mask=SVGPathClipMask(path_data="M 0 0 L 10 10 Z"),
        )
        with pytest.raises(UnsupportedFeatureError, match="SVGPath"):
            compile_card(_make_card(img))


class TestUnsupportedFeatures:
    """ImageElement features deferred to follow-up PRs raise loudly."""

    def test_effects_unsupported(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            effects=ImageEffects(grayscale=True),
        )
        with pytest.raises(UnsupportedFeatureError, match="effects"):
            compile_card(_make_card(img))

    def test_frame_style_unsupported(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, width=2.0, height=2.0,
            frame_style=PhotoFrameStyle.SHADOW,
        )
        with pytest.raises(UnsupportedFeatureError, match="frame_style"):
            compile_card(_make_card(img))

    def test_missing_width_unsupported(self) -> None:
        img = ImageElement(
            source_path=str(FIXTURE_IMAGE),
            x=0.0, y=0.0, height=2.0,  # width omitted
        )
        with pytest.raises(UnsupportedFeatureError, match="explicit width"):
            compile_card(_make_card(img))
