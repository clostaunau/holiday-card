"""Integration tests for PDF/X-1a:2003 output via ``--export-for moo-a6``.

Verifies the structural properties that a real preflight (MOO's
ingester, callas pdfToolbox, Adobe Acrobat Pro) checks for. We don't
run a real preflight here — those tools aren't installable in CI —
but we cover the same on-disk artifacts they inspect:

* PDF header version is 1.4 (PDF/X-1a:2003 conformance level).
* Document catalog has ``/OutputIntents`` with ``/S = /GTS_PDFX`` and
  an embedded ``/DestOutputProfile`` stream carrying the CGATS
  GRACoL2013_CRPC6 ICC profile (``/N = 4``, the CMYK profile
  component count).
* Document catalog has ``/Metadata`` (XMP stream) declaring
  ``GTS_PDFXVersion`` / ``GTS_PDFXConformance``.
* ``/Info /Trapped`` is ``/False`` (PDF/X-1a forbids absence or
  ``/Unknown``).
* The page content stream uses DeviceCMYK color operators
  (``k`` / ``K``) and no DeviceRGB operators (``rg`` / ``RG``).

Pairs with ``test_per_panel_output.py`` (geometry-only checks for the
moo-a6 target); together they cover the full moo-a6 export.
"""

from __future__ import annotations

import re
from pathlib import Path

import pikepdf
import pytest

from holiday_card.core.color_management import (
    DEFAULT_CMYK_PROFILE_FILENAME,
    default_cmyk_icc_path,
    rgb_to_cmyk,
)
from holiday_card.core.generators import CardGenerator
from holiday_card.renderers.pdfx_postprocess import (
    PDFXVersionError,
    apply_pdfx1a,
)

TEMPLATE_ID = "christmas-classic"


def _content_bytes(page: pikepdf.Page) -> bytes:
    """Concatenated content stream(s) of a PDF page."""
    contents = page.Contents
    streams = contents if isinstance(contents, pikepdf.Array) else [contents]
    return b"".join(s.read_bytes() for s in streams)


# Whitespace-bounded color operator patterns. We use byte-level regex
# against the latin-1-decoded stream so we don't drag a PDF lexer in.
_FILL_RGB = re.compile(rb"(?:^|\s)rg(?:\s|$)")
_STROKE_RGB = re.compile(rb"(?:^|\s)RG(?:\s|$)")
_FILL_CMYK = re.compile(rb"(?:^|\s)k(?:\s|$)")
_STROKE_CMYK = re.compile(rb"(?:^|\s)K(?:\s|$)")


