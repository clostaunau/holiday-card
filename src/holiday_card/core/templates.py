"""Template loading and discovery for holiday cards.

This module handles loading YAML template files and discovering
available templates in the templates directory.
"""

import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

from holiday_card.core.models import (
    Circle,
    Color,
    ColorStop,
    DecorativeElement,
    FoldType,
    Line,
    LinearGradientFill,
    OccasionType,
    Panel,
    PanelPosition,
    PatternFill,
    PatternType,
    RadialGradientFill,
    Rectangle,
    SolidFill,
    Star,
    SVGPath,
    Template,
    TextElement,
    Triangle,
)


class TemplateNotFoundError(Exception):
    """Raised when a template cannot be found."""

    pass


class TemplateLoadError(Exception):
    """Raised when a template fails to load."""

    pass


def get_templates_dir() -> Path:
    """Get the path to the templates directory.

    Returns:
        Path to templates directory.
    """
    # Check environment variable first
    env_path = os.environ.get("HOLIDAY_CARD_TEMPLATES")
    if env_path:
        return Path(env_path)

    # Default to templates/ in project root
    # Walk up from this file to find project root
    current = Path(__file__).parent
    while current != current.parent:
        templates_path = current / "templates"
        if templates_path.exists():
            return templates_path
        current = current.parent

    # Fallback to relative path from cwd
    return Path("templates")


def discover_templates(templates_dir: Path | None = None) -> list[dict[str, str]]:
    """Discover all available templates.

    Args:
        templates_dir: Path to templates directory. Uses default if None.

    Returns:
        List of template info dicts with 'id', 'name', 'occasion', 'path'.
    """
    if templates_dir is None:
        templates_dir = get_templates_dir()

    if not templates_dir.exists():
        return []

    templates = []

    # Scan for YAML files in occasion subdirectories
    for occasion_dir in templates_dir.iterdir():
        if occasion_dir.is_dir():
            occasion = occasion_dir.name
            for template_file in occasion_dir.glob("*.yaml"):
                try:
                    with open(template_file) as f:
                        data = yaml.safe_load(f)
                        templates.append({
                            "id": data.get("id", template_file.stem),
                            "name": data.get("name", template_file.stem),
                            "occasion": occasion,
                            "fold_type": data.get("fold_type", "half_fold"),
                            "description": data.get("description", ""),
                            "path": str(template_file),
                        })
                except (yaml.YAMLError, KeyError, TypeError, OSError) as e:
                    logger.warning(f"Skipping invalid template {template_file}: {e}")
                    continue

    return templates


def load_template(template_id: str, templates_dir: Path | None = None) -> Template:
    """Load a template by ID.

    Args:
        template_id: Template identifier (e.g., 'christmas-classic').
        templates_dir: Path to templates directory. Uses default if None.

    Returns:
        Loaded Template object.

    Raises:
        TemplateNotFoundError: If template not found.
        TemplateLoadError: If template fails to load.
    """
    if templates_dir is None:
        templates_dir = get_templates_dir()

    # Search for template file
    template_path = None
    for occasion_dir in templates_dir.iterdir():
        if occasion_dir.is_dir():
            for yaml_file in occasion_dir.glob("*.yaml"):
                try:
                    with open(yaml_file) as f:
                        data = yaml.safe_load(f)
                        if data.get("id") == template_id:
                            template_path = yaml_file
                            break
                except (yaml.YAMLError, OSError) as e:
                    logger.debug(f"Skipping {yaml_file} during search: {e}")
                    continue
        if template_path:
            break

    # Also check by filename
    if not template_path:
        for occasion_dir in templates_dir.iterdir():
            if occasion_dir.is_dir():
                possible_path = occasion_dir / f"{template_id}.yaml"
                if possible_path.exists():
                    template_path = possible_path
                    break

    if not template_path:
        raise TemplateNotFoundError(f"Template not found: {template_id}")

    return load_template_from_file(template_path)


