"""Visual-regression tests against committed PNG baselines.

The compiler+backend pixel-correctness tests prove that *specific*
elements render in the right place with the right color. They do not
prove that the whole composition still looks the way it did last
week. This suite closes that gap: render each shipped template fresh,
compute a perceptual hash, and Hamming-compare it against a baseline
PNG committed under ``tests/visual/fixtures/reference_cards/``.

Why perceptual hashing (``imagehash.phash``) instead of exact bytes
or scikit-image SSIM:

* **Exact bytes / pixel diff** would flake across platforms — font
  hinting differs slightly between Linux and macOS even at the same
  Pillow version. The CI matrix runs on both.
* **scikit-image SSIM** would add a ~30MB dev dependency. Overkill
  for the resolution we render at (72 DPI letter = 630×810).
* **Perceptual hashing** is already in the dev extras
  (``imagehash>=4.3``), is robust to anti-aliasing noise, and
  catches the regressions that actually matter — text moved, a
  panel disappeared, a color swapped.

To regenerate baselines after an intentional rendering change:

    python scripts/regenerate_visual_baselines.py

The diff between the old and new PNGs is part of the PR review;
that is the human gate.

Cross-platform note: baselines are committed by whoever last ran
the regenerate script. If the gate starts flaking on a specific CI
runner (Linux vs macOS font hinting can differ a few bits even
through the perceptual hash) the right fix is to regenerate the
baselines on the canonical CI runner (Ubuntu Linux), not to widen
the threshold — widening past 5 starts blurring genuinely different
templates together.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import imagehash
import pytest
from PIL import Image

from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.templates import discover_templates
from holiday_card.renderers.png_backend import PNGRenderer

BASELINE_DIR = Path(__file__).parent / "fixtures" / "reference_cards"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
BASELINE_DPI = 72

# Perceptual-hash Hamming distance threshold. 0 = identical; values
# above ~10 mean the images are visibly different. We allow up to 5
# bits of drift to accommodate platform font-rendering variation
# while still catching any layout-level change. Tighten if it turns
# out to be too loose; loosen if cross-platform flakes appear.
HASH_DISTANCE_THRESHOLD = 5


def _all_shipped_template_ids() -> list[str]:
    return sorted(t["id"] for t in discover_templates())


@pytest.mark.visual
@pytest.mark.parametrize("template_id", _all_shipped_template_ids())
def test_template_matches_baseline(template_id: str, tmp_path: Path) -> None:
    """Re-render the template and compare its perceptual hash to baseline."""
    baseline_path = BASELINE_DIR / f"{template_id}.png"
    assert baseline_path.exists(), (
        f"No baseline for {template_id}. "
        f"Run `python scripts/regenerate_visual_baselines.py` to create one."
    )

    fresh_path = tmp_path / f"{template_id}.png"
    generator = CardGenerator(renderer=PNGRenderer(dpi=BASELINE_DPI))
    with contextlib.chdir(FIXTURES_DIR):
        card = generator.create_card(template_id=template_id)
        commands = compile_card(card)
    generator.renderer.render(commands, fresh_path)

    fresh_hash = imagehash.phash(Image.open(fresh_path))
    baseline_hash = imagehash.phash(Image.open(baseline_path))
    distance = fresh_hash - baseline_hash

    assert distance <= HASH_DISTANCE_THRESHOLD, (
        f"{template_id} drifted from its baseline (Hamming distance "
        f"{distance} > threshold {HASH_DISTANCE_THRESHOLD}). "
        f"Inspect the fresh render at {fresh_path} versus the baseline "
        f"at {baseline_path}. If the change is intentional, "
        f"regenerate with `python scripts/regenerate_visual_baselines.py`."
    )


@pytest.mark.visual
def test_every_shipped_template_has_a_baseline() -> None:
    """Adding a new template without a baseline should be loud."""
    shipped = set(_all_shipped_template_ids())
    baselined = {p.stem for p in BASELINE_DIR.glob("*.png")}

    missing = shipped - baselined
    assert not missing, (
        f"Templates {sorted(missing)} have no visual-regression baseline. "
        f"Run `python scripts/regenerate_visual_baselines.py` and commit "
        f"the new PNGs."
    )

    orphaned = baselined - shipped
    assert not orphaned, (
        f"Baseline PNGs {sorted(orphaned)} have no matching shipped "
        f"template. Was a template renamed or deleted? Remove the orphan "
        f"baselines from {BASELINE_DIR}."
    )
