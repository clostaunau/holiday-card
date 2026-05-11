"""Render PNG previews for templates affected by a set of changed files.

Used by the ``.github/workflows/render-cards.yml`` GitHub Action — the
"cards-as-code" identity move from Leapfrog 4. The action gives this
script the list of files that changed in a PR, and we render PNG
previews of every template the change might have visually affected.

Inputs (CLI):

* ``--changed-files PATH`` — path to a file containing one changed
  file path per line (typically the output of ``git diff --name-only``).
  ``-`` reads from stdin.
* ``--output-dir PATH`` — where the PNGs land. Created if missing.
* ``--dpi N`` — render resolution, default 144.

Output:

* One ``{template_id}.png`` per affected template, in ``--output-dir``.
* A summary on stdout: one ``{template_id}\\t{png_path}`` line per
  rendered template. Used by the workflow to build the PR comment.

"Affected" rules (kept simple — a noisier rule would re-render the
whole shipping set on every typo PR):

* Direct: any ``templates/**/*.yaml`` in the changed list → render
  exactly that template.
* Indirect: any change to ``src/``, ``fonts/``, ``sentiments/``, or
  ``themes/`` → render the canonical shipping set (the same eight
  templates the snapshot tests cover).
* Pure test / docs / CI changes → render nothing (exits 0 with no
  output; the workflow will skip the PR comment).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The canonical shipping set the snapshot tests + smoke job cover.
# Keep this list in sync with tests/unit/test_compiler.py's
# SUPPORTED_SNAPSHOT_TEMPLATES and .github/workflows/ci.yml's smoke job.
SHIPPING_TEMPLATES: tuple[str, ...] = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "birthday-balloons",
    "hanukkah-menorah",
    "generic-celebration",
    "mothers-day",
)

# Top-level directories whose changes invalidate every template.
# A change to any file under one of these prefixes triggers a full
# re-render of the shipping set.
_INDIRECT_PREFIXES: tuple[str, ...] = (
    "src/",
    "fonts/",
    "sentiments/",
    "themes/",
)


def detect_affected_templates(changed_files: list[str]) -> list[str]:
    """Return the list of template ids that should be re-rendered.

    Empty list means "nothing rendering-relevant changed; skip."
    """
    direct: list[str] = []
    indirect_triggered = False

    for raw in changed_files:
        path = raw.strip()
        if not path:
            continue
        # Direct template change → resolve the template id from the
        # path. templates/{occasion}/{stem}.yaml → "{occasion}-{stem}"
        # for everything except mothers_day where the convention is
        # the directory name (see core/templates.py discovery logic).
        if path.startswith("templates/") and path.endswith(".yaml"):
            tid = _template_id_from_path(path)
            if tid is not None and tid not in direct:
                direct.append(tid)
            continue
        # Indirect: any change in core dirs invalidates everything.
        if any(path.startswith(prefix) for prefix in _INDIRECT_PREFIXES):
            indirect_triggered = True

    if indirect_triggered:
        # Union direct + the full shipping set, preserving order:
        # explicitly-touched templates first, then the rest.
        merged = list(direct)
        for tid in SHIPPING_TEMPLATES:
            if tid not in merged:
                merged.append(tid)
        return merged
    return direct


def _template_id_from_path(path: str) -> str | None:
    """Convert ``templates/{occasion}/{stem}.yaml`` → template id.

    Mirrors the discovery logic in ``core/templates.py``: id is the
    file's ``id:`` field. We can't read the file without parsing
    YAML, but the convention across the shipped templates is
    ``{occasion}-{stem}`` (with hyphens), so derive that and let the
    rendering step surface mismatches.
    """
    p = Path(path)
    parts = p.parts
    if len(parts) < 3 or parts[0] != "templates":
        return None
    occasion = parts[1]
    stem = p.stem
    # Special case mirroring discover_templates output: mothers_day's
    # "classic.yaml" file ships with id "mothers-day", not
    # "mothers_day-classic". Other templates follow {occasion}-{stem}.
    if occasion == "mothers_day" and stem == "classic":
        return "mothers-day"
    return f"{occasion}-{stem}"


def render_one(template_id: str, output_dir: Path, dpi: int = 144) -> Path:
    """Render one template to PNG; return the output path.

    Uses the same compiler pipeline the CLI's ``preview`` command does.
    The PNG carries no message override — readers see the template's
    default content.
    """
    from holiday_card.core.compiler import compile_card
    from holiday_card.core.generators import CardGenerator
    from holiday_card.renderers.png_backend import PNGRenderer

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{template_id}.png"
    card = CardGenerator().create_card(template_id=template_id)
    cmds = compile_card(card)
    PNGRenderer(dpi=dpi).render(cmds, out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changed-files",
        required=True,
        help="Path to a newline-delimited file of changed paths. '-' for stdin.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("card-previews"),
        help="Where the PNG previews land. Default: ./card-previews/",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=144,
        help="Render resolution. Default: 144 DPI.",
    )
    args = parser.parse_args(argv)

    raw = (
        sys.stdin.read()
        if args.changed_files == "-"
        else Path(args.changed_files).read_text()
    )
    changed = [line for line in raw.splitlines() if line.strip()]

    affected = detect_affected_templates(changed)
    if not affected:
        print("No rendering-relevant changes detected; nothing to render.", file=sys.stderr)
        return 0

    print(f"Rendering {len(affected)} template(s)...", file=sys.stderr)
    rendered: list[tuple[str, Path]] = []
    failures: list[tuple[str, str]] = []
    for tid in affected:
        try:
            path = render_one(tid, args.output_dir, dpi=args.dpi)
            rendered.append((tid, path))
            print(f"  ✓ {tid} → {path}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — best-effort batch render
            print(f"  ✗ {tid}: {e}", file=sys.stderr)
            failures.append((tid, str(e)))

    # Tab-separated stdout for the workflow to parse:
    # ``{template_id}\t{png_path}``
    for tid, path in rendered:
        print(f"{tid}\t{path}")

    # Exit non-zero only if EVERY render failed (so a one-off bad
    # template doesn't block the whole workflow).
    return 1 if rendered == [] and failures else 0


if __name__ == "__main__":
    sys.exit(main())
