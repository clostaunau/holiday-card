"""Glyph-subset font embedding for the SVG backend (#76)."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

from holiday_card.renderers.font_registry import CURATED_FONTS, FONT_MAP, ttf_path_for
from holiday_card.renderers.svg_fonts import (
    GENERIC_FAMILY,
    css_family,
    font_face_css,
    subset_font_bytes,
    svg_font_family,
)

CAVEAT = ttf_path_for("Caveat")


def _font(data: bytes) -> TTFont:
    return TTFont(io.BytesIO(data))


def _family_names(font: TTFont) -> set[str]:
    return {str(n) for n in font["name"].names if n.nameID == 1}


def test_subset_cmap_covers_exactly_the_text() -> None:
    assert CAVEAT is not None
    font = _font(subset_font_bytes(CAVEAT, "Merry", family_name="hc-Caveat"))
    assert set(font.getBestCmap()) == {ord(c) for c in "Mery"}
    assert font.getGlyphOrder()[0] == ".notdef"
    assert len(font.getGlyphOrder()) == 1 + len(set("Merry"))


def test_subset_is_byte_identical_across_runs() -> None:
    assert CAVEAT is not None
    first = subset_font_bytes(CAVEAT, "Merry Christmas", family_name="hc-Caveat")
    assert subset_font_bytes(CAVEAT, "Merry Christmas", family_name="hc-Caveat") == first


def test_subset_keeps_the_source_head_modified_timestamp() -> None:
    # TTFont.save() stamps head.modified with "now" unless told not to,
    # which would make every SVG differ from the last.
    assert CAVEAT is not None
    font = _font(subset_font_bytes(CAVEAT, "Merry", family_name="hc-Caveat"))
    assert font["head"].modified == TTFont(CAVEAT)["head"].modified


def test_subset_is_named_after_its_css_family() -> None:
    # resvg, rsvg and Inkscape ignore @font-face and match the font's own
    # name table, so the subset carries the CSS family name.
    assert CAVEAT is not None
    font = _font(subset_font_bytes(CAVEAT, "Merry", family_name="hc-Caveat"))
    assert _family_names(font) == {"hc-Caveat"}
    assert not [n for n in font["name"].names if n.nameID in (16, 17)]


def test_subset_keeps_copyright_and_license_records() -> None:
    assert CAVEAT is not None
    font = _font(subset_font_bytes(CAVEAT, "Merry", family_name="hc-Caveat"))
    ids = {n.nameID for n in font["name"].names}
    assert {0, 13} <= ids


def test_subset_has_no_kerning_or_shaping_tables() -> None:
    # The compiler measures unkerned advances with ReportLab; a browser
    # would apply GPOS kerning or GSUB alternates and drift from them.
    path = ttf_path_for("Helvetica")
    assert path is not None
    font = _font(subset_font_bytes(path, "AVAWAY", family_name="hc-Helvetica"))
    assert not {"GPOS", "GSUB", "kern", "DSIG"} & set(font.keys())


@pytest.mark.parametrize("font_id", sorted(FONT_MAP.keys() | CURATED_FONTS.keys()))
def test_generic_family_covers_every_font_id(font_id: str) -> None:
    assert font_id in GENERIC_FAMILY


@pytest.mark.parametrize(
    ("font_id", "generic"),
    [
        ("Cormorant-Italic", "serif"),
        ("PlayfairDisplay", "serif"),
        ("Times-Roman", "serif"),
        ("Lato-Bold", "sans-serif"),
        ("Inter", "sans-serif"),
        ("Comfortaa", "sans-serif"),
        ("Helvetica-BoldOblique", "sans-serif"),
        ("Caveat", "cursive"),
        ("Courier-Oblique", "monospace"),
    ],
)
def test_generic_family_mapping(font_id: str, generic: str) -> None:
    assert GENERIC_FAMILY[font_id] == generic


def test_svg_font_family_names_the_embedded_face_then_a_generic() -> None:
    assert css_family("Caveat") == "hc-Caveat"
    assert svg_font_family("Caveat") == "'hc-Caveat', cursive"


def test_font_face_css_embeds_a_truetype_data_uri() -> None:
    assert CAVEAT is not None
    css = font_face_css("Caveat", CAVEAT, "Merry")
    match = re.fullmatch(
        r'@font-face \{ font-family: "hc-Caveat"; '
        r'src: url\(data:font/ttf;base64,([A-Za-z0-9+/=]+)\) format\("truetype"\); \}',
        css,
    )
    assert match, css
    font = _font(base64.b64decode(match.group(1)))
    assert set(font.getBestCmap()) == {ord(c) for c in "Mery"}


def test_subset_is_much_smaller_than_the_source() -> None:
    assert CAVEAT is not None
    data = subset_font_bytes(CAVEAT, "Merry Christmas", family_name="hc-Caveat")
    assert len(data) < Path(CAVEAT).stat().st_size / 5


@pytest.mark.parametrize("font_id", ["Inter", "Caveat", "Cormorant", "PlayfairDisplay", "Comfortaa"])
def test_variable_master_is_embedded_as_its_static_default_instance(font_id: str) -> None:
    # Viewers apply font-optical-sizing: auto (Inter's opsz 14 → 32 at 32 pt)
    # and would move off the default instance ReportLab measured.
    path = ttf_path_for(font_id)
    assert path is not None
    source = TTFont(path)
    assert "fvar" in source
    font = _font(subset_font_bytes(path, "Hello", family_name=f"hc-{font_id}"))
    assert not {"fvar", "gvar", "avar", "HVAR", "MVAR", "STAT", "cvar"} & set(font.keys())
    cmap, src_cmap = font.getBestCmap(), source.getBestCmap()
    for c in "Helo":
        assert font["hmtx"][cmap[ord(c)]] == source["hmtx"][src_cmap[ord(c)]]
