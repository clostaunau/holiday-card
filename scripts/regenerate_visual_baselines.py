"""Regenerate the per-panel visual gate's full-sheet baselines (#68).

Renders each shipped template through the PNG and/or PDF backend exactly as
``tests/visual/test_visual_regression.py`` does (shared code in
``tests/visual/visual_gate.py``) and writes
``tests/visual/fixtures/reference_cards/{png,pdf}/{template_id}.png``.
For every file it prints each panel's mismatched-pixel ratio against the
old baseline, marking panels over the gate's limit with ``*``, so the
reviewer knows which PNGs to eyeball.

PNG baselines need Pillow's raqm text layout (libfribidi on the host); the
script refuses PNG without it. Committed baselines are generated on **Ubuntu CI** by the
``visual-baselines`` workflow, not on a laptop. Run locally only to see
what changed:

    python scripts/regenerate_visual_baselines.py [--backend {png,pdf,all}] [--template ID ...]

Eyeball every regenerated PNG before committing: automated regeneration
captures rendering bugs as the new truth.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image

_REPO = Path(__file__).resolve().parent.parent
# ``holiday_card`` from the checkout; the gate helpers from the test tree.
sys.path[:0] = [str(_REPO / "src"), str(_REPO / "tests"), str(_REPO / "tests" / "visual")]

from visual_gate import (  # noqa: E402
    BACKENDS,
    MAX_PANEL_RATIO,
    Backend,
    baseline_path,
    build_card,
    load_sheet,
    panel_crop_boxes,
    panel_ratios,
    png_layout_matches_baselines,
    render_sheet,
    shipped_template_ids,
)


def _describe_change(old: Path, boxes: dict[str, tuple[int, int, int, int]], new: Image.Image) -> str:
    if not old.exists():
        return "new"
    before = load_sheet(old)
    if before.size != new.size:
        return f"size {before.size} -> {new.size}"
    ratios = panel_ratios(new, before, boxes)
    return "  ".join(
        f"{name}={ratio:.3%}{'*' if ratio > MAX_PANEL_RATIO else ''}" for name, ratio in ratios.items()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", choices=[*BACKENDS, "all"], default="all")
    parser.add_argument(
        "--template",
        action="append",
        metavar="ID",
        help="regenerate only this template (repeatable; default: every shipped template)",
    )
    args = parser.parse_args(argv)

    shipped = shipped_template_ids()
    if not shipped:
        print("No templates discovered; baseline generation aborted.", file=sys.stderr)
        return 1
    template_ids = args.template or shipped
    unknown = sorted(set(template_ids) - set(shipped))
    if unknown:
        print(f"Unknown template id(s): {unknown}", file=sys.stderr)
        return 2
    backends: tuple[Backend, ...] = BACKENDS if args.backend == "all" else (args.backend,)
    if "png" in backends and not png_layout_matches_baselines():
        print(
            "Refusing to write PNG baselines: Pillow has no raqm text layout on this host "
            "(install libfribidi). The committed PNG baselines are raqm renders from "
            "ubuntu-latest; use the visual-baselines workflow.",
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        for backend in backends:
            for template_id in template_ids:
                card = build_card(template_id)
                sheet = render_sheet(card, backend, Path(tmp))
                path = baseline_path(backend, template_id)
                change = _describe_change(path, panel_crop_boxes(card), sheet)
                path.parent.mkdir(parents=True, exist_ok=True)
                sheet.save(path, optimize=True)
                print(f"  {backend}  {template_id:<32} {change}")

    print(
        f"\nRegenerated {len(template_ids) * len(backends)} baseline(s). "
        f"'*' marks panels over the {MAX_PANEL_RATIO:.2%} gate. Eyeball every PNG before committing."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