def load_template_from_file(path: Path) -> Template:
    """Load a template from a YAML file.

    Args:
        path: Path to template YAML file.

    Returns:
        Loaded Template object.

    Raises:
        TemplateLoadError: If template fails to load.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        raise TemplateLoadError(f"Failed to read template file {path}: {e}")

    try:
        return _parse_template(data)
    except (KeyError, ValueError, TypeError) as e:
        raise TemplateLoadError(f"Failed to parse template {path}: {e}")


def _parse_template(data: dict) -> Template:
    """Parse template data into a Template object.

    Args:
        data: Raw template data from YAML.

    Returns:
        Parsed Template object.
    """
    panels = []
    for panel_data in data.get("panels", []):
        panel = _parse_panel(panel_data)
        panels.append(panel)

    return Template(
        id=data["id"],
        name=data["name"],
        occasion=OccasionType(data["occasion"]),
        fold_type=FoldType(data["fold_type"]),
        default_theme_id=data.get("default_theme_id"),
        panels=panels,
        description=data.get("description"),
        preview_image=data.get("preview_image"),
    )


def _parse_panel(data: dict) -> Panel:
    """Parse panel data into a Panel object.

    Args:
        data: Raw panel data from YAML.

    Returns:
        Parsed Panel object.
    """
    text_elements = []
    for text_data in data.get("text_elements", []):
        text = _parse_text_element(text_data)
        text_elements.append(text)

    # Parse shape elements using Pydantic's discriminated union
    shape_elements = []
    for shape_data in data.get("shape_elements", []):
        shape = _parse_shape_element(shape_data)
        if shape:
            shape_elements.append(shape)

    background_color = None
    if "background_color" in data:
        bg = data["background_color"]
        background_color = Color(r=bg["r"], g=bg["g"], b=bg["b"])

    return Panel(
        id=data.get("id", ""),
        position=PanelPosition(data["position"]),
        x=data["x"],
        y=data["y"],
        width=data["width"],
        height=data["height"],
        rotation=data.get("rotation", 0.0),
        background_color=background_color,
        background_image=data.get("background_image"),
        text_elements=text_elements,
        shape_elements=shape_elements,
    )


def _parse_text_element(data: dict) -> TextElement:
    """Parse text element data into a TextElement object.

    Args:
        data: Raw text element data from YAML.

    Returns:
        Parsed TextElement object.
    """
    from holiday_card.core.models import OverflowStrategy, TextAlignment

    color = None
    if "color" in data:
        c = data["color"]
        color = Color(r=c["r"], g=c["g"], b=c["b"])

    # Parse overflow strategy if provided
    overflow_strategy = OverflowStrategy.AUTO
    if "overflow_strategy" in data:
        overflow_strategy = OverflowStrategy(data["overflow_strategy"])

    # Parse alignment if provided
    alignment = TextAlignment.LEFT
    if "alignment" in data:
        alignment = TextAlignment(data["alignment"])

    return TextElement(
        id=data.get("id", ""),
        content=data.get("content", data.get("default_content", "")),
        x=data["x"],
        y=data["y"],
        width=data.get("width"),
        font_family=data.get("font_family", "Helvetica"),
        font_size=data.get("font_size", 12),
        color=color,
        alignment=alignment,
        overflow_strategy=overflow_strategy,
        min_font_size=data.get("min_font_size", 8),
        max_lines=data.get("max_lines"),
    )


def _parse_fill_style(
    data: dict | None,
) -> SolidFill | LinearGradientFill | RadialGradientFill | PatternFill | None:
    """Parse fill style data into appropriate fill object.

    Args:
        data: Raw fill data from YAML with 'type' discriminator.

    Returns:
        Parsed fill object (SolidFill, LinearGradientFill,
        RadialGradientFill, or PatternFill), or None if invalid.
    """
    if not data:
        return None

    fill_type = data.get("type")
    if not fill_type:
        return None

    try:
        if fill_type == "solid":
            return SolidFill(color=data["color"])

        elif fill_type == "linear_gradient":
            stops = [
                ColorStop(position=s["position"], color=s["color"])
                for s in data["stops"]
            ]
            return LinearGradientFill(
                angle=data.get("angle", 0.0),
                stops=stops
            )

        elif fill_type == "radial_gradient":
            stops = [
                ColorStop(position=s["position"], color=s["color"])
                for s in data["stops"]
            ]
            return RadialGradientFill(
                center_x=data.get("center_x", 0.5),
                center_y=data.get("center_y", 0.5),
                radius=data.get("radius", 0.5),
                stops=stops
            )

        elif fill_type == "pattern":
            return PatternFill(
                pattern_type=PatternType(data["pattern_type"]),
                colors=data["colors"],
                spacing=data.get("spacing", 0.25),
                scale=data.get("scale", 1.0),
                rotation=data.get("rotation", data.get("angle", 0.0))  # Support both
            )
        else:
            logger.warning(f"Unknown fill type: {fill_type}")
            return None

    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Could not parse fill style: {e}")
        return None


def _parse_shape_element(
    data: dict,
) -> Rectangle | Circle | Triangle | Star | Line | SVGPath | DecorativeElement | None:
    """Parse shape element data into appropriate Shape object.

    Uses Pydantic's discriminated union based on 'type' field.

    Args:
        data: Raw shape element data from YAML.

    Returns:
        Parsed shape object (Rectangle, Circle, Triangle, Star, Line, or DecorativeElement),
        or None if the shape type is unknown or parsing fails.
    """
    shape_type = data.get("type")
    if not shape_type:
        return None

    # Parse fill style if present
    fill_obj = _parse_fill_style(data.get("fill"))

    try:
        if shape_type == "rectangle":
            return Rectangle(
                x=data["x"],
                y=data["y"],
                width=data["width"],
                height=data["height"],
                fill_color=data.get("fill_color"),
                fill=fill_obj,
                stroke_color=data.get("stroke_color"),
                stroke_width=data.get("stroke_width", 0),
                opacity=data.get("opacity", 1.0),
                rotation=data.get("rotation", 0),
                z_index=data.get("z_index", 0),
            )
        elif shape_type == "circle":
            return Circle(
                center_x=data["center_x"],
                center_y=data["center_y"],
                radius=data["radius"],
                fill_color=data.get("fill_color"),
                fill=fill_obj,
                stroke_color=data.get("stroke_color"),
                stroke_width=data.get("stroke_width", 0),
                opacity=data.get("opacity", 1.0),
                rotation=data.get("rotation", 0),
                z_index=data.get("z_index", 0),
            )
        elif shape_type == "triangle":
            return Triangle(
                x1=data["x1"],
                y1=data["y1"],
                x2=data["x2"],
                y2=data["y2"],
                x3=data["x3"],
                y3=data["y3"],
                fill_color=data.get("fill_color"),
                fill=fill_obj,
                stroke_color=data.get("stroke_color"),
                stroke_width=data.get("stroke_width", 0),
                opacity=data.get("opacity", 1.0),
                rotation=data.get("rotation", 0),
                z_index=data.get("z_index", 0),
            )
        elif shape_type == "star":
            return Star(
                center_x=data["center_x"],
                center_y=data["center_y"],
                outer_radius=data["outer_radius"],
                inner_radius=data["inner_radius"],
                points=data.get("points", 5),
                fill_color=data.get("fill_color"),
                fill=fill_obj,
                stroke_color=data.get("stroke_color"),
                stroke_width=data.get("stroke_width", 0),
                opacity=data.get("opacity", 1.0),
                rotation=data.get("rotation", 0),
                z_index=data.get("z_index", 0),
            )
        elif shape_type == "svg_path":
            return SVGPath(
                path_data=data["path_data"],
                scale=data.get("scale", 1.0),
                fill_color=data.get("fill_color"),
                fill=fill_obj,
                stroke_color=data.get("stroke_color"),
                stroke_width=data.get("stroke_width", 0),
                opacity=data.get("opacity", 1.0),
                rotation=data.get("rotation", 0),
                z_index=data.get("z_index", 0),
            )
        elif shape_type == "line":
            return Line(
                start_x=data.get("start_x", data.get("x1")),
                start_y=data.get("start_y", data.get("y1")),
                end_x=data.get("end_x", data.get("x2")),
                end_y=data.get("end_y", data.get("y2")),
                stroke_color=data.get("stroke_color", "#000000"),
                stroke_width=data.get("stroke_width", 1),
                opacity=data.get("opacity", 1.0),
                z_index=data.get("z_index", 0),
            )
        elif shape_type == "decorative_element":
            return DecorativeElement(
                name=data["name"],
                x=data["x"],
                y=data["y"],
                scale=data.get("scale", 1.0),
                rotation=data.get("rotation", 0),
                z_index=data.get("z_index", 0),
                color_palette=data.get("color_palette", {}),
            )
        else:
            return None
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Could not parse shape element: {e}")
        return None
