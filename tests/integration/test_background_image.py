"""Panel ``background_image`` end to end, checked on pixels (#153).

The art fills the panel's background rect (bleed included), sits under
every vector element, and rotates with its panel on the letter sheet.
Images are generated in ``tmp_path``; nothing binary is committed. PNG
goes through ``preview`` and PDF through pdfium, both at 144 DPI, sampling
well inside regions.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pikepdf
import pytest
import yaml
from PIL import Image, ImageDraw
from typer.testing import CliRunner, Result

from ai_fixtures import bake_fake_ai_asset
from holiday_card.cli.commands import app
from holiday_card.core.ai_provenance import sidecar_path_for
from holiday_card.core.imposition import PanelPlacement, panel_placements
from holiday_card.core.models import Card, PanelPosition
from holiday_card.core.templates import load_template_from_file
from rasterize import rasterize_pdf

runner = CliRunner()

DPI = 144
SHEET_H_PT = 11 * 72

GREEN = (30, 160, 60)  # top-left quadrant
BLUE = (30, 60, 200)  # top-right
YELLOW = (240, 200, 20)  # bottom-left
PURPLE = (150, 40, 160)  # bottom-right
BLACK = (0, 0, 0)  # 1/8-size marker in the top-left corner
CYAN = (0, 255, 255)  # the vector rectangle drawn over the front art
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREY = (128, 128, 128)

Pixel = tuple[int, int, int]


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _invoke(*args: str, code: int = 0) -> Result:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, _plain(result.output)
    assert "Traceback" not in result.output
    return result


def _quadrant_image(path: Path, size: tuple[int, int] = (850, 1100)) -> Path:
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w // 2 - 1, h // 2 - 1), fill=GREEN)
    draw.rectangle((w // 2, 0, w - 1, h // 2 - 1), fill=BLUE)
    draw.rectangle((0, h // 2, w // 2 - 1, h - 1), fill=YELLOW)
    draw.rectangle((w // 2, h // 2, w - 1, h - 1), fill=PURPLE)
    draw.rectangle((0, 0, w // 8 - 1, h // 8 - 1), fill=BLACK)
    img.save(path, "PNG")
    return path


def _banded_image(path: Path, *, vertical_bands: bool) -> Path:
    """A 1000x1000 grey square with 100 px red bands on two opposite edges."""
    img = Image.new("RGB", (1000, 1000), GREY)
    draw = ImageDraw.Draw(img)
    if vertical_bands:
        draw.rectangle((0, 0, 99, 999), fill=RED)
        draw.rectangle((900, 0, 999, 999), fill=RED)
    else:
        draw.rectangle((0, 0, 999, 99), fill=RED)
        draw.rectangle((0, 900, 999, 999), fill=RED)
    img.save(path, "PNG")
    return path


def _panel(position: str, **extra: Any) -> dict[str, Any]:
    return {"id": position, "position": position, "width": 4.25, "height": 5.5, **extra}


def _veil(opacity: float = 1.0) -> dict[str, Any]:
    """A cyan rectangle across the front panel's centre, under-indexed on purpose."""
    return {
        "type": "rectangle", "id": "veil", "x": 1.625, "y": 2.25, "width": 1.0,
        "height": 1.0, "fill_color": "#00FFFF", "opacity": opacity, "z_index": -5,
    }


def _template(
    directory: Path,
    front: dict[str, Any],
    inside_left: dict[str, Any] | None = None,
    name: str = "bg-card",
) -> Path:
    doc = {
        "id": name,
        "name": "Background image fixture",
        "occasion": "generic",
        "fold_type": "quarter_fold",
        "panels": [
            _panel("front", **front),
            _panel("back"),
            _panel("inside_left", **(inside_left or {})),
            _panel("inside_right"),
        ],
    }
    path = directory / f"{name}.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------


def _placements(template: Path) -> dict[PanelPosition, PanelPlacement]:
    loaded = load_template_from_file(template)
    card = Card(
        name=loaded.name, template_id=loaded.id,
        fold_type=loaded.fold_type, panels=loaded.panels,
    )
    return panel_placements(card)


