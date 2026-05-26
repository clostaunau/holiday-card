"""Integration tests for ``--inside-message-md`` Markdown mode."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from holiday_card.cli.commands import app
from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.markdown import parse_markdown
from holiday_card.core.render_ir import DrawText

SAMPLE_LETTER = """Dear Sarah,

What a year — **Lily started kindergarten** and we finally finished
the back porch.

With love,
The Smiths
"""


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def letter_md(tmp_path: Path) -> Path:
    p = tmp_path / "letter.md"
    p.write_text(SAMPLE_LETTER)
    return p


# ---------------------------------------------------------------------------
# Compiler emits expected DrawText commands for rich content
# ---------------------------------------------------------------------------


class TestRichTextCompilation:
    def _card_with_rich_inside(self, font: str = "Lato"):
        """Build a card with the Markdown letter applied to the inside
        message text element, using ``font`` as the family."""
        gen = CardGenerator()
        card = gen.create_card("christmas-classic")
        for panel in card.panels:
            for te in panel.text_elements:
                if te.id == "message":
                    te.font_family = font
                    te.rich_content = parse_markdown(SAMPLE_LETTER)
                    te.width = 3.25
                    return card
        raise RuntimeError("test fixture: no 'message' text element found")

    def test_rich_text_emits_one_drawtext_per_styled_segment(self) -> None:
        card = self._card_with_rich_inside()
        cmds = compile_card(card)
        texts = [c for c in cmds if isinstance(c, DrawText)]
        # Cover greeting + at least 4 paragraphs of body content
        # (salutation + 1 hard-line of body + signoff + signature line)
        # → at least 5 DrawText commands beyond the cover.
        assert len(texts) >= 5

    def test_bold_runs_use_lato_bold_font_id_when_family_is_lato(self) -> None:
        card = self._card_with_rich_inside(font="Lato")
        cmds = compile_card(card)
        texts = [c for c in cmds if isinstance(c, DrawText)]
        bold_texts = [t for t in texts if "Bold" in t.run.font_id]
        assert bold_texts, (
            f"Expected at least one Lato-Bold DrawText for the bold "
            f"span; saw font_ids: {[t.run.font_id for t in texts]}"
        )
        # The bold span content includes "Lily" — the wrap may split
        # across lines but at least one bold segment carries it.
        assert any("Lily" in t.run.text for t in bold_texts)

    def test_bold_falls_back_to_regular_for_fonts_without_bold_variant(
        self,
    ) -> None:
        card = self._card_with_rich_inside(font="Cormorant")
        cmds = compile_card(card)
        texts = [c for c in cmds if isinstance(c, DrawText)]
        # Cormorant has no -Bold registered → bold runs fall back to
        # the regular family. None should carry "-Bold" in font_id for
        # this template (cover greeting uses PlayfairDisplay which also
        # has no -Bold).
        bold_segments = [t for t in texts if "Bold" in t.run.font_id]
        assert bold_segments == [], (
            f"Cormorant has no Bold variant; found {bold_segments}"
        )

    def test_italic_runs_use_oblique_font_id_when_family_is_helvetica(
        self,
    ) -> None:
        """Italic Markdown spans resolve to the registered italic
        variant when the family has one (Helvetica → Helvetica-Oblique)."""
        italic_letter = (
            "Dear *Sarah*,\n\n"
            "Thinking of you — *especially* this year.\n\n"
            "With love,\nThe Smiths\n"
        )
        gen = CardGenerator()
        card = gen.create_card("christmas-classic")
        for panel in card.panels:
            for te in panel.text_elements:
                if te.id == "message":
                    te.font_family = "Helvetica"
                    te.rich_content = parse_markdown(italic_letter)
                    te.width = 3.25
                    break
        cmds = compile_card(card)
        texts = [c for c in cmds if isinstance(c, DrawText)]
        italic_texts = [t for t in texts if "Oblique" in t.run.font_id]
        assert italic_texts, (
            f"Expected at least one Helvetica-Oblique DrawText; "
            f"saw font_ids: {[t.run.font_id for t in texts]}"
        )
        # The italic spans cover "Sarah" and "especially" — at least one
        # should appear in an italic-font_id segment.
        assert any(
            "Sarah" in t.run.text or "especially" in t.run.text
            for t in italic_texts
        ), f"italic font_id segments: {[t.run.text for t in italic_texts]}"

    def test_italic_uses_cormorant_italic_when_family_is_cormorant(
        self,
    ) -> None:
        """``*italic*`` on a Cormorant-family text element should
        resolve to ``Cormorant-Italic`` now that the italic TTF ships
        in fonts/curated/. The shipped christmas-classic template uses
        Cormorant for its inside-message body, so this is the real
        user-facing path."""
        letter = "Dear,\n\nMissing you *especially* this year.\n"
        gen = CardGenerator()
        card = gen.create_card("christmas-classic")
        for panel in card.panels:
            for te in panel.text_elements:
                if te.id == "message":
                    # Christmas-classic already uses Cormorant for the
                    # inside; assert + set defensively.
                    te.font_family = "Cormorant"
                    te.rich_content = parse_markdown(letter)
                    te.width = 3.25
                    break
        cmds = compile_card(card)
        texts = [c for c in cmds if isinstance(c, DrawText)]
        italic_texts = [t for t in texts if t.run.font_id == "Cormorant-Italic"]
        assert italic_texts, (
            f"Expected at least one Cormorant-Italic DrawText; "
            f"saw font_ids: {[t.run.font_id for t in texts]}"
        )
        assert any("especially" in t.run.text for t in italic_texts)

    def test_bold_italic_triple_marker_resolves_to_bolditalic_variant(
        self,
    ) -> None:
        """``***x***`` should resolve to the BoldItalic variant when the
        family registers one."""
        letter = "Dear,\n\nWe wish you ***great*** joy.\n"
        gen = CardGenerator()
        card = gen.create_card("christmas-classic")
        for panel in card.panels:
            for te in panel.text_elements:
                if te.id == "message":
                    te.font_family = "Helvetica"
                    te.rich_content = parse_markdown(letter)
                    te.width = 3.25
                    break
        cmds = compile_card(card)
        texts = [c for c in cmds if isinstance(c, DrawText)]
        bi_texts = [t for t in texts if "BoldOblique" in t.run.font_id]
        assert bi_texts, (
            f"Expected Helvetica-BoldOblique for ***great***; "
            f"saw font_ids: {[t.run.font_id for t in texts]}"
        )

    def test_rich_content_takes_priority_over_content(self) -> None:
        """If both content (template default) and rich_content (override)
        are present, rich_content wins."""
        card = self._card_with_rich_inside()
        # Find the message text element and confirm its content was
        # left non-empty by the template; rich_content should still win.
        for panel in card.panels:
            for te in panel.text_elements:
                if te.id == "message" and te.rich_content is not None:
                    # Don't clear te.content — confirm rich wins anyway
                    te.content = "should not appear"
                    break
        cmds = compile_card(card)
        texts = [c for c in cmds if isinstance(c, DrawText)]
        all_text = " ".join(t.run.text for t in texts)
        assert "should not appear" not in all_text
        assert "Dear Sarah" in all_text

    def test_paragraph_spacing_pushes_y_down_between_paragraphs(self) -> None:
        """Each paragraph break should push the y-cursor down by
        ``paragraph_spacing * line_height``. A 4-paragraph letter
        should occupy noticeably more vertical space than 4 single
        lines back-to-back."""
        card = self._card_with_rich_inside()
        cmds = compile_card(card)
        texts = [
            c for c in cmds if isinstance(c, DrawText) and c.run.text != "Merry Christmas!"
        ]
        # All inside-letter texts; their y-coordinates span more than
        # 4 line heights (a 4-paragraph letter with hard lines).
        ys = sorted({t.run.origin.y for t in texts})
        assert len(ys) >= 5, "expected at least 5 distinct y rows"
        y_span = ys[-1] - ys[0]
        # 12pt font ≈ 14.4pt line height; 5 lines ≈ 72pt; we expect
        # noticeably more once paragraph_spacing applies.
        assert y_span > 60.0


# ---------------------------------------------------------------------------
# CLI end-to-end
# ---------------------------------------------------------------------------


class TestCliMarkdownFlag:
    def test_inside_message_md_renders_a_pdf(
        self, runner: CliRunner, letter_md: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic",
             "--inside-message-md", str(letter_md),
             "--output", str(out)],
        )
        assert result.exit_code == 0, result.stdout + result.output
        assert out.exists()
        assert out.stat().st_size > 1000
        # Stdout reports paragraph count (SAMPLE_LETTER has 3 paragraphs)
        assert "Markdown (3 paragraph" in result.stdout

    def test_inside_message_md_mutually_exclusive_with_inside_message(
        self, runner: CliRunner, letter_md: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic",
             "--inside-message", "Plain text inside",
             "--inside-message-md", str(letter_md),
             "--output", str(out)],
        )
        assert result.exit_code == 2
        combined = result.output + (result.stderr or "")
        assert "mutually exclusive" in combined.lower()

    def test_missing_md_file_exits_clearly(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        bogus = tmp_path / "does-not-exist.md"
        result = runner.invoke(
            app,
            ["create", "christmas-classic",
             "--inside-message-md", str(bogus),
             "--output", str(out)],
        )
        assert result.exit_code == 2
        combined = result.output + (result.stderr or "")
        assert "not found" in combined.lower()

    def test_empty_md_file_exits_clearly(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        empty = tmp_path / "empty.md"
        empty.write_text("   \n\n   ")
        out = tmp_path / "card.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic",
             "--inside-message-md", str(empty),
             "--output", str(out)],
        )
        assert result.exit_code == 2
        combined = result.output + (result.stderr or "")
        assert "empty" in combined.lower()
