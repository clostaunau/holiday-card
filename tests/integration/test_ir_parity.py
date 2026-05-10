"""IR backend parity tests.

For every template the Wave 2 compiler currently supports, render two
PDFs:

1. ``legacy.pdf`` via the existing ``ReportLabRenderer`` (today's prod path)
2. ``ir.pdf`` via ``compile_card`` → ``IRReportLabRenderer``

Then compare. Wave 2 Step 3 in ``/tmp/wave2_architecture.md``.

Comparison strategy in this PR
------------------------------
The architect's full plan calls for SSIM ≥ 0.995 perceptual diff via
``pypdfium2`` rasterization. Pulling in pypdfium2 + the rasterization
plumbing is a separate concern from proving the backend itself works,
so this PR uses a lighter contract:

* Both PDFs are valid (start with ``%PDF`` magic).
* Both PDFs have the same page count (proven via byte sniffing — no
  external deps).
* Both PDFs are within ±50% of each other in size (a complete-content
  smoke check; if the IR backend silently drops half the geometry, the
  size will collapse).

The follow-up PR (Step 3b) will add the perceptual SSIM gate. That's
where the architect's flagged risks (decorative-element ordering,
clip-mask state hygiene) actually surface — and those features are still
``UnsupportedFeatureError`` in the compiler, so they aren't reachable
through this test today.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.reportlab_renderer import ReportLabRenderer

# Same set as tests/unit/test_compiler.py SUPPORTED_SNAPSHOT_TEMPLATES.
# When a follow-up PR lifts more features into the compiler, add the
# template id here too.
PARITY_TEMPLATES = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "birthday-balloons",
    "hanukkah-menorah",
    "generic-celebration",
)


def _render_legacy(template_id: str, output_path: Path) -> None:
    """Run the existing CardGenerator code path."""
    generator = CardGenerator()
    card = generator.create_card(template_id=template_id, output_path=output_path)
    renderer = ReportLabRenderer()
    renderer.render(card, output_path)


def _render_ir(template_id: str, output_path: Path) -> None:
    """Run the new compile_card → IRReportLabRenderer code path."""
    card = CardGenerator().create_card(template_id=template_id)
    commands = compile_card(card)
    IRReportLabRenderer().render(commands, output_path)


def _count_pages(pdf_path: Path) -> int:
    """Count PDF pages by counting '/Type /Page' entries (no /Pages).

    No external deps required. Sufficient as a structural check.
    """
    blob = pdf_path.read_bytes()
    # Match '/Type /Page' followed by whitespace or '>' but NOT 'Pages'
    matches = re.findall(rb"/Type\s*/Page(?![s/])", blob)
    return len(matches)


@pytest.mark.parametrize("template_id", PARITY_TEMPLATES)
def test_ir_backend_produces_valid_pdf(template_id: str, tmp_path: Path) -> None:
    """Sanity: the IR pipeline writes a PDF with the right magic bytes."""
    out = tmp_path / f"{template_id}.ir.pdf"
    _render_ir(template_id, out)
    assert out.exists(), f"IR backend did not write {out}"
    assert out.read_bytes()[:4] == b"%PDF", "IR backend output is not a valid PDF"
    assert out.stat().st_size > 500, "IR backend output is suspiciously small"


@pytest.mark.parametrize("template_id", PARITY_TEMPLATES)
def test_ir_pdf_has_same_page_count_as_legacy(template_id: str, tmp_path: Path) -> None:
    """Page count is the cheapest structural parity check."""
    legacy = tmp_path / "legacy.pdf"
    ir = tmp_path / "ir.pdf"
    _render_legacy(template_id, legacy)
    _render_ir(template_id, ir)

    legacy_pages = _count_pages(legacy)
    ir_pages = _count_pages(ir)
    assert legacy_pages == ir_pages, (
        f"Page count drift for {template_id}: legacy={legacy_pages}, ir={ir_pages}"
    )
    assert legacy_pages >= 1, f"Legacy renderer produced no pages for {template_id}"


@pytest.mark.parametrize("template_id", PARITY_TEMPLATES)
def test_ir_pdf_size_is_within_bounds_of_legacy(template_id: str, tmp_path: Path) -> None:
    """Coarse content-volume parity: IR PDF must be within 50% of legacy
    PDF's size. If the IR backend silently drops half the geometry, the
    size collapses dramatically and we catch it here.

    A tighter parity gate (perceptual SSIM ≥ 0.995) is the architect's
    Step 3b — adding it requires pypdfium2 rasterization and is the
    next PR's job.
    """
    legacy = tmp_path / "legacy.pdf"
    ir = tmp_path / "ir.pdf"
    _render_legacy(template_id, legacy)
    _render_ir(template_id, ir)

    legacy_size = legacy.stat().st_size
    ir_size = ir.stat().st_size
    ratio = ir_size / legacy_size
    assert 0.5 <= ratio <= 1.5, (
        f"Size drift for {template_id}: legacy={legacy_size}B ir={ir_size}B "
        f"ratio={ratio:.2f} (expected 0.5..1.5)"
    )
