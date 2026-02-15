"""Integration tests for image clipping rendering."""

from pathlib import Path

import pytest

from holiday_card.core.models import (
    Card,
    CircleClipMask,
    Color,
    EllipseClipMask,
    FoldType,
    ImageElement,
    Panel,
    PanelPosition,
    RectangleClipMask,
    StarClipMask,
    SVGPathClipMask,
)
from holiday_card.renderers.reportlab_renderer import ReportLabRenderer


class TestCircularClipping:
    """Tests for circular clipping mask rendering."""

    @pytest.fixture
    def test_photo_path(self):
        """Path to test photo fixture."""
        return Path(__file__).parent.parent / "fixtures" / "sample_data" / "test_photo.jpg"

    def test_render_image_with_circle_clip_mask(self, test_photo_path, tmp_path):
        """Test rendering image with circular clipping mask."""
        # Create a card with an image clipped to a circle
        clip_mask = CircleClipMask(
            center_x=2.0,
            center_y=1.5,
            radius=1.2
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#FFFFFF"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        # Render to PDF
        output_path = tmp_path / "circle_clip_test.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        # Verify PDF was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_render_image_with_small_circle_clip(self, test_photo_path, tmp_path):
        """Test rendering image with small circular clipping mask."""
        clip_mask = CircleClipMask(
            center_x=1.0,
            center_y=1.0,
            radius=0.5
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.0,
            y=0.0,
            width=2.0,
            height=2.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=3.0,
            height=3.0,
            background_color=Color.from_hex("#F0F0F0"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "small_circle_clip.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()

    def test_render_multiple_images_with_circle_clips(self, test_photo_path, tmp_path):
        """Test rendering multiple images each with independent circular clipping."""
        # Create three images with different circular clips
        images = [
            ImageElement(
                source_path=str(test_photo_path),
                x=0.5,
                y=0.5,
                width=2.0,
                height=2.0,
                clip_mask=CircleClipMask(center_x=1.0, center_y=1.0, radius=0.8)
            ),
            ImageElement(
                source_path=str(test_photo_path),
                x=3.0,
                y=0.5,
                width=2.0,
                height=2.0,
                clip_mask=CircleClipMask(center_x=1.0, center_y=1.0, radius=0.9)
            ),
            ImageElement(
                source_path=str(test_photo_path),
                x=1.75,
                y=3.0,
                width=2.0,
                height=2.0,
                clip_mask=CircleClipMask(center_x=1.0, center_y=1.0, radius=1.0)
            ),
        ]

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=6.0,
            height=6.0,
            background_color=Color.from_hex("#FFFFFF"),
            image_elements=images
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "multiple_circle_clips.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()


class TestStarClipping:
    """Tests for star clipping mask rendering."""

    @pytest.fixture
    def test_photo_path(self):
        """Path to test photo fixture."""
        return Path(__file__).parent.parent / "fixtures" / "sample_data" / "test_photo.jpg"

    def test_render_image_with_star_clip_mask(self, test_photo_path, tmp_path):
        """Test rendering image with star clipping mask."""
        clip_mask = StarClipMask(
            center_x=2.0,
            center_y=1.5,
            points=5,
            outer_radius=1.4,
            inner_radius=0.7
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#FFFFFF"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "star_clip_test.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_render_image_with_six_point_star(self, test_photo_path, tmp_path):
        """Test rendering image with 6-pointed star."""
        clip_mask = StarClipMask(
            center_x=1.5,
            center_y=1.5,
            points=6,
            outer_radius=1.3,
            inner_radius=0.8
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.0,
            y=0.0,
            width=3.0,
            height=3.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=3.5,
            height=3.5,
            background_color=Color.from_hex("#E0E0FF"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "six_point_star_clip.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()

    def test_render_image_with_eight_point_star(self, test_photo_path, tmp_path):
        """Test rendering image with 8-pointed star (ornament style)."""
        clip_mask = StarClipMask(
            center_x=2.0,
            center_y=2.0,
            points=8,
            outer_radius=1.8,
            inner_radius=1.2
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.5,
            y=0.5,
            width=3.5,
            height=3.5,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=4.5,
            height=4.5,
            background_color=Color.from_hex("#FFF0E0"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "eight_point_star_clip.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()


class TestSVGPathClipping:
    """Tests for SVG path clipping mask rendering."""

    @pytest.fixture
    def test_photo_path(self):
        """Path to test photo fixture."""
        return Path(__file__).parent.parent / "fixtures" / "sample_data" / "test_photo.jpg"

    def test_render_image_with_svg_path_clip_mask(self, test_photo_path, tmp_path):
        """Test rendering image with SVG path clipping mask."""
        # Heart shape path
        heart_path = "M 50,30 C 35,20 20,30 20,45 C 20,60 35,75 50,90 C 65,75 80,60 80,45 C 80,30 65,20 50,30 Z"

        clip_mask = SVGPathClipMask(
            path_data=heart_path,
            scale=0.05
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#FFE0E0"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "svg_path_clip_test.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_render_image_with_triangle_svg_clip(self, test_photo_path, tmp_path):
        """Test rendering image with triangular SVG path clip."""
        triangle_path = "M 50 10 L 90 90 L 10 90 Z"

        clip_mask = SVGPathClipMask(
            path_data=triangle_path,
            scale=0.03
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.5,
            y=0.5,
            width=3.0,
            height=3.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=4.0,
            height=4.0,
            background_color=Color.from_hex("#E0FFE0"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "triangle_svg_clip.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()


class TestRectangleAndEllipseClipping:
    """Tests for rectangle and ellipse clipping masks."""

    @pytest.fixture
    def test_photo_path(self):
        """Path to test photo fixture."""
        return Path(__file__).parent.parent / "fixtures" / "sample_data" / "test_photo.jpg"

    def test_render_image_with_rectangle_clip(self, test_photo_path, tmp_path):
        """Test rendering image with rectangular clipping mask."""
        clip_mask = RectangleClipMask(
            x=0.5,
            y=0.5,
            width=3.0,
            height=2.0
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.0,
            y=0.0,
            width=4.0,
            height=3.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#F0F0F0"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "rectangle_clip.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()

    def test_render_image_with_ellipse_clip(self, test_photo_path, tmp_path):
        """Test rendering image with elliptical clipping mask."""
        clip_mask = EllipseClipMask(
            center_x=2.0,
            center_y=1.5,
            radius_x=1.8,
            radius_y=1.2
        )

        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.0,
            y=0.0,
            width=4.0,
            height=3.0,
            clip_mask=clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#E0E0FF"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "ellipse_clip.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()


class TestClippingEdgeCases:
    """Tests for edge cases in clipping."""

    @pytest.fixture
    def test_photo_path(self):
        """Path to test photo fixture."""
        return Path(__file__).parent.parent / "fixtures" / "sample_data" / "test_photo.jpg"

    def test_render_image_without_clip_mask(self, test_photo_path, tmp_path):
        """Test that images render correctly without clipping mask (baseline)."""
        image = ImageElement(
            source_path=str(test_photo_path),
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0
            # No clip_mask
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#FFFFFF"),
            image_elements=[image]
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "no_clip_mask.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()

    def test_render_mixed_clipped_and_unclipped_images(self, test_photo_path, tmp_path):
        """Test rendering a mix of clipped and unclipped images."""
        images = [
            # Clipped image
            ImageElement(
                source_path=str(test_photo_path),
                x=0.5,
                y=0.5,
                width=2.0,
                height=2.0,
                clip_mask=CircleClipMask(center_x=1.0, center_y=1.0, radius=0.9)
            ),
            # Unclipped image
            ImageElement(
                source_path=str(test_photo_path),
                x=3.0,
                y=0.5,
                width=2.0,
                height=2.0
            ),
        ]

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=6.0,
            height=3.0,
            background_color=Color.from_hex("#FFFFFF"),
            image_elements=images
        )

        card = Card(
            name="Test Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "mixed_clipping.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()
