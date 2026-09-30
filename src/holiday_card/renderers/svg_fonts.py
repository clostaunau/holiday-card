"""Glyph-subset font embedding for the SVG backend (#76).

The compiler measures and wraps every text run against the bundled TTFs
(through ReportLab). An SVG that only names ``font-family="Caveat"``
leaves the viewer to substitute whatever it has, so the text over- or
under-fills the boxes the compiler computed. The SVG backend instead
embeds, per page, a subset of the exact TTF each ``font_id`` resolves to
(``font_registry.ttf_path_for``) as a ``data:font/ttf`` ``@font-face``.

Each subset:

- holds ``.notdef`` plus the glyphs for the characters drawn with it;
- drops ``GSUB`` / ``GPOS`` / ``kern`` (ReportLab measures unkerned,
  unshaped advances; a browser would otherwise kern away from them) and
  hinting;
- is renamed to its CSS family ``hc-<font_id>`` (like a PDF subset's
  ``ABCDEF+`` tag), because resvg, rsvg and Inkscape ignore
  ``@font-face`` and match the font's own name table; the copyright and
  license records are kept;
- is byte-stable: fixed subsetter options and the source
  ``head.modified`` (no save-time timestamp).

Variable masters are embedded as their static default instance: the
variation tables are dropped (a variable TTF's ``glyf`` / ``hmtx`` already
hold the default master), so no ``instancer`` run is needed. Keeping them
would let viewers move off the instance ReportLab measured; browsers and
resvg apply ``font-optical-sizing: auto``, which drew Inter (``opsz`` 14 by
default) at ``opsz`` 32 for 32 pt text, visibly narrower.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Literal

from fontTools import subset
from fontTools.ttLib import TTFont

from holiday_card.renderers.font_registry import CURATED_FONTS, FONT_MAP

__all__ = [
    "GENERIC_FAMILY",
    "css_family",
    "font_face_css",
    "subset_font_bytes",
    "svg_font_family",
]

Generic = Literal["serif", "sans-serif", "monospace", "cursive"]


def _generic_for(font_id: str) -> Generic:
    if font_id.startswith(("Cormorant", "PlayfairDisplay", "Times")):
        return "serif"
    if font_id.startswith("Courier"):
        return "monospace"
    if font_id.startswith("Caveat"):
        return "cursive"
    return "sans-serif"  # Helvetica*, Lato*, Inter, Comfortaa


# CSS generic family written after the embedded face, per IR ``font_id``.
GENERIC_FAMILY: dict[str, Generic] = {
    font_id: _generic_for(font_id) for font_id in sorted(FONT_MAP.keys() | CURATED_FONTS.keys())
}

# Typographic family / subfamily (16, 17) would outrank the renamed family.
_DROPPED_NAME_IDS = frozenset({16, 17, 21, 22})
_DROPPED_TABLES = [
    "GSUB", "GPOS", "GDEF", "kern", "DSIG", "FFTM",
    # Variation tables: without them glyf / hmtx are the default instance.
    "fvar", "gvar", "avar", "cvar", "HVAR", "MVAR", "VVAR", "STAT",
]


def css_family(font_id: str) -> str:
    """The ``@font-face`` family name for ``font_id`` (``hc-<font_id>``)."""
    return f"hc-{font_id}"


def svg_font_family(font_id: str) -> str:
    """The ``font-family`` attribute value: the embedded face, then a generic."""
    return f"'{css_family(font_id)}', {GENERIC_FAMILY[font_id]}"


def _subset_options() -> subset.Options:
    options = subset.Options()
    options.layout_features = []
    options.drop_tables += _DROPPED_TABLES
    options.hinting = False
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.recalc_timestamp = False
    return options


def _rename(font: TTFont, family_name: str) -> None:
    name = font["name"]
    name.names = [n for n in name.names if n.nameID not in _DROPPED_NAME_IDS]
    postscript = family_name.replace(" ", "")
    for record in name.names:
        if record.nameID == 1:
            record.string = family_name
        elif record.nameID == 2:
            record.string = "Regular"
        elif record.nameID in (3, 4):
            record.string = family_name
        elif record.nameID == 6:
            record.string = postscript


def subset_font_bytes(ttf_path: Path, text: str, *, family_name: str) -> bytes:
    """A TrueType subset of ``ttf_path`` covering ``set(text)``, named ``family_name``.

    Only ``.notdef`` and the glyphs mapped from the characters in
    ``text`` are kept. Output is byte-identical for identical input.
    """
    font = TTFont(ttf_path, recalcTimestamp=False)
    subsetter = subset.Subsetter(_subset_options())
    subsetter.populate(unicodes=sorted({ord(c) for c in text}))
    subsetter.subset(font)
    _rename(font, family_name)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def font_face_css(font_id: str, ttf_path: Path, text: str) -> str:
    """One ``@font-face`` rule embedding the ``text`` subset of ``ttf_path``."""
    family = css_family(font_id)
    data = base64.b64encode(subset_font_bytes(ttf_path, text, family_name=family)).decode("ascii")
    return (
        f'@font-face {{ font-family: "{family}"; '
        f'src: url(data:font/ttf;base64,{data}) format("truetype"); }}'
    )
