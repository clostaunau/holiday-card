"""Build the static template-gallery microsite.

Generates a small static site that gives Sandy-the-DIY-crafter an
escape hatch into the project without abandoning the cards-as-code
thesis: every template gets a thumbnail and a page with form fields
that build the right ``holiday-card create ...`` command for
copy-paste into a terminal.

Outputs:

* ``site/index.html`` — gallery, one card per template
* ``site/templates/{template_id}.html`` — per-template page with
  preview, form, and a copy-command button
* ``site/thumbs/{template_id}.png`` — rendered thumbnail (front
  panel only, at 144 DPI)
* ``site/style.css`` — shared styles

The page JS is vanilla. No build step, no transpilation, no
third-party libraries — the whole site is just files. Deployable
to GitHub Pages via the workflow in ``.github/workflows/microsite.yml``.

Usage::

    python scripts/build_microsite.py --output site

Or run from CI; the workflow passes ``--output _site`` to match
``actions/upload-pages-artifact``'s default path.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Add the project's src/ to sys.path when run as a script.
_THIS = Path(__file__).resolve()
_REPO = _THIS.parent.parent
sys.path.insert(0, str(_REPO / "src"))

from holiday_card.core.compiler import compile_card  # noqa: E402
from holiday_card.core.generators import CardGenerator  # noqa: E402
from holiday_card.core.templates import (  # noqa: E402
    discover_templates,
    load_template,
)
from holiday_card.renderers.png_backend import PNGRenderer  # noqa: E402


@dataclass(frozen=True)
class TemplateCard:
    """The microsite-shaped view of one template — what the HTML needs."""

    id: str
    name: str
    occasion: str
    fold_type: str
    description: str
    thumbnail_path: str  # relative to site root, e.g. "thumbs/christmas-classic.png"


_OCCASION_LABELS = {
    "christmas": "Christmas",
    "birthday": "Birthday",
    "hanukkah": "Hanukkah",
    "mothers_day": "Mother's Day",
    "generic": "Generic",
}

# Voice options surfaced in the form. Matches the CLI's VOICES set.
_VOICES = ("warm", "witty", "spare", "devotional", "irreverent")


def build(output_dir: Path, dpi: int = 144) -> list[TemplateCard]:
    """Build the microsite into ``output_dir``.

    Returns the list of ``TemplateCard``s that were rendered, in
    occasion-then-name order (the same order the gallery uses).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "templates").mkdir(parents=True, exist_ok=True)
    (output_dir / "thumbs").mkdir(parents=True, exist_ok=True)

    cards: list[TemplateCard] = []
    discovered = sorted(discover_templates(), key=lambda d: d["id"])
    for entry in discovered:
        template_id = entry["id"]
        try:
            tmpl = load_template(template_id)
        except Exception as e:  # pragma: no cover — defensive
            print(f"skip {template_id!r}: load failed ({e})", file=sys.stderr)
            continue
        thumb_rel = f"thumbs/{template_id}.png"
        try:
            _render_thumbnail(template_id, output_dir / thumb_rel, dpi)
        except Exception as e:
            print(
                f"skip {template_id!r}: thumbnail render failed ({e})",
                file=sys.stderr,
            )
            continue
        cards.append(TemplateCard(
            id=template_id,
            name=tmpl.name,
            occasion=tmpl.occasion.value,
            fold_type=tmpl.fold_type.value,
            description=tmpl.description or "",
            thumbnail_path=thumb_rel,
        ))

    (output_dir / "style.css").write_text(_STYLESHEET)
    (output_dir / "index.html").write_text(_render_index(cards))
    for card in cards:
        page_html = _render_template_page(card)
        (output_dir / "templates" / f"{card.id}.html").write_text(page_html)
    return cards


