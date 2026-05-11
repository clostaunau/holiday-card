"""Post-processor that upgrades a CMYK PDF to PDF/X-1a:2003 compliance.

The PDF backend emits a "plain" CMYK PDF (DeviceCMYK color operators,
embedded TTF fonts, distinct MediaBox/TrimBox/BleedBox/ArtBox). PDF/X-1a
adds the structural metadata a press / POD preflight expects on top:

* **OutputIntent** dictionary in the catalog, with the destination
  ICC profile embedded as ``/DestOutputProfile``. Tells the printer
  how to interpret the device-CMYK values.
* **XMP metadata stream** declaring ``GTS_PDFXVersion`` /
  ``GTS_PDFXConformance``.
* **/Info /Trapped** set to ``/False`` (PDF/X-1a forbids ``/Unknown``
  or absence).
* **PDF version 1.4** (PDF/X-1a:2003 conformance level).

Caller contract: the input PDF must already be CMYK-only and have all
fonts embedded. Pairing this with
``IRReportLabRenderer(color_space="cmyk")`` satisfies both.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name, String

from holiday_card.core.color_management import default_cmyk_icc_path

__all__ = ["apply_pdfx1a", "PDFXVersionError"]


class PDFXVersionError(ValueError):
    """Raised when a PDF/X conformance level we don't implement is requested."""


_SUPPORTED_VERSIONS = ("PDF/X-1a:2003",)


def apply_pdfx1a(
    pdf_path: Path,
    *,
    icc_profile_path: Path | None = None,
    title: str | None = None,
    creator: str = "holiday-card",
    pdfx_version: str = "PDF/X-1a:2003",
) -> None:
    """In-place upgrade ``pdf_path`` to PDF/X conformance.

    Args:
        pdf_path: Path to a CMYK PDF (in place). Will be overwritten
            with the PDF/X-1a:2003 version.
        icc_profile_path: ICC profile to embed as the OutputIntent's
            ``DestOutputProfile``. Defaults to the bundled
            ``GRACoL2013_CRPC6.icc``.
        title: Document title for ``/Info /Title`` and XMP
            ``dc:title``. Falls back to the existing title or the
            file stem.
        creator: Creator string for ``/Info /Creator`` and XMP
            ``xmp:CreatorTool``.
        pdfx_version: Conformance level label. Currently only
            ``"PDF/X-1a:2003"`` is implemented; other values raise
            ``PDFXVersionError``.
    """
    if pdfx_version not in _SUPPORTED_VERSIONS:
        raise PDFXVersionError(
            f"PDF/X version {pdfx_version!r} not implemented. "
            f"Supported: {', '.join(_SUPPORTED_VERSIONS)}"
        )
    icc_path = icc_profile_path or default_cmyk_icc_path()
    icc_bytes = icc_path.read_bytes()
    profile_name = icc_path.stem

    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        # Embed the ICC profile as a stream. /N declares the number
        # of color components — 4 for CMYK profiles.
        icc_stream = pdf.make_stream(icc_bytes, N=4)

        # OutputIntent dict: tells the printer's RIP how to interpret
        # device CMYK numbers. The /S key being /GTS_PDFX is what
        # marks this as a PDF/X-style OutputIntent (vs PDF/A).
        output_intent = pdf.make_indirect(
            Dictionary({
                "/Type": Name("/OutputIntent"),
                "/S": Name("/GTS_PDFX"),
                "/OutputCondition": String(
                    "Commercial and specialty printing per CGATS TR 006 (GRACoL2013)."
                ),
                "/OutputConditionIdentifier": String("CGATS TR 006"),
                "/RegistryName": String("http://www.color.org"),
                "/Info": String(profile_name),
                "/DestOutputProfile": icc_stream,
            })
        )
        pdf.Root["/OutputIntents"] = Array([output_intent])

        # /Info dictionary
        info = pdf.docinfo
        existing_title = str(info["/Title"]) if "/Title" in info else ""
        resolved_title = title or existing_title or pdf_path.stem
        info["/Title"] = String(resolved_title)
        # PDF/X-1a requires /Trapped to be /True or /False (Name
        # values in the PDF), not /Unknown or absent.
        info["/Trapped"] = Name("/False")
        info["/Creator"] = String(creator)
        info["/Producer"] = String(f"{creator} via pikepdf + reportlab")
        if "/ModDate" not in info:
            info["/ModDate"] = String(_pdf_date_now())

        # XMP metadata stream. PDF/X requires an XMP packet declaring
        # the conformance level via the pdfx namespace.
        xmp_bytes = _build_xmp(
            title=resolved_title,
            creator=creator,
            producer=str(info["/Producer"]),
        ).encode("utf-8")
        meta_stream = pdf.make_stream(
            xmp_bytes,
            Type=Name("/Metadata"),
            Subtype=Name("/XML"),
        )
        pdf.Root["/Metadata"] = meta_stream

        # PDF/X-1a:2003 is defined at PDF version 1.4. ``pdf_version``
        # itself is read-only in pikepdf; ``force_version`` on save
        # rewrites the header (and, importantly, the catalog
        # ``/Version`` entry if present).
        pdf.save(pdf_path, force_version="1.4")


def _pdf_date_now() -> str:
    """Return the current time as a PDF date string (``D:YYYYMMDDHHmmSSZ``)."""
    now = datetime.now(UTC)
    return now.strftime("D:%Y%m%d%H%M%SZ")


def _build_xmp(*, title: str, creator: str, producer: str) -> str:
    """Return the XMP packet declaring PDF/X-1a:2003 conformance.

    Adobe's pdfx namespace (``http://ns.adobe.com/pdfx/1.3/``) carries
    the two GTS_PDFX* keys preflights look for. The bracketing
    ``<?xpacket?>`` PI is part of the XMP specification, not optional.
    """
    title_esc = _xml_escape(title)
    creator_esc = _xml_escape(creator)
    producer_esc = _xml_escape(producer)
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '    <rdf:Description rdf:about=""\n'
        '        xmlns:pdfx="http://ns.adobe.com/pdfx/1.3/"\n'
        '        xmlns:pdf="http://ns.adobe.com/pdf/1.3/"\n'
        '        xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n'
        '        xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        '      <pdfx:GTS_PDFXVersion>PDF/X-1:2001</pdfx:GTS_PDFXVersion>\n'
        '      <pdfx:GTS_PDFXConformance>PDF/X-1a:2003</pdfx:GTS_PDFXConformance>\n'
        f'      <pdf:Producer>{producer_esc}</pdf:Producer>\n'
        '      <pdf:Trapped>False</pdf:Trapped>\n'
        f'      <xmp:CreatorTool>{creator_esc}</xmp:CreatorTool>\n'
        '      <dc:title>\n'
        '        <rdf:Alt>\n'
        f'          <rdf:li xml:lang="x-default">{title_esc}</rdf:li>\n'
        '        </rdf:Alt>\n'
        '      </dc:title>\n'
        '    </rdf:Description>\n'
        '  </rdf:RDF>\n'
        '</x:xmpmeta>\n'
        '<?xpacket end="r"?>\n'
    )


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
