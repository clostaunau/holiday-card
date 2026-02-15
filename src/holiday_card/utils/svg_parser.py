"""SVG path data parser for vector graphics.

This module provides parsing of SVG path data strings into structured command lists
that can be rendered using ReportLab's path API.

Supported SVG commands:
- M/m: Move to
- L/l, H/h, V/v: Line to
- C/c, S/s: Cubic Bezier curve
- Q/q, T/t: Quadratic Bezier curve
- A/a: Elliptical arc
- Z/z: Close path
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SVGCommand(str, Enum):
    """SVG path command types."""

    MOVE = "M"
    MOVE_REL = "m"
    LINE = "L"
    LINE_REL = "l"
    HORIZONTAL = "H"
    HORIZONTAL_REL = "h"
    VERTICAL = "V"
    VERTICAL_REL = "v"
    CUBIC_BEZIER = "C"
    CUBIC_BEZIER_REL = "c"
    CUBIC_BEZIER_SMOOTH = "S"
    CUBIC_BEZIER_SMOOTH_REL = "s"
    QUADRATIC_BEZIER = "Q"
    QUADRATIC_BEZIER_REL = "q"
    QUADRATIC_BEZIER_SMOOTH = "T"
    QUADRATIC_BEZIER_SMOOTH_REL = "t"
    ARC = "A"
    ARC_REL = "a"
    CLOSE = "Z"
    CLOSE_REL = "z"


@dataclass
class PathCommand:
    """A single SVG path command with parameters."""

    command: SVGCommand
    params: list[float]


class SVGPathParser:
    """Parser for SVG path data strings.

    Converts SVG path data (d attribute) into a list of structured commands
    that can be rendered using ReportLab's canvas.Path API.

    Example:
        parser = SVGPathParser()
        commands = parser.parse("M 10 10 L 20 20 Z")
        # Returns list of PathCommand objects
    """

    # Regular expression to match SVG commands and their parameters
    COMMAND_PATTERN = re.compile(r'([MmLlHhVvCcSsQqTtAaZz])')
    NUMBER_PATTERN = re.compile(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?')

    def parse(self, path_data: str) -> list[PathCommand]:
        """Parse SVG path data string into command list.

        Args:
            path_data: SVG path data string (e.g., "M 10 10 L 20 20 Z")

        Returns:
            List of PathCommand objects

        Raises:
            ValueError: If path data contains invalid syntax
        """
        path_data = path_data.strip()
        if not path_data:
            raise ValueError("SVG path data cannot be empty")

        commands = []
        # Split path data into command segments
        segments = self.COMMAND_PATTERN.split(path_data)
        segments = [s.strip() for s in segments if s.strip()]

        i = 0
        while i < len(segments):
            if not self._is_command(segments[i]):
                raise ValueError(f"Expected command, got: {segments[i]}")

            command_char = segments[i]
            i += 1

            # Get parameters for this command (if any)
            params = []
            if i < len(segments) and not self._is_command(segments[i]):
                params = self._parse_numbers(segments[i])
                i += 1

            # Parse the command with its parameters
            try:
                cmd = self._parse_command(command_char, params)
                commands.append(cmd)
            except ValueError as e:
                # Graceful degradation: log warning and skip unsupported command
                logger.warning(f"Skipping unsupported SVG command '{command_char}': {e}")
                continue

        return commands

    def _is_command(self, s: str) -> bool:
        """Check if string is a single SVG command character."""
        return len(s) == 1 and s in 'MmLlHhVvCcSsQqTtAaZz'

    def _parse_numbers(self, param_str: str) -> list[float]:
        """Extract numbers from parameter string.

        Args:
            param_str: String containing space or comma-separated numbers

        Returns:
            List of float values
        """
        matches = self.NUMBER_PATTERN.findall(param_str)
        return [float(m) for m in matches]

    def _parse_command(self, command_char: str, params: list[float]) -> PathCommand:
        """Parse a single command with its parameters.

        Args:
            command_char: Single letter command (M, L, C, etc.)
            params: List of numeric parameters

        Returns:
            PathCommand object

        Raises:
            ValueError: If command is unsupported or has wrong parameter count
        """
        try:
            command = SVGCommand(command_char)
        except ValueError:
            raise ValueError(f"Unknown SVG command: {command_char}")

        # Validate parameter count for each command type
        expected_params = self._get_expected_param_count(command)
        if expected_params is not None and len(params) != expected_params:
            # Some commands allow multiple sets of parameters
            if len(params) % expected_params != 0:
                raise ValueError(
                    f"Command {command_char} expects {expected_params} parameters, "
                    f"got {len(params)}"
                )

        return PathCommand(command=command, params=params)

    def _get_expected_param_count(self, command: SVGCommand) -> int | None:
        """Get expected parameter count for a command.

        Args:
            command: SVG command type

        Returns:
            Number of expected parameters, or None if variable
        """
        param_counts = {
            SVGCommand.MOVE: 2,
            SVGCommand.MOVE_REL: 2,
            SVGCommand.LINE: 2,
            SVGCommand.LINE_REL: 2,
            SVGCommand.HORIZONTAL: 1,
            SVGCommand.HORIZONTAL_REL: 1,
            SVGCommand.VERTICAL: 1,
            SVGCommand.VERTICAL_REL: 1,
            SVGCommand.CUBIC_BEZIER: 6,
            SVGCommand.CUBIC_BEZIER_REL: 6,
            SVGCommand.CUBIC_BEZIER_SMOOTH: 4,
            SVGCommand.CUBIC_BEZIER_SMOOTH_REL: 4,
            SVGCommand.QUADRATIC_BEZIER: 4,
            SVGCommand.QUADRATIC_BEZIER_REL: 4,
            SVGCommand.QUADRATIC_BEZIER_SMOOTH: 2,
            SVGCommand.QUADRATIC_BEZIER_SMOOTH_REL: 2,
            SVGCommand.ARC: 7,
            SVGCommand.ARC_REL: 7,
            SVGCommand.CLOSE: 0,
            SVGCommand.CLOSE_REL: 0,
        }
        return param_counts.get(command)
