"""Integration tests for PDF/X-1a:2003 output via ``--export-for moo-a6``.

Checks the on-disk metadata a press preflight inspects on christmas-classic:

* PDF header version is 1.4 (PDF/X-1a:2003 conformance level).
* Document catalog has one ``/OutputIntents`` entry with ``/S = /GTS_PDFX``,
  ``/OutputConditionIdentifier (CGATS21-2-CRPC6)`` and an embedded
  ``/DestOutputProfile`` stream carrying the GRACoL2013_CRPC6 ICC profile
  (``/N = 4``).
* ``/Info /GTS_PDFXVersion`` and the XMP ``pdfx:GTS_PDFXVersion`` are both
  ``PDF/X-1a:2003`` (never the 2001 identifier ``PDF/X-1:2001``), and the
  XMP title, producer and dates equal their ``/Info`` counterparts.
* ``/Info /Trapped`` is ``/False`` (PDF/X-1a forbids absence or
  ``/Unknown``).
* The page content stream uses DeviceCMYK color operators
  (``k`` / ``K``) and no DeviceRGB operators (``rg`` / ``RG``).

The full rule preflight (fonts, transparency, image colour spaces, page
boxes) runs over every template in ``test_pdfx_preflight_all_templates.py``,
cross-checked in CI by poppler ``pdffonts`` and Ghostscript (#69, D11).
Pairs with ``test_per_panel_output.py`` (geometry-only checks for the
moo-a6 target).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pikepdf
import pytest

from holiday_card.core.color_management import (
    DEFAULT_CMYK_PROFILE_FILENAME,
    ICCProfileNotFoundError,
    default_cmyk_icc_path,
)
from holiday_card.core.data_paths import data_path
from holiday_card.core.generators import CardGenerator
from holiday_card.renderers.pdfx_postprocess import (
    PDFXVersionError,
    apply_pdfx1a,
)
from holiday_card.renderers.pdfx_preflight import (
    PDFXConformanceError,
    PreflightViolation,
)

pytestmark = pytest.mark.pdfx

TEMPLATE_ID = "christmas-classic"


def _content_bytes(page: pikepdf.Page) -> bytes:
    """Concatenated content stream(s) of a PDF page."""
    contents = page.Contents
    streams = contents if isinstance(contents, pikepdf.Array) else [contents]
    return b"".join(s.read_bytes() for s in streams)


# Whitespace-bounded color operator patterns. We use byte-level regex
# against the latin-1-decoded stream so we don't drag a PDF lexer in.
_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "pdf": "http://ns.adobe.com/pdf/1.3/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _xmp_fields(xmp: bytes) -> dict[str, str]:
    """Flatten the XMP fields these tests compare against /Info."""
    desc = ET.fromstring(xmp).find(".//rdf:Description", _NS)
    assert desc is not None
    out: dict[str, str] = {}
    for key in ("pdf:Producer", "xmp:CreateDate", "xmp:ModifyDate", "xmp:MetadataDate"):
        el = desc.find(key, _NS)
        assert el is not None and el.text, f"XMP lacks {key}"
        out[key] = el.text
    title = desc.find("dc:title/rdf:Alt/rdf:li", _NS)
    assert title is not None and title.text is not None
    out["dc:title"] = title.text
    return out


def _info_date(value: str) -> datetime:
    """Parse a PDF ``D:YYYYMMDDHHmmSS`` date with its ``Z`` / ``+hh'mm'`` zone.

    Written independently of the post-processor so the test doesn't share
    its parser.
    """
    m = re.fullmatch(r"D:(\d{14})(Z|[+-]\d{2}'\d{2}'?)?(?:00'00)?", value)
    assert m, f"unparsable PDF date {value!r}"
    stamp = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    zone = m.group(2) or "Z"
    if zone == "Z":
        return stamp.replace(tzinfo=UTC)
    sign = 1 if zone[0] == "+" else -1
    hours, minutes = int(zone[1:3]), int(zone[4:6])
    return stamp.replace(tzinfo=timezone(sign * timedelta(hours=hours, minutes=minutes)))


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
                assert str(oi["/OutputConditionIdentifier"]) == "CGATS21-2-CRPC6"
                assert str(oi["/OutputCondition"]) == (
                    "GRACoL 2013, CRPC6 \u2014 CGATS 21-2"
                )
                assert str(oi["/RegistryName"]) == "http://www.color.org"
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
                assert (
                    "<pdfx:GTS_PDFXVersion>PDF/X-1a:2003</pdfx:GTS_PDFXVersion>"
                    in xmp_text
                )
                assert "PDF/X-1:2001" not in xmp_text
                assert "GTS_PDFXConformance" in xmp_text

    def test_info_declares_pdfx_version(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                assert str(pdf.docinfo["/GTS_PDFXVersion"]) == "PDF/X-1a:2003"
                assert str(pdf.docinfo["/GTS_PDFXConformance"]) == "PDF/X-1a:2003"

    def test_xmp_dates_agree_with_info(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                xmp = _xmp_fields(pdf.Root["/Metadata"].read_bytes())
                created = _info_date(str(pdf.docinfo["/CreationDate"]))
                modified = _info_date(str(pdf.docinfo["/ModDate"]))
                assert datetime.fromisoformat(xmp["xmp:CreateDate"]) == created
                assert datetime.fromisoformat(xmp["xmp:ModifyDate"]) == modified
                assert datetime.fromisoformat(xmp["xmp:MetadataDate"]) == modified

    def test_xmp_producer_and_title_agree_with_info(self, rendered_dir: Path) -> None:
        for pdf_path in sorted(rendered_dir.glob("*.pdf")):
            with pikepdf.open(pdf_path) as pdf:
                xmp = _xmp_fields(pdf.Root["/Metadata"].read_bytes())
                assert xmp["pdf:Producer"] == str(pdf.docinfo["/Producer"])
                assert xmp["dc:title"] == str(pdf.docinfo["/Title"])

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

    def test_front_background_is_icc_converted(self, rendered_dir: Path) -> None:
        # The classic front bg is rgb(0.8, 0.1, 0.1). LittleCMS (rel. col. + BPC)
        # into GRACoL2013 gives 0/98.8/92.5/12.2; the naive formula gave
        # 0/.875/.875/.2 (brick-orange on press), observed 2026-09-26 (#70).
        with pikepdf.open(rendered_dir / "front.pdf") as pdf:
            first_k = next(
                [float(o) for o in operands]
                for operands, op in pikepdf.parse_content_stream(pdf.pages[0])
                if str(op) == "k"
            )
        assert first_k == pytest.approx([0.0, 0.988, 0.925, 0.122], abs=0.02)
        assert first_k != pytest.approx([0.0, 0.875, 0.875, 0.2], abs=0.005)


class TestIccProfile:
    """The bundled ICC profile is resolvable."""

    def test_default_path_exists_and_is_v4_icc(self) -> None:
        path = default_cmyk_icc_path()
        assert path.is_file()
        assert path.name == DEFAULT_CMYK_PROFILE_FILENAME
        # ICC v4 header has 'acsp' magic at byte offset 36.
        head = path.read_bytes()[:128]
        assert head[36:40] == b"acsp", "Bundled file is not an ICC profile"

    def test_default_path_is_bundled_package_data(self) -> None:
        assert default_cmyk_icc_path() == (
            data_path("icc") / DEFAULT_CMYK_PROFILE_FILENAME
        )

    def test_missing_profile_raises_icc_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import holiday_card.core.color_management as cm

        monkeypatch.setattr(cm, "data_path", lambda _kind: tmp_path)
        with pytest.raises(ICCProfileNotFoundError, match=str(tmp_path)):
            default_cmyk_icc_path()


class TestPdfxPostprocessGuards:
    """Direct unit tests for the post-processor's input validation."""

    def test_unsupported_version_raises(self, tmp_path: Path) -> None:
        bogus = tmp_path / "x.pdf"
        bogus.write_bytes(b"%PDF-1.4\n")
        with pytest.raises(PDFXVersionError):
            apply_pdfx1a(bogus, pdfx_version="PDF/X-4:2010")


