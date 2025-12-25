"""Core domain models for holiday card generation.

This module contains all Pydantic models representing the domain entities:
- Color: RGB color value object
- Enums: FoldType, OccasionType, PanelPosition, OverflowStrategy
- TextElement: Text with positioning and styling
- Panel: Card section with content
- Template: Pre-designed card layout
- Card: Complete card design
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, PrivateAttr, field_validator


class Color(BaseModel):
    """RGB color value object with validation.

    All color components must be in range 0.0 to 1.0.
    """

    r: float = Field(ge=0.0, le=1.0, description="Red component (0.0-1.0)")
    g: float = Field(ge=0.0, le=1.0, description="Green component (0.0-1.0)")
    b: float = Field(ge=0.0, le=1.0, description="Blue component (0.0-1.0)")

    def to_tuple(self) -> tuple[float, float, float]:
        """Convert to RGB tuple for ReportLab."""
        return (self.r, self.g, self.b)

    @classmethod
    def from_hex(cls, hex_color: str) -> "Color":
        """Create Color from hex string (e.g., '#FF0000' or 'FF0000')."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            raise ValueError(f"Invalid hex color: {hex_color}")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return cls(r=r, g=g, b=b)

    def to_hex(self) -> str:
        """Convert to hex string."""
        return f"#{int(self.r * 255):02x}{int(self.g * 255):02x}{int(self.b * 255):02x}"


# Pre-defined colors for convenience
class Colors:
    """Common colors used in card designs."""

    WHITE = Color(r=1.0, g=1.0, b=1.0)
    BLACK = Color(r=0.0, g=0.0, b=0.0)
    RED = Color(r=0.8, g=0.1, b=0.1)
    GREEN = Color(r=0.2, g=0.5, b=0.2)
    BLUE = Color(r=0.1, g=0.3, b=0.7)
    GOLD = Color(r=1.0, g=0.84, b=0.0)
    SILVER = Color(r=0.75, g=0.75, b=0.75)


class FoldType(str, Enum):
    """Card fold format types.

    Each fold type defines how the 8.5" x 11" paper is folded:
    - half_fold: Single horizontal fold (5.5" x 8.5" when folded)
    - quarter_fold: Two folds - horizontal and vertical (4.25" x 5.5" when folded)
    - tri_fold: Two vertical folds (3.67" x 8.5" panels)
    """

    HALF_FOLD = "half_fold"
    QUARTER_FOLD = "quarter_fold"
    TRI_FOLD = "tri_fold"


class OccasionType(str, Enum):
    """Types of occasions for card templates and themes."""

    CHRISTMAS = "christmas"
    HANUKKAH = "hanukkah"
    BIRTHDAY = "birthday"
    GENERIC = "generic"
    NEW_YEAR = "new_year"
    THANKSGIVING = "thanksgiving"


class PanelPosition(str, Enum):
    """Position identifiers for card panels.

    Different fold types use different panels:
    - Half-fold: front, back, inside_left, inside_right
    - Quarter-fold: front, back, inside_left, inside_right
    - Tri-fold: left, center, right (uses LEFT, CENTER, RIGHT values)
    """

    FRONT = "front"
    BACK = "back"
    INSIDE_LEFT = "inside_left"
    INSIDE_RIGHT = "inside_right"
    CENTER = "center"  # For tri-fold


class TextAlignment(str, Enum):
    """Text alignment options."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class FontStyle(str, Enum):
    """Font style options."""

    NORMAL = "normal"
    BOLD = "bold"
    ITALIC = "italic"
    BOLD_ITALIC = "bold_italic"


class BorderStyle(str, Enum):
    """Border style options."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    DECORATIVE = "decorative"


class OverflowStrategy(str, Enum):
    """Strategy for handling text that exceeds designated boundaries.

    - AUTO: Automatically select best strategy based on text characteristics
    - SHRINK: Reduce font size until text fits (minimum 8pt)
    - WRAP: Break text into multiple lines
    - TRUNCATE: Cut off text with ellipsis (existing behavior)
    """

    AUTO = "auto"
    SHRINK = "shrink"
    WRAP = "wrap"
    TRUNCATE = "truncate"


class Border(BaseModel):
    """Border styling for panels and elements.

    All dimensions are in points for ReportLab compatibility.
    """

    style: BorderStyle = Field(default=BorderStyle.SOLID, description="Border style")
    width: float = Field(default=1.0, ge=0.0, le=10.0, description="Border width in points")
    color: Color = Field(default_factory=lambda: Color(r=0.0, g=0.0, b=0.0), description="Border color")
    corner_radius: float = Field(default=0.0, ge=0.0, description="Corner radius in points")


class AdjustmentResult(BaseModel):
    """Result of text overflow adjustment.

    Used for debugging, logging, and future preview warnings.
    """

    was_adjusted: bool = Field(
        description="Whether any adjustment was applied"
    )
    strategy_applied: OverflowStrategy = Field(
        description="Strategy that was used"
    )
    original_font_size: int = Field(
        ge=6, le=144,
        description="Original font size in points"
    )
    final_font_size: int = Field(
        ge=6, le=144,
        description="Final font size after adjustment"
    )
    lines_used: int = Field(
        ge=1,
        description="Number of lines in final rendering"
    )
    content_truncated: bool = Field(
        default=False,
        description="Whether content was truncated"
    )


