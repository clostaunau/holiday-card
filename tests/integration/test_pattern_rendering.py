"""Integration tests for pattern fill rendering."""



from holiday_card.core.models import (
    Card,
    Color,
    FoldType,
    Panel,
    PanelPosition,
    PatternFill,
    PatternType,
    Rectangle,
)
from holiday_card.renderers.reportlab_renderer import ReportLabRenderer


class TestStripePattern:
    """Tests for stripe pattern rendering."""

    def test_render_stripe_pattern(self, tmp_path):
        """Test rendering a card with stripe pattern background."""
        # Create stripe pattern fill
        stripe_fill = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#FF0000", "#FFFFFF"],
            spacing=0.5,
            rotation=45.0,
            scale=1.0
        )

        # Create a rectangle shape with stripe pattern
        shape = Rectangle(
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0,
            fill=stripe_fill
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#EEEEEE"),
            shape_elements=[shape]
        )

        card = Card(
            name="Stripe Pattern Test",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        # Render to PDF
        output_path = tmp_path / "stripe_pattern.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        # Verify PDF was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestDotPattern:
    """Tests for dot/polka pattern rendering."""

    def test_render_dot_pattern(self, tmp_path):
        """Test rendering a card with dot/polka pattern."""
        # Create dot pattern fill
        dot_fill = PatternFill(
            pattern_type=PatternType.DOTS,
            colors=["#0000FF", "#FFFF00"],
            spacing=0.3,
            scale=1.0
        )

        # Create a rectangle shape with dot pattern
        shape = Rectangle(
            x=1.0,
            y=1.0,
            width=3.0,
            height=2.5,
            fill=dot_fill
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.5,
            background_color=Color.from_hex("#FFFFFF"),
            shape_elements=[shape]
        )

        card = Card(
            name="Dot Pattern Test",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        # Render to PDF
        output_path = tmp_path / "dot_pattern.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        # Verify PDF was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestGridPattern:
    """Tests for grid pattern rendering."""

    def test_render_grid_pattern(self, tmp_path):
        """Test rendering a card with grid pattern."""
        # Create grid pattern fill
        grid_fill = PatternFill(
            pattern_type=PatternType.GRID,
            colors=["#00FF00"],
            spacing=0.25,
            scale=1.0
        )

        # Create a rectangle shape with grid pattern
        shape = Rectangle(
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.5,
            fill=grid_fill
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.5,
            background_color=Color.from_hex("#FFFFFF"),
            shape_elements=[shape]
        )

        card = Card(
            name="Grid Pattern Test",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        # Render to PDF
        output_path = tmp_path / "grid_pattern.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        # Verify PDF was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestCheckerboardPattern:
    """Tests for checkerboard pattern rendering."""

    def test_render_checkerboard_pattern(self, tmp_path):
        """Test rendering a card with checkerboard pattern."""
        # Create checkerboard pattern fill
        checkerboard_fill = PatternFill(
            pattern_type=PatternType.CHECKERBOARD,
            colors=["#000000", "#FFFFFF"],
            spacing=0.5,
            scale=1.0
        )

        # Create a rectangle shape with checkerboard pattern
        shape = Rectangle(
            x=0.5,
            y=0.5,
            width=4.0,
            height=4.0,
            fill=checkerboard_fill
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=5.0,
            background_color=Color.from_hex("#CCCCCC"),
            shape_elements=[shape]
        )

        card = Card(
            name="Checkerboard Pattern Test",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        # Render to PDF
        output_path = tmp_path / "checkerboard_pattern.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        # Verify PDF was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestPatternVariations:
    """Tests for various pattern configurations."""

    def test_render_pattern_with_custom_spacing(self, tmp_path):
        """Test rendering patterns with different spacing values."""
        # Small spacing (dense pattern)
        dense_stripe = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#FF6B6B", "#4ECDC4"],
            spacing=0.1,
            scale=1.0
        )

        shape = Rectangle(
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0,
            fill=dense_stripe
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#FFFFFF"),
            shape_elements=[shape]
        )

        card = Card(
            name="Dense Pattern Test",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "dense_pattern.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()

    def test_render_pattern_with_rotation(self, tmp_path):
        """Test rendering stripe pattern with various rotations."""
        # Vertical stripes (90 degrees)
        vertical_stripe = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#E74C3C", "#FFFFFF"],
            spacing=0.3,
            rotation=90.0,
            scale=1.0
        )

        shape = Rectangle(
            x=0.5,
            y=0.5,
            width=4.0,
            height=3.0,
            fill=vertical_stripe
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=5.0,
            height=4.0,
            background_color=Color.from_hex("#FFFFFF"),
            shape_elements=[shape]
        )

        card = Card(
            name="Rotated Pattern Test",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "rotated_pattern.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()

    def test_render_multiple_patterns(self, tmp_path):
        """Test rendering multiple shapes with different patterns."""
        shapes = [
            # Stripe pattern
            Rectangle(
                x=0.5,
                y=0.5,
                width=2.0,
                height=1.5,
                fill=PatternFill(
                    pattern_type=PatternType.STRIPES,
                    colors=["#FF0000", "#FFFFFF"],
                    spacing=0.2,
                    scale=1.0
                )
            ),
            # Dot pattern
            Rectangle(
                x=3.0,
                y=0.5,
                width=2.0,
                height=1.5,
                fill=PatternFill(
                    pattern_type=PatternType.DOTS,
                    colors=["#0000FF"],
                    spacing=0.2,
                    scale=1.0
                )
            ),
            # Checkerboard pattern
            Rectangle(
                x=1.5,
                y=2.5,
                width=2.5,
                height=1.5,
                fill=PatternFill(
                    pattern_type=PatternType.CHECKERBOARD,
                    colors=["#000000", "#FFFFFF"],
                    spacing=0.3,
                    scale=1.0
                )
            ),
        ]

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=6.0,
            height=5.0,
            background_color=Color.from_hex("#F0F0F0"),
            shape_elements=shapes
        )

        card = Card(
            name="Multiple Patterns Test",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel]
        )

        output_path = tmp_path / "multiple_patterns.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, str(output_path))

        assert output_path.exists()
