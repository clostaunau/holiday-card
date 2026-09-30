"""Integration tests for the SVG backend.

Renders every shipped template through the SVG backend and verifies
the output is syntactically valid XML with the expected structural
shape (``<svg>`` root, expected element counts).

A perceptual SVG-vs-PDF parity test would require rasterizing both
formats — out of scope here. The structural checks here are sufficient
to prove the backend works end-to-end without silently dropping
content.
"""

from __future__ import annotations

import base64
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont
from reportlab.pdfbase import pdfmetrics

from holiday_card.core.compiler import CompileContext, compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.images import ImageSourceError
from holiday_card.core.models import ImageElement
from holiday_card.core.render_ir import RGBA, BeginPage, DrawText, EndPage, Point, TextRun
from holiday_card.renderers.font_registry import ensure_default_fonts_registered, resolve_font_id
from holiday_card.renderers.svg_backend import SVGRenderer
from holiday_card.utils.measurements import PageGeometry

# Every shipped template; mirrors ``test_png_backend.py``'s
# ``PNG_TEMPLATES``. ``tests/unit/test_compiler.py``'s
# ``SUPPORTED_SNAPSHOT_TEMPLATES`` is a strict subset (excludes
# photo templates whose IR carries machine-absolute paths).
SVG_TEMPLATES = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "christmas-festive-stripes",
    "christmas-holiday-masterpiece",
    "christmas-holly-wreath",
    "christmas-metallic-ornaments",
    "christmas-winter-sky",
    "christmas-photo-ornament",
    "christmas-family-photo",
    "birthday-balloons",
    "birthday-photo",
    "hanukkah-menorah",
    "generic-celebration",
    "mothers-day",
    "mothers-day-photo",
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

    # The default letter geometry is a true 8.5x11 page with no bleed
    # (D7, #59): 612x792 pt with the viewBox anchored at the trim corner.
    assert root.get("width") == "612", "Unexpected SVG width"
    assert root.get("height") == "792", "Unexpected SVG height"
    assert root.get("viewBox") == "0 0 612 792", "Unexpected SVG viewBox"


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


def test_svg_viewbox_includes_negative_bleed_offset(tmp_path: Path) -> None:
    """With a bleed geometry the viewBox starts at ``(-bleed, -bleed)`` so
    IR (0, 0) lands at the trim corner. Without this, content positioned
    at IR coords would appear in the bleed area. The default letter page
    has no bleed (#59), so this asks for 0.125" explicitly.
    """
    out = tmp_path / "viewbox.svg"
    card = CardGenerator().create_card(template_id="christmas-classic")
    ctx = CompileContext(geometry=PageGeometry.us_letter(bleed_in=0.125))
    SVGRenderer().render(compile_card(card, ctx), out)
    root = ET.parse(out).getroot()
    vb = root.get("viewBox")
    parts = vb.split() if vb else []
    assert len(parts) == 4
    assert float(parts[0]) == -9.0  # -bleed_pts
    assert float(parts[1]) == -9.0
    assert float(parts[2]) == 630.0  # media width
    assert float(parts[3]) == 810.0  # media height


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


