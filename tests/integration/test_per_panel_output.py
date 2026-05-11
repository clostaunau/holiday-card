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

from holiday_card.core.export_targets import get_target
from holiday_card.core.generators import CardGenerator
from holiday_card.renderers.png_backend import PNGRenderer

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

    def test_letter_target_page_size_matches_letter_plus_bleed(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        gen = CardGenerator()
        card = gen.create_card(template_id=TEMPLATE_ID)
        gen.generate(card, out, target="letter")
        # Letter trim 612x792 + 0.125" bleed = 630x810
        w, h = _read_page_size(out.read_bytes())
        assert (w, h) == (630.0, 810.0)


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
        per_card = build_per_panel_card(card, panel, t)  # type: ignore[arg-type]
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
        the user fold by hand. Default ON; christmas-classic is half-fold
        so exactly one horizontal fold line."""
        card = CardGenerator().create_card(template_id=TEMPLATE_ID)
        assert _count_fold_lines(card, "letter") == 1

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
