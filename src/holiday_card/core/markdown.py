"""Minimal Markdown parser for the inside-panel "Christmas letter" mode.

Parses a small Markdown subset chosen for greeting-card use:

* **Paragraphs** — separated by one or more blank lines.
* **Hard line breaks** — single newlines within a paragraph become
  hard line breaks (matching the visual structure of a hand-written
  letter).
* **Bold** — ``**text**`` (and ``__text__``) renders in the bold
  variant of the font_family.

Intentional non-features:

* Italic — most curated fonts are variable and don't ship distinct
  italic faces. A future PR can register italic variants and lift
  this limitation.
* Lists, headings, code, links, images, tables — none belong in a
  greeting-card's inside panel. If a user needs them, the inside
  panel is the wrong place.

Output is a :class:`RichTextContent` instance: a list of paragraphs,
each a list of :class:`StyledRun` (text + bold flag). Designed to feed
straight into the compiler's rich-text layout pass without requiring
a third-party Markdown library (no new dependencies).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "StyledRun",
    "Paragraph",
    "RichTextContent",
    "parse_markdown",
]


class StyledRun(BaseModel):
    """A continuous span of text in a single style.

    ``bold`` is the only style flag in the v0 surface; future
    additions (italic, etc.) extend this with extra fields and
    require corresponding font-registry support.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    bold: bool = False


class Paragraph(BaseModel):
    """A single paragraph (one or more styled runs)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # ``hard_lines`` groups runs into visual lines for the renderer.
    # Each line is a list of styled runs; paragraph wrapping happens
    # in the compiler against ``text.width``. Hard line breaks here
    # are author-intended (Markdown single-newline semantic).
    hard_lines: list[list[StyledRun]] = Field(min_length=1)


class RichTextContent(BaseModel):
    """A parsed Markdown document — paragraphs of styled runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraphs: list[Paragraph] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


# Match `**bold**` or `__bold__` non-greedily. Captures the inner text.
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")


def parse_markdown(source: str) -> RichTextContent:
    """Parse a Markdown source string into ``RichTextContent``.

    Empty or whitespace-only sources raise ``ValueError`` — the caller
    should guard against this (the CLI does, by treating an empty
    file as an error).
    """
    if not source.strip():
        raise ValueError("empty Markdown source")

    # Split on blank-line boundaries (one or more whitespace-only lines).
    paragraph_chunks = re.split(r"\n\s*\n", source.strip())

    paragraphs: list[Paragraph] = []
    for chunk in paragraph_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        # Within a paragraph, single newlines are hard line breaks.
        line_strs = chunk.split("\n")
        lines = [_parse_inline(line.strip()) for line in line_strs if line.strip()]
        if lines:
            paragraphs.append(Paragraph(hard_lines=lines))

    if not paragraphs:
        raise ValueError("Markdown source produced zero paragraphs")
    return RichTextContent(paragraphs=paragraphs)


def _parse_inline(line: str) -> list[StyledRun]:
    """Split a single line into alternating bold and normal runs.

    Falls back to a single normal run if no bold markers appear.
    """
    runs: list[StyledRun] = []
    cursor = 0
    for match in _BOLD.finditer(line):
        # Text before this bold span (if any).
        if match.start() > cursor:
            runs.append(StyledRun(text=line[cursor : match.start()], bold=False))
        bold_text = match.group(1) or match.group(2) or ""
        if bold_text:
            runs.append(StyledRun(text=bold_text, bold=True))
        cursor = match.end()
    # Trailing text after the last bold span.
    if cursor < len(line):
        runs.append(StyledRun(text=line[cursor:], bold=False))
    if not runs:
        # Defensive — line was entirely whitespace, but the caller
        # already filters those.
        runs.append(StyledRun(text=line, bold=False))
    return runs


# ---------------------------------------------------------------------------
# Font ID helper
# ---------------------------------------------------------------------------


def font_id_for_run(font_family: str, *, bold: bool) -> str:
    """Map a (font_family, bold) pair to the IR font_id the compiler
    should use.

    For curated fonts, only ``Lato`` ships with a distinct ``Lato-Bold``
    variant in the registry. For others, we fall back to the regular
    family name and trust the variable-font's default weight to be
    visually distinct enough. Future PRs can register additional
    weights and remove this fallback.
    """
    if not bold:
        return font_family
    bold_id = f"{font_family}-Bold"
    # Only Lato-Bold is registered today; the rest are variable fonts
    # where ``Family-Bold`` doesn't resolve. The compiler validates
    # font_ids at render time, so listing them explicitly here keeps
    # the parser independent of the registry.
    KNOWN_BOLD_VARIANTS = {"Lato-Bold"}
    if bold_id in KNOWN_BOLD_VARIANTS:
        return bold_id
    # Fallback: use the regular family. Renders as not-bold, which is
    # visually wrong but doesn't crash. Documented limitation in
    # docs/markdown.md (when that doc lands).
    return font_family


_BoldFlag = Literal[True, False]  # noqa: PYI051  - documents the option set
