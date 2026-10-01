"""Post-processor that upgrades a CMYK PDF to PDF/X-1a:2003 compliance.

The PDF backend emits a "plain" CMYK PDF (DeviceCMYK color operators,
embedded TTF fonts, distinct MediaBox/TrimBox/BleedBox/ArtBox). PDF/X-1a
adds the structural metadata a press / POD preflight expects on top:

* **OutputIntent** dictionary in the catalog, with the destination
  ICC profile embedded as ``/DestOutputProfile``. Tells the printer
  how to interpret the device-CMYK values.
  The OutputIntent names the ICC registry's ``CGATS21-2-CRPC6``
  characterization, which matches the bundled GRACoL2013 profile.
* **/Info** carries ``/GTS_PDFXVersion`` (and ``/GTS_PDFXConformance``)
  = ``PDF/X-1a:2003``, ``/Title``, ``/CreationDate``, ``/ModDate`` and
  ``/Trapped /False`` (PDF/X-1a forbids ``/Unknown`` or absence).
* **XMP metadata stream** mirroring those values: ``pdfx:GTS_PDFXVersion``
  = ``PDF/X-1a:2003`` (ISO 15930-4; ``PDF/X-1:2001`` is the 2001
  identifier), ``dc:title``, ``dc:description`` (``/Subject``),
  ``pdf:Producer`` and ``xmp:CreateDate`` / ``ModifyDate`` /
  ``MetadataDate`` equal to their /Info counterparts, plus the AI-imagery
  disclosure keys when asked. The packet comes from the shared
  ``pdf_metadata.build_xmp`` (#145).
* **PDF version 1.4** (PDF/X-1a:2003 conformance level).

Caller contract: the input PDF must already be CMYK-only, opaque and have
all fonts embedded. ``IRReportLabRenderer(color_space="cmyk")`` embeds every
font and emits CMYK operators; transparency and RGB images are still
emitted today (#71). ``renderers/pdfx_preflight.py`` checks the result.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name, String

from holiday_card.core.color_management import default_cmyk_icc_path
from holiday_card.renderers.pdf_metadata import build_xmp, iso_date
from holiday_card.renderers.pdfx_preflight import pdf_date_to_datetime

__all__ = [
    "OUTPUT_CONDITION",
    "OUTPUT_CONDITION_IDENTIFIER",
    "PDFXVersionError",
    "apply_pdfx1a",
]

# ICC characterization registry entry for the bundled GRACoL2013_CRPC6.icc
# (registry.color.org/cmyk-registry/cgats21-2-crpc6).
OUTPUT_CONDITION_IDENTIFIER = "CGATS21-2-CRPC6"
OUTPUT_CONDITION = "GRACoL 2013, CRPC6 \u2014 CGATS 21-2"


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
    ai_imagery: str | None = None,
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
        ai_imagery: The IR's ``ai_imagery`` labels when the file embeds AI
            imagery: the XMP then carries the ``hc:`` and IPTC disclosure
            keys (#145). ``/Subject`` is mirrored as ``dc:description``.
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
                "/OutputCondition": String(OUTPUT_CONDITION),
                "/OutputConditionIdentifier": String(OUTPUT_CONDITION_IDENTIFIER),
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
        # ISO 15930-4 identifies the file by /Info /GTS_PDFXVersion; the
        # Conformance key is redundant for X-1a:2003 but InDesign-style
        # consumers read it.
        info["/GTS_PDFXVersion"] = String(pdfx_version)
        info["/GTS_PDFXConformance"] = String(pdfx_version)
        now = _pdf_date_now()
        for key in ("/CreationDate", "/ModDate"):
            if key not in info or pdf_date_to_datetime(str(info[key])) is None:
                info[key] = String(now)

        # XMP metadata stream. PDF/X requires an XMP packet declaring
        # the conformance level via the pdfx namespace; its values must
        # equal their /Info counterparts.
        xmp_bytes = build_xmp(
            title=resolved_title,
            subject=str(info["/Subject"]) if "/Subject" in info else None,
            creator=creator,
            producer=str(info["/Producer"]),
            pdfx_version=pdfx_version,
            create_date=iso_date(str(info["/CreationDate"])),
            modify_date=iso_date(str(info["/ModDate"])),
            ai_imagery=ai_imagery,
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
