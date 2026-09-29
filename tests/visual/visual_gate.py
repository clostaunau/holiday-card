"""Render, crop and compare helpers for the per-panel visual gate (#68).

Shared by ``test_visual_regression.py``, ``test_visual_gate_sensitivity.py``
and ``scripts/regenerate_visual_baselines.py`` so the gate and the baseline
generator can never render differently.

Calibration (issue #68, christmas-classic, PNG @ 144 DPI, per-panel crop,
mismatched-pixel ratio at channel delta > 32):

    change                 front   inside_right  back / inside_left
    identical re-render    0.00%   0.00%         0.00%
    front text changed     2.02%   0.00%         0.00%
    all fonts → Lato       2.26%   1.17%         0.00%
    text at 80%            1.89%   0.73%         0.00%
    all text +2 pt in x    1.88%   0.86%         0.00%

``MAX_PANEL_RATIO = 0.25%`` catches every row with ≥ 2.9× margin. The old
gate (one 64-bit phash of the whole 72 DPI sheet, threshold 5) let "all
fonts → Lato" through at distance 6 of a noisy budget and could not see an
inside-panel change hiding in the whole-sheet hash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args

from PIL import Image, ImageChops, features

from holiday_card.core.compiler import CompileContext, compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.imposition import panel_placements
from holiday_card.core.models import Card
from holiday_card.core.templates import discover_templates
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.utils.measurements import PageGeometry
from rasterize import rasterize_pdf, to_rgb_on_white

# Render resolution for both backends (2 px per point).
DPI = 144
# A pixel mismatches when any channel differs by more than this (0-255).
CHANNEL_DELTA = 32
# A panel fails when more than this fraction of its pixels mismatch.
MAX_PANEL_RATIO = 0.0025
# Pixels dropped from every crop edge so seam anti-aliasing is not compared.
CROP_INSET_PX = 2

Backend = Literal["png", "pdf"]
BACKENDS: tuple[Backend, ...] = get_args(Backend)
PANELS = ("front", "back", "inside_left", "inside_right")

BASELINE_DIR = Path(__file__).parent / "fixtures" / "reference_cards"

Box = tuple[int, int, int, int]

_GEOMETRY = PageGeometry.us_letter()


def shipped_template_ids() -> list[str]:
    return sorted(t["id"] for t in discover_templates())


def png_layout_matches_baselines() -> bool:
    """Whether this host lays PNG text out like the committed baselines.

    Pillow uses libraqm (kerning) only when the system has libfribidi, else
    its basic layout; the two differ by up to 1.64% per text panel. The PNG
    baselines are raqm renders from ubuntu-latest.
    """
    return bool(features.check("raqm"))


def baseline_path(backend: Backend, template_id: str) -> Path:
    return BASELINE_DIR / backend / f"{template_id}.png"


def build_card(template_id: str) -> Card:
    return CardGenerator().create_card(template_id=template_id)


def render_sheet(card: Card, backend: Backend, workdir: Path) -> Image.Image:
    """Render ``card`` on the letter sheet (fold marks off) as an RGB image at ``DPI``."""
    commands = compile_card(card, CompileContext(geometry=_GEOMETRY, emit_fold_lines=False))
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / f"{card.template_id}.{backend}"
    if backend == "png":
        PNGRenderer(dpi=DPI).render(commands, out)
        return load_sheet(out)
    IRReportLabRenderer().render(commands, out)
    return rasterize_pdf(out, DPI)


def load_sheet(path: Path) -> Image.Image:
    with Image.open(path) as im:
        return to_rgb_on_white(im)


def panel_crop_boxes(card: Card, *, inset: int = CROP_INSET_PX) -> dict[str, Box]:
    """Pixel box (left, top, right, bottom; top-left origin) of each panel on the sheet.

    Taken from the compiler's imposition (D6), inset by ``inset`` px per edge.
    """
    scale = DPI / 72
    page_h = _GEOMETRY.trim_height_in * 72
    boxes: dict[str, Box] = {}
    for position, p in panel_placements(card).items():
        left = round(p.x_pt * scale)
        top = round((page_h - p.y_pt - p.height_pt) * scale)
        right = round((p.x_pt + p.width_pt) * scale)
        bottom = round((page_h - p.y_pt) * scale)
        boxes[position.value] = (left + inset, top + inset, right - inset, bottom - inset)
    return boxes


def _worst_channel(a: Image.Image, b: Image.Image) -> Image.Image:
    if a.size != b.size:
        raise ValueError(f"image sizes differ: {a.size} vs {b.size}")
    r, g, bl = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).split()
    return ImageChops.lighter(ImageChops.lighter(r, g), bl)


def mismatch_ratio(a: Image.Image, b: Image.Image) -> float:
    """Fraction of pixels whose largest channel difference exceeds ``CHANNEL_DELTA``."""
    bad = _worst_channel(a, b).point(lambda v: 255 if v > CHANNEL_DELTA else 0)
    return bad.histogram()[255] / (a.size[0] * a.size[1])


def panel_ratios(fresh: Image.Image, baseline: Image.Image, boxes: dict[str, Box]) -> dict[str, float]:
    return {name: mismatch_ratio(fresh.crop(box), baseline.crop(box)) for name, box in boxes.items()}


def diff_heatmap(a: Image.Image, b: Image.Image) -> Image.Image:
    """Grey copy of ``b`` with mismatched pixels painted red."""
    mask = _worst_channel(a, b).point(lambda v: 255 if v > CHANNEL_DELTA else 0)
    base = b.convert("L").point(lambda v: 128 + v // 2).convert("RGB")
    return Image.composite(Image.new("RGB", b.size, (255, 0, 0)), base, mask)
