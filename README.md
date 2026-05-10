# holiday-card

A Python CLI for creating printable greeting cards on standard letter
paper. Renders the same card design to **PDF, SVG, or PNG** from a
single YAML template.

## Install

```bash
pip install -e ".[dev]"
holiday-card --help
```

## Quick start

```bash
# List shipped templates
holiday-card templates

# Make a card (PDF)
holiday-card create christmas-classic \
  -m "Merry Christmas!" \
  --inside-message "Wishing you joy this season." \
  -o my-card.pdf

# Same card as SVG (opens in any browser)
holiday-card create christmas-classic --format svg -o my-card.svg

# Fast preview that opens in your image viewer
holiday-card preview christmas-classic
```

## Output formats

| Format | Use case | Command |
|---|---|---|
| **PDF** (default) | Print-ready output for color laser | `holiday-card create <id>` |
| **SVG** | Browser-openable, scalable, embeddable | `holiday-card create <id> --format svg` |
| **PNG** | Fast preview, no PDF reader needed | `holiday-card preview <id>` |

All three are produced by the same compiler from the same Pydantic
template — see [CLAUDE.md](CLAUDE.md#architecture) for the IR-based
pipeline.

## Setup details

See [SETUP_AND_RUN.md](SETUP_AND_RUN.md) for venv setup, custom fonts,
adding photos, and other recipes.

## Hacking on it

```bash
pip install -e ".[dev]"
pytest                         # 324 tests, runs in ~3s
ruff check src/ tests/         # lint
mypy src/                      # type-check (strict mode, zero errors)
```

CI runs lint + mypy + the full test matrix on Ubuntu and macOS across
Python 3.11/3.12/3.13, plus a smoke job that builds and renders one
template per occasion. All gates are blocking.

For architecture, dev workflow, current-state details, and known
issues, read [CLAUDE.md](CLAUDE.md).

## License

MIT (see [pyproject.toml](pyproject.toml)).