def _box(placement: PanelPlacement) -> tuple[float, float, float, float]:
    """The placement's sheet rect in raster pixels: (left, top, width, height)."""
    k = DPI / 72
    top = (SHEET_H_PT - placement.y_pt - placement.height_pt) * k
    return placement.x_pt * k, top, placement.width_pt * k, placement.height_pt * k


def _at(img: Image.Image, placement: PanelPlacement, fx: float, fy: float) -> Pixel:
    """The pixel at fraction (fx, fy) of the panel's sheet box, from its top-left."""
    left, top, width, height = _box(placement)
    px = img.getpixel((int(left + fx * width), int(top + fy * height)))
    assert isinstance(px, tuple)
    return (px[0], px[1], px[2])


def _close(actual: Pixel, expected: Pixel, tol: int = 6) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


def _render(template: Path, fmt: str) -> Image.Image:
    if fmt == "png":
        _invoke("preview", str(template), "--no-open", "--dpi", str(DPI), "-o", "sheet.png")
        with Image.open("sheet.png") as img:
            return img.convert("RGB")
    _invoke("create", str(template), "-o", "sheet.pdf")
    return rasterize_pdf(Path("sheet.pdf"), DPI)


# ---------------------------------------------------------------------------
# Letter sheet: placement, z-order, rotation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["png", "pdf"])
def test_letter_sheet_art_under_vectors_and_rotated_with_its_panel(
    workdir: Path, fmt: str
) -> None:
    _quadrant_image(workdir / "front.png")
    _quadrant_image(workdir / "inside.png")
    template = _template(
        workdir,
        front={"background_image": "front.png", "shape_elements": [_veil()]},
        inside_left={"background_image": "inside.png"},
    )
    places = _placements(template)
    img = _render(template, fmt)


    front, inside = places[PanelPosition.FRONT], places[PanelPosition.INSIDE_LEFT]
    assert front.rotation_deg == 0 and inside.rotation_deg == 180

    # Front (bottom-right of the sheet): the image as-is, marker top-left.
    assert _close(_at(img, front, 1 / 16, 1 / 16), BLACK)
    assert _close(_at(img, front, 0.25, 0.25), GREEN)
    assert _close(_at(img, front, 0.75, 0.25), BLUE)
    assert _close(_at(img, front, 0.25, 0.75), YELLOW)
    assert _close(_at(img, front, 0.75, 0.75), PURPLE)
    # The z_index -5 vector rectangle is drawn over the art.
    assert _close(_at(img, front, 0.5, 0.5), CYAN)

    # Inside-left is rotated 180°: the marker is bottom-right of its sheet box.
    assert _close(_at(img, inside, 15 / 16, 15 / 16), BLACK)
    assert _close(_at(img, inside, 0.25, 0.25), PURPLE)
    assert _close(_at(img, inside, 0.75, 0.75), GREEN)

    # Panels without a background image are untouched paper.
    for position in (PanelPosition.BACK, PanelPosition.INSIDE_RIGHT):
        for fx, fy in ((0.3, 0.3), (0.7, 0.7)):
            assert _close(_at(img, places[position], fx, fy), WHITE, tol=0)


@pytest.mark.parametrize("fmt", ["png", "pdf"])
def test_cover_crops_the_long_axis_only(workdir: Path, fmt: str) -> None:

    def red_in_front(vertical_bands: bool) -> list[Pixel]:  # distinct red colours
        _banded_image(workdir / "bands.png", vertical_bands=vertical_bands)
        template = _template(workdir, front={"background_image": "bands.png"})
        front = _placements(template)[PanelPosition.FRONT]
        img = _render(template, fmt)
        left, top, width, height = (round(v) for v in _box(front))
        crop = img.crop((left + 4, top + 4, left + width - 4, top + height - 4))
        colours = crop.getcolors(maxcolors=crop.width * crop.height) or []
        return [c for _n, c in colours if c[0] > 200 and c[1] < 60 and c[2] < 60]

    # A square on a portrait panel is scaled to the panel height: the side
    # bands (0.55 in each) fall inside the 0.625 in cropped from each side.
    assert red_in_front(vertical_bands=True) == []
    # Top and bottom bands survive: the crop axis is horizontal.
    assert red_in_front(vertical_bands=False) != []