class ImageElement(BaseModel):
    """Image content with positioning and scaling.

    Positions are relative to the panel, in inches.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_path: str = Field(description="Path to source image file")
    x: float = Field(ge=0.0, description="X position in inches from panel left")
    y: float = Field(ge=0.0, description="Y position in inches from panel bottom")
    width: Optional[float] = Field(default=None, ge=0.0, description="Image width in inches")
    height: Optional[float] = Field(default=None, ge=0.0, description="Image height in inches")
    preserve_aspect: bool = Field(default=True, description="Maintain aspect ratio when scaling")
    rotation: float = Field(default=0.0, description="Rotation in degrees")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Image opacity (0-1)")


class TextElement(BaseModel):
    """Text content with positioning and styling.

    Positions are relative to the panel, in inches.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=1, max_length=1000, description="Text content")
    x: float = Field(ge=0.0, description="X position in inches from panel left")
    y: float = Field(ge=0.0, description="Y position in inches from panel bottom")
    width: Optional[float] = Field(default=None, ge=0.0, description="Max width for text wrapping")
    font_family: str = Field(default="Helvetica", description="Font family name")
    font_size: int = Field(default=12, ge=6, le=144, description="Font size in points")
    font_style: FontStyle = Field(default=FontStyle.NORMAL, description="Font style")
    color: Optional[Color] = Field(default=None, description="Text color (uses theme if None)")
    alignment: TextAlignment = Field(default=TextAlignment.LEFT, description="Text alignment")
    rotation: float = Field(default=0.0, description="Rotation in degrees")

    # Overflow prevention fields
    overflow_strategy: OverflowStrategy = Field(
        default=OverflowStrategy.AUTO,
        description="Strategy for handling text overflow"
    )
    max_lines: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum lines when using WRAP strategy (None = unlimited)"
    )
    min_font_size: int = Field(
        default=8,
        ge=6,
        le=72,
        description="Minimum font size for SHRINK strategy (points)"
    )

    # Private field for adjustment tracking (not serialized to YAML)
    _adjustment_applied: Optional[AdjustmentResult] = PrivateAttr(default=None)

    def get_adjustment_result(self) -> Optional[AdjustmentResult]:
        """Get the overflow adjustment that was applied during rendering.

        Returns None if not yet rendered or no adjustment needed.
        """
        return self._adjustment_applied

    def set_adjustment_result(self, result: AdjustmentResult) -> None:
        """Internal use: Record adjustment result during rendering."""
        self._adjustment_applied = result


class Panel(BaseModel):
    """A distinct section of the card.

    Each panel has its own position, dimensions, and content.
    Positions are in inches from the page origin (bottom-left).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    position: PanelPosition = Field(description="Panel position identifier")
    x: float = Field(ge=0.0, description="X position in inches from page left")
    y: float = Field(ge=0.0, description="Y position in inches from page bottom")
    width: float = Field(gt=0.0, description="Panel width in inches")
    height: float = Field(gt=0.0, description="Panel height in inches")
    rotation: float = Field(default=0.0, description="Rotation in degrees (for quarter-fold)")
    background_color: Optional[Color] = Field(default=None, description="Panel background color")
    background_image: Optional[str] = Field(default=None, description="Path to background image")
    border: Optional[Border] = Field(default=None, description="Panel border styling")
    text_elements: list[TextElement] = Field(default_factory=list, description="Text on panel")
    image_elements: list[ImageElement] = Field(default_factory=list, description="Images on panel")


class Template(BaseModel):
    """Pre-designed card layout with placeholder areas.

    Templates define the structure and default content for a card design.
    """

    id: str = Field(description="Unique template identifier")
    name: str = Field(min_length=1, max_length=50, description="Display name")
    occasion: OccasionType = Field(description="Occasion type")
    fold_type: FoldType = Field(description="Default fold type")
    default_theme_id: Optional[str] = Field(default=None, description="Default theme ID")
    panels: list[Panel] = Field(description="Panel configurations")
    description: Optional[str] = Field(default=None, description="Template description")
    preview_image: Optional[str] = Field(default=None, description="Path to preview image")

    @field_validator("panels")
    @classmethod
    def validate_panels(cls, v: list[Panel]) -> list[Panel]:
        """Ensure at least one panel exists."""
        if not v:
            raise ValueError("Template must have at least one panel")
        return v


class Theme(BaseModel):
    """Color theme for coordinated card styling.

    Themes define a set of colors that work well together
    for a cohesive card design.
    """

    id: str = Field(description="Unique theme identifier")
    name: str = Field(min_length=1, max_length=50, description="Display name")
    occasion: OccasionType = Field(description="Occasion this theme is designed for")
    primary: Color = Field(description="Primary accent color")
    secondary: Color = Field(description="Secondary accent color")
    background: Color = Field(default_factory=lambda: Color(r=1.0, g=1.0, b=1.0), description="Background color")
    text: Color = Field(default_factory=lambda: Color(r=0.0, g=0.0, b=0.0), description="Text color")
    accent: Optional[Color] = Field(default=None, description="Optional tertiary accent")
    description: Optional[str] = Field(default=None, description="Theme description")


class Card(BaseModel):
    """The complete greeting card design.

    A card is created from a template and can be customized with
    different themes, messages, and images.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1, max_length=100, description="User-friendly card name")
    template_id: str = Field(description="Reference to base template")
    fold_type: FoldType = Field(description="Card fold type")
    theme_id: Optional[str] = Field(default=None, description="Override theme")
    panels: list[Panel] = Field(description="Panel configurations")
    output_path: Optional[Path] = Field(default=None, description="Target PDF file path")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last modification")

    @field_validator("panels")
    @classmethod
    def validate_panels(cls, v: list[Panel]) -> list[Panel]:
        """Ensure at least one panel exists."""
        if not v:
            raise ValueError("Card must have at least one panel")
        return v

    def model_post_init(self, __context: object) -> None:
        """Update timestamp on any change."""
        self.updated_at = datetime.now()
