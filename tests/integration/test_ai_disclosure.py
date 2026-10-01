"""Cards that embed AI imagery say so in every output format's metadata (#145).

The compiled IR records the embedded models as ``SetMetadata(ai_imagery)``
(#144). Each backend turns that record into a disclosure naming the model
read from the asset's sidecar: PDF ``/Subject`` + XMP, SVG ``<desc>`` +
RDF ``<metadata>``, PNG ``Description``. A card without AI imagery is
written exactly as before.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pikepdf
import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner, Result

from ai_fixtures import bake_fake_ai_asset
from holiday_card.cli.commands import app
from holiday_card.core.data_paths import data_path
from holiday_card.core.render_ir import (
    AI_IMAGERY_METADATA_KEY,
    RGBA,
    BeginPage,
    DrawShape,
    EndPage,
    RectGeom,
    RenderCommand,
    SetMetadata,
    SolidPaint,
)
from holiday_card.renderers.pdf_metadata import DIGITAL_SOURCE_COMPOSITE_AI
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer

runner = CliRunner()

DISCLOSURE = "Contains AI-generated imagery (gpt-image-2)"
THEME = "christmas-red-green"  # christmas-classic's default theme

_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "hc": "https://github.com/clostaunau/holiday-card/ns/ai/1.0/",
    "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
    "svg": "http://www.w3.org/2000/svg",
}


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _invoke(*args: str) -> Result:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, _plain(result.output)
    return result


def _ai_template(tmp_path: Path, model: str = "gpt-image-2") -> Path:
    """christmas-classic plus a baked AI asset on the front panel only."""
    bake_fake_ai_asset(tmp_path, "border.png", model=model, size=(600, 900))
    doc = yaml.safe_load((data_path("templates") / "christmas" / "classic.yaml").read_text())
    doc["id"] = "ai-border"
    front = next(p for p in doc["panels"] if p["position"] == "front")
    front["image_elements"] = [{
        "id": "border", "source_path": "border.png",
        "x": 0.25, "y": 0.25, "width": 1.0, "height": 1.5,
    }]
    path = tmp_path / "ai-border.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


@pytest.fixture
def ai_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return _ai_template(tmp_path)


def _xmp_keys(pdf: pikepdf.Pdf) -> dict[str, str]:
    by_uri = {uri: prefix for prefix, uri in _NS.items()}
    by_uri.update({
        "http://ns.adobe.com/pdf/1.3/": "pdf",
        "http://ns.adobe.com/pdfx/1.3/": "pdfx",
        "http://ns.adobe.com/xap/1.0/": "xmp",
    })
    root = ET.fromstring(pdf.Root["/Metadata"].read_bytes())
    desc = root.find(".//rdf:Description", _NS)
    assert desc is not None
    keys: dict[str, str] = {}
    for child in desc:
        uri, _, local = child.tag[1:].partition("}")
        li = child.find(".//rdf:li", _NS)
        keys[f"{by_uri[uri]}:{local}"] = ((li if li is not None else child).text or "").strip()
    return keys


def _assert_disclosed_pdf(path: Path, model: str = "gpt-image-2") -> None:
    with pikepdf.open(path) as pdf:
        subject = str(pdf.docinfo["/Subject"])
        assert subject == f"Contains AI-generated imagery ({model})"
        assert "/Metadata" in pdf.Root
        keys = _xmp_keys(pdf)
        assert keys["dc:description"] == subject
        assert keys["hc:aiGenerated"] == "True"
        assert keys["hc:aiModels"] == model
        assert keys["Iptc4xmpExt:DigitalSourceType"] == DIGITAL_SOURCE_COMPOSITE_AI


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def test_letter_pdf_with_ai_is_disclosed(ai_template: Path) -> None:
    _invoke("create", str(ai_template), "-o", "card.pdf")
    _assert_disclosed_pdf(Path("card.pdf"))


def test_disclosed_model_comes_from_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    template = _ai_template(tmp_path, model="gpt-image-1")
    _invoke("create", str(template), "-o", "card.pdf")
    _assert_disclosed_pdf(Path("card.pdf"), model="gpt-image-1")


def test_letter_pdf_without_ai_is_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _invoke("create", "christmas-classic", "-o", "card.pdf")
    raw = Path("card.pdf").read_bytes()
    # ReportLab's own header comment: a pikepdf rewrite would drop it.
    assert b"% ReportLab Generated PDF document" in raw
    with pikepdf.open("card.pdf") as pdf:
        assert str(pdf.docinfo["/Subject"]) == THEME
        assert "/Metadata" not in pdf.Root


def test_per_panel_pdf_marks_only_the_ai_panel(ai_template: Path) -> None:
    _invoke("create", str(ai_template), "--export-for", "per-panel-pdf", "-o", "out")
    _assert_disclosed_pdf(Path("out/front.pdf"))
    for stem in ("back", "inside-left", "inside-right"):
        with pikepdf.open(f"out/{stem}.pdf") as pdf:
            assert str(pdf.docinfo["/Subject"]) == THEME
            assert "/Metadata" not in pdf.Root


@pytest.mark.pdfx
def test_moo_a6_marks_only_the_ai_panel_and_passes_preflight(ai_template: Path) -> None:
    from holiday_card.renderers.pdfx_preflight import preflight_pdfx1a

    _invoke("create", str(ai_template), "--export-for", "moo-a6", "-o", "out")
    _assert_disclosed_pdf(Path("out/front.pdf"))
    for stem in ("back", "inside-left", "inside-right"):
        with pikepdf.open(f"out/{stem}.pdf") as pdf:
            assert str(pdf.docinfo["/Subject"]) == THEME
            keys = _xmp_keys(pdf)
            assert keys["dc:description"] == THEME
            assert not any(k.startswith(("hc:", "Iptc4xmpExt:")) for k in keys)
    for stem in ("front", "back", "inside-left", "inside-right"):
        assert preflight_pdfx1a(Path(f"out/{stem}.pdf")) == [], stem


def _subject(commands: list[RenderCommand], tmp_path: Path) -> str:
    path = tmp_path / "ir.pdf"
    IRReportLabRenderer().render(commands, path)
    with pikepdf.open(path) as pdf:
        return str(pdf.docinfo["/Subject"])


def _page(*meta: SetMetadata) -> list[RenderCommand]:
    return [
        BeginPage(width=144, height=144),
        *meta,
        DrawShape(
            geometry=RectGeom(x=0, y=0, width=144, height=144),
            fill=SolidPaint(color=RGBA(r=0.8, g=0.1, b=0.1)),
        ),
        EndPage(),
    ]


AI = SetMetadata(key=AI_IMAGERY_METADATA_KEY, value="gpt-image-2")
THEME_META = SetMetadata(key="theme_id", value=THEME)


@pytest.mark.parametrize("order", ["theme_first", "ai_first"])
def test_ai_disclosure_wins_subject_in_any_order(order: str, tmp_path: Path) -> None:
    meta = (THEME_META, AI) if order == "theme_first" else (AI, THEME_META)
    assert _subject(_page(*meta), tmp_path) == DISCLOSURE


def test_subject_is_the_theme_without_ai(tmp_path: Path) -> None:
    assert _subject(_page(THEME_META), tmp_path) == THEME


def test_reused_renderer_forgets_the_previous_files_ai(tmp_path: Path) -> None:
    renderer = IRReportLabRenderer()
    renderer.render(_page(AI, THEME_META), tmp_path / "a.pdf")
    renderer.render(_page(THEME_META), tmp_path / "b.pdf")
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        assert str(pdf.docinfo["/Subject"]) == THEME


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------


def test_svg_with_ai_carries_desc_and_rdf_metadata(ai_template: Path) -> None:
    _invoke("create", str(ai_template), "-o", "a.svg")
    _invoke("create", str(ai_template), "-o", "b.svg")
    assert Path("a.svg").read_bytes() == Path("b.svg").read_bytes()
    root = ET.parse("a.svg").getroot()
    descs = [d for d in root.iter(f"{{{_NS['svg']}}}desc") if d.get("id") == "ai-disclosure"]
    assert [d.text for d in descs] == [DISCLOSURE]
    metadata = root.findall("svg:metadata", _NS)
    assert len(metadata) == 1
    desc = metadata[0].find("rdf:RDF/rdf:Description", _NS)
    assert desc is not None
    assert desc.findtext("dc:description", namespaces=_NS) == DISCLOSURE
    assert desc.findtext("hc:aiGenerated", namespaces=_NS) == "True"
    assert desc.findtext("hc:aiModels", namespaces=_NS) == "gpt-image-2"
    assert desc.findtext(
        "Iptc4xmpExt:DigitalSourceType", namespaces=_NS,
    ) == DIGITAL_SOURCE_COMPOSITE_AI


def test_svg_without_ai_has_no_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _invoke("create", "christmas-classic", "-o", "card.svg")
    text = Path("card.svg").read_text()
    assert "<metadata" not in text
    assert "ai-disclosure" not in text
    assert "xmlns:rdf" not in text


# ---------------------------------------------------------------------------
# PNG preview
# ---------------------------------------------------------------------------


def test_png_preview_with_ai_is_disclosed_but_not_marked_as_an_asset(
    ai_template: Path,
) -> None:
    _invoke("preview", str(ai_template), "--no-open", "-o", "p.png")
    with Image.open("p.png") as im:
        text = dict(im.text)  # type: ignore[attr-defined]
    assert text["Description"] == DISCLOSURE
    assert text["ai_imagery"] == "gpt-image-2"
    assert "holiday-card:ai-generated" not in text


# ---------------------------------------------------------------------------
# CLI summary
# ---------------------------------------------------------------------------

SUMMARY = "AI imagery: gpt-image-2 (disclosed in file metadata)"


def test_create_summary_names_the_ai_imagery(ai_template: Path) -> None:
    result = _invoke("create", str(ai_template), "-o", "card.pdf")
    assert SUMMARY in _plain(result.output)


def test_preview_summary_names_the_ai_imagery(ai_template: Path) -> None:
    result = _invoke("preview", str(ai_template), "--no-open", "-o", "p.png")
    assert SUMMARY in _plain(result.output)


def test_summary_is_silent_without_ai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = _invoke("create", "christmas-classic", "-o", "card.pdf")
    assert "AI imagery" not in _plain(result.output)
