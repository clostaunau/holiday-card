"""Template loading goes through ``Template.model_validate`` with ``extra="forbid"``.

Issue #56: the hand-written YAML parser used to drop any field it did not
list (SVGPath ``x``/``y``, text ``z_index``, panel ``border`` ...) and turn
malformed shapes/fills into silently-skipped ``None``s. These tests pin the
fail-loud contract: every unknown key or type is a ``TemplateLoadError``
naming the offending key path.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from holiday_card.cli.commands import app
from holiday_card.core.models import Line, PatternFill, SVGPath
from holiday_card.core.templates import (
    TemplateLoadError,
    discover_templates,
    load_template,
    load_template_from_file,
)

_BASE: dict[str, Any] = {
    "id": "t-minimal",
    "name": "Minimal",
    "occasion": "generic",
    "fold_type": "half_fold",
    "panels": [
        {
            "id": "front",
            "position": "front",
            "x": 4.25,
            "y": 0,
            "width": 4.25,
            "height": 5.5,
            "text_elements": [{"id": "greeting", "content": "Hi", "x": 0.5, "y": 1.0}],
            "shape_elements": [
                {
                    "type": "rectangle",
                    "x": 0.1,
                    "y": 0.1,
                    "width": 1.0,
                    "height": 1.0,
                    "fill": {"type": "solid", "color": "#FF0000"},
                }
            ],
        }
    ],
}


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "t.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def _base() -> dict[str, Any]:
    return copy.deepcopy(_BASE)


def test_minimal_template_loads(tmp_path: Path) -> None:
    template = load_template_from_file(_write(tmp_path, _base()))
    assert template.panels[0].text_elements[0].content == "Hi"


@pytest.mark.parametrize(
    ("mutate", "expected_loc"),
    [
        (lambda d: d.update(colour="red"), "colour"),
        (lambda d: d["panels"][0].update(bordr=1), "panels.0.bordr"),
        (
            lambda d: d["panels"][0]["text_elements"][0].update(colr="#fff"),
            "panels.0.text_elements.0.colr",
        ),
        (
            lambda d: d["panels"][0]["shape_elements"][0].update(fill_colr="#fff"),
            "panels.0.shape_elements.0.rectangle.fill_colr",
        ),
        (
            lambda d: d["panels"][0]["shape_elements"][0]["fill"].update(shade=1),
            "panels.0.shape_elements.0.rectangle.fill.solid.shade",
        ),
    ],
    ids=["template", "panel", "text", "shape", "fill"],
)
def test_unknown_key_raises_naming_key_path(
    tmp_path: Path, mutate: Any, expected_loc: str
) -> None:
    data = _base()
    mutate(data)
    with pytest.raises(TemplateLoadError) as exc:
        load_template_from_file(_write(tmp_path, data))
    assert expected_loc in str(exc.value)


def test_unknown_shape_type_raises(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["shape_elements"][0]["type"] = "hexagon"
    with pytest.raises(TemplateLoadError, match="hexagon"):
        load_template_from_file(_write(tmp_path, data))


def test_unknown_fill_type_raises(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["shape_elements"][0]["fill"]["type"] = "plaid"
    with pytest.raises(TemplateLoadError, match="plaid"):
        load_template_from_file(_write(tmp_path, data))


def test_malformed_shape_raises_instead_of_being_skipped(tmp_path: Path) -> None:
    data = _base()
    del data["panels"][0]["shape_elements"][0]["width"]
    with pytest.raises(TemplateLoadError, match="width"):
        load_template_from_file(_write(tmp_path, data))


def test_line_accepts_x1_y1_x2_y2_aliases(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["shape_elements"] = [
        {"type": "line", "x1": 0.5, "y1": 0.6, "x2": 1.5, "y2": 1.6, "stroke_color": "#000000"}
    ]
    line = load_template_from_file(_write(tmp_path, data)).panels[0].shape_elements[0]
    assert isinstance(line, Line)
    assert (line.start_x, line.start_y, line.end_x, line.end_y) == (0.5, 0.6, 1.5, 1.6)


def test_pattern_angle_alias_loads_as_rotation(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["shape_elements"][0]["fill"] = {
        "type": "pattern",
        "pattern_type": "stripes",
        "colors": ["#FF0000", "#FFFFFF"],
        "angle": 45,
    }
    fill = load_template_from_file(_write(tmp_path, data)).panels[0].shape_elements[0].fill
    assert isinstance(fill, PatternFill)
    assert fill.rotation == 45


def test_text_fields_previously_dropped_are_kept(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["text_elements"][0].update(z_index=7, font_style="italic")
    text = load_template_from_file(_write(tmp_path, data)).panels[0].text_elements[0]
    assert text.z_index == 7
    assert text.font_style == "italic"


def test_panel_border_is_kept(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["border"] = {"style": "dashed", "width": 2.0}
    panel = load_template_from_file(_write(tmp_path, data)).panels[0]
    assert panel.border is not None
    assert panel.border.width == 2.0


def test_holly_wreath_svg_paths_keep_their_position() -> None:
    template = load_template("christmas-holly-wreath")
    front = next(p for p in template.panels if p.position == "front")
    paths = [s for s in front.shape_elements if isinstance(s, SVGPath)]
    assert len(paths) == 4
    positions = {(p.x, p.y) for p in paths}
    assert len(positions) == 4, "each leaf must sit at its own authored origin"
    assert (0.0, 0.0) not in positions, "x/y fell back to the model default"


_SHIPPED = sorted(t["id"] for t in discover_templates())


def test_all_21_templates_discovered() -> None:
    assert len(_SHIPPED) == 21


@pytest.mark.parametrize("template_id", _SHIPPED)
def test_every_shipped_template_loads_under_extra_forbid(template_id: str) -> None:
    assert load_template(template_id).id == template_id


def test_validate_cli_reports_typoed_key(tmp_path: Path) -> None:
    data = _base()
    data["panels"][0]["text_elements"][0]["colr"] = {"r": 1, "g": 0, "b": 0}
    result = CliRunner().invoke(app, ["validate", str(_write(tmp_path, data))])
    assert result.exit_code == 2
    assert "colr" in result.output