# ---------------------------------------------------------------------------
# Per-panel output: bleed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target", ["per-panel-pdf", "moo-a6"])
def test_art_fills_the_bleed_band(workdir: Path, target: str) -> None:
    _quadrant_image(workdir / "front.png")
    template = _template(workdir, front={"background_image": "front.png"})
    _invoke("create", str(template), "--export-for", target, "-o", "out")
    front = Path("out/front.pdf")
    with pikepdf.open(front) as pdf:
        page = pdf.pages[0]
        media = [float(v) for v in page.MediaBox]
        trim = [float(v) for v in page.TrimBox]
    assert trim[0] > media[0]  # there is a bleed band to sample
    img = rasterize_pdf(front, DPI)
    w, h = img.size
    for x, y in ((4, 4), (w - 5, 4), (4, h - 5), (w - 5, h - 5)):
        px = img.getpixel((x, y))
        assert isinstance(px, tuple)
        assert not _close((px[0], px[1], px[2]), WHITE, tol=30), (target, x, y, px)


# ---------------------------------------------------------------------------
# moo-a6 / PDF/X-1a
# ---------------------------------------------------------------------------


@pytest.mark.pdfx
def test_moo_a6_opaque_background_passes_preflight(workdir: Path) -> None:
    from holiday_card.renderers.pdfx_preflight import preflight_pdfx1a

    _quadrant_image(workdir / "front.png")
    template = _template(
        workdir, front={"background_image": "front.png", "shape_elements": [_veil()]},
    )
    _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out")
    front = Path("out/front.pdf")
    assert preflight_pdfx1a(front) == []
    with pikepdf.open(front) as pdf:
        (image,) = pdf.pages[0].get_images().values()
        assert str(image.ColorSpace) == "/DeviceCMYK"
        assert "/SMask" not in image


