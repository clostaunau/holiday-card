"""The shared XMP builder and the non-PDF/X disclosure writer (#145).

``build_xmp`` is the one XMP packet the PDF paths write: ``apply_pdfx1a``
for PDF/X targets and ``write_disclosure_xmp`` for a plain PDF that embeds
AI imagery. Each optional group of keys appears exactly when its input does.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pikepdf
import pytest

from holiday_card.core.render_ir import (
    RGBA,
    BeginPage,
    DrawShape,
    EndPage,
    RectGeom,
    SetMetadata,
    SolidPaint,
)
from holiday_card.renderers.pdf_metadata import (
    DIGITAL_SOURCE_COMPOSITE_AI,
    HC_NS,
    IPTC_EXT_NS,
    build_xmp,
    write_disclosure_xmp,
)
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer

_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "pdf": "http://ns.adobe.com/pdf/1.3/",
    "pdfx": "http://ns.adobe.com/pdfx/1.3/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "hc": HC_NS,
    "Iptc4xmpExt": IPTC_EXT_NS,
}


def _xmp(**overrides: Any) -> str:
    kwargs: dict[str, Any] = {
        "title": "christmas-classic",
        "subject": None,
        "producer": "ReportLab",
        "creator": "holiday-card",
        "create_date": "2026-09-30T12:00:00+00:00",
        "modify_date": "2026-09-30T12:00:00+00:00",
        "pdfx_version": None,
        "ai_imagery": None,
    }
    kwargs.update(overrides)
    return build_xmp(**kwargs)


def _keys(xmp: str) -> dict[str, str]:
    """Every property on the rdf:Description as ``prefix:name`` → text (Alt → x-default)."""
    by_uri = {uri: prefix for prefix, uri in _NS.items()}
    desc = ET.fromstring(xmp).find(".//rdf:Description", _NS)
    assert desc is not None
    out: dict[str, str] = {}
    for child in desc:
        uri, _, local = child.tag[1:].partition("}")
        li = child.find(".//rdf:li", _NS)
        out[f"{by_uri[uri]}:{local}"] = ((li if li is not None else child).text or "").strip()
    return out


def test_the_iptc_term_is_the_generative_ai_composite() -> None:
    # Re-read at https://cv.iptc.org/newscodes/digitalsourcetype/ on 2026-09-30:
    # "Mix or composite of several elements, at least one of which is Generative AI".
    assert DIGITAL_SOURCE_COMPOSITE_AI == (
        "http://cv.iptc.org/newscodes/digitalsourcetype/compositeSynthetic"
    )


def test_base_packet_parses_and_carries_the_always_keys() -> None:
    keys = _keys(_xmp())
    assert keys["dc:title"] == "christmas-classic"
    assert keys["pdf:Producer"] == "ReportLab"
    assert keys["xmp:CreatorTool"] == "holiday-card"
    assert keys["xmp:CreateDate"] == "2026-09-30T12:00:00+00:00"
    assert keys["xmp:ModifyDate"] == "2026-09-30T12:00:00+00:00"
    assert keys["xmp:MetadataDate"] == "2026-09-30T12:00:00+00:00"


def test_packet_is_wrapped_in_xpacket_processing_instructions() -> None:
    xmp = _xmp()
    assert xmp.startswith('<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>')
    assert xmp.rstrip().endswith('<?xpacket end="r"?>')


@pytest.mark.parametrize("subject", [None, "christmas-red-green"])
def test_dc_description_iff_subject(subject: str | None) -> None:
    keys = _keys(_xmp(subject=subject))
    if subject is None:
        assert "dc:description" not in keys
    else:
        assert keys["dc:description"] == subject


@pytest.mark.parametrize("version", [None, "PDF/X-1a:2003"])
def test_pdfx_keys_iff_pdfx_version(version: str | None) -> None:
    keys = _keys(_xmp(pdfx_version=version))
    pdfx = {k for k in keys if k.startswith("pdfx:")}
    if version is None:
        assert pdfx == set()
    else:
        assert keys["pdfx:GTS_PDFXVersion"] == version
        assert keys["pdfx:GTS_PDFXConformance"] == version


@pytest.mark.parametrize("labels", [None, "gpt-image-2; google/gemini-3-pro-image"])
def test_ai_keys_iff_ai_imagery(labels: str | None) -> None:
    keys = _keys(_xmp(ai_imagery=labels))
    ai = {k for k in keys if k.startswith(("hc:", "Iptc4xmpExt:"))}
    if labels is None:
        assert ai == set()
    else:
        assert keys["hc:aiGenerated"] == "True"
        assert keys["hc:aiModels"] == labels
        assert keys["Iptc4xmpExt:DigitalSourceType"] == DIGITAL_SOURCE_COMPOSITE_AI


def test_every_value_is_xml_escaped() -> None:
    nasty = 'a & b <c> "d"'
    keys = _keys(_xmp(
        title=nasty, subject=nasty, producer=nasty, creator=nasty,
        pdfx_version="PDF/X-1a:2003", ai_imagery=nasty,
    ))
    for key in ("dc:title", "dc:description", "pdf:Producer", "xmp:CreatorTool", "hc:aiModels"):
        assert keys[key] == nasty


# ---------------------------------------------------------------------------
# write_disclosure_xmp: the non-PDF/X path
# ---------------------------------------------------------------------------


def _plain_pdf(path: Path, subject: str) -> Path:
    IRReportLabRenderer().render(
        [
            BeginPage(width=144, height=144),
            SetMetadata(key="template_id", value="tpl"),
            SetMetadata(key="theme_id", value=subject),
            DrawShape(
                geometry=RectGeom(x=0, y=0, width=144, height=144),
                fill=SolidPaint(color=RGBA(r=0.8, g=0.1, b=0.1)),
            ),
            EndPage(),
        ],
        path,
    )
    return path


def test_write_disclosure_xmp_mirrors_info_and_adds_the_ai_keys(tmp_path: Path) -> None:
    path = _plain_pdf(tmp_path / "card.pdf", "Contains AI-generated imagery (gpt-image-2)")
    write_disclosure_xmp(path, ai_imagery="gpt-image-2")
    with pikepdf.open(path) as pdf:
        info = pdf.docinfo
        meta = pdf.Root["/Metadata"]
        assert str(meta["/Subtype"]) == "/XML"
        keys = _keys(meta.read_bytes().decode("utf-8"))
        assert keys["dc:title"] == str(info["/Title"]) == "tpl"
        assert keys["dc:description"] == str(info["/Subject"])
        assert keys["pdf:Producer"] == str(info["/Producer"])
        assert keys["hc:aiGenerated"] == "True"
        assert keys["hc:aiModels"] == "gpt-image-2"
        assert not any(k.startswith("pdfx:") for k in keys)
        assert "/OutputIntents" not in pdf.Root
        assert "/GTS_PDFXVersion" not in info


def test_svg_backend_does_not_load_pikepdf() -> None:
    # The SVG backend imports the namespace constants from pdf_metadata;
    # pikepdf must stay a function-local import there.
    code = (
        "import sys; import holiday_card.renderers.svg_backend; "
        "sys.exit(1 if 'pikepdf' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


# ---------------------------------------------------------------------------
# apply_pdfx1a: same identification keys, plus dc:description (and AI keys)
# ---------------------------------------------------------------------------

_PDFX_KEYS = {
    "pdfx:GTS_PDFXVersion", "pdfx:GTS_PDFXConformance", "pdf:Producer", "pdf:Trapped",
    "xmp:CreatorTool", "xmp:CreateDate", "xmp:ModifyDate", "xmp:MetadataDate", "dc:title",
}


def _pdfx(tmp_path: Path, ai_imagery: str | None) -> dict[str, str]:
    from holiday_card.renderers.pdfx_postprocess import apply_pdfx1a

    path = tmp_path / "x.pdf"
    IRReportLabRenderer(color_space="cmyk").render(
        [
            BeginPage(width=144, height=144, bleed=9),
            SetMetadata(key="theme_id", value="christmas-red-green"),
            DrawShape(
                geometry=RectGeom(x=0, y=0, width=144, height=144),
                fill=SolidPaint(color=RGBA(r=0.8, g=0.1, b=0.1)),
            ),
            EndPage(),
        ],
        path,
    )
    apply_pdfx1a(path, title="x", ai_imagery=ai_imagery)
    with pikepdf.open(path) as pdf:
        assert str(pdf.docinfo["/GTS_PDFXVersion"]) == "PDF/X-1a:2003"
        keys = _keys(pdf.Root["/Metadata"].read_bytes().decode("utf-8"))
        assert keys["dc:description"] == str(pdf.docinfo["/Subject"])
        return keys


def test_apply_pdfx1a_gains_only_dc_description(tmp_path: Path) -> None:
    keys = _pdfx(tmp_path, ai_imagery=None)
    assert set(keys) == _PDFX_KEYS | {"dc:description"}
    assert keys["dc:description"] == "christmas-red-green"
    assert keys["pdfx:GTS_PDFXVersion"] == "PDF/X-1a:2003"


def test_apply_pdfx1a_adds_the_ai_keys_when_asked(tmp_path: Path) -> None:
    keys = _pdfx(tmp_path, ai_imagery="gpt-image-2")
    assert set(keys) == _PDFX_KEYS | {
        "dc:description", "hc:aiGenerated", "hc:aiModels", "Iptc4xmpExt:DigitalSourceType",
    }
    assert keys["hc:aiModels"] == "gpt-image-2"
