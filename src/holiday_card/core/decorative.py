"""Decorative element library management.

This module provides loading and management of pre-built decorative elements
(Christmas trees, ornaments, gift boxes, etc.) composed of basic shapes.
"""

import logging
import os
from pathlib import Path

import yaml

from holiday_card.core.models import DecorativeElement

logger = logging.getLogger(__name__)


class DecorativeElementDefinition:
    """Definition of a decorative element from the library.

    Decorative elements are compositions of basic shapes that can be
    reused and customized with position, scale, rotation, and color palettes.
    """

    def __init__(
        self,
        name: str,
        description: str,
        default_width: float,
        default_height: float,
        color_roles: dict[str, str],
        shapes: list
    ):
        """Initialize decorative element definition.

        Args:
            name: Unique element name
            description: Human-readable description
            default_width: Default width in inches
            default_height: Default height in inches
            color_roles: Default color palette (role -> hex color)
            shapes: List of shape definitions
        """
        self.name = name
        self.description = description
        self.default_width = default_width
        self.default_height = default_height
        self.color_roles = color_roles
        self.shapes = shapes


class DecorativeElementLibrary:
    """Library of pre-built decorative elements.

    Loads decorative element definitions from YAML files and provides
    methods to instantiate them with custom positioning, scaling, and colors.
    """

    def __init__(self, library_path: Path | None = None):
        """Initialize the decorative element library.

        Args:
            library_path: Path to decorative elements directory.
                         Defaults to decorative_elements/ in package.
        """
        if library_path is None:
            # Default to project's decorative_elements directory
            # First try relative to package (src/holiday_card)
            package_dir = Path(__file__).parent.parent.parent
            library_path = package_dir / "decorative_elements"

            # If not found, try project root
            if not library_path.exists():
                project_root = package_dir.parent
                library_path = project_root / "decorative_elements"

        self.library_path = library_path
        self.definitions: dict[str, DecorativeElementDefinition] = {}

        # Load library if path exists
        if self.library_path.exists():
            self.load_library()

    def load_library(self) -> None:
        """Load all decorative element definitions from library directory."""
        if not self.library_path.exists():
            return

        # Find all YAML files recursively
        for yaml_file in self.library_path.glob("**/*.yaml"):
            try:
                definition = self._load_definition(yaml_file)
                self.definitions[definition.name] = definition
            except (yaml.YAMLError, KeyError, TypeError, OSError) as e:
                logger.warning(f"Failed to load decorative element {yaml_file}: {e}")

    def _load_definition(self, yaml_path: Path) -> DecorativeElementDefinition:
        """Load a decorative element definition from YAML file.

        Args:
            yaml_path: Path to YAML definition file

        Returns:
            DecorativeElementDefinition instance
        """
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        return DecorativeElementDefinition(
            name=data['name'],
            description=data.get('description', ''),
            default_width=data['default_width'],
            default_height=data['default_height'],
            color_roles=data['color_roles'],
            shapes=data['shapes']
        )

    def get_definition(self, name: str) -> DecorativeElementDefinition:
        """Get decorative element definition by name.

        Args:
            name: Element name

        Returns:
            DecorativeElementDefinition

        Raises:
            ValueError: If element not found
        """
        if name not in self.definitions:
            available = ', '.join(self.definitions.keys())
            raise ValueError(
                f"Decorative element '{name}' not found in library. "
                f"Available: {available}"
            )
        return self.definitions[name]

    def resolve_colors(
        self,
        definition: DecorativeElementDefinition,
        color_palette: dict[str, str] | None = None
    ) -> list:
        """Resolve color palette placeholders in shapes.

        Replaces {role} placeholders in fill_color and stroke_color
        with actual hex colors from the palette.

        Args:
            definition: Decorative element definition
            color_palette: Optional color overrides (role -> hex color)

        Returns:
            List of shape dictionaries with resolved colors
        """
        # Build final palette (defaults + overrides)
        palette = definition.color_roles.copy()
        if color_palette:
            palette.update(color_palette)

        resolved_shapes = []
        for shape_data in definition.shapes:
            shape_copy = shape_data.copy()

            # Resolve fill_color
            if 'fill_color' in shape_copy and isinstance(shape_copy['fill_color'], str):
                fill = shape_copy['fill_color']
                if fill.startswith('{') and fill.endswith('}'):
                    role = fill.strip('{}')
                    shape_copy['fill_color'] = palette.get(role, fill)

            # Resolve stroke_color
            if 'stroke_color' in shape_copy and isinstance(shape_copy['stroke_color'], str):
                stroke = shape_copy['stroke_color']
                if stroke.startswith('{') and stroke.endswith('}'):
                    role = stroke.strip('{}')
                    shape_copy['stroke_color'] = palette.get(role, stroke)

            resolved_shapes.append(shape_copy)

        return resolved_shapes

    def apply_transforms(
        self,
        shapes: list,
        element: DecorativeElement
    ) -> list:
        """Apply scale and position transforms to shapes.

        Args:
            shapes: List of shape dictionaries
            element: DecorativeElement instance with transforms

        Returns:
            List of transformed shape dictionaries
        """
        transformed = []

        for shape_data in shapes:
            shape_copy = shape_data.copy()

            # Apply scale to all dimensions and positions
            scale = element.scale

            if shape_copy['type'] == 'rectangle':
                shape_copy['x'] = shape_copy['x'] * scale + element.x
                shape_copy['y'] = shape_copy['y'] * scale + element.y
                shape_copy['width'] = shape_copy['width'] * scale
                shape_copy['height'] = shape_copy['height'] * scale

            elif shape_copy['type'] == 'circle':
                shape_copy['center_x'] = shape_copy['center_x'] * scale + element.x
                shape_copy['center_y'] = shape_copy['center_y'] * scale + element.y
                shape_copy['radius'] = shape_copy['radius'] * scale

            elif shape_copy['type'] == 'triangle':
                shape_copy['x1'] = shape_copy['x1'] * scale + element.x
                shape_copy['y1'] = shape_copy['y1'] * scale + element.y
                shape_copy['x2'] = shape_copy['x2'] * scale + element.x
                shape_copy['y2'] = shape_copy['y2'] * scale + element.y
                shape_copy['x3'] = shape_copy['x3'] * scale + element.x
                shape_copy['y3'] = shape_copy['y3'] * scale + element.y

            elif shape_copy['type'] == 'star':
                shape_copy['center_x'] = shape_copy['center_x'] * scale + element.x
                shape_copy['center_y'] = shape_copy['center_y'] * scale + element.y
                shape_copy['outer_radius'] = shape_copy['outer_radius'] * scale
                shape_copy['inner_radius'] = shape_copy['inner_radius'] * scale

            elif shape_copy['type'] == 'line':
                shape_copy['start_x'] = shape_copy['start_x'] * scale + element.x
                shape_copy['start_y'] = shape_copy['start_y'] * scale + element.y
                shape_copy['end_x'] = shape_copy['end_x'] * scale + element.x
                shape_copy['end_y'] = shape_copy['end_y'] * scale + element.y

            # Add element rotation to shape rotation
            current_rotation = shape_copy.get('rotation', 0.0)
            shape_copy['rotation'] = (current_rotation + element.rotation) % 360

            # Inherit z_index from element if not specified
            if 'z_index' not in shape_copy:
                shape_copy['z_index'] = element.z_index

            transformed.append(shape_copy)

        return transformed

    def expand_element(
        self,
        element: DecorativeElement
    ) -> list:
        """Expand a decorative element into its component shapes.

        Resolves colors, applies transforms, and returns a list of
        basic shapes ready for rendering.

        Args:
            element: DecorativeElement to expand

        Returns:
            List of basic shape instances
        """
        # Get definition
        definition = self.get_definition(element.name)

        # Resolve colors
        shapes_data = self.resolve_colors(definition, element.color_palette)

        # Apply transforms
        shapes_data = self.apply_transforms(shapes_data, element)

        # Convert to shape model instances
        from pydantic import TypeAdapter

        from holiday_card.core.models import Shape

        shapes = []
        for shape_data in shapes_data:
            # Parse using Pydantic discriminated union
            adapter = TypeAdapter(Shape)
            shape = adapter.validate_python(shape_data)
            shapes.append(shape)

        return shapes


# Global library instance
_library: DecorativeElementLibrary | None = None


def get_library() -> DecorativeElementLibrary:
    """Get the global decorative element library instance.

    Returns:
        DecorativeElementLibrary singleton
    """
    global _library
    if _library is None:
        # Check for custom library path from environment
        custom_path = os.environ.get('HOLIDAY_CARD_DECORATIVE_PATH')
        if custom_path:
            _library = DecorativeElementLibrary(Path(custom_path))
        else:
            _library = DecorativeElementLibrary()
    return _library
