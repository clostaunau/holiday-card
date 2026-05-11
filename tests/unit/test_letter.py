"""Unit tests for ``LetterContent`` and its TextElement integration.

Covers:

* schema-level construction, defaults, and validation
* whitespace stripping
* ``is_empty()`` semantics
* mutual exclusivity with ``RichTextContent`` on ``TextElement``
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from holiday_card.core.letter import LetterContent
from holiday_card.core.markdown import (
    Paragraph,
    RichTextContent,
    StyledRun,
)
from holiday_card.core.models import TextElement


class TestLetterContentDefaults:
    """An empty LetterContent is legal and ``is_empty``."""

    def test_default_is_all_empty(self) -> None:
        letter = LetterContent()
        assert letter.salutation == ""
        assert letter.body == ""
        assert letter.signoff == ""
        assert letter.signature == ""
        assert letter.postscript == ""
        assert letter.signature_font_family is None
        assert letter.is_empty()

    def test_any_field_makes_it_non_empty(self) -> None:
        # Each part on its own flips is_empty to False
        for field in ("salutation", "body", "signoff", "signature", "postscript"):
            letter = LetterContent(**{field: "x"})
            assert not letter.is_empty(), f"{field}='x' should make letter non-empty"

    def test_signature_font_family_alone_does_not_make_non_empty(self) -> None:
        # signature_font is a style override, not content. An empty
        # letter with only a font override is still empty.
        letter = LetterContent(signature_font_family="Caveat")
        assert letter.is_empty()


class TestLetterContentStripping:
    """Whitespace is stripped from each part at construction."""

    def test_leading_trailing_whitespace_stripped(self) -> None:
        letter = LetterContent(
            salutation="  Dear M,  ",
            body="\nHello\n",
            signoff="\tLove,\t",
            signature="  C  ",
            postscript="\n PS  ",
        )
        assert letter.salutation == "Dear M,"
        assert letter.body == "Hello"
        assert letter.signoff == "Love,"
        assert letter.signature == "C"
        assert letter.postscript == "PS"

    def test_whitespace_only_becomes_empty(self) -> None:
        letter = LetterContent(salutation="   ", body="\n\n")
        assert letter.salutation == ""
        assert letter.body == ""
        assert letter.is_empty()

    def test_internal_whitespace_preserved(self) -> None:
        # Strip only at the edges; internal newlines (for stanzas /
        # paragraph breaks) must survive.
        letter = LetterContent(body="line one\n\nline two")
        assert letter.body == "line one\n\nline two"


class TestLetterContentValidation:
    """Field-length limits and frozen-model semantics."""

    def test_salutation_max_length(self) -> None:
        with pytest.raises(ValidationError):
            LetterContent(salutation="x" * 201)

    def test_body_max_length(self) -> None:
        with pytest.raises(ValidationError):
            LetterContent(body="x" * 2001)

    def test_postscript_max_length(self) -> None:
        with pytest.raises(ValidationError):
            LetterContent(postscript="x" * 401)

    def test_frozen(self) -> None:
        letter = LetterContent(salutation="Dear M,")
        with pytest.raises(ValidationError):
            letter.salutation = "Dear N,"  # type: ignore[misc]

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            LetterContent(unknown_field="oops")  # type: ignore[call-arg]


class TestTextElementLetterIntegration:
    """``letter_content`` plays nicely with the existing TextElement fields."""

    def test_letter_content_field_defaults_none(self) -> None:
        text = TextElement(content="hi", x=0.0, y=0.0)
        assert text.letter_content is None

    def test_letter_content_alone_is_fine(self) -> None:
        text = TextElement(
            content="",
            x=0.0,
            y=0.0,
            letter_content=LetterContent(salutation="Dear M,", body="hi"),
        )
        assert text.letter_content is not None
        assert text.letter_content.salutation == "Dear M,"

    def test_letter_plus_rich_content_rejected(self) -> None:
        rich = RichTextContent(
            paragraphs=[Paragraph(hard_lines=[[StyledRun(text="hi")]])]
        )
        with pytest.raises(ValidationError) as exc_info:
            TextElement(
                content="",
                x=0.0,
                y=0.0,
                letter_content=LetterContent(body="hello"),
                rich_content=rich,
            )
        # Error message should name both fields so the user understands.
        assert "letter_content" in str(exc_info.value)
        assert "rich_content" in str(exc_info.value)

    def test_letter_plus_content_is_allowed(self) -> None:
        # content + letter_content are not exclusive — the compiler
        # picks letter when non-empty and falls back to content.
        # This keeps templates that declare a default content but
        # let CLI flags drop a letter on top working without error.
        text = TextElement(
            content="default body",
            x=0.0,
            y=0.0,
            letter_content=LetterContent(salutation="Dear M,"),
        )
        assert text.content == "default body"
        assert text.letter_content is not None
