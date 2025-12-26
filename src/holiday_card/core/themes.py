"""Theme loading and discovery for holiday cards.

This module handles loading YAML theme files and discovering
available themes in the themes directory.
"""

import logging
import os
from pathlib import Path

import yaml

from holiday_card.core.models import Color, OccasionType, Theme

logger = logging.getLogger(__name__)


class ThemeNotFoundError(Exception):
    """Raised when a theme cannot be found."""

    pass


class ThemeLoadError(Exception):
    """Raised when a theme fails to load."""

    pass


def get_themes_dir() -> Path:
    """Get the path to the themes directory.

    Returns:
        Path to themes directory.
    """
    # Check environment variable first
    env_path = os.environ.get("HOLIDAY_CARD_THEMES")
    if env_path:
        return Path(env_path)

    # Default to themes/ in project root
    # Walk up from this file to find project root
    current = Path(__file__).parent
    while current != current.parent:
        themes_path = current / "themes"
        if themes_path.exists():
            return themes_path
        current = current.parent

    # Fallback to relative path from cwd
    return Path("themes")


def discover_themes(themes_dir: Path | None = None) -> list[dict[str, str]]:
    """Discover all available themes.

    Args:
        themes_dir: Path to themes directory. Uses default if None.

    Returns:
        List of theme info dicts with 'id', 'name', 'occasion', 'description'.
    """
    if themes_dir is None:
        themes_dir = get_themes_dir()

    if not themes_dir.exists():
        return []

    themes = []

    # Scan for YAML files
    for theme_file in themes_dir.glob("*.yaml"):
        try:
            with open(theme_file) as f:
                data = yaml.safe_load(f)
                # Each file can contain multiple themes
                theme_list = data.get("themes", [data])
                for theme_data in theme_list:
                    themes.append({
                        "id": theme_data.get("id", theme_file.stem),
                        "name": theme_data.get("name", theme_file.stem),
                        "occasion": theme_data.get("occasion", "generic"),
                        "description": theme_data.get("description", ""),
                    })
        except (yaml.YAMLError, KeyError, TypeError, OSError) as e:
            logger.warning(f"Skipping invalid theme file {theme_file}: {e}")
            continue

    return themes


def load_theme(theme_id: str, themes_dir: Path | None = None) -> Theme:
    """Load a theme by ID.

    Args:
        theme_id: Theme identifier (e.g., 'christmas-red-green').
        themes_dir: Path to themes directory. Uses default if None.

    Returns:
        Loaded Theme object.

    Raises:
        ThemeNotFoundError: If theme not found.
        ThemeLoadError: If theme fails to load.
    """
    if themes_dir is None:
        themes_dir = get_themes_dir()

    # Search for theme in YAML files
    for theme_file in themes_dir.glob("*.yaml"):
        try:
            with open(theme_file) as f:
                data = yaml.safe_load(f)
                # Each file can contain multiple themes
                theme_list = data.get("themes", [data])
                for theme_data in theme_list:
                    if theme_data.get("id") == theme_id:
                        return _parse_theme(theme_data)
        except (yaml.YAMLError, OSError) as e:
            logger.debug(f"Skipping {theme_file} during search: {e}")
            continue

    raise ThemeNotFoundError(f"Theme not found: {theme_id}")


def _parse_theme(data: dict) -> Theme:
    """Parse theme data into a Theme object.

    Args:
        data: Raw theme data from YAML.

    Returns:
        Parsed Theme object.
    """
    return Theme(
        id=data["id"],
        name=data["name"],
        occasion=OccasionType(data.get("occasion", "generic")),
        primary=_parse_color(data["primary"]),
        secondary=_parse_color(data["secondary"]),
        background=_parse_color(data.get("background", {"r": 1.0, "g": 1.0, "b": 1.0})),
        text=_parse_color(data.get("text", {"r": 0.0, "g": 0.0, "b": 0.0})),
        accent=_parse_color(data["accent"]) if "accent" in data else None,
        description=data.get("description"),
    )


def _parse_color(data: dict) -> Color:
    """Parse color data into a Color object.

    Args:
        data: Color data dict with r, g, b keys.

    Returns:
        Parsed Color object.
    """
    return Color(r=data["r"], g=data["g"], b=data["b"])
