"""Tests for ``core.template_checks.check_template`` (issue #57)."""

from __future__ import annotations

import copy
from typing import Any

import pytest
import yaml

from holiday_card.core.data_paths import data_path
from holiday_card.core.models import Template
from holiday_card.core.template_checks import TemplateProblem, check_template
from holiday_card.core.templates import discover_templates, load_template

_CLASSIC = data_path("templates") / "christmas" / "classic.yaml"


def _classic_data() -> dict[str, Any]:
    data = yaml.safe_load(_CLASSIC.read_text())
    assert isinstance(data, dict)
    return copy.deepcopy(data)


def _front(data: dict[str, Any]) -> dict[str, Any]:
    return next(p for p in data["panels"] if p["position"] == "front")


def _greeting(data: dict[str, Any]) -> dict[str, Any]:
    return next(t for t in _front(data)["text_elements"] if t["id"] == "greeting")


def _check(data: dict[str, Any]) -> list[TemplateProblem]:
    return check_template(Template.model_validate(data))


def _paths(problems: list[TemplateProblem]) -> list[str]:
    return [p.path for p in problems]


class TestFonts:
    def test_unknown_font_family_is_a_problem(self) -> None:
        data = _classic_data()
        _greeting(data)["font_family"] = "NotAFont"

        problems = _check(data)

        assert _paths(problems) == ["panels[front].text_elements[greeting].font_family"]
        assert "NotAFont" in problems[0].message

    def test_known_curated_and_base14_fonts_pass(self) -> None:
        data = _classic_data()
        _greeting(data)["font_family"] = "Helvetica-Bold"
        assert _check(data) == []

    def test_element_without_authored_id_is_named_by_index(self) -> None:
        data = _classic_data()
        greeting = _greeting(data)
        del greeting["id"]
        greeting["font_family"] = "NotAFont"

        assert _paths(_check(data)) == ["panels[front].text_elements[0].font_family"]


class TestBounds:
    def test_text_anchor_outside_panel_is_a_problem(self) -> None:
        data = _classic_data()
        _greeting(data)["x"] = 99

        problems = _check(data)

        assert _paths(problems) == ["panels[front].text_elements[greeting]"]
        assert "outside" in problems[0].message
        assert "4.25" in problems[0].message

    def test_circle_outside_panel_is_a_problem(self) -> None:
        data = _classic_data()
        _front(data)["shape_elements"] = [
            {"id": "sun", "type": "circle", "center_x": 4.0, "center_y": 2.0,
             "radius": 0.5, "fill_color": "#FFCC00"},
        ]

        assert _paths(_check(data)) == ["panels[front].shape_elements[sun]"]

    @pytest.mark.parametrize(
        "shape",
        [
            {"type": "rectangle", "x": 3.0, "y": 1.0, "width": 2.0, "height": 1.0},
            {"type": "star", "center_x": 2.0, "center_y": 5.3, "outer_radius": 0.5,
             "inner_radius": 0.2},
            {"type": "triangle", "x1": 0.5, "y1": 0.5, "x2": 1.0, "y2": 6.0,
             "x3": 1.5, "y3": 0.5},
            {"type": "line", "x1": 0.5, "y1": 0.5, "x2": 5.0, "y2": 0.5},
            {"type": "svg_path", "path_data": "M 0 0 L 100 0 L 100 100 Z",
             "scale": 0.05, "x": 1.0, "y": 1.0},
        ],
        ids=["rectangle", "star", "triangle", "line", "svg_path"],
    )
    def test_each_shape_type_outside_panel_is_a_problem(
        self, shape: dict[str, Any]
    ) -> None:
        data = _classic_data()
        _front(data)["shape_elements"] = [{"fill_color": "#00AA00", **shape}]

        assert _paths(_check(data)) == ["panels[front].shape_elements[0]"]

    def test_shape_inside_panel_passes(self) -> None:
        data = _classic_data()
        _front(data)["shape_elements"] = [
            {"type": "rectangle", "x": 0.0, "y": 0.0, "width": 4.25, "height": 5.5,
             "fill_color": "#00AA00"},
        ]
        assert _check(data) == []

    def test_image_rect_outside_panel_is_a_problem(self) -> None:
        template = load_template("christmas-family-photo")
        panel = next(p for p in template.panels if p.image_elements)
        panel.image_elements[0].x = panel.width  # right edge now past the panel

        problems = check_template(template)

        assert [p.path for p in problems] == [
            f"panels[{panel.position.value}].image_elements[0]"
        ]


class TestTheme:
    def test_unknown_default_theme_is_a_problem(self) -> None:
        data = _classic_data()
        data["default_theme_id"] = "no-such-theme"

        problems = _check(data)

        assert _paths(problems) == ["default_theme_id"]
        assert "no-such-theme" in problems[0].message


class TestCompileSmoke:
    def test_compile_failure_is_a_problem_not_a_traceback(self) -> None:
        data = _classic_data()
        _front(data)["background_image"] = "bg.png"  # relative path: ImageSourceError

        problems = _check(data)

        assert _paths(problems) == ["<compile>"]
        assert "background_image" in problems[0].message

    def test_unknown_font_is_not_reported_twice(self) -> None:
        # compile_card would also refuse the font; one problem is enough.
        data = _classic_data()
        _greeting(data)["font_family"] = "NotAFont"
        assert len(_check(data)) == 1


class TestAllAtOnce:
    def test_every_problem_is_reported(self) -> None:
        data = _classic_data()
        greeting = _greeting(data)
        greeting["font_family"] = "NotAFont"
        greeting["x"] = 99
        data["default_theme_id"] = "no-such-theme"

        assert sorted(_paths(_check(data))) == [
            "default_theme_id",
            "panels[front].text_elements[greeting]",
            "panels[front].text_elements[greeting].font_family",
        ]


@pytest.mark.parametrize("template_id", sorted(t["id"] for t in discover_templates()))
def test_shipped_template_has_no_problems(template_id: str) -> None:
    assert check_template(load_template(template_id)) == []


def test_all_21_templates_are_checked() -> None:
    assert len(discover_templates()) == 21