@pytest.mark.pdfx
def test_moo_a6_rgba_background_flattens_over_the_background_colour(workdir: Path) -> None:
    from holiday_card.core.color_management import CMYKConverter, default_cmyk_icc_path
    from holiday_card.renderers.pdfx_preflight import preflight_pdfx1a

    Image.new("RGBA", (850, 1100), (0, 0, 255, 128)).save(workdir / "glass.png")
    template = _template(
        workdir,
        front={"background_image": "glass.png", "background_color": {"r": 1, "g": 0, "b": 0}},
    )
    _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out")
    front = Path("out/front.pdf")
    assert preflight_pdfx1a(front) == []
    with pikepdf.open(front) as pdf:
        (image,) = pdf.pages[0].get_images().values()
        assert "/SMask" not in image
        embedded = pikepdf.PdfImage(image).as_pil_image()
    px = embedded.getpixel((embedded.width // 2, embedded.height // 2))

    def cmyk_of(rgb: Pixel) -> tuple[int, ...]:
        converter = CMYKConverter(default_cmyk_icc_path())
        out = converter.convert_image(Image.new("RGB", (1, 1), rgb)).getpixel((0, 0))
        assert isinstance(out, tuple)
        return out

    blend_over_red = cmyk_of((round(255 * (1 - 128 / 255)), 0, 128))
    blend_over_white = cmyk_of((127, 127, 255))
    assert isinstance(px, tuple)
    assert all(abs(a - e) <= 6 for a, e in zip(px, blend_over_red, strict=True)), px
    assert not all(abs(a - e) <= 6 for a, e in zip(px, blend_over_white, strict=True))


@pytest.mark.pdfx
def test_translucent_element_over_the_art_is_refused_on_moo_a6(workdir: Path) -> None:
    _quadrant_image(workdir / "front.png")
    template = _template(
        workdir,
        front={"background_image": "front.png", "shape_elements": [_veil(opacity=0.5)]},
    )
    result = _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out", code=2)
    message = _plain(result.output)
    assert "shape_elements[0] (rectangle, id 'veil')" in message
    assert "image" in message.split("sits over a", 1)[1]
    assert not Path("out").exists()


def test_translucent_element_over_the_art_is_fine_on_letter(workdir: Path) -> None:
    _quadrant_image(workdir / "front.png")
    template = _template(
        workdir,
        front={"background_image": "front.png", "shape_elements": [_veil(opacity=0.5)]},
    )
    _invoke("create", str(template), "-o", "card.pdf")
    assert Path("card.pdf").exists()


# ---------------------------------------------------------------------------
# Print resolution (#66), measured at the covering rect
# ---------------------------------------------------------------------------


def test_moo_a6_bake_warns_at_276_ppi_on_moo_a6(workdir: Path) -> None:
    bake_fake_ai_asset(workdir, "art.png", size=(1314, 1824))
    template = _template(workdir, front={"background_image": "art.png"})
    result = _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out")
    match = re.search(r"art\.png is (\d+) PPI", _plain(result.stderr))
    assert match is not None, result.stderr
    assert abs(int(match.group(1)) - 276) <= 1


def test_moo_a6_bake_is_clean_on_letter(workdir: Path) -> None:
    bake_fake_ai_asset(workdir, "art.png", size=(1314, 1824))
    template = _template(workdir, front={"background_image": "art.png"})
    result = _invoke("create", str(template), "-o", "card.pdf")
    assert "PPI" not in result.stderr


def test_panel_background_size_is_clean_on_moo_a6(workdir: Path) -> None:
    Image.new("RGB", (1428, 1825), GREY).save(workdir / "big.png")
    template = _template(workdir, front={"background_image": "big.png"})
    result = _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out")
    assert "PPI" not in result.stderr


def test_tiny_background_is_refused_on_moo_a6(workdir: Path) -> None:
    Image.new("RGB", (400, 500), GREY).save(workdir / "tiny.png")
    template = _template(workdir, front={"background_image": "tiny.png"})
    result = _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out", code=2)
    assert "tiny.png" in _plain(result.output)
    assert not Path("out").exists()


# ---------------------------------------------------------------------------
# AI provenance
# ---------------------------------------------------------------------------


def test_baked_background_is_disclosed(workdir: Path) -> None:
    bake_fake_ai_asset(workdir, "art.png", model="gpt-image-2")
    template = _template(workdir, front={"background_image": "art.png"})
    _invoke("create", str(template), "-o", "card.pdf")
    with pikepdf.open("card.pdf") as pdf:
        assert "gpt-image-2" in str(pdf.docinfo["/Subject"])


def test_baked_background_without_sidecar_writes_nothing(workdir: Path) -> None:
    asset = bake_fake_ai_asset(workdir, "art.png")
    sidecar_path_for(asset).unlink()
    template = _template(workdir, front={"background_image": "art.png"})
    result = _invoke("create", str(template), "-o", "card.pdf", code=2)
    assert "background_image" in _plain(result.output)
    assert not Path("card.pdf").exists()


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------


def test_svg_embeds_the_art_once_inside_a_clip(workdir: Path) -> None:
    _banded_image(workdir / "bands.png", vertical_bands=True)
    template = _template(workdir, front={"background_image": "bands.png"})
    _invoke("create", str(template), "--format", "svg", "-o", "a.svg")
    _invoke("create", str(template), "--format", "svg", "-o", "b.svg")
    first = Path("a.svg").read_bytes()
    assert first == Path("b.svg").read_bytes()

    root = ET.fromstring(first)
    ns = "{http://www.w3.org/2000/svg}"
    parents = {child: parent for parent in root.iter() for child in parent}
    images = [
        el for el in root.iter(f"{ns}image")
        if el.get("href", "").startswith("data:image/png;base64,")
    ]
    assert len(images) == 1
    assert root.find(f".//{ns}clipPath") is not None
    node = images[0]
    clipped = False
    while node in parents:
        node = parents[node]
        clipped = clipped or node.get("clip-path") is not None
    assert clipped
