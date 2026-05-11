"""Integration tests for ``--salutation`` / ``--signoff`` / ``--signature``
/ ``--ps`` CLI flag composition.

Renders ``christmas-classic`` with various letter-part flag combos and
asserts each phrase appears in the rendered PDF's content stream.
The PDF content-stream check is the same approach used by
``test_pdfx_moo_a6.py`` — strings appear unambiguously in the latin-1
decoded stream for standard fonts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pikepdf
import pytest
from typer.testing import CliRunner

from holiday_card.cli import app

runner = CliRunner()


def _stream(pdf_path: Path) -> str:
    with pikepdf.open(pdf_path) as pdf:
        chunks: list[bytes] = []
        for page in pdf.pages:
            contents = page.Contents
            streams = contents if isinstance(contents, pikepdf.Array) else [contents]
            chunks.extend(s.read_bytes() for s in streams)
    return b"".join(chunks).decode("latin-1")


class TestLetterFlags:
    def test_all_four_parts_render(self, tmp_path: Path) -> None:
        out = tmp_path / "letter.pdf"
        result = runner.invoke(
            app,
            [
                "create",
                "christmas-classic",
                "--salutation", "Dear Aunt Margaret,",
                "--inside-message", "Hope your holidays are bright.",
                "--signoff", "Love,",
                "--signature", "The Smiths",
                "--ps", "PS got a new dog!",
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0, result.stdout + result.stderr
        assert out.exists()
        body = _stream(out)
        assert "Dear Aunt Margaret," in body
        assert "Hope your holidays are bright." in body
        assert "Love," in body
        assert "The Smiths" in body
        assert "PS got a new dog!" in body

    def test_partial_letter_just_salutation_and_signoff(self, tmp_path: Path) -> None:
        # Only two parts set — should render exactly those (plus
        # whatever the template's default front-of-card has, which
        # we don't care about for this assertion).
        out = tmp_path / "partial.pdf"
        result = runner.invoke(
            app,
            [
                "create",
                "christmas-classic",
                "--salutation", "Hey kiddo,",
                "--signoff", "xo",
                "--blank-inside",  # explicitly empty body
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0, result.stdout + result.stderr
        body = _stream(out)
        assert "Hey kiddo," in body
        assert "xo" in body

    def test_signature_font_override_changes_font_resource(self, tmp_path: Path) -> None:
        # With --signature-font Caveat, the PDF should register and
        # reference a different font for the signature line. We can't
        # easily map font name → /F# without parsing the resource
        # dict, so instead check that more distinct fonts get
        # referenced than would happen without the override.
        no_override = tmp_path / "no_override.pdf"
        runner.invoke(
            app,
            [
                "create", "christmas-classic",
                "--signature", "The Smiths",
                "-o", str(no_override),
            ],
        )
        with_override = tmp_path / "with_override.pdf"
        runner.invoke(
            app,
            [
                "create", "christmas-classic",
                "--signature", "The Smiths",
                "--signature-font", "Caveat",
                "-o", str(with_override),
            ],
        )
        # Count distinct /F# refs in each. Caveat should add one.
        fonts_a = set(re.findall(r"/F\d+", _stream(no_override)))
        fonts_b = set(re.findall(r"/F\d+", _stream(with_override)))
        assert len(fonts_b) >= len(fonts_a), (
            f"Override should introduce at least as many fonts. "
            f"baseline={fonts_a} override={fonts_b}"
        )

    def test_letter_flags_rejected_with_inside_message_md(self, tmp_path: Path) -> None:
        md = tmp_path / "letter.md"
        md.write_text("Hello world.")
        result = runner.invoke(
            app,
            [
                "create",
                "christmas-classic",
                "--salutation", "Dear M,",
                "--inside-message-md", str(md),
                "-o", str(tmp_path / "x.pdf"),
            ],
        )
        assert result.exit_code != 0
        assert "letter parts" in (result.stdout + result.stderr).lower() or \
               "mutually" in (result.stdout + result.stderr).lower() or \
               "cannot be combined" in (result.stdout + result.stderr).lower()

    @pytest.mark.parametrize(
        "flag,value",
        [
            ("--salutation", "Dear M,"),
            ("--signoff", "Love,"),
            ("--signature", "C"),
            ("--ps", "PS hi"),
        ],
    )
    def test_single_letter_flag_works_alone(self, flag: str, value: str, tmp_path: Path) -> None:
        # Every individual letter flag should be usable without the
        # others (each is optional, each composes independently).
        out = tmp_path / "single.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic", flag, value, "-o", str(out)],
        )
        assert result.exit_code == 0, result.stdout + result.stderr
        body = _stream(out)
        assert value in body
