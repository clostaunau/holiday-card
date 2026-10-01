"""docs/template-authoring.md: every YAML example is a valid template (issue #57)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image

from holiday_card.core.models import Template
from holiday_card.core.template_checks import check_template
from holiday_card.core.templates import load_template_from_file
from holiday_card.renderers.font_registry import known_font_ids

_ROOT = Path(__file__).resolve().parents[2]
_GUIDE = _ROOT / "docs" / "template-authoring.md"


def _yaml_blocks() -> list[Any]:
    text = _GUIDE.read_text()
    return [yaml.safe_load(b) for b in re.findall(r"```yaml\n(.*?)```", text, re.S)]


def _skeleton() -> dict[str, Any]:
    return next(b for b in _yaml_blocks() if isinstance(b, dict) and "panels" in b)


def _raw_template_with(**front: Any) -> dict[str, Any]:
    data = _skeleton()
    positions = ["front", "back", "inside_left", "inside_right"]
    data["panels"] = [
        {"position": p, "width": 4.25, "height": 5.5, **(front if p == "front" else {})}
        for p in positions
    ]
    return data


def _template_with(**front: Any) -> Template:
    return Template.model_validate(_raw_template_with(**front))


def _blocks_with(key: str) -> list[Any]:
    return [b for b in _yaml_blocks() if isinstance(b, dict) and key in b]


def test_skeleton_is_a_valid_template() -> None:
    Template.model_validate(_skeleton())


def test_shape_and_text_examples_pass_every_check() -> None:
    [shapes] = _blocks_with("shape_elements")
    [texts] = _blocks_with("text_elements")
    template = _template_with(**shapes, **texts)
    assert {s.type.value for s in template.panels[0].shape_elements} == {
        "rectangle", "circle", "triangle", "star", "line", "svg_path",
    }
    assert check_template(template) == []


@pytest.mark.parametrize("index", range(4))
def test_fill_examples_are_valid(index: int) -> None:
    fills = _blocks_with("fill")
    assert len(fills) == 4
    shape = {"type": "rectangle", "x": 0, "y": 0, "width": 4.25, "height": 5.5,
             **fills[index]}
    assert check_template(_template_with(shape_elements=[shape])) == []


def test_image_example_is_valid() -> None:
    # Loaded without the file (source_path resolves against a real template).
    [images] = _blocks_with("image_elements")
    _template_with(**images)


def test_background_image_example_passes_every_check(tmp_path: Path) -> None:
    # #153: the art sits next to the template; the loader resolves it there.
    [background] = _blocks_with("background_image")
    data = _raw_template_with(**background)
    image = tmp_path / background["background_image"]
    image.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1314, 1824), (40, 90, 60)).save(image)
    path = tmp_path / "t.yaml"
    path.write_text(yaml.safe_dump(data))
    template = load_template_from_file(path)
    assert template.panels[0].background_image == str(image.resolve())
    assert check_template(template) == []


def test_font_table_lists_every_known_font_id() -> None:
    text = _GUIDE.read_text()
    listed = set(re.findall(r"`([A-Za-z]+(?:-[A-Za-z]+)?)`", text))
    assert known_font_ids() <= listed


def test_guide_is_linked_from_readme_and_claude_md() -> None:
    for doc in ("README.md", "CLAUDE.md"):
        assert "docs/template-authoring.md" in (_ROOT / doc).read_text(), doc
