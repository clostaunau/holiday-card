"""Integration tests for the SVG backend.

Renders every Wave 2-supported template through the SVG backend and
verifies the output is syntactically valid XML with the expected
structural shape (``<svg>`` root, expected element counts).

A perceptual SVG-vs-PDF parity test would require rasterizing both
formats — out of scope for this PR. The structural checks here are
sufficient to prove the backend works end-to-end without silently
dropping content.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.renderers.svg_backend import SVGRenderer

# Same set as the compiler snapshot suite (PR #6); kept in sync because
# the SVG backend supports exactly what the compiler emits.
SVG_TEMPLATES = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "birthday-balloons",
    "hanukkah-menorah",
    "generic-celebration",
)

_SVG_NS = "http://www.w3.org/2000/svg"


def _render_svg(template_id: str, output_path: Path) -> None:
    card = CardGenerator().create_card(template_id=template_id)
    commands = compile_card(card)
    SVGRenderer().render(commands, output_path)


@pytest.mark.parametrize("template_id", SVG_TEMPLATES)
def test_svg_renders_valid_xml(template_id: str, tmp_path: Path) -> None:
    out = tmp_path / f"{template_id}.svg"
    _render_svg(template_id, out)

    assert out.exists(), f"SVG backend did not write {out}"
    assert out.stat().st_size > 200, "SVG output is suspiciously small"

    # Parses without error == syntactically valid XML.
    tree = ET.parse(out)
    root = tree.getroot()

    # Root tag should be the SVG element. ElementTree includes the
    # namespace in the tag.
    assert root.tag == f"{{{_SVG_NS}}}svg", (
        f"Root element is {root.tag!r}, expected svg"
    )

    # The page is letter size in points.
    assert root.get("width") == "612", "Unexpected SVG width"
    assert root.get("height") == "792", "Unexpected SVG height"


@pytest.mark.parametrize("template_id", SVG_TEMPLATES)
def test_svg_contains_at_least_one_drawn_shape(
    template_id: str, tmp_path: Path
) -> None:
    """Watchdog: a card with all panels having backgrounds must yield
    at least one ``<rect>`` (or other shape). Catches the failure mode
    where the backend silently drops every command.
    """
    out = tmp_path / f"{template_id}.svg"
    _render_svg(template_id, out)
    root = ET.parse(out).getroot()
    drawn = (
        root.findall(f".//{{{_SVG_NS}}}rect")
        + root.findall(f".//{{{_SVG_NS}}}circle")
        + root.findall(f".//{{{_SVG_NS}}}polygon")
        + root.findall(f".//{{{_SVG_NS}}}polyline")
        + root.findall(f".//{{{_SVG_NS}}}path")
    )
    assert len(drawn) >= 1, (
        f"{template_id} produced an SVG with no drawn shapes"
    )


def test_svg_text_alignment_emits_text_anchor(tmp_path: Path) -> None:
    """The CLI flag we depend on (alignment → SVG text-anchor) must round-trip.
    christmas-classic uses center-aligned text, so its SVG must contain at
    least one ``text-anchor="middle"``.
    """
    out = tmp_path / "centred.svg"
    _render_svg("christmas-classic", out)
    text_elems = ET.parse(out).getroot().findall(f".//{{{_SVG_NS}}}text")
    anchors = {t.get("text-anchor") for t in text_elems}
    assert "middle" in anchors, (
        f"christmas-classic should have at least one center-aligned text run; "
        f"saw text-anchors {anchors!r}"
    )


def test_svg_emits_title_metadata(tmp_path: Path) -> None:
    out = tmp_path / "metadata.svg"
    _render_svg("christmas-classic", out)
    title = ET.parse(out).getroot().find(f"./{{{_SVG_NS}}}title")
    assert title is not None and title.text == "christmas-classic", (
        f"Expected <title>christmas-classic</title>, got {title!r}"
    )


def test_svg_fold_line_is_dashed(tmp_path: Path) -> None:
    """Half-fold cards emit a single horizontal fold line, which the
    backend renders as a dashed ``<line>`` element.
    """
    out = tmp_path / "fold.svg"
    _render_svg("christmas-classic", out)
    lines = ET.parse(out).getroot().findall(f".//{{{_SVG_NS}}}line")
    assert any(
        line.get("stroke-dasharray") == "3 3" for line in lines
    ), "Expected at least one dashed line (the fold guide)"


def test_svg_rotated_panel_uses_pivot_rotate_transform(tmp_path: Path) -> None:
    """christmas-geometric (and -modern, -artist) have a back panel rotated
    180° around its center. The IR's ``Transform`` represents this as a
    pivot-rotate idiom (``translate(pivot) rotate(-θ) translate(-pivot)``
    in SVG coords). The previous SVG backend emitted a wrong transform
    that produced "valid" SVG but with the rotated content in the wrong
    place — this test catches that class of bug.

    Pairs with ``test_png_rotated_panel_renders_at_expected_position``
    in the PNG suite, which catches the same bug at the pixel level.
    """
    out = tmp_path / "rotated.svg"
    _render_svg("christmas-geometric", out)
    root = ET.parse(out).getroot()
    groups = root.findall(f".//{{{_SVG_NS}}}g")
    transforms = [g.get("transform", "") for g in groups]
    rotated = [t for t in transforms if "rotate" in t]
    assert rotated, (
        "christmas-geometric should produce at least one rotated group; "
        "the back panel of a half-fold card rotates 180°."
    )
    # The IR pivot-rotate idiom emits a translate, then a rotate, then an
    # untranslate (a translate by the negated pivot). Verify the chain.
    for t in rotated:
        # Cheap structural check: presence of 'translate', 'rotate', 'translate'
        # in that order means we're using pivot-rotate semantics, not just
        # `translate(...) rotate(...)` which would put content in the wrong place.
        first_translate = t.find("translate")
        rotate_pos = t.find("rotate", first_translate)
        second_translate = t.find("translate", rotate_pos)
        assert first_translate < rotate_pos < second_translate, (
            f"Group transform {t!r} is missing the second translate of the "
            f"pivot-rotate idiom (translate pivot; rotate; translate -pivot). "
            f"Without it, rotated content lands in the wrong place."
        )