def _render_thumbnail(template_id: str, out_path: Path, dpi: int) -> None:
    """Render the template's full sheet as a PNG thumbnail.

    Uses the default letter export target so the thumbnail shows the
    whole half-fold imposition. Sandy will recognise this as the
    "printable" view; using just the front panel would lose context
    (where's the inside message? the back? — visible structure that
    distinguishes templates).

    Photo-card templates reference ``sample_photo.jpg`` as a relative
    path; the compiler resolves it against CWD. We ``chdir`` to the
    test-fixtures directory so the bundled sample image is in scope
    for thumbnail rendering. This keeps the placeholder sample
    visible in the gallery without coupling the build to a specific
    runtime CWD.
    """
    generator = CardGenerator(renderer=PNGRenderer(dpi=dpi))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fixtures_dir = _REPO / "tests" / "fixtures"
    with contextlib.chdir(fixtures_dir):
        card = generator.create_card(template_id=template_id)
        commands = compile_card(card)
    generator.renderer.render(commands, out_path)


def _render_index(cards: list[TemplateCard]) -> str:
    """Render the gallery index page.

    Groups templates by occasion. Each card is a thumbnail + name +
    occasion badge linking to the per-template page.
    """
    by_occasion: dict[str, list[TemplateCard]] = {}
    for card in cards:
        by_occasion.setdefault(card.occasion, []).append(card)

    section_chunks: list[str] = []
    for occasion in sorted(by_occasion):
        label = _OCCASION_LABELS.get(occasion, occasion.title())
        cards_html = "\n".join(_index_card(c) for c in by_occasion[occasion])
        section_chunks.append(f"""
    <section class="occasion">
      <h2>{html.escape(label)}</h2>
      <div class="grid">
        {cards_html}
      </div>
    </section>""")

    sections = "\n".join(section_chunks)
    return _HTML_FRAME.format(
        title="holiday-card — templates",
        head_extra="",
        style_href="style.css",
        body=f"""
  <header class="hero">
    <h1>holiday-card</h1>
    <p class="tagline">Greeting cards as code. {len(cards)} templates. Pick one.</p>
    <p class="install"><code>pipx install holiday-card</code></p>
  </header>
  <main>{sections}
  </main>
  <footer>
    <p>
      Open source · MIT · <a href="https://github.com/clostaunau/holiday-card">GitHub</a>
    </p>
  </footer>
""",
    )


def _index_card(card: TemplateCard) -> str:
    """Render one tile in the gallery."""
    label = _OCCASION_LABELS.get(card.occasion, card.occasion.title())
    return f"""
        <a class="card" href="templates/{html.escape(card.id)}.html">
          <img class="thumb" src="{html.escape(card.thumbnail_path)}" alt="{html.escape(card.name)} preview"/>
          <div class="card-body">
            <div class="card-name">{html.escape(card.name)}</div>
            <div class="card-meta">
              <span class="badge badge-{html.escape(card.occasion)}">{html.escape(label)}</span>
              <span class="card-id">{html.escape(card.id)}</span>
            </div>
          </div>
        </a>""".strip()


