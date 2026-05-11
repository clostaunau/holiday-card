"""Integration tests for gradient + pattern fills across all three backends.

Each backend renders a minimal card carrying a shape with one of:
linear gradient, radial gradient, stripes / dots / grid / checkerboard
pattern. The test asserts backend-specific structural evidence that
the fill landed correctly:

* PDF: content-stream contains `Sh` (shading-network draw) or `cs`
  (color space) markers indicating a non-DeviceRGB fill.
* SVG: ``<linearGradient>`` / ``<radialGradient>`` / ``<pattern>``
  element appears in ``<defs>`` and is referenced by a ``url(#id)``
  fill.
* PNG: pixel-sample inside the shape returns a non-white color
  (proving the fill rendered through the shape mask) and is consistent
  with the fill type (e.g. midpoint of a red→blue gradient is purple-ish).
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
    ColorStop,
    FoldType,
    LinearGradientFill,
    OccasionType,
    Panel,
    PanelPosition,
    PatternFill,
    PatternType,
    RadialGradientFill,
    Rectangle,
)
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer


def _shape_card(rect: Rectangle) -> Card:
    panel = Panel(
        position=PanelPosition.FRONT,
        x=0.0, y=0.0, width=4.0, height=5.0,
        shape_elements=[rect],
    )
    return Card(
        name="t",
        template_id="t",
        occasion=OccasionType.GENERIC,
        fold_type=FoldType.HALF_FOLD,
        panels=[panel],
    )


@pytest.fixture
def linear_card() -> Card:
    return _shape_card(Rectangle(
        x=0.5, y=0.5, width=3.0, height=4.0,
        fill=LinearGradientFill(
            angle=90.0,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF"),
            ],
        ),
        z_index=10,
    ))


@pytest.fixture
def radial_card() -> Card:
    return _shape_card(Rectangle(
        x=0.5, y=0.5, width=3.0, height=4.0,
        fill=RadialGradientFill(
            center_x=2.0, center_y=2.5, radius=1.5,
            stops=[
                ColorStop(position=0.0, color="#FFFF00"),
                ColorStop(position=1.0, color="#FF0000"),
            ],
        ),
        z_index=10,
    ))


@pytest.fixture
def pattern_card() -> Card:
    return _shape_card(Rectangle(
        x=0.5, y=0.5, width=3.0, height=4.0,
        fill=PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#FFFFFF", "#FF0000"],
            spacing=0.25,
        ),
        z_index=10,
    ))


class TestSVGGradients:
    def test_linear_emits_lineargradient_def(self, linear_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "linear.svg"
        SVGRenderer().render(compile_card(linear_card), out)
        body = out.read_text()
        assert "<linearGradient" in body
        # The shape should reference the gradient via url(#id).
        assert re.search(r'fill="url\(#lg_\d+\)"', body) is not None

    def test_radial_emits_radialgradient_def(self, radial_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "radial.svg"
        SVGRenderer().render(compile_card(radial_card), out)
        body = out.read_text()
        assert "<radialGradient" in body
        assert re.search(r'fill="url\(#rg_\d+\)"', body) is not None

    def test_pattern_emits_pattern_def(self, pattern_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "pattern.svg"
        SVGRenderer().render(compile_card(pattern_card), out)
        body = out.read_text()
        assert "<pattern" in body
        assert re.search(r'fill="url\(#pat_\d+\)"', body) is not None


class TestPDFGradients:
    """PDF gradients render as Shading patterns; check the page resources."""

    def test_linear_produces_shading_resource(self, linear_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "linear.pdf"
        IRReportLabRenderer().render(compile_card(linear_card), out)
        with pikepdf.open(out) as pdf:
            page = pdf.pages[0]
            resources = page.get("/Resources", {})
            # ReportLab adds /Pattern (which holds the shading) or
            # /Shading directly depending on version.
            has_shading = (
                "/Shading" in resources
                or "/Pattern" in resources
            )
            assert has_shading, (
                f"Expected /Shading or /Pattern in page resources for "
                f"linear gradient. Got: {dict(resources)}"
            )

    def test_radial_produces_shading_resource(self, radial_card: Card, tmp_path: Path) -> None:
        out = tmp_path / "radial.pdf"
        IRReportLabRenderer().render(compile_card(radial_card), out)
        with pikepdf.open(out) as pdf:
            page = pdf.pages[0]
            resources = page.get("/Resources", {})
            has_shading = (
                "/Shading" in resources
                or "/Pattern" in resources
            )
            assert has_shading, "Expected /Shading or /Pattern for radial gradient"

    def test_pattern_renders_without_error(self, pattern_card: Card, tmp_path: Path) -> None:
        # Patterns are drawn as composite shapes inside the clip — no
        # /Pattern PDF resource. Just verify the PDF renders cleanly
        # and has meaningful content (multiple stripe rectangles in
        # the content stream).
        out = tmp_path / "pattern.pdf"
        IRReportLabRenderer().render(compile_card(pattern_card), out)
        with pikepdf.open(out) as pdf:
            page = pdf.pages[0]
            contents = page.Contents
            streams = contents if isinstance(contents, pikepdf.Array) else [contents]
            body = b"".join(s.read_bytes() for s in streams).decode("latin-1")
            # Stripes: many rectangles inside a clip. Count 're' fill ops.
            re_count = len(re.findall(r"(?<=\s)re(?=\s|\n)", body))
            assert re_count >= 5, (
                f"Pattern should emit multiple rectangles; got {re_count}"
            )


class TestPNGGradients:
    """PNG fills composite through a shape mask; sample pixels to verify."""

    def test_linear_gradient_mid_pixel_blends(
        self, linear_card: Card, tmp_path: Path,
    ) -> None:
        out = tmp_path / "linear.png"
        PNGRenderer(dpi=72).render(compile_card(linear_card), out)
        with Image.open(out) as img:
            # Shape spans IR (0.5, 0.5) - (3.5, 4.5) at panel-relative inches.
            # Vertical gradient (angle=90) from red at bottom to blue at top.
            # Sample at vertical midpoint: should be roughly purple (R≈128, B≈128).
            bleed_pt = 9
            # IR x: panel.x + 0.5 + width/2 = 2.0 → 144 pts
            # IR y: panel.y + 2.5 = 2.5 → 180 pts (vertical midpoint)
            cx_pt = 144
            cy_pt = 180
            page_h_pt = 792  # US Letter default
            px_x = int(cx_pt + bleed_pt)
            px_y = int((page_h_pt - cy_pt) + bleed_pt)
            r, g, b = img.convert("RGB").getpixel((px_x, px_y))
            # Midpoint of red→blue gradient: R and B both around 120-140.
            assert 60 < r < 200, f"Mid-gradient R should blend (got {r})"
            assert 60 < b < 200, f"Mid-gradient B should blend (got {b})"
            # Green channel should stay low (gradient is red→blue).
            assert g < 80, f"Mid-gradient G should be low (got {g})"

    def test_radial_gradient_center_is_inner_color(
        self, radial_card: Card, tmp_path: Path,
    ) -> None:
        out = tmp_path / "radial.png"
        PNGRenderer(dpi=72).render(compile_card(radial_card), out)
        with Image.open(out) as img:
            # Gradient center at panel-rel (2.0, 2.5) → IR (144, 180) pts.
            bleed_pt = 9
            page_h_pt = 792
            cx_pt = 144
            cy_pt = 180
            px_x = int(cx_pt + bleed_pt)
            px_y = int((page_h_pt - cy_pt) + bleed_pt)
            r, g, b = img.convert("RGB").getpixel((px_x, px_y))
            # Inner stop is #FFFF00 (yellow): R≈255, G≈255, B≈0.
            assert r > 200 and g > 200, (
                f"Radial center should be yellow inner color (got R={r} G={g} B={b})"
            )
            assert b < 80

    def test_pattern_stripes_renders_alternating_pixels(
        self, pattern_card: Card, tmp_path: Path,
    ) -> None:
        out = tmp_path / "pattern.png"
        PNGRenderer(dpi=72).render(compile_card(pattern_card), out)
        with Image.open(out) as img:
            # Sample two pixels within the shape's height, 18 pixels
            # apart vertically — should span one stripe period (0.25"
            # at 72 DPI = 18 px) and produce different colors.
            bleed_pt = 9
            page_h_pt = 792
            cx_pt = 144  # panel-relative 2.0" (in the shape)
            cy_a = 180  # bottom
            cy_b = 162  # 18 pts (= one full stripe period) up
            px_x = int(cx_pt + bleed_pt)
            pixels = img.convert("RGB")
            # Stripes alternate so consecutive bands have different
            # colors. We don't pin which pixel is which (anti-aliasing
            # makes exact bands hard to nail), but the COLOR DIVERSITY
            # in the shape should be non-zero across the strip period.
            _ = (cy_a, cy_b)  # reference the y anchors for clarity
            sample_count = 0
            distinct_colors: set[tuple[int, int, int]] = set()
            for dy in range(0, 36, 2):  # span ~half inch
                pixel = pixels.getpixel((px_x, int((page_h_pt - (cy_a + dy)) + bleed_pt)))
                distinct_colors.add(pixel)
                sample_count += 1
            assert len(distinct_colors) >= 2, (
                f"Stripe pattern should produce at least 2 distinct colors "
                f"across the height; got {distinct_colors} from {sample_count} samples"
            )


class TestDeadTemplatesNowCompile:
    """Three previously dead christmas templates should now compile cleanly."""

    @pytest.mark.parametrize("template_id", [
        "christmas-winter-sky",
        "christmas-metallic-ornaments",
        "christmas-festive-stripes",
    ])
    def test_template_compiles(self, template_id: str) -> None:
        from holiday_card.core.generators import CardGenerator
        card = CardGenerator().create_card(template_id=template_id)
        # Should not raise UnsupportedFeatureError
        commands = compile_card(card)
        assert len(commands) > 0
