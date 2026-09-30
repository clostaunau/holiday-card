"""Shipped-template text: SVG (embedded subsets) vs PDF, per panel (#76, D12).

Each template's IR is reduced to its text (groups kept, so rotated inside
panels stay rotated; everything else dropped; ink forced to opaque black so
white-on-colour text shows on white), rendered through SVG and PDF, and
rasterized at 144 DPI. The SVG rasterizer loads only the fonts embedded in the
SVG. Every panel's text ink bbox must agree within 2 px per edge.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.imposition import panel_placements
from holiday_card.core.render_ir import (
    RGBA,
    BeginGroup,
    BeginPage,
    DrawText,
    EndGroup,
    EndPage,
    RenderCommand,
)
from holiday_card.core.templates import discover_templates
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer

DPI = 144
BBOX_TOLERANCE_PX = 2
_BLACK = RGBA(r=0, g=0, b=0)
_KEEP = (BeginPage, EndPage, BeginGroup, EndGroup)
_TEMPLATE_IDS = sorted(t["id"] for t in discover_templates() if t["source"] == "builtin")


def _text_only(commands: list[RenderCommand]) -> list[RenderCommand]:
    kept: list[RenderCommand] = []
    for cmd in commands:
        if isinstance(cmd, DrawText):
            run = cmd.run.model_copy(update={"color": _BLACK})
            kept.append(cmd.model_copy(update={"run": run, "opacity": 1.0}))
        elif isinstance(cmd, BeginGroup):
            kept.append(cmd.model_copy(update={"opacity": 1.0}))
        elif isinstance(cmd, _KEEP):
            kept.append(cmd)
    return kept


def _ink_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


def test_every_shipped_template_is_checked() -> None:
    assert len(_TEMPLATE_IDS) == 21


@pytest.mark.parametrize("template_id", _TEMPLATE_IDS)
def test_template_text_matches_pdf_per_panel(
    template_id: str,
    tmp_path: Path,
    rasterize_svg: Callable[[Path, int], Image.Image],
    rasterize_pdf: Callable[[Path, int], Image.Image],
) -> None:
    card = CardGenerator().create_card(template_id=template_id)
    commands = _text_only(compile_card(card))
    if not any(isinstance(c, DrawText) for c in commands):
        pytest.skip(f"{template_id} draws no text")
    svg, pdf = tmp_path / "t.svg", tmp_path / "t.pdf"
    SVGRenderer().render(commands, svg)
    IRReportLabRenderer().render(commands, pdf)
    svg_img, pdf_img = rasterize_svg(svg, DPI), rasterize_pdf(pdf, DPI)
    assert svg_img.size == pdf_img.size

    scale = DPI / 72
    page_h = svg_img.size[1] / scale
    for position, p in panel_placements(card).items():
        box = (
            round(p.x_pt * scale),
            round((page_h - p.y_pt - p.height_pt) * scale),
            round((p.x_pt + p.width_pt) * scale),
            round((page_h - p.y_pt) * scale),
        )
        got, want = _ink_bbox(svg_img.crop(box)), _ink_bbox(pdf_img.crop(box))
        where = f"{template_id}/{position.value}: svg {got} vs pdf {want}"
        assert (got is None) == (want is None), where
        if got is not None and want is not None:
            assert all(abs(a - b) <= BBOX_TOLERANCE_PX for a, b in zip(got, want, strict=True)), where
