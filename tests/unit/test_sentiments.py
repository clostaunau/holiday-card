"""Unit tests for the sentiment library loader and resolver."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from holiday_card.core.models import OccasionType
from holiday_card.core.sentiments import (
    ROLES,
    VOICES,
    Sentiment,
    SentimentNotFoundError,
    get_sentiments_dir,
    load_sentiment_file,
    pick_sentiment,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def fake_lib(tmp_path: Path) -> Path:
    """Build a tiny ``sentiments/{occasion}/{voice}/{role}.yaml`` tree
    isolated from the repo's real library."""
    base = tmp_path / "sentiments"
    occasion_dir = base / "christmas" / "warm"
    occasion_dir.mkdir(parents=True)
    (occasion_dir / "cover.yaml").write_text(
        yaml.safe_dump({
            "voice": "warm", "occasion": "christmas", "role": "cover",
            "sentiments": ["A", "B", "C"],
        })
    )
    (occasion_dir / "inside.yaml").write_text(
        yaml.safe_dump({
            "voice": "warm", "occasion": "christmas", "role": "inside",
            "sentiments": ["only-line"],
        })
    )
    return base


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class TestVocabulary:
    def test_voices_match_panel_recommendation(self) -> None:
        # The panel's "copy subset" of Agreement 1 named these five.
        # If you're adding a new voice, expand this assertion intentionally.
        assert set(VOICES) == {"warm", "witty", "spare", "devotional", "irreverent"}

    def test_roles_are_cover_and_inside(self) -> None:
        assert set(ROLES) == {"cover", "inside"}


# ---------------------------------------------------------------------------
# Sentiment model validation
# ---------------------------------------------------------------------------


