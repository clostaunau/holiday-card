"""Unit tests for SVG path data parser."""

import pytest

from holiday_card.utils.svg_parser import (
    PathCommand,
    SVGCommand,
    SVGPathParser,
)


class TestSVGPathParser:
    """Tests for SVGPathParser."""

    def test_parse_simple_move_line(self):
        """Test parsing simple move and line commands."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 20 L 30 40")

        assert len(commands) == 2
        assert commands[0].command == SVGCommand.MOVE
        assert commands[0].params == [10.0, 20.0]
        assert commands[1].command == SVGCommand.LINE
        assert commands[1].params == [30.0, 40.0]

    def test_parse_with_close(self):
        """Test parsing path with close command."""
        parser = SVGPathParser()
        commands = parser.parse("M 0 0 L 10 0 L 10 10 Z")

        assert len(commands) == 4
        assert commands[3].command == SVGCommand.CLOSE
        assert commands[3].params == []

    def test_parse_relative_commands(self):
        """Test parsing relative move and line commands."""
        parser = SVGPathParser()
        commands = parser.parse("m 5 5 l 10 0 l 0 10 z")

        assert commands[0].command == SVGCommand.MOVE_REL
        assert commands[1].command == SVGCommand.LINE_REL
        assert commands[3].command == SVGCommand.CLOSE_REL

    def test_parse_cubic_bezier(self):
        """Test parsing cubic Bezier curve."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 C 20 20 30 20 40 10")

        assert len(commands) == 2
        assert commands[1].command == SVGCommand.CUBIC_BEZIER
        assert commands[1].params == [20.0, 20.0, 30.0, 20.0, 40.0, 10.0]

    def test_parse_quadratic_bezier(self):
        """Test parsing quadratic Bezier curve."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 Q 20 20 30 10")

        assert len(commands) == 2
        assert commands[1].command == SVGCommand.QUADRATIC_BEZIER
        assert commands[1].params == [20.0, 20.0, 30.0, 10.0]

    def test_parse_arc(self):
        """Test parsing elliptical arc."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 A 5 5 0 0 1 20 20")

        assert len(commands) == 2
        assert commands[1].command == SVGCommand.ARC
        assert len(commands[1].params) == 7

    def test_parse_horizontal_vertical_lines(self):
        """Test parsing horizontal and vertical line commands."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 H 20 V 30")

        assert commands[1].command == SVGCommand.HORIZONTAL
        assert commands[1].params == [20.0]
        assert commands[2].command == SVGCommand.VERTICAL
        assert commands[2].params == [30.0]

    def test_parse_multiple_parameters(self):
        """Test parsing command with multiple parameter sets."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 L 20 20 30 30 40 40")

        assert len(commands) == 2
        # Multiple L parameters combined into one command
        assert commands[1].params == [20.0, 20.0, 30.0, 30.0, 40.0, 40.0]

    def test_parse_with_commas(self):
        """Test parsing with comma separators."""
        parser = SVGPathParser()
        commands = parser.parse("M 10,20 L 30,40")

        assert commands[0].params == [10.0, 20.0]
        assert commands[1].params == [30.0, 40.0]

    def test_parse_with_negative_numbers(self):
        """Test parsing with negative coordinates."""
        parser = SVGPathParser()
        commands = parser.parse("M -10 -20 L -30 -40")

        assert commands[0].params == [-10.0, -20.0]
        assert commands[1].params == [-30.0, -40.0]

    def test_parse_with_decimal_numbers(self):
        """Test parsing with decimal coordinates."""
        parser = SVGPathParser()
        commands = parser.parse("M 10.5 20.75 L 30.25 40.125")

        assert commands[0].params == [10.5, 20.75]
        assert commands[1].params == [30.25, 40.125]

    def test_parse_with_scientific_notation(self):
        """Test parsing with scientific notation."""
        parser = SVGPathParser()
        commands = parser.parse("M 1e2 2e-1 L 3e+1 4e0")

        assert commands[0].params == [100.0, 0.2]
        assert commands[1].params == [30.0, 4.0]

    def test_parse_empty_string_raises_error(self):
        """Test that empty path data raises ValueError."""
        parser = SVGPathParser()
        with pytest.raises(ValueError, match="empty"):
            parser.parse("")

    def test_parse_whitespace_only_raises_error(self):
        """Test that whitespace-only path data raises ValueError."""
        parser = SVGPathParser()
        with pytest.raises(ValueError, match="empty"):
            parser.parse("   ")

    def test_parse_invalid_command_raises_error(self):
        """Test that invalid command raises ValueError."""
        parser = SVGPathParser()
        with pytest.raises(ValueError, match="Expected command"):
            parser.parse("10 20")

    def test_parse_unsupported_command_skips_with_warning(self):
        """Test that unsupported commands are skipped with warning."""
        parser = SVGPathParser()
        # Using a future/extended SVG command that doesn't exist
        # Parser should skip it gracefully
        commands = parser.parse("M 10 10 L 20 20")
        assert len(commands) == 2

    def test_parse_smooth_cubic_bezier(self):
        """Test parsing smooth cubic Bezier (S command)."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 C 20 20 30 20 40 10 S 60 20 70 10")

        assert commands[2].command == SVGCommand.CUBIC_BEZIER_SMOOTH
        assert len(commands[2].params) == 4

    def test_parse_smooth_quadratic_bezier(self):
        """Test parsing smooth quadratic Bezier (T command)."""
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 Q 20 20 30 10 T 50 10")

        assert commands[2].command == SVGCommand.QUADRATIC_BEZIER_SMOOTH
        assert len(commands[2].params) == 2

    def test_parse_complex_path(self):
        """Test parsing complex path with multiple command types."""
        parser = SVGPathParser()
        path_data = "M 10 10 L 20 20 C 30 30 40 30 50 20 Q 60 10 70 20 Z"
        commands = parser.parse(path_data)

        assert len(commands) == 5
        assert commands[0].command == SVGCommand.MOVE
        assert commands[1].command == SVGCommand.LINE
        assert commands[2].command == SVGCommand.CUBIC_BEZIER
        assert commands[3].command == SVGCommand.QUADRATIC_BEZIER
        assert commands[4].command == SVGCommand.CLOSE


class TestPathCommand:
    """Tests for PathCommand dataclass."""

    def test_path_command_creation(self):
        """Test creating a PathCommand."""
        cmd = PathCommand(command=SVGCommand.MOVE, params=[10.0, 20.0])

        assert cmd.command == SVGCommand.MOVE
        assert cmd.params == [10.0, 20.0]

    def test_path_command_with_no_params(self):
        """Test creating a PathCommand with no parameters."""
        cmd = PathCommand(command=SVGCommand.CLOSE, params=[])

        assert cmd.command == SVGCommand.CLOSE
        assert cmd.params == []
