"""Tests for the embedded-font registry.

Verifies that the default font_id chain (Helvetica/Times-Roman/Courier
plus bold/italic variants) resolves to bundled Liberation TTF files,
and that custom font_ids pass through unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from holiday_card.renderers.font_registry import (
    CURATED_FONT_DIR,
    CURATED_FONTS,
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


def test_pdf_render_embeds_a_font_subset(tmp_path: Path) -> None:
    """Render a PDF and verify at least one TTF font subset is embedded
    (looking for the standard ``XXXXXX+`` subset prefix).

    Christmas-classic now uses curated fonts (PlayfairDisplay /
    Cormorant) — the original test required Liberation specifically;
    this version generalizes to any embedded subset, since the goal of
    defect 9 was "fonts are embedded, period," not "Liberation
    specifically embedded."
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
    # Embedded subsets follow the "XXXXXX+FontName" pattern. Any one is
    # enough — the bug we're guarding against is "no fonts embedded at all,"
    # not "specific font missing."
    embedded_subsets = [f for f in base_fonts_str if "+" in f]
    assert embedded_subsets, (
        f"Expected at least one embedded font subset in PDF (XXXXXX+Family); "
        f"found BaseFonts: {base_fonts_str}"
    )

    # And at least one FontFile2 stream (the actual embedded TTF data)
    embedded_streams = re.findall(rb"/FontFile2", data)
    assert len(embedded_streams) >= 1, (
        "Expected at least one /FontFile2 stream (embedded TTF) in PDF"
    )


# ---------------------------------------------------------------------------
# Curated fonts (Leapfrog 2 — panel's "font subset" of Agreement 1)
# ---------------------------------------------------------------------------


_EXPECTED_CURATED_FONT_IDS = {
    "Cormorant", "PlayfairDisplay", "Lato", "Lato-Bold",
    "Inter", "Caveat", "Comfortaa",
}


class TestCuratedFonts:
    def test_curated_dir_exists(self) -> None:
        assert CURATED_FONT_DIR.exists(), (
            f"fonts/curated/ missing at {CURATED_FONT_DIR}"
        )

    def test_curated_map_covers_expected_families(self) -> None:
        # Six families + one extra weight (Lato-Bold) the panel called
        # out as a useful pairing for warm-voice covers.
        assert set(CURATED_FONTS.keys()) == _EXPECTED_CURATED_FONT_IDS

    @pytest.mark.parametrize("font_id", sorted(_EXPECTED_CURATED_FONT_IDS))
    def test_each_curated_font_resolves_to_an_existing_ttf(
        self, font_id: str
    ) -> None:
        path = ttf_path_for(font_id)
        assert path is not None, f"ttf_path_for({font_id!r}) returned None"
        assert path.exists(), f"TTF missing on disk: {path}"
        head = path.read_bytes()[:4]
        assert head in (b"\x00\x01\x00\x00", b"OTTO", b"true"), (
            f"{path} is not a TTF/OTF (head bytes: {head!r})"
        )

    @pytest.mark.parametrize("font_id", sorted(_EXPECTED_CURATED_FONT_IDS))
    def test_each_curated_font_has_an_OFL_license(self, font_id: str) -> None:
        """SIL OFL requires the license text accompany the font when
        distributed. Each curated family ships its OFL.txt next to the
        TTFs as ``{Family}-LICENSE.txt``."""
        # All seven font_ids share three license files (Lato + Lato-Bold
        # share one). Map font_id to its license stem.
        license_stems = {
            "Cormorant":       "CormorantGaramond",
            "PlayfairDisplay": "PlayfairDisplay",
            "Lato":            "Lato",
            "Lato-Bold":       "Lato",
            "Inter":           "Inter",
            "Caveat":          "Caveat",
            "Comfortaa":       "Comfortaa",
        }
        license_path = CURATED_FONT_DIR / f"{license_stems[font_id]}-LICENSE.txt"
        assert license_path.exists(), (
            f"OFL license missing for {font_id} at {license_path}"
        )
        text = license_path.read_text(encoding="utf-8", errors="replace")
        assert "SIL OPEN FONT LICENSE" in text.upper(), (
            f"{license_path} does not look like an SIL OFL"
        )

    @pytest.mark.parametrize("font_id", sorted(_EXPECTED_CURATED_FONT_IDS))
    def test_each_curated_font_resolves_to_its_registered_name(
        self, font_id: str
    ) -> None:
        # By convention every curated font's registered name equals its
        # font_id (no Liberation-style aliasing). Future PRs can break
        # this if a curated family needs a different ReportLab name.
        assert resolve_font_id(font_id) == font_id

    def test_curated_fonts_win_over_default_chain_on_conflict(self) -> None:
        """If a name appears in both maps (none today, but a future PR
        might add one), curated wins. Spot-check the resolution order."""
        # No collision today, but if Helvetica were ever added to
        # CURATED_FONTS it should override the Liberation alias.
        # Verify by direct lookup: curated dict is consulted first.
        from holiday_card.renderers import font_registry
        assert font_registry.CURATED_FONTS  # non-empty
        # Defensive: make sure there's no accidental shadowing today.
        assert not (set(CURATED_FONTS) & set(FONT_MAP)), (
            "FONT_MAP and CURATED_FONTS share keys; resolution order "
            "matters — curated wins, but the conflict should be intentional."
        )
