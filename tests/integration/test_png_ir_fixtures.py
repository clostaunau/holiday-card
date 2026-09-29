"""Hand-built IR fixtures for the PNG backend (issue #61).

Each fixture is a module-level ``list[RenderCommand]`` on a 200x200 pt
page, rendered with ``PNGRenderer(dpi=72)`` so one pixel is one point.
They are importable on purpose: the backend-parity matrix (#67) reuses
them against the SVG oracle (D12).

Pixel lookups use Pillow coordinates: ``(x, 200 - y_ir)``.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.render_ir import (
    RGBA,
    BeginClip,
    BeginGroup,
    BeginPage,
    CircleGeom,
    DrawImage,
    DrawShape,
    DrawText,
    EndClip,
    EndGroup,
    EndPage,
    GradientStop,
    ImageRef,
    LinearGradientPaint,
    Point,
    PolylineGeom,
    RectGeom,
    RenderCommand,
    SolidPaint,
    Stroke,
    TextRun,
    Transform,
)
from holiday_card.renderers.png_backend import PNGRenderer

_SAMPLE_PHOTO = Path(__file__).resolve().parent.parent / "fixtures" / "sample_photo.jpg"

_RED = RGBA(r=1, g=0, b=0)
_BLUE = RGBA(r=0, g=0, b=1)
_BLACK = RGBA(r=0, g=0, b=0)

_WHITE_PX = (255, 255, 255)
_RED_PX = (255, 0, 0)
_BLUE_PX = (0, 0, 255)


def _page(*body: RenderCommand) -> list[RenderCommand]:
    return [BeginPage(width=200, height=200, bleed=0), *body, EndPage()]


def _p(x: float, y: float) -> Point:
    return Point(x=x, y=y)


def _full_page(color: RGBA) -> DrawShape:
    return DrawShape(geometry=RectGeom(x=0, y=0, width=200, height=200), fill=SolidPaint(color=color))


def _photo_ref() -> ImageRef:
    with Image.open(_SAMPLE_PHOTO) as im:
        w, h = im.size
    return ImageRef(
        source=str(_SAMPLE_PHOTO),
        rect=RectGeom(x=0, y=0, width=200, height=200),
        format="jpeg",
        width_px=w,
        height_px=h,
        preserve_aspect=False,
    )


_CIRCLE_CLIP = BeginClip(geometry=CircleGeom(center=_p(100, 100), radius=50))
_RIGHT_HALF_CLIP = BeginClip(geometry=RectGeom(x=100, y=0, width=100, height=200))
_LEFT_HALF_CLIP = BeginClip(geometry=RectGeom(x=0, y=0, width=100, height=200))


# ---------------------------------------------------------------------------
# Fixtures (importable; #67 reuses them)
# ---------------------------------------------------------------------------

CLIP_SHAPE_IN_CIRCLE: list[RenderCommand] = _page(_CIRCLE_CLIP, _full_page(_RED), EndClip())

CLIP_TEXT_IN_RECT: list[RenderCommand] = _page(
    _LEFT_HALF_CLIP,
    DrawText(
        run=TextRun(
            text="MMMM", origin=_p(100, 90), font_id="Helvetica", size_pt=60,
            color=_BLACK, align="center",
        )
    ),
    EndClip(),
)

CLIP_NESTED_INTERSECT: list[RenderCommand] = _page(
    _CIRCLE_CLIP,
    _RIGHT_HALF_CLIP,
    _full_page(_RED),
    EndClip(),
    EndClip(),
    DrawShape(geometry=RectGeom(x=0, y=0, width=20, height=20), fill=SolidPaint(color=_BLUE)),
)

CLIP_IMAGE_NESTED: list[RenderCommand] = _page(
    _CIRCLE_CLIP,
    _RIGHT_HALF_CLIP,
    DrawImage(image=_photo_ref()),
    EndClip(),
    EndClip(),
)

CLIP_UNDER_ROTATED_GROUP: list[RenderCommand] = _page(
    _LEFT_HALF_CLIP,
    BeginGroup(transform=Transform(pivot_x=100, pivot_y=100, rotate_deg=180)),
    _full_page(_RED),
    EndGroup(),
    EndClip(),
)

CLIP_POLYLINE: list[RenderCommand] = _page(
    BeginClip(geometry=PolylineGeom(points=(_p(0, 0), _p(100, 100), _p(200, 0)))),
    EndClip(),
)


def dashed_rect(dash: tuple[float, ...]) -> list[RenderCommand]:
    return _page(
        DrawShape(
            geometry=RectGeom(x=20, y=20, width=160, height=160),
            stroke=Stroke(color=_BLACK, width=4, dash=dash),
        )
    )


DASHED_RECT: list[RenderCommand] = dashed_rect((10, 10))
SOLID_RECT: list[RenderCommand] = dashed_rect(())

DASHED_CIRCLE: list[RenderCommand] = _page(
    DrawShape(
        geometry=CircleGeom(center=_p(100, 100), radius=60),
        stroke=Stroke(color=_BLACK, width=4, dash=(6, 6)),
    )
)


def text_opacity_over_red(color_a: float, opacity: float) -> list[RenderCommand]:
    return _page(
        _full_page(_RED),
        DrawText(
            run=TextRun(
                text="M", origin=_p(40, 40), font_id="Helvetica", size_pt=150,
                color=RGBA(r=0, g=0, b=0, a=color_a),
            ),
            opacity=opacity,
        ),
    )


TEXT_OPACITY_OVER_RED: list[RenderCommand] = text_opacity_over_red(1.0, 0.5)

GRADIENT_OPACITY_OVER_RED: list[RenderCommand] = _page(
    _full_page(_RED),
    DrawShape(
        geometry=RectGeom(x=50, y=50, width=100, height=100),
        fill=LinearGradientPaint(
            start=_p(50, 50), end=_p(150, 50),
            stops=(GradientStop(position=0, color=_BLACK), GradientStop(position=1, color=_BLACK)),
        ),
        opacity=0.5,
    ),
)

UNKNOWN_FONT: list[RenderCommand] = _page(
    DrawText(
        run=TextRun(text="Hi", origin=_p(20, 100), font_id="NoSuchFont", size_pt=24, color=_BLACK)
    )
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render(commands: list[RenderCommand], tmp_path: Path) -> Image.Image:
    out = tmp_path / "out.png"
    PNGRenderer(dpi=72).render(commands, out)
    with Image.open(out) as im:
        return im.convert("RGB")


def _assert_px(img: Image.Image, xy: tuple[int, int], expected: tuple[int, int, int]) -> None:
    actual = img.getpixel(xy)
    assert isinstance(actual, tuple)
    assert all(abs(a - e) <= 8 for a, e in zip(actual, expected, strict=True)), (
        f"pixel {xy} is {actual}, expected {expected} (±8)"
    )


# ---------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------


class TestClipMasks:
    def test_shape_in_circle_clip_is_clipped(self, tmp_path: Path) -> None:
        img = _render(CLIP_SHAPE_IN_CIRCLE, tmp_path)
        for xy in [(100, 100), (140, 100)]:
            _assert_px(img, xy, _RED_PX)
        for xy in [(10, 10), (160, 100), (100, 170)]:
            _assert_px(img, xy, _WHITE_PX)

    def test_text_in_rect_clip_is_clipped(self, tmp_path: Path) -> None:
        img = _render(CLIP_TEXT_IN_RECT, tmp_path)
        px = img.load()
        assert px is not None
        dark_left = 0
        for y in range(200):
            for x in range(200):
                r, g, b = px[x, y]  # type: ignore[misc]
                if x >= 102:
                    assert min(r, g, b) >= 240, f"ink at ({x}, {y}) outside the clip"
                elif x < 98 and max(r, g, b) < 64:
                    dark_left += 1
        assert dark_left >= 50

    def test_nested_clips_intersect_and_pop(self, tmp_path: Path) -> None:
        img = _render(CLIP_NESTED_INTERSECT, tmp_path)
        _assert_px(img, (130, 100), _RED_PX)
        _assert_px(img, (70, 100), _WHITE_PX)
        _assert_px(img, (10, 190), _BLUE_PX)

    def test_image_in_nested_clips_intersects(self, tmp_path: Path) -> None:
        img = _render(CLIP_IMAGE_NESTED, tmp_path)
        _assert_px(img, (70, 100), _WHITE_PX)
        _assert_px(img, (180, 100), _WHITE_PX)
        assert img.getpixel((130, 100)) != _WHITE_PX

    def test_clip_outside_rotated_group_still_applies(self, tmp_path: Path) -> None:
        img = _render(CLIP_UNDER_ROTATED_GROUP, tmp_path)
        _assert_px(img, (50, 100), _RED_PX)
        _assert_px(img, (150, 100), _WHITE_PX)

    def test_polyline_clip_raises_at_begin_clip(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError, match="PolylineGeom"):
            _render(CLIP_POLYLINE, tmp_path)


# ---------------------------------------------------------------------------
# Dashes
# ---------------------------------------------------------------------------


def _inked_runs(flags: list[bool]) -> int:
    return sum(1 for i, f in enumerate(flags) if f and (i == 0 or not flags[i - 1]))


def _bottom_edge_ink(img: Image.Image) -> list[bool]:
    return [
        any(min(img.getpixel((x, y))) < 128 for y in range(174, 185))  # type: ignore[arg-type]
        for x in range(30, 171)
    ]


class TestDashes:
    def test_dashed_rect_is_dashed(self, tmp_path: Path) -> None:
        inked = _bottom_edge_ink(_render(DASHED_RECT, tmp_path))
        fraction = sum(inked) / len(inked)
        assert 0.35 <= fraction <= 0.65, fraction
        assert _inked_runs(inked) >= 6

    def test_undashed_rect_is_solid(self, tmp_path: Path) -> None:
        inked = _bottom_edge_ink(_render(SOLID_RECT, tmp_path))
        assert sum(inked) / len(inked) > 0.95

    def test_dashed_circle_is_dashed(self, tmp_path: Path) -> None:
        img = _render(DASHED_CIRCLE, tmp_path)
        inked = 0
        for deg in range(360):
            a = math.radians(deg)
            if any(
                min(img.getpixel((round(100 + r * math.cos(a)), round(100 + r * math.sin(a))))) < 128  # type: ignore[arg-type]
                for r in range(58, 63)
            ):
                inked += 1
        assert 0.3 <= inked / 360 <= 0.7, inked / 360


# ---------------------------------------------------------------------------
# Text alpha
# ---------------------------------------------------------------------------


class TestTextOpacity:
    @pytest.mark.parametrize(
        ("color_a", "opacity", "expected_r"),
        [(1.0, 0.5, 127), (0.5, 1.0, 127), (0.5, 0.5, 191)],
    )
    def test_text_alpha_blends_over_red(
        self, tmp_path: Path, color_a: float, opacity: float, expected_r: int
    ) -> None:
        img = _render(text_opacity_over_red(color_a, opacity), tmp_path)
        pixels = [img.getpixel((x, y)) for x in range(200) for y in range(200)]
        darkest = min(pixels, key=sum)  # type: ignore[arg-type]
        r, g, b = darkest  # type: ignore[misc]
        assert abs(r - expected_r) <= 12, darkest
        assert g <= 12 and b <= 12, darkest


class TestGradientOpacity:
    def test_translucent_gradient_blends_over_red_not_white(self, tmp_path: Path) -> None:
        img = _render(GRADIENT_OPACITY_OVER_RED, tmp_path)
        _assert_px(img, (100, 100), (127, 0, 0))


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------


class TestFonts:
    def test_unknown_font_raises(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError, match="NoSuchFont"):
            _render(UNKNOWN_FONT, tmp_path)
