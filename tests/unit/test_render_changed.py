"""Unit tests for the GitHub Action's render-changed-templates helper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The script lives in scripts/ rather than the package, so add it
# to sys.path for importing.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from render_changed_templates import (  # noqa: E402  (sys.path manipulation)
    SHIPPING_TEMPLATES,
    _template_id_from_path,
    detect_affected_templates,
    render_one,
)


class TestTemplateIdFromPath:
    """Path → template-id resolution mirrors discover_templates()."""

    def test_christmas_classic(self) -> None:
        assert _template_id_from_path("templates/christmas/classic.yaml") == "christmas-classic"

    def test_birthday_balloons(self) -> None:
        assert _template_id_from_path("templates/birthday/balloons.yaml") == "birthday-balloons"

    def test_mothers_day_classic_special_cases_to_mothers_day(self) -> None:
        # mothers_day/classic.yaml ships with id="mothers-day", not
        # "mothers_day-classic". Discovery code does the same special-case.
        assert _template_id_from_path("templates/mothers_day/classic.yaml") == "mothers-day"

    def test_non_template_path_returns_none(self) -> None:
        assert _template_id_from_path("src/holiday_card/foo.py") is None
        assert _template_id_from_path("README.md") is None
        assert _template_id_from_path("templates/christmas") is None  # missing yaml stem


class TestDetectAffected:
    """The detection rules: direct → just that template, indirect →
    union with the full shipping set."""

    def test_no_relevant_changes_returns_empty(self) -> None:
        assert detect_affected_templates(["docs/foo.md", "tests/test_x.py"]) == []

    def test_direct_template_change_renders_only_that(self) -> None:
        affected = detect_affected_templates(["templates/christmas/classic.yaml"])
        assert affected == ["christmas-classic"]

    def test_multiple_direct_changes_render_each(self) -> None:
        affected = detect_affected_templates([
            "templates/christmas/classic.yaml",
            "templates/birthday/balloons.yaml",
            "docs/something.md",  # ignored
        ])
        assert set(affected) == {"christmas-classic", "birthday-balloons"}

    def test_src_change_triggers_full_shipping_set(self) -> None:
        affected = detect_affected_templates(["src/holiday_card/core/compiler.py"])
        assert set(affected) == set(SHIPPING_TEMPLATES)

    def test_fonts_change_triggers_full_shipping_set(self) -> None:
        affected = detect_affected_templates(["fonts/curated/Lato-Regular.ttf"])
        assert set(affected) == set(SHIPPING_TEMPLATES)

    def test_sentiments_change_triggers_full_shipping_set(self) -> None:
        affected = detect_affected_templates(["sentiments/christmas/warm/cover.yaml"])
        assert set(affected) == set(SHIPPING_TEMPLATES)

    def test_themes_change_triggers_full_shipping_set(self) -> None:
        affected = detect_affected_templates(["themes/christmas-red-green.yaml"])
        assert set(affected) == set(SHIPPING_TEMPLATES)

    def test_indirect_change_unions_with_explicit_direct(self) -> None:
        """When both an indirect change and a direct template change
        appear, the affected list starts with the direct one and then
        adds the rest of the shipping set in order."""
        affected = detect_affected_templates([
            "templates/christmas/classic.yaml",
            "src/holiday_card/core/compiler.py",
        ])
        # christmas-classic appears first (direct); the rest are the
        # remaining shipping templates.
        assert affected[0] == "christmas-classic"
        assert set(affected) == set(SHIPPING_TEMPLATES)
        # Ordering: the direct hit comes first, then the rest of the
        # shipping set in its declaration order.
        assert affected.index("christmas-classic") == 0

    def test_blank_lines_in_changed_files_are_ignored(self) -> None:
        affected = detect_affected_templates([
            "",
            "   ",
            "templates/christmas/classic.yaml",
            "",
        ])
        assert affected == ["christmas-classic"]

    def test_nonshipping_template_change_is_still_detected(self) -> None:
        """A change to a template that doesn't compile (e.g. a
        gradient/pattern demo) is still listed — the rendering step
        handles the failure gracefully."""
        affected = detect_affected_templates([
            "templates/christmas/holly-wreath.yaml",
        ])
        assert affected == ["christmas-holly-wreath"]


class TestRenderOne:
    """End-to-end render of a single template via the helper API."""

    def test_renders_a_valid_png(self, tmp_path: Path) -> None:
        out = render_one("christmas-classic", tmp_path, dpi=72)
        assert out.exists()
        assert out.suffix == ".png"
        assert out.stat().st_size > 1000
        # PNG magic bytes
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_unknown_template_id_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Exception):  # noqa: B017 — intentionally broad
            render_one("not-a-real-template", tmp_path)
