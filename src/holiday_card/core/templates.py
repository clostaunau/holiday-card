"""Template loading and discovery for holiday cards.

This module handles loading YAML template files and discovering
available templates in the templates directory.
"""

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from holiday_card.core.data_paths import data_path
from holiday_card.core.images import ImageSourceError, resolve_template_image_path
from holiday_card.core.models import Template

logger = logging.getLogger(__name__)


class TemplateNotFoundError(Exception):
    """Raised when a template cannot be found."""

    pass


class TemplateLoadError(Exception):
    """Raised when a template fails to load."""

    pass


def get_templates_dir() -> Path:
    """Return the templates directory (bundled, or ``HOLIDAY_CARD_TEMPLATES``)."""
    return data_path("templates")


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


def templates_with_photo_slots(templates_dir: Path | None = None) -> list[str]:
    """Return the sorted ids of templates with at least one photo ``slot``.

    Templates that fail to load are skipped (``discover_templates`` already
    lists what exists; ``validate`` reports why a template is broken).
    """
    ids: list[str] = []
    for info in discover_templates(templates_dir):
        try:
            template = load_template_from_file(Path(info["path"]))
        except TemplateLoadError as e:
            logger.debug(f"Skipping {info['path']}: {e}")
            continue
        if any(e.slot for p in template.panels for e in p.image_elements):
            ids.append(template.id)
    return sorted(ids)


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
        raise TemplateLoadError(f"Failed to read template file {path}: {e}") from e

    try:
        template = Template.model_validate(data)
    except ValidationError as e:
        raise TemplateLoadError(
            f"Failed to parse template {path}:\n{_format_validation_error(e)}"
        ) from e
    _resolve_image_paths(template, path)
    return template


def _resolve_image_paths(template: Template, path: Path) -> None:
    # D5: image paths are relative to the template file, never to cwd.
    errors: list[str] = []
    for p, panel in enumerate(template.panels):
        for i, image in enumerate(panel.image_elements):
            try:
                image.source_path = str(
                    resolve_template_image_path(image.source_path, path.parent)
                )
            except ImageSourceError as e:
                errors.append(f"  panels.{p}.image_elements.{i}.source_path: {e}")
    if errors:
        raise TemplateLoadError(f"Failed to parse template {path}:\n" + "\n".join(errors))


def _format_validation_error(error: ValidationError) -> str:
    # One line per error, keyed by its dotted location (e.g. ``panels.0.colr``).
    return "\n".join(
        f"  {'.'.join(str(part) for part in err['loc']) or '<root>'}: {err['msg']}"
        for err in error.errors()
    )
