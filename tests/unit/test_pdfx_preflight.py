"""Unit tests for the PDF/X-1a:2003 rule preflight (#69, D11).

Every rule gets one hand-built PDF that proves it fires. The starting point
is a clean file: a one-page CMYK render of a rect plus Lato text through
``IRReportLabRenderer(color_space="cmyk")`` and ``apply_pdfx1a``. Each test
mutates that file with pikepdf to introduce exactly one violation.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest
from pikepdf import Array, Dictionary, Name, String
from reportlab.pdfgen import canvas as _canvas

from holiday_card.core.render_ir import (
    RGBA,
    BeginPage,
    DrawShape,
    DrawText,
    EndPage,
    Point,
    RectGeom,
    SolidPaint,
    TextRun,
)
from holiday_card.renderers.pdfx_postprocess import apply_pdfx1a
from holiday_card.renderers.pdfx_preflight import (
    PreflightViolation,
    preflight_pdfx1a,
)
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer

pytestmark = pytest.mark.pdfx


def _rules(violations: list[PreflightViolation]) -> set[str]:
    return {v.rule for v in violations}


@pytest.fixture
def clean_pdf(tmp_path: Path) -> Path:
    """A PDF/X-1a:2003 file with no violations."""
    path = tmp_path / "clean.pdf"
    IRReportLabRenderer(color_space="cmyk").render(
        [
            BeginPage(width=144, height=144, bleed=9),
            DrawShape(
                geometry=RectGeom(x=0, y=0, width=144, height=144),
                fill=SolidPaint(color=RGBA(r=0.8, g=0.1, b=0.1)),
            ),
            DrawText(
                run=TextRun(
                    text="Hello", origin=Point(x=20, y=60), font_id="Lato",
                    size_pt=24, color=RGBA(r=0, g=0, b=0),
                ),
            ),
            EndPage(),
        ],
        path,
    )
    apply_pdfx1a(path, title="clean")
    return path


def _mutate(path: Path, fn: Callable[[pikepdf.Pdf], None]) -> Path:
    """Apply ``fn`` to the PDF at ``path`` and save it in place as PDF 1.4."""
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        fn(pdf)
        pdf.save(path, force_version="1.4")
    return path


def _page_resources(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
    page = pdf.pages[0].obj
    if "/Resources" not in page:
        page["/Resources"] = Dictionary()
    return page["/Resources"]


def _add_resource(pdf: pikepdf.Pdf, category: str, key: str, value: object) -> None:
    res = _page_resources(pdf)
    if category not in res:
        res[category] = Dictionary()
    res[category][key] = value


def _append_content(pdf: pikepdf.Pdf, ops: bytes) -> None:
    pdf.pages[0].contents_add(pdf.make_stream(ops), prepend=False)


def _rgb_image(pdf: pikepdf.Pdf, **extra: object) -> pikepdf.Stream:
    img = pdf.make_stream(b"\xff\x00\x00", Type=Name.XObject, Subtype=Name.Image,
                          Width=1, Height=1, BitsPerComponent=8,
                          ColorSpace=Name.DeviceRGB)
    for k, v in extra.items():
        img[f"/{k}"] = v
    return img


def _cmyk_image(pdf: pikepdf.Pdf, **extra: object) -> pikepdf.Stream:
    img = pdf.make_stream(b"\x00\xff\xff\x00", Type=Name.XObject, Subtype=Name.Image,
                          Width=1, Height=1, BitsPerComponent=8,
                          ColorSpace=Name.DeviceCMYK)
    for k, v in extra.items():
        img[f"/{k}"] = v
    return img


class TestCleanFile:
    def test_clean_file_has_no_violations(self, clean_pdf: Path) -> None:
        assert preflight_pdfx1a(clean_pdf) == []

    def test_violation_is_a_frozen_dataclass(self) -> None:
        v = PreflightViolation(rule="font.not_embedded", page=1, detail="x")
        with pytest.raises(AttributeError):
            v.rule = "y"  # type: ignore[misc]


class TestFonts:
    def test_default_reportlab_canvas_has_unembedded_initial_font(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "default.pdf"
        c = _canvas.Canvas(str(path))
        c.showPage()
        c.save()
        violations = preflight_pdfx1a(path)
        font = [v for v in violations if v.rule == "font.not_embedded"]
        assert font, violations
        assert font[0].page == 1
        assert "Helvetica" in font[0].detail

    def test_unembedded_font_in_page_resources(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/Font", "/FX", pdf.make_indirect(Dictionary(
                Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica,
            )),
        ))
        assert "font.not_embedded" in _rules(preflight_pdfx1a(clean_pdf))

    def test_unembedded_font_nested_in_form_xobject(self, clean_pdf: Path) -> None:
        def mutate(pdf: pikepdf.Pdf) -> None:
            form = pdf.make_stream(
                b"BT /FX 12 Tf (x) Tj ET",
                Type=Name.XObject, Subtype=Name.Form, BBox=[0, 0, 10, 10],
                Resources=Dictionary(Font=Dictionary(FX=Dictionary(
                    Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/Times-Roman"),
                ))),
            )
            _add_resource(pdf, "/XObject", "/Fm1", form)

        _mutate(clean_pdf, mutate)
        violations = preflight_pdfx1a(clean_pdf)
        assert any(
            v.rule == "font.not_embedded" and "Times-Roman" in v.detail
            for v in violations
        ), violations

    def test_type0_font_checks_descendant_descriptor(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/Font", "/FX", Dictionary(
                Type=Name.Font, Subtype=Name.Type0, BaseFont=Name("/Foo"),
                Encoding=Name("/Identity-H"),
                DescendantFonts=Array([Dictionary(
                    Type=Name.Font, Subtype=Name.CIDFontType2, BaseFont=Name("/Foo"),
                    FontDescriptor=Dictionary(Type=Name.FontDescriptor,
                                              FontName=Name("/Foo")),
                )]),
            ),
        ))
        assert "font.not_embedded" in _rules(preflight_pdfx1a(clean_pdf))


class TestHeaderAndTrailer:
    def test_header_must_be_1_4(self, clean_pdf: Path) -> None:
        with pikepdf.open(clean_pdf, allow_overwriting_input=True) as pdf:
            pdf.save(clean_pdf, force_version="1.6")
        assert "header.version" in _rules(preflight_pdfx1a(clean_pdf))

    def test_trailer_id_required(self, clean_pdf: Path) -> None:
        # qpdf always writes /ID, so blank the key in place (same length
        # keeps the xref offsets valid).
        data = clean_pdf.read_bytes()
        idx = data.rfind(b"/ID")
        assert idx != -1
        clean_pdf.write_bytes(data[:idx] + b"/XX" + data[idx + 3:])
        assert "trailer.id" in _rules(preflight_pdfx1a(clean_pdf))

    def test_encryption_forbidden(self, clean_pdf: Path) -> None:
        with pikepdf.open(clean_pdf, allow_overwriting_input=True) as pdf:
            pdf.save(clean_pdf, force_version="1.4",
                     encryption=pikepdf.Encryption(owner="o", user="", R=3,
                                                     metadata=False, aes=False))
        assert "trailer.encrypt" in _rules(preflight_pdfx1a(clean_pdf))


class TestInfoAndXmp:
    @pytest.mark.parametrize("key", ["/Title", "/CreationDate", "/ModDate"])
    def test_required_info_keys(self, clean_pdf: Path, key: str) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.docinfo.__delitem__(key))
        assert "info.missing" in _rules(preflight_pdfx1a(clean_pdf))

    def test_trapped_must_be_true_or_false(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.docinfo.__setitem__(
            "/Trapped", Name("/Unknown")))
        assert "info.trapped" in _rules(preflight_pdfx1a(clean_pdf))

    def test_gts_pdfxversion_must_be_x1a_2003(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.docinfo.__setitem__(
            "/GTS_PDFXVersion", String("PDF/X-1:2001")))
        assert "info.pdfx_version" in _rules(preflight_pdfx1a(clean_pdf))

    def test_gts_pdfxversion_missing(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.docinfo.__delitem__("/GTS_PDFXVersion"))
        assert "info.pdfx_version" in _rules(preflight_pdfx1a(clean_pdf))

    def test_xmp_required(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.Root.__delitem__("/Metadata"))
        assert "xmp.missing" in _rules(preflight_pdfx1a(clean_pdf))

    def test_xmp_title_must_match_info(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.docinfo.__setitem__(
            "/Title", String("something else")))
        violations = preflight_pdfx1a(clean_pdf)
        assert any(v.rule == "xmp.mismatch" and "dc:title" in v.detail
                   for v in violations), violations

    def test_xmp_description_must_match_info_subject(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.docinfo.__setitem__(
            "/Subject", String("christmas-red-green")))
        violations = preflight_pdfx1a(clean_pdf)
        assert any(v.rule == "xmp.mismatch" and "dc:description" in v.detail
                   for v in violations), violations

    def test_xmp_mod_date_must_match_info(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.docinfo.__setitem__(
            "/ModDate", String("D:20000101000000Z")))
        violations = preflight_pdfx1a(clean_pdf)
        assert any(v.rule == "xmp.mismatch" and "xmp:ModifyDate" in v.detail
                   for v in violations), violations

    def test_xmp_pdfx_version_must_match_info(self, clean_pdf: Path) -> None:
        def mutate(pdf: pikepdf.Pdf) -> None:
            xmp = pdf.Root.Metadata.read_bytes().replace(
                b"<pdfx:GTS_PDFXVersion>PDF/X-1a:2003",
                b"<pdfx:GTS_PDFXVersion>PDF/X-1:2001",
            )
            pdf.Root.Metadata.write(xmp)

        _mutate(clean_pdf, mutate)
        violations = preflight_pdfx1a(clean_pdf)
        assert any(v.rule == "xmp.mismatch" and "GTS_PDFXVersion" in v.detail
                   for v in violations), violations


class TestOutputIntent:
    def test_output_intent_required(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.Root.__delitem__("/OutputIntents"))
        assert "output_intent.count" in _rules(preflight_pdfx1a(clean_pdf))

    def test_exactly_one_gts_pdfx_intent(self, clean_pdf: Path) -> None:
        def mutate(pdf: pikepdf.Pdf) -> None:
            oi = pdf.Root.OutputIntents[0]
            pdf.Root.OutputIntents = Array([oi, oi])

        _mutate(clean_pdf, mutate)
        assert "output_intent.count" in _rules(preflight_pdfx1a(clean_pdf))

    def test_dest_profile_must_be_cmyk(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.Root.OutputIntents[0]
                .DestOutputProfile.__setitem__("/N", 3))
        assert "output_intent.profile" in _rules(preflight_pdfx1a(clean_pdf))


class TestPageBoxes:
    def test_trim_outside_bleed(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.pages[0].obj.__setitem__(
            "/TrimBox", Array([-5, -5, 170, 170])))
        violations = preflight_pdfx1a(clean_pdf)
        assert any(v.rule == "boxes.nesting" and v.page == 1 for v in violations)

    def test_bleed_outside_media(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.pages[0].obj.__setitem__(
            "/BleedBox", Array([-1, 0, 162, 162])))
        assert "boxes.nesting" in _rules(preflight_pdfx1a(clean_pdf))

    def test_art_outside_trim(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.pages[0].obj.__setitem__(
            "/ArtBox", Array([0, 0, 162, 162])))
        assert "boxes.nesting" in _rules(preflight_pdfx1a(clean_pdf))

    def test_trim_box_required(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.pages[0].obj.__delitem__("/TrimBox"))
        assert "boxes.missing" in _rules(preflight_pdfx1a(clean_pdf))


class TestTransparency:
    @pytest.mark.parametrize(("key", "value", "rule"), [
        ("/ca", 0.5, "transparency.ca"),
        ("/CA", 0.5, "transparency.ca"),
        ("/BM", Name.Multiply, "transparency.blend_mode"),
        ("/SMask", Dictionary(Type=Name.Mask, S=Name.Luminosity), "transparency.smask"),
    ])
    def test_extgstate_transparency(
        self, clean_pdf: Path, key: str, value: object, rule: str
    ) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/ExtGState", "/GSx", Dictionary({key: value})))
        assert rule in _rules(preflight_pdfx1a(clean_pdf))

    @pytest.mark.parametrize(("key", "value"), [
        ("/ca", 1.0), ("/CA", 1), ("/BM", Name.Normal), ("/BM", Name.Compatible),
        ("/SMask", Name("/None")),
    ])
    def test_opaque_extgstate_is_allowed(
        self, clean_pdf: Path, key: str, value: object
    ) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/ExtGState", "/GSx", Dictionary({key: value})))
        assert preflight_pdfx1a(clean_pdf) == []

    def test_image_smask(self, clean_pdf: Path) -> None:
        def mutate(pdf: pikepdf.Pdf) -> None:
            mask = pdf.make_stream(b"\x80", Type=Name.XObject, Subtype=Name.Image,
                                   Width=1, Height=1, BitsPerComponent=8,
                                   ColorSpace=Name.DeviceGray)
            _add_resource(pdf, "/XObject", "/Im9", _cmyk_image(pdf, SMask=mask))

        _mutate(clean_pdf, mutate)
        assert "transparency.image_smask" in _rules(preflight_pdfx1a(clean_pdf))

    def test_transparency_group_on_page(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.pages[0].obj.__setitem__(
            "/Group", Dictionary(Type=Name.Group, S=Name.Transparency)))
        assert "transparency.group" in _rules(preflight_pdfx1a(clean_pdf))

    def test_extgstate_nested_in_form_xobject(self, clean_pdf: Path) -> None:
        def mutate(pdf: pikepdf.Pdf) -> None:
            form = pdf.make_stream(
                b"/G1 gs", Type=Name.XObject, Subtype=Name.Form, BBox=[0, 0, 1, 1],
                Resources=Dictionary(ExtGState=Dictionary(G1=Dictionary(ca=0.3))),
            )
            _add_resource(pdf, "/XObject", "/Fm1", form)

        _mutate(clean_pdf, mutate)
        assert "transparency.ca" in _rules(preflight_pdfx1a(clean_pdf))


class TestColourSpaces:
    @pytest.mark.parametrize("ops", [b"1 0 0 rg", b"0 0 1 RG"])
    def test_rgb_operators(self, clean_pdf: Path, ops: bytes) -> None:
        _mutate(clean_pdf, lambda pdf: _append_content(pdf, ops))
        assert "colorspace.rgb_content" in _rules(preflight_pdfx1a(clean_pdf))

    def test_device_rgb_via_cs(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _append_content(
            pdf, b"/DeviceRGB cs 1 0 0 scn"))
        assert "colorspace.rgb_content" in _rules(preflight_pdfx1a(clean_pdf))

    @pytest.mark.parametrize("family", ["/ICCBased", "/CalRGB", "/Lab"])
    def test_named_colourspace_resource(self, clean_pdf: Path, family: str) -> None:
        def mutate(pdf: pikepdf.Pdf) -> None:
            if family == "/ICCBased":
                cs = Array([Name(family), pdf.make_stream(b"x", N=3)])
            else:
                cs = Array([Name(family), Dictionary(WhitePoint=[0.95, 1, 1.09])])
            _add_resource(pdf, "/ColorSpace", "/CS9", cs)
            _append_content(pdf, b"/CS9 CS")

        _mutate(clean_pdf, mutate)
        violations = preflight_pdfx1a(clean_pdf)
        assert any(v.rule == "colorspace.rgb_content" and family[1:] in v.detail
                   for v in violations), violations

    def test_rgb_image(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/XObject", "/Im9", _rgb_image(pdf)))
        violations = preflight_pdfx1a(clean_pdf)
        assert any(v.rule == "colorspace.rgb_image" and v.page == 1
                   for v in violations), violations

    def test_indexed_rgb_image(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/XObject", "/Im9", _cmyk_image(pdf, ColorSpace=Array([
                Name.Indexed, Name.DeviceRGB, 0, String(b"\xff\x00\x00"),
            ])),
        ))
        assert "colorspace.rgb_image" in _rules(preflight_pdfx1a(clean_pdf))

    def test_rgb_shading(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/Shading", "/Sh9", Dictionary(
                ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=[0, 0, 1, 0],
                Function=Dictionary(FunctionType=2, Domain=[0, 1], C0=[1, 0, 0],
                                    C1=[0, 0, 1], N=1),
            ),
        ))
        assert "colorspace.rgb_shading" in _rules(preflight_pdfx1a(clean_pdf))

    def test_cmyk_image_is_allowed(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/XObject", "/Im9", _cmyk_image(pdf)))
        assert preflight_pdfx1a(clean_pdf) == []


class TestForbiddenFeatures:
    def test_javascript_open_action(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.Root.__setitem__(
            "/OpenAction", Dictionary(S=Name.JavaScript, JS=String("app.alert(1)"))))
        assert "forbidden.javascript" in _rules(preflight_pdfx1a(clean_pdf))

    def test_javascript_name_tree(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: pdf.Root.__setitem__(
            "/Names", Dictionary(JavaScript=Dictionary(Names=Array([])))))
        assert "forbidden.javascript" in _rules(preflight_pdfx1a(clean_pdf))

    def test_jpx_image(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/XObject", "/Im9", _cmyk_image(pdf, Filter=Name.JPXDecode)))
        assert "forbidden.jpx" in _rules(preflight_pdfx1a(clean_pdf))

    @pytest.mark.parametrize(("key", "value"), [
        ("/TR", Name.Identity), ("/TR2", Name.Identity),
    ])
    def test_transfer_functions(self, clean_pdf: Path, key: str, value: object) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/ExtGState", "/GSx", Dictionary({key: value})))
        assert "forbidden.transfer_function" in _rules(preflight_pdfx1a(clean_pdf))

    def test_tr2_default_is_allowed(self, clean_pdf: Path) -> None:
        _mutate(clean_pdf, lambda pdf: _add_resource(
            pdf, "/ExtGState", "/GSx", Dictionary(TR2=Name.Default)))
        assert preflight_pdfx1a(clean_pdf) == []
