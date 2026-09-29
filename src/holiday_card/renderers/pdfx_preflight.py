"""Rule-based PDF/X-1a:2003 preflight (ISO 15930-4) over pikepdf.

veraPDF has no PDF/X profile (D11, amended 2026-09-26), so this module is the
project's conformance checker. It reports every violation it finds as data;
it never raises for a non-conforming file. ``tests/integration/
test_pdfx_preflight_all_templates.py`` runs it over every shipped template's
``--export-for moo-a6`` output, and the ``pdfx-preflight`` CI job cross-checks
it with poppler ``pdffonts`` and Ghostscript ``inkcov``.

Rules (``PreflightViolation.rule``):

* ``header.version`` / ``trailer.id`` / ``trailer.encrypt``: header 1.4,
  ``/ID`` present, no ``/Encrypt``.
* ``info.missing`` / ``info.trapped`` / ``info.pdfx_version``: ``/Title``,
  ``/CreationDate``, ``/ModDate``; ``/Trapped`` is ``/True`` or ``/False``;
  ``/GTS_PDFXVersion`` is ``PDF/X-1a:2003``.
* ``xmp.missing`` / ``xmp.mismatch``: an XMP packet whose title, producer,
  PDF/X version and dates equal their ``/Info`` counterparts.
* ``output_intent.count`` / ``output_intent.profile``: exactly one
  ``/GTS_PDFX`` OutputIntent with an ``N=4`` ``/DestOutputProfile``.
* ``boxes.missing`` / ``boxes.nesting``: MediaBox ⊇ BleedBox ⊇ TrimBox and
  ArtBox ⊆ TrimBox on every page.
* ``font.not_embedded``: every font reachable from a page (Form XObjects,
  tiling patterns and Type 3 glyph resources included) is embedded.
* ``transparency.ca`` / ``transparency.blend_mode`` / ``transparency.smask``
  / ``transparency.image_smask`` / ``transparency.group``.
* ``colorspace.rgb_content`` / ``colorspace.rgb_image`` /
  ``colorspace.rgb_shading``: DeviceRGB, CalRGB, ICCBased or Lab in content
  operators, images or shadings.
* ``forbidden.javascript`` / ``forbidden.jpx`` /
  ``forbidden.transfer_function``.

Not wired into the generator yet: #71 turns violations into errors once the
transparency and RGB-image rules pass for the shipped templates.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name, Stream

__all__ = ["PDFX_VERSION", "PDFXConformanceError", "PreflightViolation", "preflight_pdfx1a"]

PDFX_VERSION = "PDF/X-1a:2003"

_Add = Callable[[str, str], None]

_FORBIDDEN_CS = frozenset({"/DeviceRGB", "/CalRGB", "/ICCBased", "/Lab"})
_ALLOWED_BLEND = frozenset({"/Normal", "/Compatible"})

_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "pdf": "http://ns.adobe.com/pdf/1.3/",
    "pdfx": "http://ns.adobe.com/pdfx/1.3/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


@dataclass(frozen=True)
class PreflightViolation:
    """One PDF/X-1a rule the file breaks.

    Attributes:
        rule: Dotted rule id, e.g. ``"font.not_embedded"``.
        page: 1-based page number, or ``None`` for document-level rules.
        detail: Human-readable description naming the offending object.
    """

    rule: str
    page: int | None
    detail: str


class PDFXConformanceError(Exception):
    """A file written for a PDF/X target fails its own preflight (D4).

    ``violations`` holds every rule broken; ``str()`` lists them one per line.
    """

    def __init__(self, path: Path, violations: list[PreflightViolation]) -> None:
        self.path = path
        self.violations = violations
        lines = [
            f"  {v.rule}" + (f" (page {v.page})" if v.page is not None else "") + f": {v.detail}"
            for v in violations
        ]
        super().__init__(
            f"{path.name} is not {PDFX_VERSION} conformant "
            f"({len(violations)} violation{'s' if len(violations) != 1 else ''}):\n"
            + "\n".join(lines)
        )


def preflight_pdfx1a(pdf_path: Path) -> list[PreflightViolation]:
    """Return every PDF/X-1a:2003 violation in ``pdf_path`` (``[]`` if clean)."""
    out: list[PreflightViolation] = []
    with pikepdf.open(pdf_path) as pdf:
        _check_document(pdf, out)
        for index, page in enumerate(pdf.pages, start=1):
            _check_page(page, index, out)
    return out


# ----------------------------------------------------------------------
# Document-level rules
# ----------------------------------------------------------------------


def _check_document(pdf: pikepdf.Pdf, out: list[PreflightViolation]) -> None:
    def add(rule: str, detail: str) -> None:
        out.append(PreflightViolation(rule, None, detail))

    if pdf.pdf_version != "1.4":
        add("header.version", f"header is PDF-{pdf.pdf_version}, need 1.4")
    if "/ID" not in pdf.trailer:
        add("trailer.id", "trailer has no /ID")
    if pdf.is_encrypted or "/Encrypt" in pdf.trailer:
        add("trailer.encrypt", "file is encrypted")

    info = pdf.docinfo
    for key in ("/Title", "/CreationDate", "/ModDate"):
        if key not in info:
            add("info.missing", f"/Info has no {key}")
    trapped = str(info.get("/Trapped", ""))
    if trapped not in ("/True", "/False"):
        add("info.trapped", f"/Info /Trapped is {trapped or 'absent'}, need /True or /False")
    version = str(info.get("/GTS_PDFXVersion", ""))
    if version != PDFX_VERSION:
        add("info.pdfx_version",
            f"/Info /GTS_PDFXVersion is {version or 'absent'!r}, need {PDFX_VERSION!r}")

    _check_xmp(pdf, add)
    _check_output_intents(pdf, add)
    _check_forbidden_document(pdf, add)


def _check_xmp(pdf: pikepdf.Pdf, add: _Add) -> None:
    if "/Metadata" not in pdf.Root:
        add("xmp.missing", "catalog has no /Metadata XMP stream")
        return
    try:
        root = ET.fromstring(pdf.Root["/Metadata"].read_bytes())
    except ET.ParseError as e:
        add("xmp.missing", f"XMP packet is not well-formed XML: {e}")
        return
    xmp = _xmp_values(root)
    info = pdf.docinfo

    def compare(xmp_key: str, info_key: str) -> None:
        if info_key not in info:
            return
        info_value = str(info[info_key])
        xmp_value = xmp.get(xmp_key)
        if xmp_value != info_value:
            add("xmp.mismatch", f"XMP {xmp_key} {xmp_value!r} != /Info {info_key} {info_value!r}")

    def compare_date(xmp_key: str, info_key: str) -> None:
        if info_key not in info:
            return
        info_date = pdf_date_to_datetime(str(info[info_key]))
        raw = xmp.get(xmp_key)
        xmp_date = _iso_to_datetime(raw) if raw else None
        if info_date is None or xmp_date is None or info_date != xmp_date:
            add("xmp.mismatch",
                f"XMP {xmp_key} {raw!r} != /Info {info_key} {str(info[info_key])!r}")

    compare("dc:title", "/Title")
    compare("pdf:Producer", "/Producer")
    compare("pdfx:GTS_PDFXVersion", "/GTS_PDFXVersion")
    compare_date("xmp:CreateDate", "/CreationDate")
    compare_date("xmp:ModifyDate", "/ModDate")
    compare_date("xmp:MetadataDate", "/ModDate")


def _xmp_values(root: ET.Element) -> dict[str, str]:
    """Flatten simple XMP properties (element or attribute form) to ``prefix:name``."""
    by_uri = {uri: prefix for prefix, uri in _NS.items()}
    values: dict[str, str] = {}

    def key(tag: str) -> str | None:
        if not tag.startswith("{"):
            return None
        uri, _, local = tag[1:].partition("}")
        prefix = by_uri.get(uri)
        return f"{prefix}:{local}" if prefix else None

    for desc in root.iter(f"{{{_NS['rdf']}}}Description"):
        for attr, value in desc.attrib.items():
            if (k := key(attr)) is not None:
                values[k] = value
        for child in desc:
            k = key(child.tag)
            if k is None:
                continue
            li = child.find(".//rdf:li", _NS)
            text = li.text if li is not None else child.text
            values[k] = (text or "").strip()
    return values


def _check_output_intents(pdf: pikepdf.Pdf, add: _Add) -> None:
    intents = pdf.Root.get("/OutputIntents", Array())
    gts = [oi for oi in intents if str(oi.get("/S", "")) == "/GTS_PDFX"]
    if len(gts) != 1:
        add("output_intent.count", f"{len(gts)} /GTS_PDFX OutputIntents, need exactly 1")
        return
    profile = gts[0].get("/DestOutputProfile")
    if not isinstance(profile, Stream):
        add("output_intent.profile", "OutputIntent has no /DestOutputProfile stream")
    elif int(profile.get("/N", 0)) != 4:
        add("output_intent.profile",
            f"/DestOutputProfile /N is {profile.get('/N')}, need 4 (CMYK)")


def _check_forbidden_document(pdf: pikepdf.Pdf, add: _Add) -> None:
    names = pdf.Root.get("/Names")
    if isinstance(names, Dictionary) and "/JavaScript" in names:
        add("forbidden.javascript", "catalog /Names has a /JavaScript tree")
    for obj in pdf.objects:
        if isinstance(obj, Dictionary | Stream) and _is_javascript_action(obj):
            add("forbidden.javascript", f"JavaScript action in object {obj.objgen}")
    open_action = pdf.Root.get("/OpenAction")
    if isinstance(open_action, Dictionary) and not open_action.is_indirect \
            and _is_javascript_action(open_action):
        add("forbidden.javascript", "catalog /OpenAction is JavaScript")


def _is_javascript_action(obj: Dictionary | Stream) -> bool:
    return str(obj.get("/S", "")) == "/JavaScript" or "/JS" in obj


# ----------------------------------------------------------------------
# Page-level rules
# ----------------------------------------------------------------------


def _check_page(page: pikepdf.Page, index: int, out: list[PreflightViolation]) -> None:
    def add(rule: str, detail: str) -> None:
        out.append(PreflightViolation(rule, index, detail))

    _check_boxes(page, add)
    if _is_transparency_group(page.obj):
        add("transparency.group", "page has a /Group /S /Transparency")
    walker = _ResourceWalker(add)
    walker.walk(_inherited(page.obj, "/Resources"), page.obj)


def _check_boxes(page: pikepdf.Page, add: _Add) -> None:
    obj = page.obj
    media = _box(_inherited(obj, "/MediaBox"))
    if media is None:
        add("boxes.missing", "page has no /MediaBox")
        return
    trim = _box(obj.get("/TrimBox"))
    if trim is None:
        add("boxes.missing", "page has no /TrimBox")
        return
    bleed = _box(obj.get("/BleedBox")) or media
    art = _box(obj.get("/ArtBox"))
    if not _contains(media, bleed):
        add("boxes.nesting", f"BleedBox {bleed} is outside MediaBox {media}")
    if not _contains(bleed, trim):
        add("boxes.nesting", f"TrimBox {trim} is outside BleedBox {bleed}")
    if art is not None and not _contains(trim, art):
        add("boxes.nesting", f"ArtBox {art} is outside TrimBox {trim}")


_Box = tuple[float, float, float, float]


def _box(value: object) -> _Box | None:
    if not isinstance(value, Array) or len(value) != 4:
        return None
    x0, y0, x1, y1 = (float(v) for v in value)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _contains(outer: _Box, inner: _Box, tol: float = 1e-3) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol
            and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def _inherited(obj: Dictionary, key: str) -> object:
    node: object = obj
    seen = 0
    while isinstance(node, Dictionary) and seen < 64:
        if key in node:
            return node[key]
        node = node.get("/Parent")
        seen += 1
    return None


def _is_transparency_group(obj: Dictionary | Stream) -> bool:
    group = obj.get("/Group")
    return isinstance(group, Dictionary) and str(group.get("/S", "")) == "/Transparency"


class _ResourceWalker:
    """Visits a resource dict and every resource dict nested inside it once."""

    def __init__(self, add: _Add) -> None:
        self._add = add
        self._seen: set[tuple[int, int]] = set()

    def walk(self, resources: object, content_owner: Dictionary | Stream | None) -> None:
        if content_owner is not None:
            self._check_content(content_owner, resources)
        if not isinstance(resources, Dictionary):
            return
        if isinstance(fonts := resources.get("/Font"), Dictionary):
            for name, font in fonts.items():
                self._check_font(name, font)
        if isinstance(states := resources.get("/ExtGState"), Dictionary):
            for name, gs in states.items():
                self._check_extgstate(name, gs)
        if isinstance(xobjects := resources.get("/XObject"), Dictionary):
            for name, xobj in xobjects.items():
                self._check_xobject(name, xobj)
        if isinstance(shadings := resources.get("/Shading"), Dictionary):
            for name, sh in shadings.items():
                self._check_shading(name, sh)
        if isinstance(patterns := resources.get("/Pattern"), Dictionary):
            for name, pat in patterns.items():
                self._check_pattern(name, pat)

    def _first_visit(self, obj: object) -> bool:
        if isinstance(obj, pikepdf.Object) and obj.is_indirect:
            if obj.objgen in self._seen:
                return False
            self._seen.add(obj.objgen)
        return True

    # -- fonts -----------------------------------------------------------

    def _check_font(self, name: str, font: object) -> None:
        if not isinstance(font, Dictionary) or not self._first_visit(font):
            return
        subtype = str(font.get("/Subtype", ""))
        base = str(font.get("/BaseFont", "?")).lstrip("/")
        if subtype == "/Type3":
            self.walk(font.get("/Resources"), None)
            return
        described: pikepdf.Object = font
        if subtype == "/Type0":
            descendants = font.get("/DescendantFonts")
            if isinstance(descendants, Array) and len(descendants) > 0:
                described = descendants[0]
        descriptor = described.get("/FontDescriptor") if isinstance(
            described, Dictionary) else None
        embedded = isinstance(descriptor, Dictionary) and any(
            k in descriptor for k in ("/FontFile", "/FontFile2", "/FontFile3"))
        if not embedded:
            self._add("font.not_embedded", f"font {name} ({base}, {subtype}) is not embedded")

    # -- graphics state --------------------------------------------------

    def _check_extgstate(self, name: str, gs: object) -> None:
        if not isinstance(gs, Dictionary) or not self._first_visit(gs):
            return
        for key in ("/ca", "/CA"):
            if key in gs and float(gs[key]) < 1:
                self._add("transparency.ca", f"ExtGState {name} {key} {float(gs[key])}")
        if "/BM" in gs:
            modes = gs["/BM"]
            names = [str(m) for m in modes] if isinstance(modes, Array) else [str(modes)]
            if not names or names[0] not in _ALLOWED_BLEND:
                self._add("transparency.blend_mode", f"ExtGState {name} /BM {names}")
        if "/SMask" in gs and str(gs["/SMask"]) != "/None":
            self._add("transparency.smask", f"ExtGState {name} has a soft mask")
        if "/TR" in gs:
            self._add("forbidden.transfer_function", f"ExtGState {name} has /TR")
        if "/TR2" in gs and str(gs["/TR2"]) != "/Default":
            self._add("forbidden.transfer_function", f"ExtGState {name} has /TR2")

    # -- XObjects --------------------------------------------------------

    def _check_xobject(self, name: str, xobj: object) -> None:
        if not isinstance(xobj, Stream) or not self._first_visit(xobj):
            return
        subtype = str(xobj.get("/Subtype", ""))
        if subtype == "/Image":
            self._check_image(name, xobj)
        elif subtype == "/Form":
            if _is_transparency_group(xobj):
                self._add("transparency.group", f"Form XObject {name} is a transparency group")
            self.walk(xobj.get("/Resources"), xobj)

    def _check_image(self, name: str, image: Stream) -> None:
        if "/SMask" in image:
            self._add("transparency.image_smask", f"image {name} has an /SMask")
        if not image.get("/ImageMask", False):
            family = _forbidden_family(image.get("/ColorSpace"), None)
            if family:
                self._add("colorspace.rgb_image", f"image {name} uses {family}")
        filters = image.get("/Filter")
        names = [str(f) for f in filters] if isinstance(filters, Array) else [str(filters)]
        if "/JPXDecode" in names:
            self._add("forbidden.jpx", f"image {name} is JPEG 2000 (/JPXDecode)")

    # -- shadings and patterns -------------------------------------------

    def _check_shading(self, name: str, shading: object) -> None:
        if not isinstance(shading, Dictionary | Stream) or not self._first_visit(shading):
            return
        family = _forbidden_family(shading.get("/ColorSpace"), None)
        if family:
            self._add("colorspace.rgb_shading", f"shading {name} uses {family}")

    def _check_pattern(self, name: str, pattern: object) -> None:
        if not isinstance(pattern, Dictionary | Stream) or not self._first_visit(pattern):
            return
        if int(pattern.get("/PatternType", 0)) == 2:
            self._check_shading(f"{name}/Shading", pattern.get("/Shading"))
            gs = pattern.get("/ExtGState")
            if gs is not None:
                self._check_extgstate(f"{name}/ExtGState", gs)
        elif isinstance(pattern, Stream):
            self.walk(pattern.get("/Resources"), pattern)

    # -- content operators -----------------------------------------------

    def _check_content(self, owner: Dictionary | Stream, resources: object) -> None:
        try:
            instructions = pikepdf.parse_content_stream(owner)
        except pikepdf.PdfError as e:
            self._add("content.unparsable", f"content stream could not be parsed: {e}")
            return
        for operands, operator in _plain(instructions):
            op = str(operator)
            if op in ("rg", "RG"):
                self._add("colorspace.rgb_content", f"'{op}' operator (DeviceRGB)")
            elif op in ("cs", "CS") and operands:
                family = _forbidden_family(operands[0], resources)
                if family:
                    self._add("colorspace.rgb_content",
                              f"'{op}' selects {operands[0]} ({family})")


def _plain(instructions: Sequence[object]) -> Iterator[tuple[list[object], object]]:
    for item in instructions:
        if isinstance(item, pikepdf.ContentStreamInstruction):
            yield list(item.operands), item.operator


def _forbidden_family(cs: object, resources: object) -> str | None:
    """Return the forbidden colour-space family ``cs`` resolves to, if any."""
    for _ in range(8):
        if isinstance(cs, Name):
            name = str(cs)
            if name in _FORBIDDEN_CS:
                return name.lstrip("/")
            named = resources.get("/ColorSpace") if isinstance(resources, Dictionary) else None
            if isinstance(named, Dictionary) and name in named:
                cs = named[name]
                resources = None
                continue
            return None
        if isinstance(cs, Array) and len(cs) > 0:
            family = str(cs[0])
            if family in _FORBIDDEN_CS:
                return family.lstrip("/")
            if family == "/Indexed" and len(cs) > 1:
                cs = cs[1]
                continue
            return None
        return None
    return None


# ----------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------

_PDF_DATE = re.compile(
    r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
    r"(?:(Z)|([+-])(\d{2})'?(\d{2})?'?)?$"
)


def pdf_date_to_datetime(value: str) -> datetime | None:
    """Parse a PDF date string (``D:YYYYMMDDHHmmSSOHH'mm'``); ``None`` if invalid.

    A missing zone is read as UTC, which is how the post-processor writes it.
    """
    m = _PDF_DATE.match(value.strip())
    if m is None:
        return None
    year, month, day, hour, minute, second = (
        int(g) if g else d for g, d in zip(m.groups()[:6], (0, 1, 1, 0, 0, 0), strict=True)
    )
    tz = UTC
    if m.group(8):
        offset = timedelta(hours=int(m.group(9)), minutes=int(m.group(10) or 0))
        tz = timezone(offset if m.group(8) == "+" else -offset)
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=tz)
    except ValueError:
        return None


def _iso_to_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
