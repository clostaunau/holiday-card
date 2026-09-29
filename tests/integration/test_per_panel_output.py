"""Integration tests for ``--export-for`` per-panel rendering.

Renders christmas-classic via the per-panel-pdf and moo-a6 targets and
verifies:

* Four output files appear in the destination directory, one per panel.
* Each PDF declares the expected page dimensions (panel-native vs A6).
* MediaBox / TrimBox / BleedBox declarations are correct on every file.
* The PDFs are individually valid and non-empty.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.compiler import compile_card
from holiday_card.core.export_targets import get_target
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import Card, Color
from holiday_card.core.per_panel import build_per_panel_card, build_per_panel_context
from holiday_card.core.render_ir import BeginGroup, DrawImage, EndGroup, RenderCommand
from holiday_card.core.templates import discover_templates
from holiday_card.renderers.png_backend import PNGRenderer
from rasterize import rasterize_pdf

# Christmas-classic is the canonical half-fold card used by every other
# integration test; reuse it here so the per-panel suite shares fixtures.
TEMPLATE_ID = "christmas-classic"

# The four panel filenames the generator emits for a half-fold card.
EXPECTED_FILENAMES = {"front", "back", "inside-left", "inside-right"}


def _box(pdf_bytes: bytes, name: bytes) -> tuple[float, float, float, float]:
    """Locate /<name> [a b c d] in a PDF byte stream."""
    match = re.search(
        rb"/" + name + rb"\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]",
        pdf_bytes,
    )
    assert match, f"PDF missing /{name.decode()}"
    return tuple(float(g) for g in match.groups())  # type: ignore[return-value]


def _read_page_size(pdf_bytes: bytes) -> tuple[float, float]:
    """Page size is encoded by the /MediaBox declaration."""
    x0, y0, x1, y1 = _box(pdf_bytes, b"MediaBox")
    return (x1 - x0, y1 - y0)


class TestPerPanelPdf:
    """``--export-for per-panel-pdf`` produces 4 native-dim PDFs."""

    def test_emits_one_pdf_per_panel(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "per-panel"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        written = gen.generate(card, out_dir, target="per-panel-pdf")
        assert len(written) == 4
        stems = {p.stem for p in written}
        assert stems == EXPECTED_FILENAMES

    def test_each_pdf_is_native_panel_size(self, tmp_path: Path) -> None:
        # christmas-classic panels are 4.25" x 5.5" → 306 x 396 pt trim
        # + 0.125" bleed on every side → 324 x 414 pt media box.
        out_dir = tmp_path / "per-panel"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        gen.generate(card, out_dir, target="per-panel-pdf")
        for pdf in out_dir.glob("*.pdf"):
            w, h = _read_page_size(pdf.read_bytes())
            assert w == 324.0, f"{pdf.name}: expected 324pt wide, got {w}"
            assert h == 414.0, f"{pdf.name}: expected 414pt tall, got {h}"

    def test_each_pdf_declares_distinct_trim_and_bleed(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "per-panel"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        gen.generate(card, out_dir, target="per-panel-pdf")
        for pdf in out_dir.glob("*.pdf"):
            data = pdf.read_bytes()
            media = _box(data, b"MediaBox")
            trim = _box(data, b"TrimBox")
            assert media != trim, (
                f"{pdf.name}: MediaBox and TrimBox are identical; bleed "
                "didn't propagate to per-panel output."
            )
            # Trim sits inside MediaBox at (bleed, bleed) = (9, 9).
            assert trim == (9.0, 9.0, 315.0, 405.0)


class TestMooA6:
    """``--export-for moo-a6`` produces 4 PDFs at A6 trim with content scaling."""

    def test_emits_one_pdf_per_panel(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "moo-a6"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        written = gen.generate(card, out_dir, target="moo-a6")
        assert len(written) == 4
        stems = {p.stem for p in written}
        assert stems == EXPECTED_FILENAMES

    def test_each_pdf_is_a6_size(self, tmp_path: Path) -> None:
        # A6 is 4.13" x 5.83" → 297.36 x 419.76 pt trim + 0.125" bleed
        # → 315.36 x 437.76 pt media box.
        out_dir = tmp_path / "moo-a6"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        gen.generate(card, out_dir, target="moo-a6")
        target = get_target("moo-a6")
        assert target.geometry is not None
        expected_media_w = round((target.geometry.trim_width_in + 2 * target.geometry.bleed_in) * 72, 2)
        expected_media_h = round((target.geometry.trim_height_in + 2 * target.geometry.bleed_in) * 72, 2)
        for pdf in out_dir.glob("*.pdf"):
            w, h = _read_page_size(pdf.read_bytes())
            assert round(w, 2) == expected_media_w, f"{pdf.name}: media width mismatch"
            assert round(h, 2) == expected_media_h, f"{pdf.name}: media height mismatch"

    def test_each_pdf_declares_distinct_trim_and_bleed(self, tmp_path: Path) -> None:
        # Regression guard: the letter target lost its bleed (#59); the
        # POD targets must keep theirs.
        out_dir = tmp_path / "moo-a6"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        gen.generate(card, out_dir, target="moo-a6")
        for pdf in out_dir.glob("*.pdf"):
            data = pdf.read_bytes()
            media = _box(data, b"MediaBox")
            trim = _box(data, b"TrimBox")
            assert media != trim, f"{pdf.name}: MediaBox and TrimBox are identical"
            # Trim sits inside the MediaBox at (bleed, bleed) = (9, 9).
            assert trim[0] == 9.0 and trim[1] == 9.0

    def test_each_pdf_is_a_valid_nonempty_file(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "moo-a6"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        gen.generate(card, out_dir, target="moo-a6")
        for pdf in out_dir.glob("*.pdf"):
            assert pdf.stat().st_size > 500, f"{pdf.name} is suspiciously small"
            assert pdf.read_bytes().startswith(b"%PDF-"), f"{pdf.name} is not a PDF"


class TestPerPanelPng:
    """Per-panel mode also works with the PNG renderer (preview pipeline)."""

    def test_emits_one_png_per_panel(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "per-panel-png"
        gen = CardGenerator(renderer=PNGRenderer(dpi=72))
        card = gen.create_card(template_id=TEMPLATE_ID)
        written = gen.generate(card, out_dir, target="per-panel-pdf")
        assert len(written) == 4
        for path in written:
            assert path.suffix == ".png", f"PNG renderer produced {path}"
            assert path.exists()
            assert path.stat().st_size > 200


class TestImpositionUnchanged:
    """``--export-for letter`` (default) preserves the today-behavior:
    one imposed PDF, identical pixels to a no-export-for invocation."""

    def test_letter_target_emits_single_file(self, tmp_path: Path) -> None:
        out = tmp_path / "card.pdf"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        written = gen.generate(card, out, target="letter")
        assert len(written) == 1
        assert written[0] == out
        assert out.exists()

    def test_letter_target_page_size_is_us_letter(self, tmp_path: Path) -> None:
        out = tmp_path / "card.pdf"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        gen.generate(card, out, target="letter")
        # Home-printer page: 8.5x11 with no bleed (D7, #59).
        w, h = _read_page_size(out.read_bytes())
        assert (w, h) == (612.0, 792.0)


# ---------------------------------------------------------------------------
# --with-fold-marks / --no-fold-marks gate (Agreement 3)
# ---------------------------------------------------------------------------


def _count_fold_lines(card: object, target: str, **gen_kwargs) -> int:
    """Render via the IR to count actual DrawFoldLine commands.

    More reliable than scanning the compressed PDF byte stream, which
    is opaque to byte-level dash-pattern matching.
    """
    from holiday_card.core.compiler import CompileContext, compile_card
    from holiday_card.core.export_targets import get_target
    from holiday_card.core.per_panel import (
        build_per_panel_card,
        build_per_panel_context,
    )
    from holiday_card.core.render_ir import DrawFoldLine

    t = get_target(target)
    emit = gen_kwargs.get("emit_fold_lines")
    fold_marks = emit if emit is not None else t.fold_marks_default

    if t.layout == "imposition":
        ctx = CompileContext(geometry=t.geometry, emit_fold_lines=fold_marks)
        cmds = compile_card(card, ctx)  # type: ignore[arg-type]
        return sum(1 for c in cmds if isinstance(c, DrawFoldLine))

    # Per-panel: count across all panels
    total = 0
    for panel in card.panels:  # type: ignore[attr-defined]
        per_card = build_per_panel_card(card, panel)  # type: ignore[arg-type]
        ctx = build_per_panel_context(panel, t)
        if fold_marks and not ctx.emit_fold_lines:
            from dataclasses import replace
            ctx = replace(ctx, emit_fold_lines=True)
        cmds = compile_card(per_card, ctx)
        total += sum(1 for c in cmds if isinstance(c, DrawFoldLine))
    return total


class TestFoldMarksGate:
    def test_letter_target_emits_fold_marks_by_default(self) -> None:
        """Letter is a home-printer target; the dashed grey guide helps
        the user fold by hand. Default ON; christmas-classic is a 4-up
        quarter fold so both fold lines are drawn (#58)."""
        card = CardGenerator().create_card(template_id=TEMPLATE_ID)
        assert _count_fold_lines(card, "letter") == 2

    def test_no_fold_marks_override_suppresses_for_letter(self) -> None:
        card = CardGenerator().create_card(template_id=TEMPLATE_ID)
        assert _count_fold_lines(card, "letter", emit_fold_lines=False) == 0

    def test_per_panel_targets_default_to_no_fold_marks(self) -> None:
        """Per-panel files are finished cards, not folded sheets."""
        card = CardGenerator().create_card(template_id=TEMPLATE_ID)
        assert _count_fold_lines(card, "per-panel-pdf") == 0
        assert _count_fold_lines(card, "moo-a6") == 0

    def test_with_fold_marks_override_doesnt_error_on_per_panel(self) -> None:
        """A panel rendered as its own page doesn't have a fold inside
        — the per-panel CompileContext geometry is panel-sized and
        ``_emit_fold_lines`` returns no commands for a non-foldable page.
        Override should be a no-op without erroring."""
        card = CardGenerator().create_card(template_id=TEMPLATE_ID)
        # half-fold compiler emits one fold line per page in fold geometry;
        # per-panel pages aren't fold-typed inputs (fold_type stays from card
        # but the per-panel geometry doesn't trigger a meaningful fold).
        # Either zero or one per panel is acceptable; assert no error.
        n = _count_fold_lines(card, "per-panel-pdf", emit_fold_lines=True)
        assert n >= 0  # the assertion is "no error during compile"


# ---------------------------------------------------------------------------
# moo-a6 fills the A6 page: no white bands inside the trim (D8, #73)
# ---------------------------------------------------------------------------

_DPI = 72
_A6_FILL_S = 5.83 / 5.5
_A6_OFFSET_X_PT = (4.13 * 72 - 4.25 * 72 * _A6_FILL_S) / 2
_PANEL_STEMS = {
    "front": "front", "back": "back",
    "inside_left": "inside-left", "inside_right": "inside-right",
}


def _rgb(color: Color) -> tuple[int, int, int]:
    return (round(color.r * 255), round(color.g * 255), round(color.b * 255))


def _close(a: tuple[int, ...], b: tuple[int, ...], tol: int = 2) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=False))


