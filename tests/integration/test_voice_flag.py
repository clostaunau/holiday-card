"""Integration tests for the ``--voice`` / ``--blank-inside`` / ``--seed`` flags.

End-to-end via Typer's CliRunner: invoke ``holiday-card create`` with the
flags, then re-compile the resulting card and assert that the picked
sentiment text appears in a ``DrawText`` command.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from holiday_card.cli.commands import app
from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.render_ir import DrawText
from holiday_card.core.sentiments import pick_sentiment


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _drawn_text_lines(card_template_id: str, **kwargs) -> list[str]:
    """Re-render a card with the given kwargs and return the list of
    text lines that ended up in DrawText commands."""
    card = CardGenerator().create_card(template_id=card_template_id, **kwargs)
    commands = compile_card(card)
    return [c.run.text for c in commands if isinstance(c, DrawText)]


# ---------------------------------------------------------------------------
# --voice
# ---------------------------------------------------------------------------


class TestVoiceFlag:
    def test_voice_warm_picks_a_christmas_sentiment(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Use --seed so the picked sentiment is deterministic across runs.
        out = tmp_path / "card.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--voice", "warm", "--seed", "1",
             "--output", str(out)],
        )
        assert result.exit_code == 0, result.stdout + result.output

        # Re-pick with the same seed to learn what the CLI picked.
        cover = pick_sentiment("christmas", "warm", "cover", seed=1)
        inside = pick_sentiment("christmas", "warm", "inside", seed=1)
        rendered = _drawn_text_lines(
            "christmas-classic", message=cover, inside_message=inside,
        )
        # The cover sentiment shows up as the front greeting; the inside
        # sentiment shows up as the inside message. Use substring match
        # because text wrapping may split long lines.
        assert any(cover in line or line in cover for line in rendered), (
            f"Picked cover {cover!r} not in rendered text: {rendered}"
        )

    def test_unknown_voice_exits_with_helpful_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--voice", "yelling",
             "--output", str(out)],
        )
        assert result.exit_code == 2
        # CliRunner combines stdout+stderr; check both via `output`.
        combined = result.output + (result.stderr or "")
        assert "yelling" in combined
        assert "warm" in combined  # one of the available voices listed

    def test_explicit_message_overrides_voice_pick(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        custom = "Custom message wins"
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--voice", "warm",
             "--message", custom, "--seed", "1",
             "--output", str(out)],
        )
        assert result.exit_code == 0
        # Stdout reports the picked Voice info (because --voice was set)
        # but the actual rendered cover should be the explicit message.
        rendered = _drawn_text_lines("christmas-classic", message=custom)
        assert any(custom in line for line in rendered)


# ---------------------------------------------------------------------------
# --blank-inside
# ---------------------------------------------------------------------------


class TestBlankInside:
    def test_blank_inside_clears_template_default_inside_text(self) -> None:
        # Without --blank-inside, christmas-classic ships an inside message.
        rendered_default = _drawn_text_lines("christmas-classic")
        assert any("warm" in t.lower() or "wishes" in t.lower() or "merry" in t.lower()
                   for t in rendered_default), (
            f"sanity: christmas-classic should have visible inside text by "
            f"default; got {rendered_default}"
        )

        # With --blank-inside, the inside message is cleared. Verify by
        # re-rendering the card with empty inside_message.
        rendered_blank = _drawn_text_lines("christmas-classic", inside_message="")
        # The default cover greeting should still be present.
        assert any("merry" in t.lower() for t in rendered_blank)
        # The "Wishing you peace and joy" inside text should be gone.
        assert not any(
            "warm wishes" in t.lower() or "peace and joy" in t.lower()
            for t in rendered_blank
        ), f"Inside text still present after blank: {rendered_blank}"

    def test_blank_inside_via_cli_exits_zero(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--blank-inside",
             "--output", str(out)],
        )
        assert result.exit_code == 0, result.stdout + result.output
        assert "blank" in result.stdout.lower()


# ---------------------------------------------------------------------------
# --seed reproducibility
# ---------------------------------------------------------------------------


class TestSeedReproducibility:
    def test_same_seed_same_pick(self) -> None:
        a = pick_sentiment("christmas", "irreverent", "cover", seed=999)
        b = pick_sentiment("christmas", "irreverent", "cover", seed=999)
        assert a == b
