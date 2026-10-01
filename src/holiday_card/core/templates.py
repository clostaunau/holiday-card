"""Template loading and discovery for holiday cards.

This module handles loading YAML template files and discovering the
templates on the layered search path (:func:`template_search_path`):
``HOLIDAY_CARD_TEMPLATES`` entries, then the XDG user dir, then the
bundled templates. :func:`resolve_template` is the one resolver for a
template reference, whether an id or a file path (#79).
"""

import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from holiday_card.core.data_paths import data_path
from holiday_card.core.errors import UnsupportedFeatureError
from holiday_card.core.images import ImageSourceError, resolve_template_image_path
from holiday_card.core.imposition import letter_slot
from holiday_card.core.models import Template

logger = logging.getLogger(__name__)


class TemplateNotFoundError(Exception):
    """Raised when a template cannot be found."""

    pass


class TemplateLoadError(Exception):
    """Raised when a template fails to load.

    ``problems`` holds every ``(path, message)`` found, e.g.
    ``("panels[0].text_elements[0].colr", "Extra inputs are not permitted")``;
    a file that can't be read or parsed as YAML is one ``"<file>"`` problem.
    """

    def __init__(self, message: str, problems: Sequence[tuple[str, str]] = ()) -> None:
        super().__init__(message)
        self.problems = list(problems)


def _load_error(path: Path, problems: list[tuple[str, str]]) -> TemplateLoadError:
    lines = "\n".join(f"  {loc}: {message}" for loc, message in problems)
    return TemplateLoadError(f"Failed to parse template {path}:\n{lines}", problems)


TEMPLATES_ENV_VAR = "HOLIDAY_CARD_TEMPLATES"
_TEMPLATE_SUFFIXES = (".yaml", ".yml")


def user_templates_dir() -> Path:
    """Return the user template layer: ``$XDG_DATA_HOME/holiday-card/templates``.

    ``XDG_DATA_HOME`` unset or empty falls back to ``~/.local/share``.
    """
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "holiday-card" / "templates"


def template_search_path() -> list[tuple[str, Path]]:
    """Ordered (source, dir) layers; earlier wins. Sources: "env", "user", "builtin".

    Each ``os.pathsep``-separated entry of ``HOLIDAY_CARD_TEMPLATES`` comes
    first, then :func:`user_templates_dir`, then the bundled templates. Like
    ``PATH``, a layer that doesn't exist is skipped by the searches.
    """
    layers: list[tuple[str, Path]] = [
        ("env", Path(entry).expanduser())
        for entry in os.environ.get(TEMPLATES_ENV_VAR, "").split(os.pathsep)
        if entry
    ]
    layers.append(("user", user_templates_dir()))
    layers.append(("builtin", data_path("templates")))
    return layers


def _layers(templates_dir: Path | None) -> list[tuple[str, Path]]:
    # An explicit dir (tests, the microsite) is the only layer searched.
    return template_search_path() if templates_dir is None else [("dir", templates_dir)]


def _layer_files(directory: Path) -> list[Path]:
    # Any depth, so a user layer needs no occasion subfolder.
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.rglob("*") if p.suffix in _TEMPLATE_SUFFIXES and p.is_file()
    )


def _read_mapping(path: Path) -> dict[str, Any] | None:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Skipping invalid template {path}: {e}")
        return None
    if not isinstance(data, dict):
        logger.warning(f"Skipping invalid template {path}: not a YAML mapping")
        return None
    return data


def discover_templates(templates_dir: Path | None = None) -> list[dict[str, str]]:
    """Discover the templates on the search path.

    Args:
        templates_dir: Search only this directory. Uses
            :func:`template_search_path` if None.

    Returns:
        One info dict per template id with 'id', 'name', 'occasion' (from the
        YAML), 'fold_type', 'description', 'path' and 'source' (the layer it
        came from). A template that shadows the same id in a later layer is
        listed once, with 'shadows' naming that layer.
    """
    found: dict[str, dict[str, str]] = {}
    for source, directory in _layers(templates_dir):
        for template_file in _layer_files(directory):
            data = _read_mapping(template_file)
            if data is None:
                continue
            template_id = str(data.get("id", template_file.stem))
            if template_id in found:
                found[template_id].setdefault("shadows", source)
                continue
            found[template_id] = {
                "id": template_id,
                "name": str(data.get("name", template_file.stem)),
                "occasion": str(data.get("occasion", "")),
                "fold_type": str(data.get("fold_type", "half_fold")),
                "description": str(data.get("description", "")),
                "path": str(template_file),
                "source": source,
            }
    return list(found.values())


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