class TestSentimentModel:
    def test_valid_file_loads(self) -> None:
        s = Sentiment(
            voice="warm", occasion="christmas", role="cover",
            sentiments=["Hello"],
        )
        assert s.sentiments == ["Hello"]

    def test_unknown_voice_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Sentiment(
                voice="screaming",  # not a recognized voice
                occasion="christmas",
                role="cover",
                sentiments=["x"],
            )

    def test_unknown_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Sentiment(
                voice="warm", occasion="christmas",
                role="signature",  # not a recognized role
                sentiments=["x"],
            )

    def test_empty_sentiments_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Sentiment(
                voice="warm", occasion="christmas", role="cover",
                sentiments=[],  # min_length=1
            )

    def test_extra_fields_rejected(self) -> None:
        # Catches typos or stale schema. Forbidding extras keeps the
        # YAML files honest about what the loader actually consumes.
        with pytest.raises(ValidationError):
            Sentiment(
                voice="warm", occasion="christmas", role="cover",
                sentiments=["x"], author="someone",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------


class TestLoadSentimentFile:
    def test_loads_a_valid_file(self, fake_lib: Path) -> None:
        s = load_sentiment_file("christmas", "warm", "cover", sentiments_dir=fake_lib)
        assert s.sentiments == ["A", "B", "C"]

    def test_missing_file_raises_clearly(self, fake_lib: Path) -> None:
        with pytest.raises(SentimentNotFoundError, match="no sentiment file"):
            load_sentiment_file("birthday", "warm", "cover", sentiments_dir=fake_lib)

    def test_path_metadata_mismatch_raises(self, tmp_path: Path) -> None:
        """File declares ``occasion: birthday`` but lives in
        ``christmas/`` directory — fail loud."""
        base = tmp_path / "sentiments"
        wrong = base / "christmas" / "warm"
        wrong.mkdir(parents=True)
        (wrong / "cover.yaml").write_text(
            yaml.safe_dump({
                "voice": "warm", "occasion": "birthday",  # mismatch!
                "role": "cover", "sentiments": ["x"],
            })
        )
        with pytest.raises(ValueError, match="declares occasion="):
            load_sentiment_file("christmas", "warm", "cover", sentiments_dir=base)


class TestSentimentsDirDiscovery:
    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOLIDAY_CARD_SENTIMENTS", "/tmp/custom-sentiments")
        assert get_sentiments_dir() == Path("/tmp/custom-sentiments")


# ---------------------------------------------------------------------------
# Picker
# ---------------------------------------------------------------------------


class TestPickSentiment:
    def test_picks_a_line_with_a_seed(self, fake_lib: Path) -> None:
        line = pick_sentiment(
            "christmas", "warm", "cover", seed=42, sentiments_dir=fake_lib,
        )
        assert line in {"A", "B", "C"}

    def test_same_seed_picks_the_same_line(self, fake_lib: Path) -> None:
        a = pick_sentiment("christmas", "warm", "cover", seed=42, sentiments_dir=fake_lib)
        b = pick_sentiment("christmas", "warm", "cover", seed=42, sentiments_dir=fake_lib)
        assert a == b

    def test_different_seeds_can_differ(self, fake_lib: Path) -> None:
        # With 3 lines and 50 distinct seeds, at least two seeds should
        # produce different picks unless the RNG is broken.
        picks = {
            pick_sentiment("christmas", "warm", "cover", seed=s, sentiments_dir=fake_lib)
            for s in range(50)
        }
        assert len(picks) >= 2

    def test_unknown_voice_raises(self, fake_lib: Path) -> None:
        with pytest.raises(ValueError, match="unknown voice"):
            pick_sentiment("christmas", "screaming", "cover", sentiments_dir=fake_lib)

    def test_unknown_role_raises(self, fake_lib: Path) -> None:
        with pytest.raises(ValueError, match="unknown role"):
            pick_sentiment("christmas", "warm", "signature", sentiments_dir=fake_lib)

    def test_accepts_occasion_enum_or_string(self, fake_lib: Path) -> None:
        a = pick_sentiment(
            OccasionType.CHRISTMAS, "warm", "cover", seed=0, sentiments_dir=fake_lib,
        )
        b = pick_sentiment(
            "christmas", "warm", "cover", seed=0, sentiments_dir=fake_lib,
        )
        assert a == b


# ---------------------------------------------------------------------------
# Real library coverage — every (occasion, voice, role) the CLI advertises
# must have a sentiment file with at least one line.
# ---------------------------------------------------------------------------


_SHIPPED_OCCASIONS = ("christmas", "birthday", "hanukkah", "mothers_day", "generic")


@pytest.mark.parametrize("occasion", _SHIPPED_OCCASIONS)
@pytest.mark.parametrize("voice", VOICES)
@pytest.mark.parametrize("role", ROLES)
def test_shipped_library_covers_every_combination(
    occasion: str, voice: str, role: str
) -> None:
    """Every (occasion × voice × role) advertised by the CLI must have
    a non-empty sentiment file. Catches a missing file in the
    repo-shipped sentiments/ tree."""
    line = pick_sentiment(occasion, voice, role, seed=0)
    assert line, f"empty sentiment for ({occasion}, {voice}, {role})"


# Sympathy-class occasions (panel L2 taxonomy) intentionally ship only a
# subset of voices. The "absent rather than wrong" principle: a bad
# sympathy card is worse than no sympathy card. Witty + irreverent are
# always inappropriate for grief. Devotional ships for adult-loss only
# (sympathy + condolence); miscarriage and pet_loss skip devotional
# because religious framing of pregnancy loss or pet death is delicate
# enough that absence beats getting it wrong.
_SYMPATHY_LIBRARY: dict[str, tuple[str, ...]] = {
    "sympathy":    ("warm", "spare", "devotional"),
    "condolence":  ("warm", "spare", "devotional"),
    "miscarriage": ("warm", "spare"),
    "pet_loss":    ("warm", "spare"),
}

_SYMPATHY_SUPPORTED = [
    (occ, voice, role)
    for occ, voices in _SYMPATHY_LIBRARY.items()
    for voice in voices
    for role in ROLES
]

_SYMPATHY_UNSUPPORTED = (
    [(occ, "witty") for occ in _SYMPATHY_LIBRARY]
    + [(occ, "irreverent") for occ in _SYMPATHY_LIBRARY]
    + [("miscarriage", "devotional"), ("pet_loss", "devotional")]
)


@pytest.mark.parametrize(("occasion", "voice", "role"), _SYMPATHY_SUPPORTED)
def test_sympathy_class_sentiments_load(
    occasion: str, voice: str, role: str
) -> None:
    """Every supported (sympathy-class occasion × voice × role) has a
    non-empty sentiment file."""
    line = pick_sentiment(occasion, voice, role, seed=0)
    assert line, f"empty sentiment for ({occasion}, {voice}, {role})"


@pytest.mark.parametrize(("occasion", "voice"), _SYMPATHY_UNSUPPORTED)
def test_sympathy_class_inappropriate_voices_raise(
    occasion: str, voice: str
) -> None:
    """Voices deliberately not shipped for sympathy-class occasions
    must raise SentimentNotFoundError — fail-loud convention. A future
    contributor adding e.g. ``sentiments/sympathy/witty/`` would fail
    this test, prompting a conversation about whether that's actually
    a good idea."""
    with pytest.raises(SentimentNotFoundError):
        pick_sentiment(occasion, voice, "cover", seed=0)
