"""Minimal Markdown parser for the inside-panel "Christmas letter" mode.

Parses a small Markdown subset chosen for greeting-card use:

* **Paragraphs** — separated by one or more blank lines.
* **Hard line breaks** — single newlines within a paragraph become
  hard line breaks (matching the visual structure of a hand-written
  letter).
* **Bold** — ``**text**`` (and ``__text__``) renders in the bold
  variant of the font_family.
* **Italic** — ``*text*`` (and ``_text_``) renders in the italic
  variant of the font_family. Combined: ``***text***`` and
  ``___text___`` render as bold-italic.

Intentional non-features:

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
    """A continuous span of text in a single style."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    bold: bool = False
    italic: bool = False


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


# Markdown marker priority: triple-marker (bold+italic) wins over
# double (bold) wins over single (italic). All three regexes are
# evaluated; the one that matches earliest in the input wins, and its
# captured content is recursively re-parsed for any *higher-marker*
# styles it still permits (e.g. italic inside bold).
_TRIPLE_BOLD_ITALIC = re.compile(r"\*\*\*(.+?)\*\*\*|___(.+?)___")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
# Italic forbids the same marker char inside (no nesting same-marker
# spans) and forbids newlines (no spanning paragraphs).
_ITALIC = re.compile(r"\*([^*\n]+?)\*|_([^_\n]+?)_")


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
    """Split a single line into styled runs.

    Recursive descent over marker priority (triple > double > single).
    At each position the earliest matching marker wins; the captured
    content is recursively re-parsed with the discovered style turned
    on, enabling italic-inside-bold (``**a *b* c**``) and the
    triple-marker bold-italic shortcut (``***x***``).
    """
    runs: list[StyledRun] = []
    _walk(line, bold=False, italic=False, runs=runs)
    if not runs:
        runs.append(StyledRun(text=line, bold=False, italic=False))
    return runs


def _walk(
    text: str, *, bold: bool, italic: bool, runs: list[StyledRun]
) -> None:
    if not text:
        return
    if bold and italic:
        runs.append(StyledRun(text=text, bold=True, italic=True))
        return

    candidates: list[tuple[re.Pattern[str], bool, bool]] = []
    if not bold and not italic:
        candidates.append((_TRIPLE_BOLD_ITALIC, True, True))
    if not bold:
        candidates.append((_BOLD, True, False))
    if not italic:
        candidates.append((_ITALIC, False, True))

    best: tuple[re.Match[str], bool, bool] | None = None
    for pattern, set_bold, set_italic in candidates:
        match = pattern.search(text)
        if match is None:
            continue
        if best is None or match.start() < best[0].start():
            best = (match, set_bold, set_italic)

    if best is None:
        runs.append(StyledRun(text=text, bold=bold, italic=italic))
        return

    match, set_bold, set_italic = best
    if match.start() > 0:
        runs.append(StyledRun(
            text=text[: match.start()], bold=bold, italic=italic,
        ))
    inner = match.group(1) or match.group(2) or ""
    if inner:
        _walk(
            inner,
            bold=bold or set_bold,
            italic=italic or set_italic,
            runs=runs,
        )
    _walk(text[match.end():], bold=bold, italic=italic, runs=runs)


# ---------------------------------------------------------------------------
# Font ID helper
# ---------------------------------------------------------------------------


def font_id_for_run(
    font_family: str, *, bold: bool = False, italic: bool = False
) -> str:
    """Map a (font_family, bold, italic) triple to the IR font_id the
    compiler should use.

    Resolution order for (bold, italic):

    * Both flags off → ``font_family`` verbatim.
    * Bold-italic requested → try the BoldItalic variant; degrade to
      Bold, then Italic, then regular.
    * Bold only → try the Bold variant; degrade to regular.
    * Italic only → try the Italic variant; degrade to regular.

    The known-variant sets are explicit (not derived from the font
    registry) so this module stays independent of ReportLab. Curated
    fonts ship Regular only today — italic and bold spans on those
    fonts render as Regular. Documented limitation; lifts when italic
    TTFs are added to ``fonts/curated/``.
    """
    if not bold and not italic:
        return font_family

    if bold and italic:
        bi_id = _BOLD_ITALIC_VARIANT.get(font_family, f"{font_family}-BoldItalic")
        if bi_id in _KNOWN_BOLD_ITALIC_VARIANTS:
            return bi_id
        bold_id = f"{font_family}-Bold"
        if bold_id in _KNOWN_BOLD_VARIANTS:
            return bold_id
        italic_id = _ITALIC_VARIANT.get(font_family, f"{font_family}-Italic")
        if italic_id in _KNOWN_ITALIC_VARIANTS:
            return italic_id
        return font_family

    if bold:
        bold_id = f"{font_family}-Bold"
        if bold_id in _KNOWN_BOLD_VARIANTS:
            return bold_id
        return font_family

    # italic only
    italic_id = _ITALIC_VARIANT.get(font_family, f"{font_family}-Italic")
    if italic_id in _KNOWN_ITALIC_VARIANTS:
        return italic_id
    return font_family


# PDF base-14 conventions use "Oblique" for sans/mono and "Italic"
# for serif. The italic variant id can't be mechanically generated
# from the family name; table-driven.
_ITALIC_VARIANT: dict[str, str] = {
    "Helvetica":   "Helvetica-Oblique",
    "Times-Roman": "Times-Italic",
    "Courier":     "Courier-Oblique",
}
_BOLD_ITALIC_VARIANT: dict[str, str] = {
    "Helvetica":   "Helvetica-BoldOblique",
    "Times-Roman": "Times-BoldItalic",
    "Courier":     "Courier-BoldOblique",
}

# Variants known to be registered in renderers/font_registry.py.
_KNOWN_BOLD_VARIANTS = frozenset({
    "Helvetica-Bold", "Times-Bold", "Courier-Bold",
    "Lato-Bold",
})
_KNOWN_ITALIC_VARIANTS = frozenset({
    "Helvetica-Oblique", "Times-Italic", "Courier-Oblique",
})
_KNOWN_BOLD_ITALIC_VARIANTS = frozenset({
    "Helvetica-BoldOblique", "Times-BoldItalic", "Courier-BoldOblique",
})


_BoldFlag = Literal[True, False]  # noqa: PYI051  - documents the option set