def is_template_path(ref: str) -> bool:
    """Whether ``ref`` names a file rather than a template id.

    True when it ends with ``.yaml``/``.yml``, contains a path separator, or
    starts with ``.`` or ``~``.
    """
    return (
        ref.endswith(_TEMPLATE_SUFFIXES)
        or os.sep in ref
        or "/" in ref
        or ref.startswith((".", "~"))
    )


def resolve_template(
    ref: str, *, templates_dir: Path | None = None
) -> tuple[Template, Path]:
    """Path-like ref (endswith .yaml/.yml, or contains os.sep / '/', or starts with '.' or '~')
    → load_template_from_file(expanduser(ref)); missing file → TemplateNotFoundError naming the path.
    Otherwise → search template_search_path() by id, then by filename stem.

    ``templates_dir`` replaces the search path with that one directory. The
    returned path is the absolute path of the loaded file.

    Raises:
        TemplateNotFoundError: no file at the path, or no layer has the id.
        TemplateLoadError: the file was found but doesn't load.
    """
    if is_template_path(ref):
        path = Path(ref).expanduser()
        if not path.is_file():
            raise TemplateNotFoundError(f"Template not found: {ref}")
        path = path.resolve()
        return load_template_from_file(path), path

    files = [f for _, directory in _layers(templates_dir) for f in _layer_files(directory)]
    for template_file in files:
        data = _read_mapping(template_file)
        if data is not None and data.get("id") == ref:
            return load_template_from_file(template_file), template_file
    for template_file in files:
        if template_file.stem == ref:
            return load_template_from_file(template_file), template_file
    raise TemplateNotFoundError(f"Template not found: {ref}")


def load_template(template_id: str, templates_dir: Path | None = None) -> Template:
    """Load a template by id (or path); see :func:`resolve_template`."""
    return resolve_template(template_id, templates_dir=templates_dir)[0]


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
        raise TemplateLoadError(
            f"Failed to read template file {path}: {e}", [("<file>", str(e))]
        ) from e

    try:
        template = Template.model_validate(data)
    except ValidationError as e:
        raise _load_error(path, _validation_problems(e)) from e
    _check_panel_coordinates(template, data, path)
    _resolve_image_paths(template, path)
    return template


def _check_panel_coordinates(template: Template, data: Any, path: Path) -> None:
    # D6: panel x/y/rotation are computed from fold_type. A YAML that still
    # sets them is accepted only when it agrees with the computed slot.
    raw_panels = data.get("panels") if isinstance(data, dict) else None
    if not isinstance(raw_panels, list):
        return
    errors: list[tuple[str, str]] = []
    for index, (raw, panel) in enumerate(zip(raw_panels, template.panels, strict=False)):
        if not isinstance(raw, dict):
            continue
        try:
            slot = letter_slot(template.fold_type, panel.position)
        except UnsupportedFeatureError:
            continue  # no letter imposition to disagree with
        computed = {"x": slot.x_in, "y": slot.y_in, "rotation": slot.rotation_deg % 360.0}
        given = {"x": panel.x, "y": panel.y, "rotation": panel.rotation % 360.0}
        mismatched = [
            f"{key}={given[key]} (computed {computed[key]})"
            for key in ("x", "y", "rotation")
            if key in raw and abs(given[key] - computed[key]) > 1e-9
        ]
        if mismatched:
            errors.append(
                (
                    f"panels[{index}] ({panel.position.value})",
                    f"{', '.join(mismatched)}; "
                    f"delete x/y/rotation; imposition is computed from fold_type",
                )
            )
    if errors:
        raise _load_error(path, errors)


def _resolve_image_paths(template: Template, path: Path) -> None:
    # D5: image paths are relative to the template file, never to cwd.
    errors: list[tuple[str, str]] = []
    for p, panel in enumerate(template.panels):
        if panel.background_image is not None:
            try:
                panel.background_image = str(
                    resolve_template_image_path(panel.background_image, path.parent)
                )
            except ImageSourceError as e:
                errors.append((f"panels[{p}].background_image", str(e)))
        for i, image in enumerate(panel.image_elements):
            try:
                image.source_path = str(
                    resolve_template_image_path(image.source_path, path.parent)
                )
            except ImageSourceError as e:
                errors.append((f"panels[{p}].image_elements[{i}].source_path", str(e)))
    if errors:
        raise _load_error(path, errors)


def _validation_problems(error: ValidationError) -> list[tuple[str, str]]:
    # One problem per error, keyed by its location (e.g. ``panels[0].colr``).
    return [(_format_loc(err["loc"]), err["msg"]) for err in error.errors()]


def _format_loc(loc: tuple[int | str, ...]) -> str:
    text = "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in loc)
    return text.removeprefix(".") or "<root>"