def _render_template_page(card: TemplateCard) -> str:
    """Render the per-template page with form + copy-command JS."""
    voices_html = "\n".join(
        f'              <option value="{v}">{v.title()}</option>'
        for v in _VOICES
    )
    metadata_json = json.dumps({
        "id": card.id,
        "name": card.name,
        "occasion": card.occasion,
        "fold_type": card.fold_type,
    })

    head_extra = ""
    body = f"""
  <header class="page-header">
    <a class="back" href="../index.html">← all templates</a>
    <h1>{html.escape(card.name)}</h1>
    <p class="card-id">{html.escape(card.id)}</p>
  </header>
  <main class="detail">
    <section class="preview">
      <img src="../{html.escape(card.thumbnail_path)}" alt="{html.escape(card.name)} preview"/>
    </section>
    <section class="composer">
      <h2>Customize</h2>
      <p class="hint">
        Fill in the fields you want. The command below updates as you type.
        Copy and paste it into a terminal where <code>holiday-card</code>
        is installed.
      </p>
      <form id="composer" autocomplete="off">
        <label>
          Greeting (front)
          <input type="text" id="f-message" placeholder="Merry Christmas!"/>
        </label>
        <label>
          Inside message
          <input type="text" id="f-inside" placeholder="Hope your holidays are bright."/>
        </label>
        <label>
          Voice (curated sentiment)
          <select id="f-voice">
            <option value="">(none)</option>
{voices_html}
          </select>
        </label>
        <fieldset>
          <legend>Optional letter parts</legend>
          <label>
            Salutation
            <input type="text" id="f-salutation" placeholder="Dear Aunt Margaret,"/>
          </label>
          <label>
            Signoff
            <input type="text" id="f-signoff" placeholder="Love,"/>
          </label>
          <label>
            Signature
            <input type="text" id="f-signature" placeholder="The Smiths"/>
          </label>
          <label>
            P.S.
            <input type="text" id="f-ps" placeholder="PS — we got a new dog!"/>
          </label>
        </fieldset>
        <fieldset>
          <legend>Output</legend>
          <label class="inline">
            <input type="checkbox" id="f-moo-a6"/>
            MOO A6 print-ready PDF (CMYK + PDF/X-1a:2003)
          </label>
        </fieldset>
      </form>
      <h2>Run this</h2>
      <pre id="command-box" class="command"></pre>
      <button id="copy-btn" type="button">Copy command</button>
      <p id="copy-feedback" class="copy-feedback" aria-live="polite"></p>
    </section>
  </main>
  <script>
    const TEMPLATE = {metadata_json};

    function shellEscape(s) {{
      if (s === '' || s === null) return '""';
      if (/^[A-Za-z0-9_.\\/=:@%+,-]+$/.test(s)) return s;
      return "'" + s.replace(/'/g, "'\\\\''") + "'";
    }}

    function buildCommand() {{
      const parts = ['holiday-card', 'create', TEMPLATE.id];
      const v = id => document.getElementById(id).value.trim();
      const chk = id => document.getElementById(id).checked;

      if (v('f-message')) parts.push('-m', shellEscape(v('f-message')));
      if (v('f-inside')) parts.push('--inside-message', shellEscape(v('f-inside')));
      if (v('f-voice')) parts.push('--voice', shellEscape(v('f-voice')));
      if (v('f-salutation')) parts.push('--salutation', shellEscape(v('f-salutation')));
      if (v('f-signoff')) parts.push('--signoff', shellEscape(v('f-signoff')));
      if (v('f-signature')) parts.push('--signature', shellEscape(v('f-signature')));
      if (v('f-ps')) parts.push('--ps', shellEscape(v('f-ps')));
      if (chk('f-moo-a6')) parts.push('--export-for', 'moo-a6', '-o', './out-' + TEMPLATE.id + '/');
      return parts.join(' ');
    }}

    function update() {{
      document.getElementById('command-box').textContent = buildCommand();
    }}

    document.querySelectorAll('#composer input, #composer select').forEach(el => {{
      el.addEventListener('input', update);
      el.addEventListener('change', update);
    }});

    document.getElementById('copy-btn').addEventListener('click', () => {{
      const cmd = buildCommand();
      navigator.clipboard.writeText(cmd).then(() => {{
        const fb = document.getElementById('copy-feedback');
        fb.textContent = 'Copied. Paste into a terminal.';
        setTimeout(() => {{ fb.textContent = ''; }}, 3000);
      }});
    }});

    update();
  </script>
  <footer>
    <p>
      <a href="../index.html">← back to gallery</a> ·
      <a href="https://github.com/clostaunau/holiday-card">source on GitHub</a>
    </p>
  </footer>
"""
    return _HTML_FRAME.format(
        title=f"{card.name} — holiday-card",
        head_extra=head_extra,
        style_href="../style.css",
        body=body,
    )


_HTML_FRAME = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{title}</title>
  <link rel="stylesheet" href="{style_href}"/>
  {head_extra}
</head>
<body>{body}
</body>
</html>
"""


# Single stylesheet shared by both pages. Conservative palette, system
# font stack, no web fonts (the project's curated TTFs ship in the
# CLI; the microsite doesn't try to recreate the print typography).
_STYLESHEET = """
:root {
  --bg: #faf8f3;
  --ink: #2a2a2a;
  --muted: #6a6660;
  --line: #d8d3c8;
  --accent: #b03030;
  --accent-bg: #fbeded;
}

