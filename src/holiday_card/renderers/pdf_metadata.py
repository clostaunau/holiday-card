"""The one XMP builder for PDF output, and the AI-imagery disclosure writer (#145).

``build_xmp`` serves both PDF paths: ``pdfx_postprocess.apply_pdfx1a`` (PDF/X
targets, with the ``pdfx:`` identification keys) and ``write_disclosure_xmp``
(a plain PDF that embeds AI imagery). Every value mirrors its ``/Info``
counterpart; ``dc:description`` is the standard XMP mapping of ``/Subject``.

When the card embeds AI imagery the packet also carries ``hc:aiGenerated``,
``hc:aiModels`` (the IR's ``ai_imagery`` labels) and the IPTC
``Iptc4xmpExt:DigitalSourceType``. The SVG backend reuses the namespace
constants, so ``pikepdf`` (and ``pdfx_preflight``, which imports it) stay
function-local here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

__all__ = [
    "DIGITAL_SOURCE_COMPOSITE_AI",
    "HC_NS",
    "IPTC_EXT_NS",
    "build_xmp",
    "iso_date",
    "write_disclosure_xmp",
    "xml_escape",
]

HC_NS: Final = "https://github.com/clostaunau/holiday-card/ns/ai/1.0/"
IPTC_EXT_NS: Final = "http://iptc.org/std/Iptc4xmpExt/2008-02-29/"
# IPTC Digital Source Type "compositeSynthetic": "Mix or composite of several
# elements, at least one of which is Generative AI" (cv.iptc.org, read
# 2026-09-30) — a vector card plus a baked AI raster.
DIGITAL_SOURCE_COMPOSITE_AI: Final = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/compositeSynthetic"
)


def build_xmp(
    *,
    title: str,
    subject: str | None,
    producer: str,
    creator: str,
    create_date: str,
    modify_date: str,
    pdfx_version: str | None,
    ai_imagery: str | None,
) -> str:
    """Return the XMP packet mirroring a PDF's ``/Info``.

    Always: ``dc:title``, ``pdf:Producer``, ``pdf:Trapped``,
    ``xmp:CreatorTool`` and the three ``xmp:*Date`` values (``MetadataDate``
    is the ``/Info /ModDate``: both change together). ``dc:description``
    only when ``subject`` is set. Adobe's pdfx namespace keys only when
    ``pdfx_version`` is set: for a PDF/X-1a:2003 file ``GTS_PDFXVersion`` is
    ``PDF/X-1a:2003`` (ISO 15930-4). The ``hc:`` and IPTC keys only when
    ``ai_imagery`` is set. The bracketing ``<?xpacket?>`` PI is part of the
    XMP specification, not optional.
    """
    ns = [
        '        xmlns:pdfx="http://ns.adobe.com/pdfx/1.3/"\n' if pdfx_version else "",
        '        xmlns:pdf="http://ns.adobe.com/pdf/1.3/"\n',
        '        xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n',
        '        xmlns:dc="http://purl.org/dc/elements/1.1/"',
        f'\n        xmlns:hc="{HC_NS}"\n        xmlns:Iptc4xmpExt="{IPTC_EXT_NS}"'
        if ai_imagery is not None else "",
    ]
    props: list[str] = []
    if pdfx_version is not None:
        version = xml_escape(pdfx_version)
        props += [
            f"      <pdfx:GTS_PDFXVersion>{version}</pdfx:GTS_PDFXVersion>\n",
            f"      <pdfx:GTS_PDFXConformance>{version}</pdfx:GTS_PDFXConformance>\n",
        ]
    props += [
        f"      <pdf:Producer>{xml_escape(producer)}</pdf:Producer>\n",
        "      <pdf:Trapped>False</pdf:Trapped>\n",
        f"      <xmp:CreatorTool>{xml_escape(creator)}</xmp:CreatorTool>\n",
        f"      <xmp:CreateDate>{create_date}</xmp:CreateDate>\n",
        f"      <xmp:ModifyDate>{modify_date}</xmp:ModifyDate>\n",
        f"      <xmp:MetadataDate>{modify_date}</xmp:MetadataDate>\n",
        _alt("dc:title", title),
    ]
    if subject is not None:
        props.append(_alt("dc:description", subject))
    if ai_imagery is not None:
        props += [
            "      <hc:aiGenerated>True</hc:aiGenerated>\n",
            f"      <hc:aiModels>{xml_escape(ai_imagery)}</hc:aiModels>\n",
            "      <Iptc4xmpExt:DigitalSourceType>"
            f"{DIGITAL_SOURCE_COMPOSITE_AI}</Iptc4xmpExt:DigitalSourceType>\n",
        ]
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '    <rdf:Description rdf:about=""\n'
        + "".join(ns) + ">\n"
        + "".join(props)
        + "    </rdf:Description>\n"
        "  </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="r"?>\n'
    )


def _alt(tag: str, value: str) -> str:
    """A language-alternative property with only the ``x-default`` item."""
    return (
        f"      <{tag}>\n"
        "        <rdf:Alt>\n"
        f'          <rdf:li xml:lang="x-default">{xml_escape(value)}</rdf:li>\n'
        "        </rdf:Alt>\n"
        f"      </{tag}>\n"
    )


def xml_escape(s: str) -> str:
    """Escape ``s`` for XML element text and attribute values."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def iso_date(pdf_date: str) -> str:
    """Convert a PDF ``D:`` date to the ISO-8601 form XMP dates use."""
    from holiday_card.renderers.pdfx_preflight import pdf_date_to_datetime

    parsed = pdf_date_to_datetime(pdf_date)
    if parsed is None:
        raise ValueError(f"unparsable PDF date {pdf_date!r}")
    return parsed.isoformat()


def write_disclosure_xmp(pdf_path: Path, *, ai_imagery: str) -> None:
    """Add the AI-disclosure XMP packet to the plain PDF at ``pdf_path``, in place.

    The packet mirrors the ``/Info`` the renderer wrote (whose ``/Subject``
    is already the disclosure) and adds the AI keys; no PDF/X keys. Any
    failure raises: a disclosed card never ships undisclosed (D4).
    """
    import pikepdf
    from pikepdf import Name

    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        info = pdf.docinfo
        xmp = build_xmp(
            title=str(info.get("/Title", "")),
            subject=str(info["/Subject"]) if "/Subject" in info else None,
            producer=str(info.get("/Producer", "")),
            creator=str(info.get("/Creator", "")),
            create_date=iso_date(str(info["/CreationDate"])),
            modify_date=iso_date(str(info["/ModDate"])),
            pdfx_version=None,
            ai_imagery=ai_imagery,
        )
        pdf.Root["/Metadata"] = pdf.make_stream(
            xmp.encode("utf-8"), Type=Name("/Metadata"), Subtype=Name("/XML"),
        )
        pdf.save(pdf_path)
