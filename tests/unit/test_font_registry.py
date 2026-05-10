"""Tests for the embedded-font registry.

Verifies that the default font_id chain (Helvetica/Times-Roman/Courier
plus bold/italic variants) resolves to bundled Liberation TTF files,
and that custom font_ids pass through unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from holiday_card.renderers.font_registry import (
    FONT_DIR,
    FONT_MAP,
    ensure_default_fonts_registered,
    resolve_font_id,
    ttf_path_for,
)


def test_font_dir_exists_and_contains_ttfs() -> None:
    """Without the TTFs on disk, every backend silently falls back to
    the bitmap default. This test catches the case where the fonts/
    directory was removed or never installed.
    """
    assert FONT_DIR.exists(), f"fonts/ directory missing at {FONT_DIR}"
    ttfs = list(FONT_DIR.glob("*.ttf"))
    assert len(ttfs) >= 12, (
        f"Expected at least 12 Liberation TTFs in {FONT_DIR}, found {len(ttfs)}"
    )


def test_font_map_covers_all_pdf_base14_default_chain() -> None:
    """The base PDF 14 family chain (Helvetica/Times/Courier × 4 styles)
    should all map to a Liberation equivalent.
    """
    expected = {
        "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
        "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
        "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
    }
    assert set(FONT_MAP.keys()) >= expected


@pytest.mark.parametrize("font_id", list(FONT_MAP.keys()))
def test_each_default_font_resolves_to_an_existing_ttf(font_id: str) -> None:
    path = ttf_path_for(font_id)
    assert path is not None, f"ttf_path_for({font_id!r}) returned None"
    assert isinstance(path, Path)
    assert path.exists(), f"TTF missing on disk: {path}"
    # Sanity check — a real TTF starts with the magic bytes 0x00 0x01 0x00 0x00
    # (TrueType outlines) or "OTTO" (PostScript-flavored OpenType).
    head = path.read_bytes()[:4]
    assert head in (b"\x00\x01\x00\x00", b"OTTO", b"true"), (
        f"{path} is not a recognizable TTF/OTF (head bytes: {head!r})"
    )


def test_resolve_default_font_returns_liberation_name() -> None:
    assert resolve_font_id("Helvetica") == "LiberationSans"
    assert resolve_font_id("Helvetica-Bold") == "LiberationSans-Bold"
    assert resolve_font_id("Times-Italic") == "LiberationSerif-Italic"
    assert resolve_font_id("Courier") == "LiberationMono"


def test_resolve_unknown_font_id_passes_through() -> None:
    """Custom fonts (e.g. ``GreatVibes``) are registered separately by
    the renderer; the registry must not interfere with those.
    """
    assert resolve_font_id("GreatVibes") == "GreatVibes"
    assert resolve_font_id("PlayfairDisplay-Italic") == "PlayfairDisplay-Italic"


def test_ensure_default_fonts_registered_is_idempotent() -> None:
    """Called from every render() call — must not error or double-register."""
    ensure_default_fonts_registered()
    ensure_default_fonts_registered()
    ensure_default_fonts_registered()


def test_pdf_render_embeds_liberation_subset(tmp_path: Path) -> None:
    """Render a PDF and verify a Liberation font subset is embedded
    (looking for the standard ``XXXXXX+`` subset prefix).
    """
    import re

    from holiday_card.core.compiler import compile_card
    from holiday_card.core.generators import CardGenerator
    from holiday_card.renderers.reportlab_backend import IRReportLabRenderer

    out = tmp_path / "fonted.pdf"
    card = CardGenerator().create_card("christmas-classic")
    cmds = compile_card(card)
    IRReportLabRenderer().render(cmds, out)

    data = out.read_bytes()
    base_fonts = re.findall(rb"/BaseFont\s*/(\S+?)[\s<>/]", data)
    base_fonts_str = [f.decode() for f in base_fonts]
    # Expect at least one Liberation subset (XXXXXX+LiberationSans pattern)
    liberation_subsets = [
        f for f in base_fonts_str
        if "+" in f and "Liberation" in f
    ]
    assert liberation_subsets, (
        f"Expected at least one embedded Liberation subset in PDF, "
        f"found BaseFonts: {base_fonts_str}"
    )

    # And at least one FontFile2 stream (the actual embedded TTF data)
    embedded_streams = re.findall(rb"/FontFile2", data)
    assert len(embedded_streams) >= 1, (
        "Expected at least one /FontFile2 stream (embedded TTF) in PDF"
    )
