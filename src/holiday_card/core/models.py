"""Core domain models for holiday card generation.

This module contains all Pydantic models representing the domain entities:
- Color: RGB color value object
- Enums: FoldType, OccasionType, PanelPosition, OverflowStrategy, ShapeType
- TextElement: Text with positioning and styling
- ImageElement: Image with positioning and scaling
- Shape: Vector graphics primitives (Rectangle, Circle, Triangle, Star, Line)
- DecorativeElement: Reusable shape compositions
- Panel: Card section with content
- Template: Pre-designed card layout
- Card: Complete card design
"""

from datetime import datetime

__all__ = [
    # Value objects
    "Color",
    "Colors",
    "Border",
    "AdjustmentResult",
    # Enums
    "FoldType",
    "OccasionType",
    "PanelPosition",
    "TextAlignment",
    "FontStyle",
    "BorderStyle",
    "OverflowStrategy",
    "ShapeType",
    "PatternType",
    # Content elements
    "ImageElement",
    "TextElement",
    # Shapes
    "BaseShape",
    "Rectangle",
    "Circle",
    "Triangle",
    "Star",
    "Line",
    "SVGPath",
    "DecorativeElement",
    "Shape",
    # Fill styles
    "ColorStop",
    "SolidFill",
    "LinearGradientFill",
    "RadialGradientFill",
    "PatternFill",
    "FillStyle",
    # Clip masks
    "CircleClipMask",
    "RectangleClipMask",
    "EllipseClipMask",
    "StarClipMask",
    "SVGPathClipMask",
    "ClipMask",
    # Card structure
    "Panel",
    "Template",
    "Theme",
    "Card",
]
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal
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


class ShapeType(str, Enum):
    """Vector shape types for discriminated union.

    Used as the discriminator field for shape polymorphism in Pydantic.
    """

    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    STAR = "star"
    LINE = "line"
    SVG_PATH = "svg_path"  # T001: Add SVG_PATH enum value
    DECORATIVE_ELEMENT = "decorative_element"


class PatternType(str, Enum):
    """Pattern fill types for repeating patterns.

    - STRIPES: Parallel lines with configurable width and angle
    - DOTS: Polka dots with configurable spacing and size
    - GRID: Perpendicular lines forming a grid
    - CHECKERBOARD: Alternating squares
    """

    STRIPES = "stripes"
    DOTS = "dots"
    GRID = "grid"
    CHECKERBOARD = "checkerboard"


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


# Fill Style Models (Phase 2: Foundational)

class ColorStop(BaseModel):
    """A color stop within a gradient.

    Defines a color at a specific position along the gradient.
    """

    position: float = Field(ge=0.0, le=1.0, description="Position along gradient (0.0=start, 1.0=end)")
    color: str = Field(description="Color as hex string (#RRGGBB)")

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#"):
            v = f"#{v}"
        if len(v) != 7:
            raise ValueError(f"Hex color must be 7 characters (#RRGGBB), got: {v}")
        try:
            int(v[1:], 16)  # Validate hex digits
        except ValueError:
            raise ValueError(f"Invalid hex color: {v}")
        return v


