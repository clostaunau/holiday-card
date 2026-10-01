"""A transparent AI motif (#169) placed as an ``image_elements`` rect, end to end.

The motif is baked through the real ``generate_ai_asset`` (no network; see
``tests/ai_fixtures.py``): green over the middle half of each axis, fully
transparent around it. On letter / PNG the panel colour shows through the
transparent area; on moo-a6 (PDF/X, D10) it flattens over a solid fill, and
over a ``background_image`` it is refused, naming the element.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pikepdf
import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner, Result

from ai_fixtures import bake_fake_ai_asset
from holiday_card.cli.commands import app
from holiday_card.core.ai_provenance import read_sidecar

runner = CliRunner()

DPI = 144
MOTIF = (10, 120, 60)
PANEL = {"r": 0.8, "g": 0.1, "b": 0.1}  # the panel colour that must show through
PANEL_RGB = (204, 26, 26)
# The motif rect on the front panel, in panel inches from its top-left.
X, Y, W, H = 1.125, 1.75, 2.0, 2.0


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _invoke(*args: str, code: int = 0) -> Result:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, _plain(result.output)
    assert "Traceback" not in result.output
    return result


def _template(directory: Path, **front: Any) -> Path:
    def panel(position: str, **extra: Any) -> dict[str, Any]:
        return {"id": position, "position": position, "width": 4.25, "height": 5.5, **extra}

    motif = {
        "id": "holly", "source_path": "motif.png", "x": X, "y": Y, "width": W, "height": H,
        "z_index": 10,
    }  # fmt: skip
    doc = {
        "id": "motif-card",
        "name": "Transparent motif fixture",
        "occasion": "christmas",
        "fold_type": "quarter_fold",
        "panels": [
            panel("front", background_color=PANEL, image_elements=[motif], **front),
            panel("back"),
            panel("inside_left"),
            panel("inside_right"),
        ],
    }
    path = directory / "motif-card.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    bake_fake_ai_asset(tmp_path, "motif.png", size=(600, 600), color=MOTIF, transparent=True)
    return tmp_path


def _close(actual: tuple[int, ...], expected: tuple[int, ...], tol: int = 8) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


def test_the_baked_motif_is_a_marked_rgba_png_with_a_transparent_sidecar(workdir: Path) -> None:
    with Image.open(workdir / "motif.png") as img:
        assert img.mode == "RGBA"
        assert img.getpixel((5, 5))[3] == 0
        assert img.getpixel((300, 300)) == (*MOTIF, 255)
    assert read_sidecar(workdir / "motif.png").background == "transparent"


def test_png_preview_shows_the_panel_colour_through_the_transparent_area(
    workdir: Path,
) -> None:
    template = _template(workdir)
    _invoke("preview", str(template), "--no-open", "--dpi", str(DPI), "-o", "sheet.png")
    with Image.open("sheet.png") as sheet:
        rgb = sheet.convert("RGB")
    # The front panel is the bottom-right quarter of the letter sheet (D6).
    left, top = 4.25 * DPI, 5.5 * DPI

    def at(x_in: float, y_in: float) -> tuple[int, ...]:
        px = rgb.getpixel((round(left + x_in * DPI), round(top + y_in * DPI)))
        assert isinstance(px, tuple)
        return px

    assert _close(at(X + W / 2, Y + H / 2), MOTIF)  # the motif's opaque middle
    assert _close(at(X + W / 8, Y + H / 8), PANEL_RGB)  # its transparent corner
    assert _close(at(0.3, 0.3), PANEL_RGB)  # the panel outside the motif


@pytest.mark.pdfx
def test_moo_a6_flattens_the_motif_over_the_solid_panel_colour(workdir: Path) -> None:
    from holiday_card.renderers.pdfx_preflight import preflight_pdfx1a

    template = _template(workdir)
    _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out")
    front = Path("out/front.pdf")
    assert preflight_pdfx1a(front) == []
    with pikepdf.open(front) as pdf:
        (image,) = pdf.pages[0].get_images().values()
        assert str(image.ColorSpace) == "/DeviceCMYK"
        assert "/SMask" not in image
        embedded = pikepdf.PdfImage(image).as_pil_image()
    corner = embedded.getpixel((2, 2))
    middle = embedded.getpixel((embedded.width // 2, embedded.height // 2))
    # The transparent corner became the panel's red, distinct from the motif.
    assert corner != middle
    assert isinstance(corner, tuple)
    assert corner[1] > 150 and corner[2] > 150  # CMYK red: high magenta and yellow


def test_moo_a6_refuses_the_motif_over_a_background_image(workdir: Path) -> None:
    Image.new("RGB", (850, 1100), (30, 60, 200)).save(workdir / "bg.png")
    template = _template(workdir, background_image="bg.png")
    result = _invoke("create", str(template), "--export-for", "moo-a6", "-o", "out", code=2)
    message = _plain(result.output)
    assert "image_elements[0]" in message
    assert "holly" in message
    assert not Path("out").exists()


def test_letter_composites_the_motif_over_a_background_image(workdir: Path) -> None:
    Image.new("RGB", (850, 1100), (30, 60, 200)).save(workdir / "bg.png")
    template = _template(workdir, background_image="bg.png")
    _invoke("create", str(template), "-o", "card.pdf")
    assert Path("card.pdf").exists()
