"""The template JSON Schema, generated from the Pydantic models (#57, D3).

``holiday-card schema`` prints :func:`render_template_schema`; the committed
copy is ``docs/template-schema.json`` (a test keeps it in sync). Editors such
as VS Code YAML use it to complete and check template files.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, get_args

from pydantic import AliasChoices, BaseModel

from holiday_card.core.models import Template

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def template_json_schema() -> dict[str, Any]:
    """Return ``Template.model_json_schema()`` plus the loader's alias names.

    Pydantic lists only the first spelling of an ``AliasChoices`` field
    (``Line.start_x``, not ``x1``), and with ``additionalProperties: false``
    an editor would then flag templates the loader accepts. Every spelling
    is listed with the same schema, and a required field needs any one of
    them.
    """
    schema = Template.model_json_schema()
    defs = schema.get("$defs", {})
    for model in _reachable_models(Template):
        target = schema if model is Template else defs.get(model.__name__)
        if target is not None:
            _add_alias_choices(model, target)
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


def render_template_schema() -> str:
    """The schema as indented, key-sorted JSON with a trailing newline."""
    return json.dumps(template_json_schema(), indent=2, sort_keys=True) + "\n"


def _reachable_models(root: type[BaseModel]) -> Iterator[type[BaseModel]]:
    seen: set[type[BaseModel]] = set()
    stack = [root]
    while stack:
        model = stack.pop()
        if model in seen:
            continue
        seen.add(model)
        yield model
        for field in model.model_fields.values():
            stack.extend(_model_types(field.annotation))


def _model_types(annotation: Any) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for arg in get_args(annotation):
        yield from _model_types(arg)


def _add_alias_choices(model: type[BaseModel], target: dict[str, Any]) -> None:
    properties: dict[str, Any] = target.get("properties", {})
    for field in model.model_fields.values():
        alias = field.validation_alias
        if not isinstance(alias, AliasChoices):
            continue
        names = [choice for choice in alias.choices if isinstance(choice, str)]
        primary = names[0]
        for other in names[1:]:
            properties[other] = dict(properties[primary])
        required: list[str] = target.get("required", [])
        if primary in required:
            required.remove(primary)
            target.setdefault("allOf", []).append(
                {"anyOf": [{"required": [name]} for name in names]}
            )
            if not required:
                del target["required"]
