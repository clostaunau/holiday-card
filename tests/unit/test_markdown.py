"""Unit tests for the inside-panel Markdown parser."""

from __future__ import annotations

import pytest

from holiday_card.core.markdown import (
    Paragraph,
    RichTextContent,
    StyledRun,
    font_id_for_run,
    parse_markdown,
)


class TestParagraphSplitting:
    def test_single_paragraph_single_line(self) -> None:
        result = parse_markdown("Hello world.")
        assert len(result.paragraphs) == 1
        assert result.paragraphs[0].hard_lines == [
            [StyledRun(text="Hello world.", bold=False)]
        ]

    def test_blank_line_splits_paragraphs(self) -> None:
        result = parse_markdown("First.\n\nSecond.\n\nThird.")
        assert len(result.paragraphs) == 3
        assert result.paragraphs[0].hard_lines[0][0].text == "First."
        assert result.paragraphs[1].hard_lines[0][0].text == "Second."
        assert result.paragraphs[2].hard_lines[0][0].text == "Third."

    def test_multiple_blank_lines_collapse(self) -> None:
        result = parse_markdown("A.\n\n\n\nB.")
        assert len(result.paragraphs) == 2

    def test_single_newlines_are_hard_line_breaks(self) -> None:
        result = parse_markdown("Line one\nLine two\nLine three")
        assert len(result.paragraphs) == 1
        assert len(result.paragraphs[0].hard_lines) == 3
        assert result.paragraphs[0].hard_lines[0][0].text == "Line one"
        assert result.paragraphs[0].hard_lines[1][0].text == "Line two"
        assert result.paragraphs[0].hard_lines[2][0].text == "Line three"

    def test_leading_and_trailing_whitespace_stripped(self) -> None:
        result = parse_markdown("\n\n  Hello.  \n\n")
        assert len(result.paragraphs) == 1
        assert result.paragraphs[0].hard_lines[0][0].text == "Hello."

    def test_empty_source_raises(self) -> None:
        with pytest.raises(ValueError, match="empty Markdown"):
            parse_markdown("")
        with pytest.raises(ValueError, match="empty Markdown"):
            parse_markdown("   \n\n   ")


class TestBoldParsing:
    def test_double_asterisk_bold(self) -> None:
        result = parse_markdown("Hello **world**.")
        runs = result.paragraphs[0].hard_lines[0]
        assert runs == [
            StyledRun(text="Hello ", bold=False),
            StyledRun(text="world", bold=True),
            StyledRun(text=".", bold=False),
        ]

    def test_double_underscore_bold(self) -> None:
        result = parse_markdown("Hello __world__.")
        runs = result.paragraphs[0].hard_lines[0]
        assert runs == [
            StyledRun(text="Hello ", bold=False),
            StyledRun(text="world", bold=True),
            StyledRun(text=".", bold=False),
        ]

    def test_multiple_bold_spans_in_one_line(self) -> None:
        result = parse_markdown(
            "Some **bold one**, then **bold two**, then plain."
        )
        runs = result.paragraphs[0].hard_lines[0]
        bolded = [r.text for r in runs if r.bold]
        assert bolded == ["bold one", "bold two"]

    def test_entire_line_is_bold(self) -> None:
        result = parse_markdown("**All bold here**")
        runs = result.paragraphs[0].hard_lines[0]
        assert len(runs) == 1
        assert runs[0].bold is True
        assert runs[0].text == "All bold here"

    def test_empty_bold_marker_is_skipped(self) -> None:
        # ``**hello**`` - parse should not produce an empty bold run.
        # ``****`` (no inner text) - the regex requires at least one char.
        result = parse_markdown("Plain **bold** text")
        runs = result.paragraphs[0].hard_lines[0]
        assert all(r.text for r in runs), f"empty run in {runs}"

    def test_unclosed_asterisks_treated_as_literal(self) -> None:
        result = parse_markdown("Five stars: **never closed")
        runs = result.paragraphs[0].hard_lines[0]
        # No match, so the whole line is one normal run.
        assert len(runs) == 1
        assert runs[0].bold is False
        assert "**" in runs[0].text