class SolidFill(BaseModel):
    """Solid color fill."""

    type: Literal["solid"] = "solid"
    color: str = Field(description="Fill color as hex string (#RRGGBB)")

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format."""
        if not v.startswith("#"):
            v = f"#{v}"
        if len(v) != 7:
            raise ValueError(f"Hex color must be 7 characters (#RRGGBB), got: {v}")
        try:
            int(v[1:], 16)
        except ValueError:
            raise ValueError(f"Invalid hex color: {v}")
        return v


class LinearGradientFill(BaseModel):
    """Linear gradient fill with color stops.

    Gradient transitions smoothly between color stops along a line
    defined by the angle parameter.
    """

    type: Literal["linear_gradient"] = "linear_gradient"
    angle: float = Field(default=0.0, ge=0.0, lt=360.0, description="Gradient angle in degrees (0=horizontal right)")
    stops: list[ColorStop] = Field(min_length=2, max_length=20, description="Color stops (minimum 2)")

    @field_validator("stops")
    @classmethod
    def validate_stops_ascending(cls, v: list[ColorStop]) -> list[ColorStop]:
        """Ensure color stops are in ascending position order."""
        positions = [stop.position for stop in v]
        if positions != sorted(positions):
            raise ValueError("Color stops must be in ascending position order")
        return v


class RadialGradientFill(BaseModel):
    """Radial gradient fill with color stops.

    Gradient radiates from a center point outward through the color stops.
    """

    type: Literal["radial_gradient"] = "radial_gradient"
    center_x: float = Field(default=0.5, ge=0.0, le=1.0, description="Center X position (0.0-1.0 relative to shape)")
    center_y: float = Field(default=0.5, ge=0.0, le=1.0, description="Center Y position (0.0-1.0 relative to shape)")
    radius: float = Field(default=0.5, gt=0.0, le=1.0, description="Gradient radius (relative to shape size)")
    stops: list[ColorStop] = Field(min_length=2, max_length=20, description="Color stops (minimum 2)")

    @field_validator("stops")
    @classmethod
    def validate_stops_ascending(cls, v: list[ColorStop]) -> list[ColorStop]:
        """Ensure color stops are in ascending position order."""
        positions = [stop.position for stop in v]
        if positions != sorted(positions):
            raise ValueError("Color stops must be in ascending position order")
        return v


class PatternFill(BaseModel):
    """Repeating pattern fill.

    Creates decorative repeating patterns like stripes, dots, grid, or checkerboard.
    """

    type: Literal["pattern"] = "pattern"
    pattern_type: PatternType = Field(description="Pattern type (stripes, dots, grid, checkerboard)")
    colors: list[str] = Field(min_length=1, max_length=4, description="Pattern colors as hex strings")
    spacing: float = Field(default=0.25, gt=0.0, le=2.0, description="Pattern spacing in inches")
    scale: float = Field(default=1.0, gt=0.0, le=5.0, description="Pattern scale multiplier")
    rotation: float = Field(default=0.0, ge=0.0, lt=360.0, description="Pattern rotation in degrees")

    @field_validator("colors")
    @classmethod
    def validate_hex_colors(cls, v: list[str]) -> list[str]:
        """Validate all colors are valid hex strings."""
        validated = []
        for color in v:
            if not color.startswith("#"):
                color = f"#{color}"
            if len(color) != 7:
                raise ValueError(f"Hex color must be 7 characters (#RRGGBB), got: {color}")
            try:
                int(color[1:], 16)
            except ValueError:
                raise ValueError(f"Invalid hex color: {color}")
            validated.append(color)
        return validated


# Discriminated union for fill styles
FillStyle = Annotated[
    SolidFill | LinearGradientFill | RadialGradientFill | PatternFill,
    Field(discriminator='type')
]


# Clip Mask Models (Phase 2: Foundational)

class CircleClipMask(BaseModel):
    """Circular clipping mask for images."""

    type: Literal["circle"] = "circle"
    center_x: float = Field(ge=0.0, description="Center X position in inches (relative to image)")
    center_y: float = Field(ge=0.0, description="Center Y position in inches (relative to image)")
    radius: float = Field(gt=0.0, description="Circle radius in inches")


class RectangleClipMask(BaseModel):
    """Rectangular clipping mask for images."""

    type: Literal["rectangle"] = "rectangle"
    x: float = Field(ge=0.0, description="X position in inches (relative to image)")
    y: float = Field(ge=0.0, description="Y position in inches (relative to image)")
    width: float = Field(gt=0.0, description="Width in inches")
    height: float = Field(gt=0.0, description="Height in inches")


class EllipseClipMask(BaseModel):
    """Elliptical clipping mask for images."""

    type: Literal["ellipse"] = "ellipse"
    center_x: float = Field(ge=0.0, description="Center X position in inches (relative to image)")
    center_y: float = Field(ge=0.0, description="Center Y position in inches (relative to image)")
    radius_x: float = Field(gt=0.0, description="Horizontal radius in inches")
    radius_y: float = Field(gt=0.0, description="Vertical radius in inches")


class StarClipMask(BaseModel):
    """Star-shaped clipping mask for images."""

    type: Literal["star"] = "star"
    center_x: float = Field(ge=0.0, description="Center X position in inches (relative to image)")
    center_y: float = Field(ge=0.0, description="Center Y position in inches (relative to image)")
    outer_radius: float = Field(gt=0.0, description="Outer point radius in inches")
    inner_radius: float = Field(gt=0.0, description="Inner point radius in inches")
    points: int = Field(default=5, ge=3, le=20, description="Number of star points")

    @field_validator("inner_radius")
    @classmethod
    def validate_inner_smaller_than_outer(cls, v: float, info) -> float:
        """Ensure inner radius is smaller than outer radius."""
        if "outer_radius" in info.data and v >= info.data["outer_radius"]:
            raise ValueError(f"inner_radius ({v}) must be less than outer_radius ({info.data['outer_radius']})")
        return v


class SVGPathClipMask(BaseModel):
    """SVG path clipping mask for images.

    Uses SVG path data to define custom clipping shapes.
    Path must be closed (end with Z command).
    """

    type: Literal["svg_path"] = "svg_path"
    path_data: str = Field(min_length=1, description="SVG path data string (must be closed path)")
    scale: float = Field(default=1.0, gt=0.0, le=10.0, description="Path scale multiplier")

    @field_validator("path_data")
    @classmethod
    def validate_closed_path(cls, v: str) -> str:
        """Ensure path is closed (ends with Z or z)."""
        v = v.strip()
        if not (v.endswith('Z') or v.endswith('z')):
            raise ValueError("SVG path for clipping mask must be closed (end with Z or z)")
        return v


# Discriminated union for clip masks
ClipMask = Annotated[
    CircleClipMask | RectangleClipMask | EllipseClipMask | StarClipMask | SVGPathClipMask,
    Field(discriminator='type')
]


class ImageElement(BaseModel):
    """Image content with positioning and scaling.

    Positions are relative to the panel, in inches.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_path: str = Field(description="Path to source image file")
    x: float = Field(ge=0.0, description="X position in inches from panel left")
    y: float = Field(ge=0.0, description="Y position in inches from panel bottom")
    width: float | None = Field(default=None, ge=0.0, description="Image width in inches")
    height: float | None = Field(default=None, ge=0.0, description="Image height in inches")
    preserve_aspect: bool = Field(default=True, description="Maintain aspect ratio when scaling")
    rotation: float = Field(default=0.0, description="Rotation in degrees")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Image opacity (0-1)")
    z_index: int = Field(default=100, description="Rendering layer (higher = on top)")
    clip_mask: ClipMask | None = Field(default=None, description="Optional clipping mask")  # T018


