"""Per-panel visual-regression gate for PNG and PDF (#68, D12).

Every shipped template is rendered fresh through both deliverable backends
(``PNGRenderer`` and ``IRReportLabRenderer`` rasterized with pypdfium2) at
144 DPI on the letter target (no bleed, fold marks off), then each panel is
cropped where imposition puts it (``core/imposition.panel_placements``) and
compared with the committed full-sheet baseline by mismatched-pixel ratio.
The constants and their calibration live in ``visual_gate.py``;
``test_visual_gate_sensitivity.py`` locks them.

Baselines are ``fixtures/reference_cards/{png,pdf}/{template_id}.png`` and are
**generated on Ubuntu CI**, never on a laptop:

1. Run the ``visual-baselines`` workflow (Actions → visual-baselines → Run
   workflow, on your branch). It runs
   ``python scripts/regenerate_visual_baselines.py`` on ubuntu-latest and
   uploads ``reference_cards/`` as an artifact.
2. Download it, **eyeball every PNG** (automated regeneration captures bugs
   as truth), and commit it over ``tests/visual/fixtures/reference_cards/``.

Locally, ``python scripts/regenerate_visual_baselines.py [--backend
{png,pdf,all}] [--template ID]`` prints each panel's ratio against the old
baseline, so you know which files changed. PNG needs Pillow's raqm text
layout (libfribidi on the host; see the cross-host policy below): without it
the PNG cases skip and the script refuses to write PNG baselines. On a failure, the fresh sheet,
the baseline and fresh crops and a diff heatmap are written to
``$HOLIDAY_CARD_VISUAL_OUT`` (CI uploads it) or the test's ``tmp_path``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest
from PIL import Image
from visual_gate import (
    BACKENDS,
    BASELINE_DIR,
    MAX_PANEL_RATIO,
    PANELS,
    Backend,
    baseline_path,
    build_card,
    diff_heatmap,
    load_sheet,
    mismatch_ratio,
    panel_crop_boxes,
    png_layout_matches_baselines,
    render_sheet,
    shipped_template_ids,
)

pytestmark = pytest.mark.visual

Box = tuple[int, int, int, int]
Sheets = Callable[[str, Backend], tuple[Image.Image, dict[str, Box]]]

# Cross-host policy (#68), measured against the ubuntu-latest baselines for all
# 21 x 2 x 4 crops. PDF: pdfium rasterizes identically on macOS (max 0.0000%).
# PNG: Pillow lays text out with libraqm (kerning) only when the host has
# libfribidi, else with its basic layout, and the two differ by up to 1.636%
# per panel (christmas-family-photo inside_right). ubuntu-latest has fribidi;
# macOS and python:3.12-slim do not. With fribidi loaded, macOS is within
# 0.1019% (christmas-artist front), under half the 0.25% limit, so both OSes
# are gated: CI installs fribidi on macOS and sets HOLIDAY_CARD_REQUIRE_PNG_VISUAL
# so a runner without raqm fails instead of silently skipping. Locally without
# raqm the PNG cases skip (macOS: `brew install fribidi` and run with
# DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix fribidi)/lib").
_PNG_SKIP_REASON = (
    "Pillow has no raqm layout here (no libfribidi); PNG text would differ from the "
    "raqm-rendered baselines by up to 1.64% per panel (measured in #68)"
)


def _require_png_layout(backend: Backend) -> None:
    if backend != "png" or png_layout_matches_baselines():
        return
    if os.environ.get("HOLIDAY_CARD_REQUIRE_PNG_VISUAL"):
        pytest.fail(f"HOLIDAY_CARD_REQUIRE_PNG_VISUAL is set but {_PNG_SKIP_REASON}")
    pytest.skip(_PNG_SKIP_REASON)


_REGEN_HINT = (
    "Regenerate on Ubuntu CI with the visual-baselines workflow "
    "(see tests/visual/test_visual_regression.py) and eyeball every PNG."
)


def _artifact_dir(tmp_path: Path) -> Path:
    out = os.environ.get("HOLIDAY_CARD_VISUAL_OUT")
    return Path(out) if out else tmp_path


@pytest.fixture(scope="session")
def fresh_sheets(tmp_path_factory: pytest.TempPathFactory) -> Sheets:
    """Render each (template, backend) sheet once per session."""
    workdir = tmp_path_factory.mktemp("visual-fresh")

    @cache
    def _render(template_id: str, backend: Backend) -> tuple[Image.Image, dict[str, Box]]:
        card = build_card(template_id)
        return render_sheet(card, backend, workdir), panel_crop_boxes(card)

    return _render


@pytest.mark.parametrize("panel", PANELS)
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("template_id", shipped_template_ids())
def test_panel_matches_baseline(
    template_id: str, backend: Backend, panel: str, fresh_sheets: Sheets, tmp_path: Path
) -> None:
    _require_png_layout(backend)
    fresh, boxes = fresh_sheets(template_id, backend)
    out = _artifact_dir(tmp_path)
    path = baseline_path(backend, template_id)

    if not path.exists():
        fresh_path = out / "fresh" / backend / f"{template_id}.png"
        fresh_path.parent.mkdir(parents=True, exist_ok=True)
        fresh.save(fresh_path)
        pytest.fail(
            f"No {backend} baseline for {template_id} at {path}. "
            f"Fresh sheet written to {fresh_path}. {_REGEN_HINT}"
        )

    baseline = load_sheet(path)
    assert baseline.size == fresh.size, (
        f"{path} is {baseline.size}, fresh render is {fresh.size}. {_REGEN_HINT}"
    )
    box = boxes[panel]
    fresh_crop, base_crop = fresh.crop(box), baseline.crop(box)
    ratio = mismatch_ratio(fresh_crop, base_crop)

    if ratio > MAX_PANEL_RATIO:
        stem = out / "diff" / backend / f"{template_id}-{panel}"
        stem.parent.mkdir(parents=True, exist_ok=True)
        fresh_sheet = out / "fresh" / backend / f"{template_id}.png"
        fresh_sheet.parent.mkdir(parents=True, exist_ok=True)
        fresh.save(fresh_sheet)
        paths = {
            "fresh": Path(f"{stem}-fresh.png"),
            "baseline": Path(f"{stem}-baseline.png"),
            "diff": Path(f"{stem}-diff.png"),
        }
        fresh_crop.save(paths["fresh"])
        base_crop.save(paths["baseline"])
        diff_heatmap(fresh_crop, base_crop).save(paths["diff"])
        listing = "\n".join(f"  {k}: {v}" for k, v in paths.items())
        pytest.fail(
            f"{template_id} {backend} {panel}: {ratio:.3%} of pixels differ "
            f"(limit {MAX_PANEL_RATIO:.2%}).\n{listing}\n  fresh sheet: {fresh_sheet}\n"
            f"If the change is intentional: {_REGEN_HINT}"
        )


def test_every_shipped_template_has_a_baseline_per_backend() -> None:
    """A new template without baselines, or an orphan baseline, is loud."""
    shipped = set(shipped_template_ids())
    for backend in BACKENDS:
        baselined = {p.stem for p in (BASELINE_DIR / backend).glob("*.png")}
        missing = shipped - baselined
        assert not missing, f"no {backend} baseline for {sorted(missing)}. {_REGEN_HINT}"
        orphaned = baselined - shipped
        assert not orphaned, (
            f"{backend} baselines {sorted(orphaned)} match no shipped template; "
            f"delete them from {BASELINE_DIR / backend}."
        )


def test_no_stray_files_outside_the_backend_dirs() -> None:
    """The old 72 DPI whole-sheet PNGs lived at the root; nothing may remain there."""
    stray = sorted(p.name for p in BASELINE_DIR.iterdir() if p.name not in BACKENDS)
    assert not stray, f"unexpected files in {BASELINE_DIR}: {stray}"
