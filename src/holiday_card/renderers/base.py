"""Base renderer protocol for card output generation.

This module defines the Renderer protocol that all output renderers must implement.
Following the Strategy pattern allows different backends (PDF, preview, etc.).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from holiday_card.core.models import Card, Panel, TextElement


@runtime_checkable
class Renderer(Protocol):
    """Protocol defining the interface for card renderers.

    All renderers must implement this protocol to ensure consistent
    behavior across different output formats (PDF, preview images, etc.).
    """

    def setup_canvas(self, width: float, height: float) -> None:
        """Initialize the rendering canvas.

        Args:
            width: Canvas width in inches.
            height: Canvas height in inches.
        """
        ...

    def render_panel(self, panel: Panel) -> None:
        """Render a single panel with its content.

        Args:
            panel: Panel to render with all its elements.
        """
        ...

    def render_text(self, text: TextElement, panel: Panel) -> None:
        """Render a text element within a panel.

        Args:
            text: Text element to render.
            panel: Parent panel for coordinate reference.
        """
        ...

    def draw_fold_lines(self, fold_type: str) -> None:
        """Draw fold guide lines on the canvas.

        Args:
            fold_type: Type of fold (half_fold, quarter_fold, tri_fold).
        """
        ...

    def save(self, path: Path) -> None:
        """Save the rendered output to a file.

        Args:
            path: Output file path.
        """
        ...


class BaseRenderer(ABC):
    """Abstract base class for renderers with common functionality.

    Provides shared implementation details while requiring subclasses
    to implement format-specific methods.
    """

    def __init__(self) -> None:
        """Initialize the renderer."""
        self._width: float = 0.0
        self._height: float = 0.0

    @abstractmethod
    def setup_canvas(self, width: float, height: float) -> None:
        """Initialize the rendering canvas."""
        self._width = width
        self._height = height

    @abstractmethod
    def render_panel(self, panel: Panel) -> None:
        """Render a single panel with its content."""
        pass

    @abstractmethod
    def render_text(self, text: TextElement, panel: Panel) -> None:
        """Render a text element within a panel."""
        pass

    @abstractmethod
    def draw_fold_lines(self, fold_type: str) -> None:
        """Draw fold guide lines on the canvas."""
        pass

    @abstractmethod
    def save(self, path: Path) -> None:
        """Save the rendered output to a file."""
        pass

    def render_card(self, card: Card) -> None:
        """Render a complete card with all panels.

        This is a template method that orchestrates the rendering process.

        Args:
            card: Card to render.
        """
        # Render each panel
        for panel in card.panels:
            self.render_panel(panel)

        # Draw fold lines based on card's fold type
        self.draw_fold_lines(card.fold_type.value)