class TestFlattenWiring:
    """Only PDF/X targets flatten transparency in the compiler (#71, D10)."""

    @pytest.mark.parametrize(
        ("target", "expected"), [("moo-a6", True), ("per-panel-pdf", False)]
    )
    def test_per_panel_context_flattens_only_for_pdfx(
        self, target: str, expected: bool
    ) -> None:
        from holiday_card.core.export_targets import get_target
        from holiday_card.core.per_panel import build_per_panel_context

        card = CardGenerator().create_card(TEMPLATE_ID)
        ctx = build_per_panel_context(card.panels[0], get_target(target))
        assert ctx.flatten_transparency is expected


@pytest.fixture(scope="module")
def front(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """christmas-photo-ornament's moo-a6 front panel."""
    gen = CardGenerator()
    out = tmp_path_factory.mktemp("photo-ornament")
    gen.generate(gen.create_card("christmas-photo-ornament"), out, target="moo-a6")
    return out / "front.pdf"


class TestPhotoOrnamentFront:
    """The photo is converted to CMYK and nothing is translucent (#71)."""

    def test_single_image_is_device_cmyk_without_smask(self, front: Path) -> None:
        with pikepdf.open(front) as pdf:
            images = list(pdf.pages[0].get_images().values())
            assert len(images) == 1
            assert str(images[0].ColorSpace) == "/DeviceCMYK"
            assert "/SMask" not in images[0]

    def test_no_translucent_extgstate(self, front: Path) -> None:
        with pikepdf.open(front) as pdf:
            states = pdf.pages[0].Resources.get("/ExtGState", {})
            assert all(float(gs.get(k, 1)) >= 1 for gs in states.values()
                       for k in ("/ca", "/CA"))


_VIOLATION = PreflightViolation(rule="transparency.ca", page=1, detail="/GS1 /ca 0.5")


class TestPdfxSelfCheck:
    """Every PDF/X file is preflighted after ``apply_pdfx1a`` (#71, D4)."""

    def test_violation_raises_conformance_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from holiday_card.renderers import pdfx_preflight

        monkeypatch.setattr(pdfx_preflight, "preflight_pdfx1a", lambda _p: [_VIOLATION])
        gen = CardGenerator()
        with pytest.raises(PDFXConformanceError) as err:
            gen.generate(gen.create_card(TEMPLATE_ID), tmp_path / "out", target="moo-a6")
        assert err.value.violations == [_VIOLATION]
        assert "transparency.ca" in str(err.value)

    def test_clean_files_pass(self, tmp_path: Path) -> None:
        gen = CardGenerator()
        written = gen.generate(gen.create_card(TEMPLATE_ID), tmp_path / "out", target="moo-a6")
        assert len(written) == 4

    def test_cli_exits_non_zero_listing_violations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from holiday_card.cli.commands import app
        from holiday_card.renderers import pdfx_preflight

        monkeypatch.setattr(pdfx_preflight, "preflight_pdfx1a", lambda _p: [_VIOLATION])
        result = CliRunner().invoke(
            app, ["create", TEMPLATE_ID, "--export-for", "moo-a6", "-o", str(tmp_path / "o")]
        )
        assert result.exit_code == 2, result.output
        assert "PDF/X-1a" in result.output
        assert "transparency.ca" in result.output
        assert "/GS1 /ca 0.5" in result.output
        assert "Traceback" not in result.output


def _translucent_extgstates(pdf_path: Path) -> int:
    with pikepdf.open(pdf_path) as pdf:
        return sum(
            1
            for page in pdf.pages
            for gs in page.Resources.get("/ExtGState", {}).values()
            if any(float(gs.get(k, 1)) < 1 for k in ("/ca", "/CA"))
        )


class TestLiveAlphaOutsidePdfx:
    """Flattening is PDF/X-only: ``letter`` keeps live alpha (#71).

    christmas-winter-sky was migrated to opaque colours, so this pins the
    rule on birthday-balloons, whose confetti is translucent over a solid
    background and is flattened only for moo-a6.
    """

    def test_letter_keeps_ca_but_moo_a6_does_not(self, tmp_path: Path) -> None:
        gen = CardGenerator()
        card = gen.create_card("birthday-balloons")
        [letter] = gen.generate(card, tmp_path / "letter.pdf")
        moo = gen.generate(card, tmp_path / "moo", target="moo-a6")
        assert _translucent_extgstates(letter) > 0
        assert sum(_translucent_extgstates(p) for p in moo) == 0
