"""Integration tests for ImageElement rendering across all three backends.

Each backend renders the same minimal card (one panel, one image with
a circular clip) and the test asserts the output is non-empty and
contains backend-specific evidence of an image:

* PDF: ``/XObject`` resource of subtype ``/Image`` in the page.
* SVG: ``<image>`` element with a ``data:image`` href.
* PNG: pixel-sample inside the clip vs outside — clip should be
  occupied by image pixels (non-white-page), outside should remain
  the page background.

The fixture image is a 400×400 solid red square with a blue interior
circle (created during this PR; see ``tests/fixtures/sample_photo.jpg``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from holiday_card.core.compiler import compile_card
from holiday_card.core.models import (
    Card,
    CircleClipMask,
    FoldType,
    ImageElement,
    OccasionType,
    Panel,
    PanelPosition,
)
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer

FIXTURE_IMAGE = Path(__file__).parent.parent / "fixtures" / "sample_photo.jpg"


@pytest.fixture
def image_card() -> Card:
    """A minimal one-panel card carrying one circle-clipped image."""
    image = ImageElement(
        source_path=str(FIXTURE_IMAGE),
        x=1.0, y=1.0, width=2.0, height=2.0,
        clip_mask=CircleClipMask(center_x=2.0, center_y=2.0, radius=0.8),
    )
    panel = Panel(
        position=PanelPosition.FRONT,
        x=0.0, y=0.0, width=4.25, height=5.5,
        image_elements=[image],
    )
    return Card(
        name="image test",
        template_id="t",
        occasion=OccasionType.GENERIC,
        fold_type=FoldType.HALF_FOLD,
        panels=[panel],
    )


class TestPDFImageRendering:
    def test_pdf_contains_image_xobject(self, image_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "image.pdf"
        renderer = IRReportLabRenderer()
        renderer.render(compile_card(image_card), out)
        assert out.exists() and out.stat().st_size > 0
        with pikepdf.open(out) as pdf:
            page = pdf.pages[0]
            resources = page.get("/Resources", {})
            xobj = resources.get("/XObject", {})
            assert len(xobj) >= 1, "PDF page should reference at least one XObject"
            image_xobjs = [
                v for v in xobj.values()
                if v.get("/Subtype") == pikepdf.Name("/Image")
            ]
            assert len(image_xobjs) >= 1, "Page should carry at least one Image XObject"


class TestSVGImageRendering:
    def test_svg_embeds_base64_image(self, image_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "image.svg"
        renderer = SVGRenderer()
        renderer.render(compile_card(image_card), out)
        assert out.exists()
        body = out.read_text()
        # Expect an <image> element with a base64 data URI.
        match = re.search(r'<image[^>]*href="data:image/(jpeg|png)[^"]+"', body)
        assert match is not None, (
            "SVG should contain an <image> element with a base64 data href"
        )

    def test_svg_image_inside_clip_path(self, image_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "image.svg"
        SVGRenderer().render(compile_card(image_card), out)
        body = out.read_text()
        # Clip is declared (<clipPath>) and applied (clip-path="url(#…)")
        assert "<clipPath" in body
        assert "clip-path=" in body


class TestPNGImageRendering:
    def test_png_image_pixels_inside_clip(self, image_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "image.png"
        # 144 DPI for the test; the fixture image's red/blue pixels
        # should land in the clipped region.
        renderer = PNGRenderer(dpi=72)  # 1 pt = 1 px → easy math
        renderer.render(compile_card(image_card), out)
        assert out.exists() and out.stat().st_size > 0
        with Image.open(out) as img:
            # Page: bleed extends canvas; trim corners at (bleed, bleed).
            # Image is at panel-relative (1.0, 1.0) inches → IR (72, 72) pts.
            # The image rect is 2"×2" centered around (2.0, 2.0).
            # Clip is a circle at center (2.0, 2.0) with radius 0.8" → 57.6 pt.
            # At 72 DPI: bleed = 9 pt (the default 0.125 inch).
            # IR rect (72, 72, 144, 144) → media-pixel (81, _, 225, _).
            # IR (2.0", 2.0") = (144, 144) pts → media-pixel
            # ((144+9), height_px - (144+9)) ≈ center of clip.
            #
            # Default page is letter = 612×792 pts; trim height 5.5" panel
            # but the actual page geometry... wait — image_card uses no
            # CompileContext so it gets default US Letter.
            #
            # For a robust check, sample inside the rect's center
            # (definitely inside the 0.8" clip circle) and confirm
            # it's NOT plain white (255,255,255). The fixture image
            # is solid red/blue, neither of which is pure white.
            cx_pt = 144  # image center x (IR pts)
            cy_pt = 144  # image center y (IR pts)
            bleed_pt = 9  # default 0.125 inch
            # PNG canvas has bleed margin added; IR origin (0,0) is at (bleed, height - bleed) in PNG pixels.
            # Pixel y is top-down; IR y is bottom-up; page is 11" tall by default.
            page_h_pt = 792  # US Letter height in pts
            px_x = int(cx_pt + bleed_pt)
            px_y = int((page_h_pt - cy_pt) + bleed_pt)
            r, g, b = img.convert("RGB").getpixel((px_x, px_y))
            # Fixture image at center is solid blue (the inscribed circle).
            # Expect blue dominance.
            assert b > r and b > g, (
                f"Pixel at center of clipped image should be blue-ish "
                f"(got R={r} G={g} B={b})"
            )

    def test_png_image_pixels_outside_clip_are_white(
        self, image_card: Card, tmp_path: Path,
    ) -> None:
        out = tmp_path / "image.png"
        PNGRenderer(dpi=72).render(compile_card(image_card), out)
        with Image.open(out) as img:
            # Top-left corner of the rendered page should be the
            # default white background (no image, no shape there).
            r, g, b = img.convert("RGB").getpixel((2, 2))
            assert (r, g, b) == (255, 255, 255), (
                f"Top-left page corner should be white background "
                f"(got R={r} G={g} B={b})"
            )
