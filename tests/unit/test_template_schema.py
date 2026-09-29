"""The committed template JSON Schema (issue #57, D3: generated, never hand-written)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

from holiday_card.core.data_paths import data_path
from holiday_card.core.models import Template
from holiday_card.core.template_schema import render_template_schema, template_json_schema

_COMMITTED = Path(__file__).resolve().parents[2] / "docs" / "template-schema.json"
_SHIPPED = sorted(data_path("templates").rglob("*.yaml"))


def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def test_committed_schema_matches_the_models() -> None:
    assert _COMMITTED.read_text() == render_template_schema(), (
        "docs/template-schema.json is stale: run "
        "`holiday-card schema -o docs/template-schema.json`"
    )


def test_rendered_schema_is_sorted_indented_json() -> None:
    text = render_template_schema()
    assert text.endswith("}\n")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    schema = template_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_shipped_templates_count() -> None:
    assert len(_SHIPPED) == 21


@pytest.mark.parametrize("path", _SHIPPED, ids=lambda p: p.stem)
def test_shipped_yaml_passes_model_validate(path: Path) -> None:
    Template.model_validate(_yaml(path))


@pytest.mark.parametrize("path", _SHIPPED, ids=lambda p: p.stem)
def test_shipped_yaml_passes_the_committed_json_schema(path: Path) -> None:
    # What an editor wired to docs/template-schema.json would check.
    schema = json.loads(_COMMITTED.read_text())
    jsonschema.validate(_yaml(path), schema, cls=jsonschema.Draft202012Validator)


class TestAliases:
    """``AliasChoices`` names are accepted by the loader, so the schema lists them."""

    @staticmethod
    def _line(**coords: float) -> dict[str, Any]:
        return {
            "id": "t",
            "name": "T",
            "occasion": "generic",
            "fold_type": "quarter_fold",
            "panels": [
                {
                    "position": "front",
                    "width": 4.25,
                    "height": 5.5,
                    "shape_elements": [{"type": "line", **coords}],
                }
            ],
        }

    def _errors(self, data: dict[str, Any]) -> list[str]:
        validator = jsonschema.Draft202012Validator(template_json_schema())
        return [e.message for e in validator.iter_errors(data)]

    def test_line_accepts_either_spelling(self) -> None:
        assert self._errors(self._line(x1=0, y1=0, x2=1, y2=1)) == []
        assert self._errors(self._line(start_x=0, start_y=0, end_x=1, end_y=1)) == []

    def test_line_still_requires_each_coordinate(self) -> None:
        assert self._errors(self._line(x1=0, y1=0, x2=1)) != []

    def test_pattern_angle_alias_is_listed(self) -> None:
        props = template_json_schema()["$defs"]["PatternFill"]["properties"]
        assert props["angle"] == props["rotation"]