def test_svg_refuses_non_image_source(tmp_path: Path) -> None:
    """Regression (#64): a non-image ``source_path`` was base64-embedded
    into the SVG as ``application/octet-stream``, leaking the file."""
    secret = tmp_path / "secret.env"
    secret_bytes = b"AWS_SECRET_ACCESS_KEY=hunter2"
    secret.write_bytes(secret_bytes)
    card = CardGenerator().create_card(template_id="christmas-classic")
    card.panels[0].image_elements.append(
        ImageElement(source_path=str(secret), x=0.5, y=0.5, width=1, height=1)
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(ImageSourceError, match="secret.env"):
        SVGRenderer().render(compile_card(card), out_dir / "card.svg")

    encoded = base64.b64encode(secret_bytes)
    for produced in out_dir.iterdir():
        data = produced.read_bytes()
        assert secret_bytes not in data and encoded[:16] not in data


# ---------------------------------------------------------------------------
# Embedded font subsets (#76)
# ---------------------------------------------------------------------------

_FONT_FACE = re.compile(
    r'@font-face \{ font-family: "(hc-[^"]+)"; '
    r'src: url\(data:font/ttf;base64,([A-Za-z0-9+/=]+)\) format\("truetype"\); \}'
)
_GENERICS = ("serif", "sans-serif", "monospace", "cursive")


def _texts(root: ET.Element) -> list[ET.Element]:
    return root.findall(f".//{{{_SVG_NS}}}text")


def _embedded_faces(root: ET.Element) -> list[tuple[str, bytes]]:
    style = root.find(f"./{{{_SVG_NS}}}defs/{{{_SVG_NS}}}style")
    assert style is not None and style.text, "expected <defs><style> with @font-face"
    return [(family, base64.b64decode(data)) for family, data in _FONT_FACE.findall(style.text)]


def _text_family(elem: ET.Element) -> str:
    match = re.fullmatch(r"'(hc-[^']+)', ([a-z-]+)", elem.get("font-family", ""))
    assert match, f"font-family {elem.get('font-family')!r} is not \"'hc-<id>', <generic>\""
    assert match.group(2) in _GENERICS
    return match.group(1)


@pytest.mark.parametrize("template_id", SVG_TEMPLATES)
def test_svg_text_names_an_embedded_face_then_a_generic(
    template_id: str, tmp_path: Path
) -> None:
    out = tmp_path / f"{template_id}.svg"
    _render_svg(template_id, out)
    root = ET.parse(out).getroot()
    texts = _texts(root)
    if not texts:
        pytest.skip(f"{template_id} draws no text")
    faces = _embedded_faces(root)
    families = [family for family, _ in faces]
    used = {_text_family(t) for t in texts}
    assert sorted(families) == sorted(used), "exactly one @font-face per used family"
    assert len(families) == len(set(families))

    chars: dict[str, set[str]] = {}
    for t in texts:
        chars.setdefault(_text_family(t), set()).update(t.text or "")
    for family, data in faces:
        cmap = TTFont(io.BytesIO(data)).getBestCmap()
        missing = {c for c in chars[family] if ord(c) not in cmap}
        assert not missing, f"{family} subset lacks {sorted(missing)}"


def test_svg_names_embedded_font_licenses(tmp_path: Path) -> None:
    out = tmp_path / "artist.svg"
    _render_svg("christmas-artist", out)
    text = out.read_text(encoding="utf-8")
    comment = re.search(r"<!--(.*?)-->", text, re.S)
    assert comment and "hc-Caveat" in comment.group(1)
    assert "SIL Open Font License 1.1" in comment.group(1)


def test_svg_is_byte_identical_across_runs(tmp_path: Path) -> None:
    a, b = tmp_path / "a.svg", tmp_path / "b.svg"
    _render_svg("christmas-classic", a)
    _render_svg("christmas-classic", b)
    assert a.read_bytes() == b.read_bytes()


def test_svg_refuses_a_font_it_cannot_embed(tmp_path: Path) -> None:
    commands = [
        BeginPage(width=144, height=144),
        DrawText(run=TextRun(text="Hi", origin=Point(x=10, y=10), font_id="NoSuchFont",
                             size_pt=12, color=RGBA(r=0, g=0, b=0))),
        EndPage(),
    ]
    with pytest.raises(NotImplementedError, match="cannot embed font 'NoSuchFont'"):
        SVGRenderer().render(commands, tmp_path / "x.svg")


def test_embedded_advances_match_reportlab_measurement(tmp_path: Path) -> None:
    """D12: the SVG draws with exactly the metrics the compiler wrapped with."""
    card = CardGenerator().create_card(template_id="christmas-classic")
    commands = compile_card(card)
    out = tmp_path / "classic.svg"
    SVGRenderer().render(commands, out)
    faces = {family: TTFont(io.BytesIO(data)) for family, data in _embedded_faces(ET.parse(out).getroot())}
    ensure_default_fonts_registered()
    runs = [c.run for c in commands if isinstance(c, DrawText)]
    assert runs
    for run in runs:
        font = faces[f"hc-{run.font_id}"]
        cmap, hmtx = font.getBestCmap(), font["hmtx"]
        upem = font["head"].unitsPerEm
        width = sum(hmtx[cmap[ord(c)]][0] for c in run.text) * run.size_pt / upem
        expected = pdfmetrics.stringWidth(run.text, resolve_font_id(run.font_id), run.size_pt)
        assert width == pytest.approx(expected, rel=0.005), run.text
