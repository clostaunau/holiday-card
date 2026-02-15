"""Integration tests for SVG path rendering.

Tests end-to-end SVG path rendering in card generation,
including complex paths, clipping, and edge cases.
"""


from holiday_card.core.models import (
    Card,
    Circle,
    ColorStop,
    FoldType,
    LinearGradientFill,
    Panel,
    PanelPosition,
    SolidFill,
    SVGPath,
)
from holiday_card.renderers.reportlab_renderer import ReportLabRenderer


class TestSVGPathRendering:
    """Integration tests for SVG path rendering."""

    def test_render_simple_svg_path(self, tmp_path):
        """Test rendering a simple SVG path (rectangle)."""
        # Simple rectangle as SVG path
        svg_path = SVGPath(
            path_data="M 0.5 0.5 L 1.5 0.5 L 1.5 1.5 L 0.5 1.5 Z",
            fill_color="#FF0000",
            stroke_color="#000000",
            stroke_width=1.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[svg_path],
        )

        card = Card(
            name="SVG Path Test Card",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "simple_svg_path.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_render_svg_path_with_solid_fill(self, tmp_path):
        """Test SVG path with modern SolidFill style."""
        svg_path = SVGPath(
            path_data="M 1 1 L 2 1 L 2 2 L 1 2 Z",
            fill=SolidFill(color="#00FF00"),
            stroke_color="#000000",
            stroke_width=2.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[svg_path],
        )

        card = Card(
            name="SVG with SolidFill",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "svg_solid_fill.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_render_svg_path_with_gradient_fill(self, tmp_path):
        """Test SVG path with gradient fill."""
        gradient = LinearGradientFill(
            angle=45.0,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF"),
            ],
        )

        svg_path = SVGPath(
            path_data="M 1 1 L 3 1 L 3 3 L 1 3 Z",
            fill=gradient,
            stroke_color="#000000",
            stroke_width=1.5,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[svg_path],
        )

        card = Card(
            name="SVG with Gradient",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "svg_gradient_fill.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_render_holly_leaf_svg(self, tmp_path):
        """Test rendering a realistic holly leaf SVG path."""
        # Holly leaf path (from holly_leaf.svg fixture)
        holly_path = """M 50 10
           C 55 15, 60 15, 65 10
           C 70 15, 70 20, 68 25
           C 72 28, 75 28, 78 25
           C 80 32, 78 38, 72 40
           C 75 45, 75 50, 70 55
           C 72 60, 70 65, 65 68
           C 68 72, 68 77, 65 82
           C 58 80, 54 78, 50 80
           C 46 78, 42 80, 35 82
           C 32 77, 32 72, 35 68
           C 30 65, 28 60, 30 55
           C 25 50, 25 45, 28 40
           C 22 38, 20 32, 22 25
           C 25 28, 28 28, 32 25
           C 30 20, 30 15, 35 10
           C 40 15, 45 15, 50 10 Z"""

        # Scale down to fit nicely on card (convert from 100x100 viewbox to inches)
        svg_path = SVGPath(
            path_data=holly_path,
            scale=0.01,  # Scale from 100px to ~1 inch
            fill_color="#2d5016",  # Dark green
            stroke_color="#1a3010",  # Darker green outline
            stroke_width=1.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[svg_path],
        )

        card = Card(
            name="Holly Leaf Card",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "holly_leaf.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 1000  # Should have meaningful content

    def test_render_svg_path_with_curves(self, tmp_path):
        """Test SVG path with cubic Bezier curves."""
        curved_path = SVGPath(
            path_data="M 1 2 C 1 1, 2 1, 2 2 C 2 3, 1 3, 1 2 Z",
            fill_color="#0000FF",
            stroke_color="#000080",
            stroke_width=1.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[curved_path],
        )

        card = Card(
            name="Curved SVG Path",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "curved_svg_path.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_render_svg_path_with_quadratic_curves(self, tmp_path):
        """Test SVG path with quadratic Bezier curves."""
        quad_path = SVGPath(
            path_data="M 1 2 Q 1.5 1, 2 2 Q 1.5 3, 1 2 Z",
            fill_color="#FFFF00",
            stroke_color="#808000",
            stroke_width=1.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[quad_path],
        )

        card = Card(
            name="Quadratic Curve SVG",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "quad_curve_svg_path.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_render_svg_path_with_arcs(self, tmp_path):
        """Test SVG path with elliptical arcs."""
        arc_path = SVGPath(
            path_data="M 1 2 A 0.5 0.5 0 0 1 2 2 L 2 3 A 0.5 0.5 0 0 1 1 3 Z",
            fill_color="#FF00FF",
            stroke_color="#800080",
            stroke_width=1.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[arc_path],
        )

        card = Card(
            name="Arc SVG Path",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "arc_svg_path.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_render_multiple_svg_paths(self, tmp_path):
        """Test rendering multiple SVG paths on the same panel."""
        path1 = SVGPath(
            path_data="M 1 1 L 2 1 L 2 2 L 1 2 Z",
            fill_color="#FF0000",
            z_index=1,
        )

        path2 = SVGPath(
            path_data="M 1.5 1.5 L 2.5 1.5 L 2.5 2.5 L 1.5 2.5 Z",
            fill_color="#0000FF",
            z_index=2,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[path1, path2],
        )

        card = Card(
            name="Multiple SVG Paths",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "multiple_svg_paths.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_render_svg_path_with_rotation(self, tmp_path):
        """Test SVG path with rotation."""
        rotated_path = SVGPath(
            path_data="M 2 2 L 3 2 L 3 3 L 2 3 Z",
            fill_color="#00FFFF",
            rotation=45.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[rotated_path],
        )

        card = Card(
            name="Rotated SVG Path",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "rotated_svg_path.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_render_svg_path_with_opacity(self, tmp_path):
        """Test SVG path with opacity."""
        opaque_path = SVGPath(
            path_data="M 1 1 L 3 1 L 3 3 L 1 3 Z",
            fill_color="#FF0000",
            opacity=0.5,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[opaque_path],
        )

        card = Card(
            name="Opaque SVG Path",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "opaque_svg_path.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_svg_path_mixed_with_other_shapes(self, tmp_path):
        """Test SVG path rendering alongside other shape types."""
        svg_path = SVGPath(
            path_data="M 1 1 L 2 1 L 2 2 L 1 2 Z",
            fill_color="#FF0000",
            z_index=2,
        )

        circle = Circle(
            center_x=2.5,
            center_y=2.5,
            radius=0.5,
            fill_color="#0000FF",
            z_index=1,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[circle, svg_path],  # Mix of different shape types
        )

        card = Card(
            name="Mixed Shapes",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "mixed_shapes.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()


class TestSVGPathEdgeCases:
    """Edge case tests for SVG path rendering."""

    def test_svg_path_extending_beyond_safe_margins(self, tmp_path):
        """Test SVG path that extends beyond safe print margins.

        Per spec.md edge case 5: Paths extending beyond safe margins
        should be clipped or generate a warning.
        """
        # Large path extending beyond typical safe margins (0.25 inch)
        large_path = SVGPath(
            path_data="M 0.1 0.1 L 8.4 0.1 L 8.4 10.9 L 0.1 10.9 Z",  # Near page edges
            fill_color="#FF0000",
            stroke_color="#000000",
            stroke_width=1.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[large_path],
        )

        card = Card(
            name="Large Path Test",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "large_path.pdf"
        renderer = ReportLabRenderer()

        # Should render without error (clipping should happen automatically)
        renderer.render(card, output_path)

        assert output_path.exists()
        # Note: In production, this should also log a warning

    def test_svg_path_with_relative_commands(self, tmp_path):
        """Test SVG path using relative commands (lowercase)."""
        relative_path = SVGPath(
            path_data="M 1 1 l 1 0 l 0 1 l -1 0 z",  # lowercase = relative
            fill_color="#00FF00",
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[relative_path],
        )

        card = Card(
            name="Relative Commands",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "relative_commands.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_svg_path_with_horizontal_vertical_lines(self, tmp_path):
        """Test SVG path with H/h and V/v commands."""
        path_with_hv = SVGPath(
            path_data="M 1 1 H 2 V 2 H 1 V 1 Z",  # H = horizontal, V = vertical
            fill_color="#0000FF",
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[path_with_hv],
        )

        card = Card(
            name="H/V Commands",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "hv_commands.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_svg_path_with_smooth_curves(self, tmp_path):
        """Test SVG path with smooth curve commands (S/s and T/t)."""
        smooth_path = SVGPath(
            path_data="M 1 2 C 1 1, 2 1, 2 2 S 3 3, 3 2 Z",  # S = smooth cubic
            fill_color="#FFFF00",
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[smooth_path],
        )

        card = Card(
            name="Smooth Curves",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "smooth_curves.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_svg_path_with_scale(self, tmp_path):
        """Test SVG path with scale transformation."""
        scaled_path = SVGPath(
            path_data="M 10 10 L 20 10 L 20 20 L 10 20 Z",  # 10x10 units
            scale=0.1,  # Scale down to 1x1 inches
            fill_color="#FF00FF",
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[scaled_path],
        )

        card = Card(
            name="Scaled Path",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "scaled_path.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()

    def test_svg_path_complex_decorative_element(self, tmp_path):
        """Test complex decorative SVG path (e.g., snowflake)."""
        # Simplified 6-point snowflake
        snowflake_path = SVGPath(
            path_data="""M 2.5 2
                        L 2.5 2.3 L 2.7 2.15 L 2.5 2.3 L 2.5 2.5
                        L 2.3 2.7 L 2.5 2.5 L 2.7 2.7 L 2.5 2.5
                        L 2.5 2.7 L 2.3 2.85 L 2.5 2.7 L 2.5 3
                        L 2 2.5 L 2.5 2 Z""",
            fill_color="#FFFFFF",
            stroke_color="#AAAAFF",
            stroke_width=0.5,
            scale=1.0,
        )

        panel = Panel(
            position=PanelPosition.FRONT,
            x=0,
            y=0,
            width=8.5,
            height=11.0,
            shape_elements=[snowflake_path],
        )

        card = Card(
            name="Snowflake Decoration",
            template_id="test",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )

        output_path = tmp_path / "snowflake.pdf"
        renderer = ReportLabRenderer()
        renderer.render(card, output_path)

        assert output_path.exists()