class TestItalicParsing:
    def test_single_asterisk_italic(self) -> None:
        result = parse_markdown("Hello *world*.")
        runs = result.paragraphs[0].hard_lines[0]
        assert runs == [
            StyledRun(text="Hello ", bold=False, italic=False),
            StyledRun(text="world", bold=False, italic=True),
            StyledRun(text=".", bold=False, italic=False),
        ]

    def test_single_underscore_italic(self) -> None:
        result = parse_markdown("Hello _world_.")
        runs = result.paragraphs[0].hard_lines[0]
        assert runs == [
            StyledRun(text="Hello ", bold=False, italic=False),
            StyledRun(text="world", bold=False, italic=True),
            StyledRun(text=".", bold=False, italic=False),
        ]

    def test_double_asterisk_still_bold_not_italic(self) -> None:
        # Regression: **x** must remain bold-only, never split as ``*<*x*>*``.
        result = parse_markdown("**bold**")
        runs = result.paragraphs[0].hard_lines[0]
        assert runs == [StyledRun(text="bold", bold=True, italic=False)]

    def test_triple_asterisk_is_bold_italic(self) -> None:
        result = parse_markdown("***both***")
        runs = result.paragraphs[0].hard_lines[0]
        assert runs == [StyledRun(text="both", bold=True, italic=True)]

    def test_triple_underscore_is_bold_italic(self) -> None:
        result = parse_markdown("___both___")
        runs = result.paragraphs[0].hard_lines[0]
        assert runs == [StyledRun(text="both", bold=True, italic=True)]

    def test_mixed_bold_and_italic_in_one_line(self) -> None:
        result = parse_markdown("Plain *it* **bold** *more*.")
        runs = result.paragraphs[0].hard_lines[0]
        styles = [(r.text, r.bold, r.italic) for r in runs]
        assert styles == [
            ("Plain ", False, False),
            ("it", False, True),
            (" ", False, False),
            ("bold", True, False),
            (" ", False, False),
            ("more", False, True),
            (".", False, False),
        ]

    def test_multiple_italic_spans_in_one_line(self) -> None:
        result = parse_markdown("*one* and *two* and plain.")
        runs = result.paragraphs[0].hard_lines[0]
        italicized = [r.text for r in runs if r.italic]
        assert italicized == ["one", "two"]

    def test_unclosed_single_asterisk_is_literal(self) -> None:
        # ``*never closed`` should pass through, not silently absorb
        # everything to end-of-line as italic.
        result = parse_markdown("Five stars: *never closed")
        runs = result.paragraphs[0].hard_lines[0]
        assert len(runs) == 1
        assert runs[0].italic is False
        assert "*" in runs[0].text


class TestRealisticChristmasLetter:
    """Sanity-check the parser on the canonical 'Christmas letter'
    example used in the README and the PR description."""

    LETTER = """Dear Sarah and Mike,

What a year — **Lily started kindergarten**, **Mark switched jobs**, and we
finally finished the back porch.

Hoping yours has been kinder, or at least funnier, than the news.

With love,
The Smiths
"""

    def test_parses_into_four_paragraphs(self) -> None:
        result = parse_markdown(self.LETTER)
        assert len(result.paragraphs) == 4

    def test_first_paragraph_is_salutation(self) -> None:
        result = parse_markdown(self.LETTER)
        runs = result.paragraphs[0].hard_lines[0]
        assert runs[0].text == "Dear Sarah and Mike,"

    def test_signature_paragraph_has_two_hard_lines(self) -> None:
        result = parse_markdown(self.LETTER)
        signature = result.paragraphs[3]
        assert len(signature.hard_lines) == 2
        assert signature.hard_lines[0][0].text == "With love,"
        assert signature.hard_lines[1][0].text == "The Smiths"

    def test_body_paragraph_carries_two_bold_spans(self) -> None:
        result = parse_markdown(self.LETTER)
        body = result.paragraphs[1]
        # Flatten all runs across the body's hard lines
        all_runs = [r for line in body.hard_lines for r in line]
        bolded = [r.text for r in all_runs if r.bold]
        assert "Lily started kindergarten" in bolded
        assert "Mark switched jobs" in bolded


