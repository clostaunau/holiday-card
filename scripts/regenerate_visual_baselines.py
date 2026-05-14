"""Regenerate visual-regression baseline PNGs.

The visual regression suite in ``tests/visual/test_visual_regression.py``
compares freshly-rendered cards against committed PNG baselines using
perceptual hashing (``imagehash``). When the rendering pipeline changes
in a way that is *intentionally* visible (a new font, a fixed bleed
bug, an updated theme), the baselines need to be regenerated and
re-committed.

This script:

* Discovers every shipped template via ``discover_templates()``.
* Renders each to ``tests/visual/fixtures/reference_cards/{template_id}.png``
  at the same DPI the regression test uses (72; matches the PNG
  backend integration tests and keeps committed artifacts small).
* ``chdir``-s into the test fixtures directory while compiling so
  photo-card templates can resolve their relative
  ``sample_photo.jpg`` path. Same pattern as
  ``scripts/build_microsite.py``.

Run from the repo root:

    python scripts/regenerate_visual_baselines.py

Inspect the resulting ``tests/visual/fixtures/reference_cards/*.png``
in a PR review before committing — that is the human gate.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

# Make ``holiday_card`` importable when running this script directly
# from a checkout (no install required).
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from holiday_card.core.compiler import compile_card  # noqa: E402
from holiday_card.core.generators import CardGenerator  # noqa: E402
from holiday_card.core.templates import discover_templates  # noqa: E402
from holiday_card.renderers.png_backend import PNGRenderer  # noqa: E402

BASELINE_DPI = 72
BASELINE_DIR = _REPO / "tests" / "visual" / "fixtures" / "reference_cards"
FIXTURES_DIR = _REPO / "tests" / "fixtures"


def regenerate_one(template_id: str) -> Path:
    """Render ``template_id`` and write its baseline PNG. Returns the path."""
    out_path = BASELINE_DIR / f"{template_id}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    generator = CardGenerator(renderer=PNGRenderer(dpi=BASELINE_DPI))
    with contextlib.chdir(FIXTURES_DIR):
        card = generator.create_card(template_id=template_id)
        commands = compile_card(card)
    generator.renderer.render(commands, out_path)
    return out_path


def main() -> int:
    templates = sorted(discover_templates(), key=lambda t: t["id"])
    if not templates:
        print("No templates discovered; baseline generation aborted.", file=sys.stderr)
        return 1

    for entry in templates:
        path = regenerate_one(entry["id"])
        size_kb = path.stat().st_size / 1024
        print(f"  {entry['id']:<35} → {path.relative_to(_REPO)} ({size_kb:.1f} KB)")

    print(f"\nRegenerated {len(templates)} baseline(s) in {BASELINE_DIR.relative_to(_REPO)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