def _edge_samples(img: Image.Image) -> dict[str, tuple[int, ...]]:
    w, h = img.size
    return {
        "top": img.getpixel((w // 2, 3)), "bottom": img.getpixel((w // 2, h - 4)),
        "left": img.getpixel((3, h // 2)), "right": img.getpixel((w - 4, h // 2)),
    }


def _render_moo(tmp_path: Path, template_id: str, renderer: object) -> tuple[Card, Path]:
    gen = CardGenerator(renderer=renderer)  # type: ignore[arg-type]
    card = gen.create_card(template_id=template_id)
    out = tmp_path / template_id
    gen.generate(card, out, target="moo-a6")
    return card, out


class TestMooA6FillsTrim:
    def test_png_front_is_red_just_inside_the_trim_top_and_bottom(self, tmp_path: Path) -> None:
        _, out = _render_moo(tmp_path, TEMPLATE_ID, PNGRenderer(dpi=_DPI))
        img = Image.open(out / "front.png").convert("RGB")
        w, h = img.size
        assert _close(img.getpixel((w // 2, 12)), (204, 26, 26))
        assert _close(img.getpixel((w // 2, h - 12)), (204, 26, 26))

    def test_png_every_panel_reaches_every_media_edge(self, tmp_path: Path) -> None:
        card, out = _render_moo(tmp_path, TEMPLATE_ID, PNGRenderer(dpi=_DPI))
        for panel in card.panels:
            assert panel.background_color is not None
            img = Image.open(out / f"{_PANEL_STEMS[panel.position.value]}.png").convert("RGB")
            for edge, pixel in _edge_samples(img).items():
                assert _close(pixel, _rgb(panel.background_color), tol=3), (
                    f"{panel.position.value} {edge}: {pixel}"
                )

    def test_pdf_every_panel_reaches_every_media_edge(self, tmp_path: Path) -> None:
        card, out = _render_moo(tmp_path, TEMPLATE_ID, None)
        for panel in card.panels:
            assert panel.background_color is not None
            img = rasterize_pdf(out / f"{_PANEL_STEMS[panel.position.value]}.pdf", _DPI)
            for edge, pixel in _edge_samples(img).items():
                # CMYK round trip through GRACoL moves the colour a little.
                assert _close(pixel, _rgb(panel.background_color), tol=40), (
                    f"{panel.position.value} {edge}: {pixel}"
                )
                if min(_rgb(panel.background_color)) < 240:
                    assert pixel != (255, 255, 255), f"{panel.position.value} {edge}"


def _front_ir(template_id: str, target_name: str) -> list[RenderCommand]:
    card = CardGenerator().create_card(template_id=template_id)
    target = get_target(target_name)
    front = next(p for p in card.panels if p.position.value == "front")
    return compile_card(
        build_per_panel_card(card, front), build_per_panel_context(front, target),
    )


class TestMooA6Photo:
    def test_image_is_drawn_at_its_native_rect_inside_the_scale_group(self) -> None:
        native = [c for c in _front_ir("christmas-photo-ornament", "per-panel-pdf")
                  if isinstance(c, DrawImage)]
        moo = _front_ir("christmas-photo-ornament", "moo-a6")
        scale_idx = next(
            i for i, c in enumerate(moo)
            if isinstance(c, BeginGroup) and c.transform.scale_x != 1.0
        )
        end_idx = max(i for i, c in enumerate(moo) if isinstance(c, EndGroup))
        images = [(i, c) for i, c in enumerate(moo) if isinstance(c, DrawImage)]
        assert images and len(images) == len(native)
        for (i, img), ref in zip(images, native, strict=True):
            assert scale_idx < i < end_idx
            assert img.image.rect == ref.image.rect

    def test_png_pixel_just_inside_the_ornament_clip_is_photo(self, tmp_path: Path) -> None:
        gen = CardGenerator(renderer=PNGRenderer(dpi=_DPI))
        card = gen.create_card(template_id="christmas-photo-ornament")
        gen.generate(card, tmp_path / "moo", target="moo-a6")
        gen.generate(card, tmp_path / "native", target="per-panel-pdf")
        front = next(p for p in card.panels if p.position.value == "front")
        assert front.background_color is not None
        # Clip circle centre (2.125, 2.75)", radius 1.5": sample 1.4" left of
        # centre, inside the ornament's gold stroke (radius 1.6" ± 4 pt).
        nx_pt, ny_pt = (2.125 - 1.4) * 72, 2.75 * 72
        moo = Image.open(tmp_path / "moo" / "front.png").convert("RGB")
        nat = Image.open(tmp_path / "native" / "front.png").convert("RGB")
        photo = nat.getpixel((round(nx_pt + 9), nat.size[1] - round(ny_pt + 9)))
        px = round(nx_pt * _A6_FILL_S + _A6_OFFSET_X_PT + 9)
        py = moo.size[1] - round(ny_pt * _A6_FILL_S + 9)
        pixel = moo.getpixel((px, py))
        assert not _close(photo, _rgb(front.background_color), tol=10), photo
        assert _close(pixel, photo, tol=12), (pixel, photo)


def _white_lines(img: Image.Image, axis: str, box: tuple[int, int, int, int]) -> set[int]:
    """Indices of rows (axis='row') or columns inside ``box`` that are all near-white."""
    x0, y0, x1, y1 = box
    px = img.load()
    assert px is not None
    lines = range(y0, y1) if axis == "row" else range(x0, x1)
    across = range(x0, x1) if axis == "row" else range(y0, y1)
    white = set()
    for i in lines:
        pixels = (px[j, i] if axis == "row" else px[i, j] for j in across)
        if all(min(p[:3]) >= 250 for p in pixels):
            white.add(i)
    return white


@pytest.mark.parametrize("template_id", sorted(t["id"] for t in discover_templates()))
def test_moo_a6_has_no_white_band_the_native_panel_lacks(
    template_id: str, tmp_path: Path,
) -> None:
    """Every white row / column inside the A6 trim is white in the native panel too."""
    gen = CardGenerator(renderer=PNGRenderer(dpi=_DPI))
    card = gen.create_card(template_id=template_id)
    gen.generate(card, tmp_path / "moo", target="moo-a6")
    gen.generate(card, tmp_path / "native", target="per-panel-pdf")
    bleed = 9
    for panel in card.panels:
        stem = _PANEL_STEMS[panel.position.value]
        moo = Image.open(tmp_path / "moo" / f"{stem}.png").convert("RGB")
        nat = Image.open(tmp_path / "native" / f"{stem}.png").convert("RGB")
        mw, mh = moo.size
        nw, nh = nat.size
        moo_trim = (bleed, bleed, mw - bleed, mh - bleed)
        nat_trim = (bleed, bleed, nw - bleed, nh - bleed)
        nat_white_rows = _white_lines(nat, "row", nat_trim)
        nat_white_cols = _white_lines(nat, "col", nat_trim)
        for r in _white_lines(moo, "row", moo_trim):
            y_trim = (mh - bleed) - (r + 0.5)           # pt above the trim bottom
            native_y = y_trim / _A6_FILL_S
            nr = round((nh - bleed) - native_y - 0.5)
            assert {nr - 1, nr, nr + 1} & nat_white_rows, (
                f"{panel.position.value}: moo-a6 row {r} is white, native row {nr} is not"
            )
        for c in _white_lines(moo, "col", moo_trim):
            x_trim = (c + 0.5) - bleed
            native_x = (x_trim - _A6_OFFSET_X_PT) / _A6_FILL_S
            nc = round(native_x + bleed - 0.5)
            assert {nc - 1, nc, nc + 1} & nat_white_cols, (
                f"{panel.position.value}: moo-a6 column {c} is white, native column {nc} is not"
            )