* { box-sizing: border-box; }
html, body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

.hero, .page-header {
  max-width: 1100px;
  margin: 2rem auto 1rem;
  padding: 0 1.5rem;
}
.hero h1 { font-size: 2.4rem; margin: 0 0 0.25rem; }
.tagline { font-size: 1.1rem; color: var(--muted); margin: 0 0 1rem; }
.install code {
  background: var(--accent-bg);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  color: var(--accent);
}

main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1rem 1.5rem 3rem;
}

section.occasion { margin: 2rem 0; }
section.occasion h2 {
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.3rem;
  font-size: 1.4rem;
  margin: 0 0 1rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.25rem;
}

.card {
  display: block;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
  transition: transform 0.1s, box-shadow 0.1s;
  color: var(--ink);
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  text-decoration: none;
}
.thumb {
  width: 100%;
  aspect-ratio: 8.5 / 11;
  object-fit: contain;
  background: #f0eee8;
  display: block;
}
.card-body { padding: 0.75rem 1rem 1rem; }
.card-name { font-weight: 600; font-size: 1.1rem; margin-bottom: 0.25rem; }
.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--muted);
  font-size: 0.85rem;
}
.badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: #efece5;
}
.badge-christmas { background: #fbeded; color: var(--accent); }
.badge-birthday { background: #eef2ff; color: #3050a0; }
.badge-hanukkah { background: #eaf3fa; color: #205070; }
.badge-mothers_day { background: #fef0f5; color: #a04060; }
.badge-generic { background: #efece5; color: var(--muted); }

/* Per-template page */
.page-header { display: flex; flex-direction: column; gap: 0.25rem; }
.page-header h1 { margin: 0; font-size: 1.8rem; }
.back { font-size: 0.9rem; color: var(--muted); margin-bottom: 0.25rem; }
.card-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--muted);
  font-size: 0.85rem;
}

.detail {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
}
@media (min-width: 800px) {
  .detail { grid-template-columns: 1fr 1fr; }
}

.preview img {
  width: 100%;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 6px;
}

.composer h2 { font-size: 1.15rem; margin: 0 0 0.5rem; }
.composer h2:not(:first-of-type) { margin-top: 1.5rem; }
.composer .hint { color: var(--muted); margin: 0 0 1rem; font-size: 0.95rem; }

form label {
  display: block;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.75rem;
}
form label.inline {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.95rem;
  color: var(--ink);
}
form input[type=text], form select {
  display: block;
  width: 100%;
  font-size: 1rem;
  padding: 0.4rem 0.6rem;
  margin-top: 0.2rem;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: #fff;
  color: var(--ink);
  font-family: inherit;
}
form input[type=text]:focus, form select:focus {
  outline: 2px solid var(--accent);
  outline-offset: -1px;
  border-color: var(--accent);
}
form fieldset {
  border: 1px solid var(--line);
  border-radius: 4px;
  margin: 0.75rem 0;
  padding: 0.75rem 1rem 0.25rem;
}
form fieldset legend {
  padding: 0 0.5rem;
  color: var(--muted);
  font-size: 0.85rem;
}

pre.command {
  background: #1f1d1a;
  color: #f8f4ec;
  padding: 1rem;
  border-radius: 4px;
  font-size: 0.85rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

#copy-btn {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.95rem;
  background: var(--accent);
  color: #fff;
  border: 1px solid var(--accent);
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
}
#copy-btn:hover { background: #962020; }
.copy-feedback {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: var(--muted);
  min-height: 1.2em;
}

footer {
  max-width: 1100px;
  margin: 3rem auto 2rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.85rem;
  text-align: center;
}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", "-o", type=Path, default=Path("site"),
        help="Output directory (default: site/)",
    )
    parser.add_argument(
        "--dpi", type=int, default=144,
        help="Thumbnail render resolution (default: 144)",
    )
    args = parser.parse_args(argv)
    cards = build(args.output, dpi=args.dpi)
    print(f"Built microsite: {len(cards)} templates → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