class TestPdfxMooA6:
    """End-to-end: moo-a6 target produces PDF/X-1a:2003 output."""

    @pytest.fixture
    def rendered_dir(self, tmp_path: Path) -> Path:
        gen = CardGenerator()
        out = tmp_path / "moo-a6"
        paths = gen.generate(
            gen.create_card(TEMPLATE_ID, message="Merry Christmas!"),
            out,
            target="moo-a6",
        )
        # Sanity check before each test inspects the artifacts.
        assert len(paths) == 4
        assert all(p.suffix == ".pdf" and p.exists() for p in paths)
        return out

    def test_pdf_version_is_1_4(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                assert pdf.pdf_version == "1.4", (
                    f"{pdf_path.name}: expected PDF version 1.4, got {pdf.pdf_version}"
                )

    def test_output_intent_present_and_well_formed(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                assert "/OutputIntents" in pdf.Root, f"{pdf_path.name}: no /OutputIntents"
                output_intents = pdf.Root["/OutputIntents"]
                assert len(output_intents) == 1, (
                    f"{pdf_path.name}: expected exactly one OutputIntent"
                )
                oi = output_intents[0]
                assert str(oi["/Type"]) == "/OutputIntent"
                assert str(oi["/S"]) == "/GTS_PDFX"
                assert "CGATS" in str(oi["/OutputConditionIdentifier"])
                assert "color.org" in str(oi["/RegistryName"])
                profile = oi["/DestOutputProfile"]
                assert int(profile["/N"]) == 4, (
                    f"{pdf_path.name}: DestOutputProfile /N should be 4 (CMYK)"
                )
                # Profile body should be ~3.4MB raw, but pikepdf may
                # re-compress with /Filter. Bound loosely.
                assert int(profile["/Length"]) > 1000

    def test_metadata_xmp_declares_pdfx_conformance(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                assert "/Metadata" in pdf.Root, f"{pdf_path.name}: no /Metadata"
                xmp_bytes = pdf.Root["/Metadata"].read_bytes()
                xmp_text = xmp_bytes.decode("utf-8")
                assert "GTS_PDFXVersion" in xmp_text
                assert "PDF/X-1:2001" in xmp_text
                assert "GTS_PDFXConformance" in xmp_text
                assert "PDF/X-1a:2003" in xmp_text

    def test_info_trapped_is_false(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                assert "/Trapped" in pdf.docinfo, f"{pdf_path.name}: no /Trapped key"
                assert str(pdf.docinfo["/Trapped"]) == "/False", (
                    f"{pdf_path.name}: /Trapped must be /False"
                )

    def test_content_stream_uses_cmyk_operators(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    body = _content_bytes(page)
                    rgb_fill = len(_FILL_RGB.findall(body))
                    rgb_stroke = len(_STROKE_RGB.findall(body))
                    cmyk_fill = len(_FILL_CMYK.findall(body))
                    cmyk_stroke = len(_STROKE_CMYK.findall(body))
                    assert rgb_fill == 0 and rgb_stroke == 0, (
                        f"{pdf_path.name} page {page_idx}: "
                        f"RGB ops present (rg={rgb_fill}, RG={rgb_stroke}); "
                        "PDF/X-1a forbids DeviceRGB."
                    )
                    # At least one color operator should appear — every
                    # christmas-classic panel has at least a background.
                    assert (cmyk_fill + cmyk_stroke) > 0, (
                        f"{pdf_path.name} page {page_idx}: "
                        "no CMYK color operators found in content stream."
                    )


class TestRgbToCmyk:
    """``rgb_to_cmyk`` formula correctness."""

    def test_pure_black(self) -> None:
        assert rgb_to_cmyk(0.0, 0.0, 0.0) == (0.0, 0.0, 0.0, 1.0)

    def test_pure_white(self) -> None:
        assert rgb_to_cmyk(1.0, 1.0, 1.0) == (0.0, 0.0, 0.0, 0.0)

    def test_pure_red(self) -> None:
        c, m, y, k = rgb_to_cmyk(1.0, 0.0, 0.0)
        assert (c, m, y, k) == (0.0, 1.0, 1.0, 0.0)

    def test_pure_green(self) -> None:
        c, m, y, k = rgb_to_cmyk(0.0, 1.0, 0.0)
        assert (c, m, y, k) == (1.0, 0.0, 1.0, 0.0)

    def test_pure_blue(self) -> None:
        c, m, y, k = rgb_to_cmyk(0.0, 0.0, 1.0)
        assert (c, m, y, k) == (1.0, 1.0, 0.0, 0.0)

    def test_clamping(self) -> None:
        # Out-of-range inputs are clamped rather than crashing.
        assert rgb_to_cmyk(-0.5, 0.5, 1.5) == rgb_to_cmyk(0.0, 0.5, 1.0)


class TestIccProfile:
    """The bundled ICC profile is resolvable."""

    def test_default_path_exists_and_is_v4_icc(self) -> None:
        path = default_cmyk_icc_path()
        assert path.is_file()
        assert path.name == DEFAULT_CMYK_PROFILE_FILENAME
        # ICC v4 header has 'acsp' magic at byte offset 36.
        head = path.read_bytes()[:128]
        assert head[36:40] == b"acsp", "Bundled file is not an ICC profile"


class TestPdfxPostprocessGuards:
    """Direct unit tests for the post-processor's input validation."""

    def test_unsupported_version_raises(self, tmp_path: Path) -> None:
        bogus = tmp_path / "x.pdf"
        bogus.write_bytes(b"%PDF-1.4\n")
        with pytest.raises(PDFXVersionError):
            apply_pdfx1a(bogus, pdfx_version="PDF/X-4:2010")