class TestFontIdResolution:
    def test_normal_run_uses_family_directly(self) -> None:
        assert font_id_for_run("Cormorant", bold=False) == "Cormorant"
        assert font_id_for_run("Lato", bold=False) == "Lato"

    def test_lato_bold_uses_registered_bold_variant(self) -> None:
        # Lato is the only curated font with a -Bold registered today.
        assert font_id_for_run("Lato", bold=True) == "Lato-Bold"

    def test_curated_editorial_serifs_have_bold_variants(self) -> None:
        # Cormorant and PlayfairDisplay ship static Bold + BoldItalic
        # TTFs (instanced from the variable masters at weight=700).
        assert font_id_for_run("Cormorant", bold=True) == "Cormorant-Bold"
        assert (
            font_id_for_run("PlayfairDisplay", bold=True)
            == "PlayfairDisplay-Bold"
        )

    def test_remaining_curated_fonts_still_fall_back_for_bold(self) -> None:
        # Inter, Caveat, Comfortaa are variable fonts with no static
        # Bold TTF yet — they fall back to regular. Documented limitation.
        assert font_id_for_run("Inter", bold=True) == "Inter"
        assert font_id_for_run("Caveat", bold=True) == "Caveat"
        assert font_id_for_run("Comfortaa", bold=True) == "Comfortaa"


class TestFontIdItalic:
    """Italic font resolution mirrors the bold story. Liberation-backed
    PDF base-14 names have registered italic variants (Helvetica-Oblique,
    Times-Italic, Courier-Oblique). Curated fonts fall back to the
    regular face — documented limitation, same as bold."""

    def test_pdf_base14_italic_resolves(self) -> None:
        assert font_id_for_run("Helvetica", italic=True) == "Helvetica-Oblique"
        assert font_id_for_run("Times-Roman", italic=True) == "Times-Italic"
        assert font_id_for_run("Courier", italic=True) == "Courier-Oblique"

    def test_pdf_base14_bold_italic_resolves(self) -> None:
        assert (
            font_id_for_run("Helvetica", bold=True, italic=True)
            == "Helvetica-BoldOblique"
        )
        assert (
            font_id_for_run("Times-Roman", bold=True, italic=True)
            == "Times-BoldItalic"
        )
        assert (
            font_id_for_run("Courier", bold=True, italic=True)
            == "Courier-BoldOblique"
        )

    def test_curated_editorial_serifs_have_italic_variants(self) -> None:
        # Cormorant and PlayfairDisplay are the editorial-serif families
        # in the curated chain — italic matters most for them. Both ship
        # italic TTFs in fonts/curated/.
        assert font_id_for_run("Cormorant", italic=True) == "Cormorant-Italic"
        assert (
            font_id_for_run("PlayfairDisplay", italic=True)
            == "PlayfairDisplay-Italic"
        )

    def test_remaining_curated_fonts_still_fall_back_for_italic(self) -> None:
        # Inter, Caveat, Comfortaa, Lato don't ship italic TTFs in the
        # curated chain yet — they fall back to regular. Documented
        # limitation that lifts when more italic variants are added.
        assert font_id_for_run("Inter", italic=True) == "Inter"
        assert font_id_for_run("Caveat", italic=True) == "Caveat"
        assert font_id_for_run("Comfortaa", italic=True) == "Comfortaa"
        assert font_id_for_run("Lato", italic=True) == "Lato"

    def test_lato_bold_italic_falls_back_to_lato_bold(self) -> None:
        # Lato has a Bold but no BoldItalic; degrade to Bold rather than
        # losing the weight signal entirely.
        assert font_id_for_run("Lato", bold=True, italic=True) == "Lato-Bold"

    def test_curated_editorial_serifs_have_bold_italic_variants(self) -> None:
        # Cormorant and PlayfairDisplay ship both Bold and BoldItalic
        # statics. ``***x***`` on those families resolves to the
        # combined variant directly.
        assert (
            font_id_for_run("Cormorant", bold=True, italic=True)
            == "Cormorant-BoldItalic"
        )
        assert (
            font_id_for_run("PlayfairDisplay", bold=True, italic=True)
            == "PlayfairDisplay-BoldItalic"
        )


class TestRichTextSchema:
    def test_paragraph_requires_at_least_one_hard_line(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Paragraph(hard_lines=[])

    def test_rich_text_requires_at_least_one_paragraph(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RichTextContent(paragraphs=[])

    def test_rich_text_is_immutable(self) -> None:
        from pydantic import ValidationError
        rt = parse_markdown("Hello.")
        with pytest.raises(ValidationError):
            rt.paragraphs = []  # type: ignore[misc]
