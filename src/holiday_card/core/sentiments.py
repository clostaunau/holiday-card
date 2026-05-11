"""Sentiment library loader and resolver.

Loads YAML files from ``sentiments/{occasion}/{voice}/{role}.yaml`` and
exposes :func:`pick_sentiment` for the CLI's ``--voice`` flag. Each
file is a list of greeting copy in a particular voice and role; the
resolver picks one (random by default, deterministic with ``seed=N``).

The library directory is auto-discovered the same way templates are
(walk up from the package source until ``sentiments/`` appears, fall
back to ``./sentiments``). Override via ``HOLIDAY_CARD_SENTIMENTS`` for
testing or vendor-managed installs.

This module is intentionally read-only at import time: files are
loaded on first ``pick_sentiment`` call and cached. Tests that need a
fresh load can call :func:`reset_cache`.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from holiday_card.core.models import OccasionType

__all__ = [
    "VOICES",
    "ROLES",
    "Voice",
    "Role",
    "Sentiment",
    "SentimentNotFoundError",
    "pick_sentiment",
    "load_sentiment_file",
    "get_sentiments_dir",
    "reset_cache",
]


# Five voices, per the industry-panel recommendation
# (consensus-general.md, Agreement 1, "copy subset"). These map to
# subdirectories under ``sentiments/{occasion}/``.
VOICES: tuple[str, ...] = ("warm", "witty", "spare", "devotional", "irreverent")
Voice = Literal["warm", "witty", "spare", "devotional", "irreverent"]

# Two roles: cover greeting (front panel) and inside message
# (interior panel).
ROLES: tuple[str, ...] = ("cover", "inside")
Role = Literal["cover", "inside"]


class SentimentNotFoundError(LookupError):
    """No sentiment file at the requested ``(occasion, voice, role)``.

    Subclass of LookupError so callers can ``except LookupError`` if
    they want to fall back gracefully.
    """


class Sentiment(BaseModel):
    """One ``sentiments/{occasion}/{voice}/{role}.yaml`` file.

    The ``voice``, ``occasion``, and ``role`` fields must match the
    file's directory path; this is verified by ``load_sentiment_file``
    so a renamed file doesn't quietly load with wrong metadata.
    """

    model_config = ConfigDict(extra="forbid")

    voice: Voice
    occasion: str  # OccasionType value (e.g. "christmas", "mothers_day")
    role: Role
    sentiments: list[str] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Filesystem discovery
# ---------------------------------------------------------------------------


def get_sentiments_dir() -> Path:
    """Locate the ``sentiments/`` directory.

    Override via ``HOLIDAY_CARD_SENTIMENTS`` env var (used by tests).
    Otherwise walk up from this file looking for ``sentiments/`` in the
    project root, then fall back to a relative path.
    """
    env = os.environ.get("HOLIDAY_CARD_SENTIMENTS")
    if env:
        return Path(env)

    current = Path(__file__).parent
    while current != current.parent:
        candidate = current / "sentiments"
        if candidate.exists() and candidate.is_dir():
            return candidate
        current = current.parent

    return Path("sentiments")


# ---------------------------------------------------------------------------
# Load + cache
# ---------------------------------------------------------------------------


# Keyed by (occasion, voice, role); value is the loaded Sentiment.
_cache: dict[tuple[str, str, str], Sentiment] = {}


def reset_cache() -> None:
    """Clear the in-memory sentiment cache. Tests use this when a
    fixture writes new files into a tmp sentiments dir."""
    _cache.clear()


def load_sentiment_file(
    occasion: str, voice: str, role: str, sentiments_dir: Path | None = None
) -> Sentiment:
    """Load one sentiment file, validating that its metadata matches
    the directory path it was found in.

    Cached: the second call with the same ``(occasion, voice, role)``
    returns the cached instance unless ``sentiments_dir`` is provided
    (test usage forces a fresh load).
    """
    cache_key = (occasion, voice, role)
    if sentiments_dir is None and cache_key in _cache:
        return _cache[cache_key]

    base = sentiments_dir or get_sentiments_dir()
    path = base / occasion / voice / f"{role}.yaml"
    if not path.exists():
        raise SentimentNotFoundError(
            f"no sentiment file at {path} "
            f"(occasion={occasion!r}, voice={voice!r}, role={role!r})"
        )

    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    sentiment = Sentiment.model_validate(raw)

    # Cross-check: file metadata must match directory placement so a
    # mis-filed file is loud, not silent.
    if sentiment.occasion != occasion:
        raise ValueError(
            f"{path}: file declares occasion={sentiment.occasion!r} but "
            f"lives under occasion={occasion!r}"
        )
    if sentiment.voice != voice:
        raise ValueError(
            f"{path}: file declares voice={sentiment.voice!r} but "
            f"lives under voice={voice!r}"
        )
    if sentiment.role != role:
        raise ValueError(
            f"{path}: file declares role={sentiment.role!r} but "
            f"lives under role={role!r}"
        )

    if sentiments_dir is None:
        _cache[cache_key] = sentiment
    return sentiment


# ---------------------------------------------------------------------------
# Public picker
# ---------------------------------------------------------------------------


def pick_sentiment(
    occasion: OccasionType | str,
    voice: str,
    role: str,
    *,
    seed: int | None = None,
    sentiments_dir: Path | None = None,
) -> str:
    """Return one sentiment line for the requested target.

    Args:
        occasion: ``OccasionType`` member or its string value.
        voice: One of :data:`VOICES`.
        role: One of :data:`ROLES`.
        seed: If provided, picks deterministically (same seed +
            same input → same line). Default ``None`` picks randomly
            using the global RNG so successive CLI runs vary.
        sentiments_dir: Override directory; only used by tests.

    Raises:
        ValueError: voice or role not in the recognized vocabulary.
        SentimentNotFoundError: no sentiment file for that combination.
    """
    if voice not in VOICES:
        raise ValueError(
            f"unknown voice {voice!r}. Available: {', '.join(VOICES)}"
        )
    if role not in ROLES:
        raise ValueError(
            f"unknown role {role!r}. Available: {', '.join(ROLES)}"
        )

    occasion_str = occasion.value if isinstance(occasion, OccasionType) else occasion
    sentiment = load_sentiment_file(occasion_str, voice, role, sentiments_dir)

    if seed is None:
        return random.choice(sentiment.sentiments)
    rng = random.Random(seed)
    return rng.choice(sentiment.sentiments)
