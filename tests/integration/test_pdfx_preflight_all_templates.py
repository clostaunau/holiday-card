"""PDF/X-1a preflight over every shipped template's moo-a6 output (#69, D11).

Each template is rendered once with ``--export-for moo-a6`` (four panel PDFs)
and checked three ways:

* ``preflight_pdfx1a`` (the pikepdf rule checker) returns no violation:
  fonts, metadata, boxes, forbidden features, transparency (flattened in
  the compiler) and image colour spaces (converted to CMYK), #71.
* poppler ``pdffonts``: every font row says ``emb yes``.
* poppler ``pdfimages -list``: every image is ``cmyk``.
* Ghostscript ``inkcov``: every file renders and reports four ink values
  per page.

The external tools are skipped when missing, unless
``HOLIDAY_CARD_REQUIRE_PREFLIGHT_TOOLS=1`` (set by the ``pdfx-preflight`` CI
job, which installs both) turns the skip into a failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from holiday_card.core.generators import CardGenerator
from holiday_card.core.templates import discover_templates
from holiday_card.renderers.pdfx_preflight import (
    PreflightViolation,
    preflight_pdfx1a,
)

pytestmark = pytest.mark.pdfx

TEMPLATE_IDS = sorted(t["id"] for t in discover_templates())
# Templates whose front panel embeds a raster image (placeholder photo).
IMAGE_TEMPLATES = (
    "birthday-photo", "christmas-family-photo", "christmas-holiday-masterpiece",
    "christmas-photo-ornament", "mothers-day-photo",
)


@pytest.fixture(scope="module")
def moo_outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[Path]]:
    gen = CardGenerator()
    root = tmp_path_factory.mktemp("moo-a6")
    return {
        tid: gen.generate(gen.create_card(tid), root / tid, target="moo-a6")
        for tid in TEMPLATE_IDS
    }


@pytest.fixture(scope="module")
def moo_violations(
    moo_outputs: dict[str, list[Path]],
) -> dict[str, list[tuple[str, PreflightViolation]]]:
    return {
        tid: [(p.name, v) for p in paths for v in preflight_pdfx1a(p)]
        for tid, paths in moo_outputs.items()
    }


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        message = f"{name} is not installed"
        if os.environ.get("HOLIDAY_CARD_REQUIRE_PREFLIGHT_TOOLS") == "1":
            pytest.fail(f"{message} (HOLIDAY_CARD_REQUIRE_PREFLIGHT_TOOLS=1)")
        pytest.skip(message)
    return path


def _pdffonts_unembedded(pdffonts: str, pdf: Path) -> list[str]:
    """Rows of ``pdffonts`` whose ``emb`` column is not ``yes``."""
    result = subprocess.run([pdffonts, str(pdf)], capture_output=True, text=True,
                            check=True)
    lines = result.stdout.splitlines()
    column = lines[0].index("emb")
    return [row for row in lines[2:] if row[column:column + 3].strip() != "yes"]


def test_every_shipped_template_is_covered() -> None:
    assert len(TEMPLATE_IDS) == 21


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_preflight_is_clean(
    moo_outputs: dict[str, list[Path]],
    moo_violations: dict[str, list[tuple[str, PreflightViolation]]],
    template_id: str,
) -> None:
    assert len(moo_outputs[template_id]) == 4
    assert moo_violations[template_id] == []


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_no_transparency(
    moo_violations: dict[str, list[tuple[str, PreflightViolation]]], template_id: str
) -> None:
    found = [(n, v) for n, v in moo_violations[template_id]
             if v.rule.startswith("transparency.")]
    assert found == []


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_no_rgb_images(
    moo_violations: dict[str, list[tuple[str, PreflightViolation]]], template_id: str
) -> None:
    found = [(n, v) for n, v in moo_violations[template_id]
             if v.rule == "colorspace.rgb_image"]
    assert found == []


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_pdffonts_reports_every_font_embedded(
    moo_outputs: dict[str, list[Path]], template_id: str
) -> None:
    pdffonts = _require_tool("pdffonts")
    for pdf in moo_outputs[template_id]:
        assert _pdffonts_unembedded(pdffonts, pdf) == [], pdf.name


def _pdfimages_colours(pdfimages: str, pdf: Path) -> list[str]:
    """The ``color`` column of ``pdfimages -list``, one entry per image."""
    result = subprocess.run([pdfimages, "-list", str(pdf)], capture_output=True,
                            text=True, check=True)
    lines = result.stdout.splitlines()
    column = lines[0].split().index("color")
    return [row.split()[column] for row in lines[2:]]


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_pdfimages_reports_cmyk_for_every_image(
    moo_outputs: dict[str, list[Path]], template_id: str
) -> None:
    pdfimages = _require_tool("pdfimages")
    colours = [c for pdf in moo_outputs[template_id]
               for c in _pdfimages_colours(pdfimages, pdf)]
    assert all(c == "cmyk" for c in colours), colours
    if template_id in IMAGE_TEMPLATES:
        assert colours, "expected the placeholder photo"


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_ghostscript_inkcov_renders_every_page(
    moo_outputs: dict[str, list[Path]], template_id: str
) -> None:
    gs = _require_tool("gs")
    for pdf in moo_outputs[template_id]:
        result = subprocess.run(
            [gs, "-dBATCH", "-dNOPAUSE", "-dQUIET", "-sDEVICE=inkcov", "-o", "-",
             str(pdf)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"{pdf.name}: {result.stderr}"
        pages = [line.split() for line in result.stdout.splitlines() if line.strip()]
        assert len(pages) == 1, f"{pdf.name}: {result.stdout!r}"
        for fields in pages:
            values = [float(v) for v in fields[:4]]
            assert len(values) == 4 and fields[4:6] == ["CMYK", "OK"], fields


@pytest.fixture(scope="module")
def letter_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    gen = CardGenerator()
    out = tmp_path_factory.mktemp("letter") / "christmas-classic.pdf"
    [path] = gen.generate(gen.create_card("christmas-classic"), out)
    return path


class TestLetterPdfFonts:
    """The default sRGB ``letter`` PDF is not PDF/X, but embeds every font."""

    def test_preflight_finds_no_unembedded_font(self, letter_pdf: Path) -> None:
        assert [v for v in preflight_pdfx1a(letter_pdf)
                if v.rule == "font.not_embedded"] == []

    def test_pdffonts_reports_every_font_embedded(self, letter_pdf: Path) -> None:
        pdffonts = _require_tool("pdffonts")
        assert _pdffonts_unembedded(pdffonts, letter_pdf) == []
