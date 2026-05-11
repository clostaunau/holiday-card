"""First-class structured letter content for the inside panel.

A greeting card's inside isn't a blob of text — it's a small,
conventional composition with named parts. The panel review's
copywriter critique (``docs/industry-review/critiques/general-copywriter.md``)
called this out as the data-layer gap that turns every shipped
template into a Post-it: the schema only carries ``content: str``,
which can't even hold ``Dear Mom,\\n\\nLove,\\nC`` with proper
spacing between salutation, body, signoff, and signature.

This module defines :class:`LetterContent`, a frozen Pydantic
model that carries the five conventional parts:

* **salutation** — ``Dear Aunt Margaret,`` / ``Hey kiddo,`` / ``For Sarah,``
* **body** — the prose (paragraph breaks via blank lines, hard line
  breaks via ``\\n``)
* **signoff** — ``Love,`` / ``Always,`` / ``— C``
* **signature** — the writer's name; rendered in an optionally
  different (often handwritten-feel) font via
  ``signature_font_family``
* **postscript** — ``PS — we got a new dog!`` rendered at 85%
  size, conventionally the most-read line on a card

All five are optional. An entirely empty ``LetterContent`` is legal
(used by templates that want to declare the field but defer to a
``--blank-inside`` rendering). The compiler's
``_compile_letter_content`` lays out whichever parts are present
top-to-bottom with conventional spacing.

``LetterContent`` is mutually exclusive with ``RichTextContent`` on
the same :class:`TextElement`. The two represent different authoring
surfaces: rich text is "a Christmas letter as a Markdown blob,"
letter content is "a structured five-part card." A future merge
could let body carry rich text, but v1 keeps them separate to
constrain combinatorial layout cases.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["LetterContent"]


class LetterContent(BaseModel):
    """Structured inside-panel letter with five named parts.

    All fields default to empty strings — an empty ``LetterContent``
    is legal (renders nothing). At least one non-empty part is the
    common case but not enforced; a blank instance is a useful
    placeholder for templates that want a "render whatever the CLI
    flags supply" slot.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    salutation: str = Field(default="", max_length=200, description="e.g. 'Dear Aunt Margaret,'")
    body: str = Field(
        default="",
        max_length=2000,
        description=(
            "The letter's prose. Newlines split into hard line breaks; "
            "blank lines split into paragraphs."
        ),
    )
    signoff: str = Field(default="", max_length=100, description="e.g. 'Love,' or '— C'")
    signature: str = Field(default="", max_length=100, description="Writer's name")
    postscript: str = Field(
        default="",
        max_length=400,
        description="P.S. line; rendered smaller and below the signature",
    )
    signature_font_family: str | None = Field(
        default=None,
        description=(
            "Optional font_family override for the signature line. "
            "Defaults to None (= use the surrounding TextElement's "
            "font_family). Common pick: 'Caveat' (a curated "
            "handwritten font shipped in fonts/curated/)."
        ),
    )

    @field_validator(
        "salutation", "body", "signoff", "signature", "postscript",
        mode="before",
    )
    @classmethod
    def _strip_string(cls, value: Any) -> Any:
        # Trim whitespace on each text part at construction time.
        # Whitespace-only inputs collapse to empty strings so
        # ``is_empty()`` and the compiler's skip-empty logic agree
        # with the user's intent. Frozen-model construction goes
        # through validators *before* the instance is built, so this
        # is the right hook (model_validator(mode="after") can't
        # mutate a frozen model in place).
        if isinstance(value, str):
            return value.strip()
        return value

    def is_empty(self) -> bool:
        """True when every part is the empty string.

        Useful for the generator to decide whether to apply this
        letter at all (an entirely empty letter is functionally a
        no-op and shouldn't trigger the rich-content / letter
        dispatch).
        """
        return not any(
            (self.salutation, self.body, self.signoff, self.signature, self.postscript)
        )