class TextElement(BaseModel):
    """Text content with positioning and styling.

    Positions are relative to the panel, in inches.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(min_length=1, max_length=1000, description="Text content")
    x: float = Field(ge=0.0, description="X position in inches from panel left")
    y: float = Field(ge=0.0, description="Y position in inches from panel bottom")
    width: float | None = Field(default=None, ge=0.0, description="Max width for text wrapping")
    font_family: str = Field(default="Helvetica", description="Font family name")
    font_size: int = Field(default=12, ge=6, le=144, description="Font size in points")
    font_style: FontStyle = Field(default=FontStyle.NORMAL, description="Font style")
    color: Color | None = Field(default=None, description="Text color (uses theme if None)")
    alignment: TextAlignment = Field(default=TextAlignment.LEFT, description="Text alignment")
    rotation: float = Field(default=0.0, description="Rotation in degrees")
    z_index: int = Field(default=100, description="Rendering layer (higher = on top)")

    # Overflow prevention fields
    overflow_strategy: OverflowStrategy = Field(
        default=OverflowStrategy.AUTO,
        description="Strategy for handling text overflow"
    )
    max_lines: int | None = Field(
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
    _adjustment_applied: AdjustmentResult | None = PrivateAttr(default=None)

    def get_adjustment_result(self) -> AdjustmentResult | None:
        """Get the overflow adjustment that was applied during rendering.

        Returns None if not yet rendered or no adjustment needed.
        """
        return self._adjustment_applied

    def set_adjustment_result(self, result: AdjustmentResult) -> None:
        """Internal use: Record adjustment result during rendering."""
        self._adjustment_applied = result


# Vector Graphics Shape Models

class BaseShape(BaseModel):
    """Base model for all vector graphics shapes.

    Provides common properties: position, styling, layering.
    All measurements in inches except stroke_width (points).
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique shape identifier")
    type: ShapeType = Field(description="Shape type discriminator")
    z_index: int = Field(default=0, description="Rendering layer (higher = on top)")
    fill_color: str | None = Field(default=None, description="Fill color as hex string (#RRGGBB) - legacy support")
    stroke_color: str | None = Field(default=None, description="Stroke color as hex string (#RRGGBB)")
    stroke_width: float = Field(default=0.0, ge=0.0, description="Stroke width in points")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Opacity 0.0-1.0")
    rotation: float = Field(default=0.0, ge=0.0, lt=360.0, description="Rotation in degrees")
    fill: FillStyle | None = Field(default=None, description="Fill style (solid, gradient, or pattern)")  # T017

    @field_validator("fill_color", "stroke_color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        """Validate hex color format."""
        if v is None:
            return v
        if not v.startswith("#"):
            v = f"#{v}"
        if len(v) != 7:
            raise ValueError(f"Hex color must be 7 characters (#RRGGBB), got: {v}")
        try:
            int(v[1:], 16)  # Validate hex digits
        except ValueError:
            raise ValueError(f"Invalid hex color: {v}")
        return v


class Rectangle(BaseShape):
    """Rectangle shape with position and dimensions."""

    type: Literal[ShapeType.RECTANGLE] = ShapeType.RECTANGLE
    x: float = Field(ge=0.0, description="X position in inches from panel left")
    y: float = Field(ge=0.0, description="Y position in inches from panel bottom")
    width: float = Field(gt=0.0, description="Width in inches")
    height: float = Field(gt=0.0, description="Height in inches")


class Circle(BaseShape):
    """Circle shape with center and radius."""

    type: Literal[ShapeType.CIRCLE] = ShapeType.CIRCLE
    center_x: float = Field(ge=0.0, description="Center X position in inches")
    center_y: float = Field(ge=0.0, description="Center Y position in inches")
    radius: float = Field(gt=0.0, description="Radius in inches")


class Triangle(BaseShape):
    """Triangle shape with three vertices."""

    type: Literal[ShapeType.TRIANGLE] = ShapeType.TRIANGLE
    x1: float = Field(ge=0.0, description="Vertex 1 X position in inches")
    y1: float = Field(ge=0.0, description="Vertex 1 Y position in inches")
    x2: float = Field(ge=0.0, description="Vertex 2 X position in inches")
    y2: float = Field(ge=0.0, description="Vertex 2 Y position in inches")
    x3: float = Field(ge=0.0, description="Vertex 3 X position in inches")
    y3: float = Field(ge=0.0, description="Vertex 3 Y position in inches")


class Star(BaseShape):
    """Star shape with configurable points."""

    type: Literal[ShapeType.STAR] = ShapeType.STAR
    center_x: float = Field(ge=0.0, description="Center X position in inches")
    center_y: float = Field(ge=0.0, description="Center Y position in inches")
    outer_radius: float = Field(gt=0.0, description="Outer point radius in inches")
    inner_radius: float = Field(gt=0.0, description="Inner point radius in inches")
    points: int = Field(default=5, ge=3, le=20, description="Number of star points")

    @field_validator("inner_radius")
    @classmethod
    def validate_inner_smaller_than_outer(cls, v: float, info) -> float:
        """Ensure inner radius is smaller than outer radius."""
        if "outer_radius" in info.data and v >= info.data["outer_radius"]:
            raise ValueError(f"inner_radius ({v}) must be less than outer_radius ({info.data['outer_radius']})")
        return v


class Line(BaseShape):
    """Line shape with start and end points."""

    type: Literal[ShapeType.LINE] = ShapeType.LINE
    start_x: float = Field(ge=0.0, description="Start X position in inches")
    start_y: float = Field(ge=0.0, description="Start Y position in inches")
    end_x: float = Field(ge=0.0, description="End X position in inches")
    end_y: float = Field(ge=0.0, description="End Y position in inches")


class SVGPath(BaseShape):
    """SVG path shape for complex vector graphics.

    Supports SVG path data containing move, line, curve, arc, and close commands.
    Path data uses inches for coordinates.
    """

    type: Literal[ShapeType.SVG_PATH] = ShapeType.SVG_PATH
    path_data: str = Field(min_length=1, description="SVG path data string (M, L, C, Q, A, Z commands)")
    scale: float = Field(default=1.0, gt=0.0, le=10.0, description="Path scale multiplier")

    @field_validator("path_data")
    @classmethod
    def validate_path_syntax(cls, v: str) -> str:
        """Basic validation of SVG path syntax."""
        v = v.strip()
        if not v:
            raise ValueError("SVG path data cannot be empty")
        # Check for at least one valid SVG command
        valid_commands = set('MmLlHhVvCcSsQqTtAaZz')
        if not any(c in valid_commands for c in v):
            raise ValueError("SVG path must contain at least one valid command (M, L, C, Q, A, Z)")
        return v


class DecorativeElement(BaseModel):
    """Reusable composition of shapes forming a design unit.

    Examples: Christmas tree, ornament, gift box.
    Supports position, scale, rotation, and color customization.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique element identifier")
    type: Literal[ShapeType.DECORATIVE_ELEMENT] = ShapeType.DECORATIVE_ELEMENT
    name: str = Field(description="Decorative element name (references library)")
    x: float = Field(ge=0.0, description="Anchor X position in inches")
    y: float = Field(ge=0.0, description="Anchor Y position in inches")
    scale: float = Field(default=1.0, gt=0.0, description="Proportional scale multiplier")
    rotation: float = Field(default=0.0, ge=0.0, lt=360.0, description="Rotation in degrees")
    color_palette: dict[str, str] | None = Field(default=None, description="Color role overrides")
    z_index: int = Field(default=0, description="Rendering layer (higher = on top)")


# Discriminated union for all shape types
Shape = Annotated[
    Rectangle | Circle | Triangle | Star | Line | SVGPath | DecorativeElement,
    Field(discriminator='type')
]


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
    background_color: Color | None = Field(default=None, description="Panel background color")
    background_image: str | None = Field(default=None, description="Path to background image")
    border: Border | None = Field(default=None, description="Panel border styling")
    text_elements: list[TextElement] = Field(default_factory=list, description="Text on panel")
    image_elements: list[ImageElement] = Field(default_factory=list, description="Images on panel")
    shape_elements: list[Shape] = Field(default_factory=list, description="Vector shapes and decorative elements")


class Template(BaseModel):
    """Pre-designed card layout with placeholder areas.

    Templates define the structure and default content for a card design.
    """

    id: str = Field(description="Unique template identifier")
    name: str = Field(min_length=1, max_length=50, description="Display name")
    occasion: OccasionType = Field(description="Occasion type")
    fold_type: FoldType = Field(description="Default fold type")
    default_theme_id: str | None = Field(default=None, description="Default theme ID")
    panels: list[Panel] = Field(description="Panel configurations")
    description: str | None = Field(default=None, description="Template description")
    preview_image: str | None = Field(default=None, description="Path to preview image")

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
    accent: Color | None = Field(default=None, description="Optional tertiary accent")
    description: str | None = Field(default=None, description="Theme description")


class Card(BaseModel):
    """The complete greeting card design.

    A card is created from a template and can be customized with
    different themes, messages, and images.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1, max_length=100, description="User-friendly card name")
    template_id: str = Field(description="Reference to base template")
    fold_type: FoldType = Field(description="Card fold type")
    theme_id: str | None = Field(default=None, description="Override theme")
    panels: list[Panel] = Field(description="Panel configurations")
    output_path: Path | None = Field(default=None, description="Target PDF file path")
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
