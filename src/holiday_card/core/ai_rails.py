"""Hard category rails for AI imagery (Leapfrog 3).

The industry panel (``docs/industry-review/consensus-ai-feature.md``,
section "The hard rails") requires default-on refusal for a fixed set of
categories where AI-composed imagery is a predictable failure mode:

* **Sympathy-class occasions** — sympathy / condolence / miscarriage /
  pet_loss. "A small additional cruelty on top of the loss."
* **Religious iconography** — Nativity, menorah, crucifix, etc. The
  models hallucinate wrong-branched menorahs and six-fingered Jesus.
* **Trademark / brand prompts** — Disney/Marvel/Pokémon/Coca-Cola. The
  project must not be the vector for a DMCA action.
* **Recognizable likenesses & photo-card replacement** — a card's photo
  is meant to be the actual photo of the actual family.

Each check is a pure function over the prompt text (no network, no
model). ``evaluate_rails`` composes them into a list of
:class:`RailViolation`. The CLI refuses by default and only proceeds
when ``--i-know-what-im-doing`` is passed, after printing every reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from holiday_card.core.models import OccasionType

__all__ = [
    "RailViolation",
    "AI_DISALLOWED_OCCASIONS",
    "TRADEMARK_BLOCKLIST",
    "RELIGIOUS_ICONOGRAPHY_TERMS",
    "LIKENESS_TERMS",
    "ai_imagery_allowed",
    "check_trademarks",
    "check_religious_iconography",
    "check_likeness",
    "evaluate_rails",
]


@dataclass(frozen=True)
class RailViolation:
    """One reason AI imagery is refused for a given request.

    ``category`` is a stable machine key (``"occasion"``,
    ``"trademark"``, ``"religious_iconography"``, ``"likeness"``).
    ``reason`` is a human-readable sentence printed in the override
    prompt. ``matched`` lists the specific terms that tripped the rail.
    """

    category: str
    reason: str
    matched: list[str] = field(default_factory=list)


# Sympathy-class occasions: AI imagery is refused by default. These are
# the L2 taxonomy categories that exist precisely so this gate has
# something to refuse against (see models.OccasionType).
AI_DISALLOWED_OCCASIONS: frozenset[OccasionType] = frozenset(
    {
        OccasionType.SYMPATHY,
        OccasionType.CONDOLENCE,
        OccasionType.MISCARRIAGE,
        OccasionType.PET_LOSS,
    }
)

# Curated (non-exhaustive) trademark / brand blocklist. The panel calls
# for ~200 names; this hand-curated starter set covers the highest-risk
# franchises. Extend freely — matching is word-boundary, case-insensitive.
TRADEMARK_BLOCKLIST: frozenset[str] = frozenset(
    {
        "disney",
        "mickey mouse",
        "minnie mouse",
        "marvel",
        "spider-man",
        "spiderman",
        "iron man",
        "the avengers",
        "star wars",
        "baby yoda",
        "grogu",
        "darth vader",
        "pokemon",
        "pokémon",
        "pikachu",
        "nintendo",
        "super mario",
        "mario",
        "luigi",
        "zelda",
        "coca-cola",
        "coca cola",
        "pepsi",
        "nike",
        "adidas",
        "batman",
        "superman",
        "wonder woman",
        "harry potter",
        "hogwarts",
        "hello kitty",
        "sanrio",
        "barbie",
        "lego",
        "minecraft",
        "fortnite",
        "spongebob",
        "peppa pig",
        "paw patrol",
        "frozen elsa",
        "elsa frozen",
        "winnie the pooh",
        "snoopy",
        "peanuts charlie brown",
        "the grinch",
        "dr seuss",
        "playstation",
        "xbox",
        "starbucks",
    }
)

# Religious iconography terms. Generic winter / seasonal imagery is
# explicitly carved out by the panel; only depictions with religious
# figures or ritual objects trip this rail.
RELIGIOUS_ICONOGRAPHY_TERMS: frozenset[str] = frozenset(
    {
        "nativity",
        "manger",
        "baby jesus",
        "jesus",
        "christ",
        "crucifix",
        "crucifixion",
        "the cross",
        "virgin mary",
        "madonna and child",
        "menorah",
        "dreidel",
        "star of david",
        "torah",
        "buddha",
        "ganesh",
        "ganesha",
        "diya",
        "diwali deity",
        "lakshmi",
        "eid",
        "ramadan",
        "quran",
        "allah",
        "day of the dead",
        "dia de los muertos",
        "día de los muertos",
        "calavera",
        "saint",
        "angel gabriel",
        "the three wise men",
    }
)

# Likeness / photo-replacement terms. Catches both named public figures
# and prompts that ask for a depiction of a specific real person (the
# photo-card replacement failure mode).
LIKENESS_TERMS: frozenset[str] = frozenset(
    {
        # Patterns that request a real person's depiction.
        "photo of",
        "portrait of",
        "headshot",
        "selfie",
        "likeness of",
        "picture of my",
        "photo of my",
        "real person",
        "my grandmother",
        "my grandfather",
        "my mother",
        "my father",
        "my family",
        "family photo",
        # A small set of named public figures (illustrative, not complete).
        "taylor swift",
        "elon musk",
        "donald trump",
        "joe biden",
        "the president",
        "the queen",
        "beyonce",
        "beyoncé",
        "kim kardashian",
        "cristiano ronaldo",
        "lionel messi",
    }
)


def ai_imagery_allowed(occasion: OccasionType) -> bool:
    """Return ``False`` for occasions on the sympathy-class hard rail."""
    return occasion not in AI_DISALLOWED_OCCASIONS


def _find_terms(prompt: str, terms: frozenset[str]) -> list[str]:
    """Return blocklist ``terms`` that appear in ``prompt`` (word-boundary).

    Matching is case-insensitive and anchored on word boundaries so that
    ``"mario"`` does not trip on ``"marionette"``. Multi-word and
    hyphenated terms match as literal phrases.
    """
    lowered = prompt.lower()
    hits: list[str] = []
    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, lowered):
            hits.append(term)
    return sorted(hits)


def check_trademarks(prompt: str) -> list[str]:
    """Return trademark/brand terms found in ``prompt``."""
    return _find_terms(prompt, TRADEMARK_BLOCKLIST)


def check_religious_iconography(prompt: str) -> list[str]:
    """Return religious-iconography terms found in ``prompt``."""
    return _find_terms(prompt, RELIGIOUS_ICONOGRAPHY_TERMS)


def check_likeness(prompt: str) -> list[str]:
    """Return likeness / photo-replacement terms found in ``prompt``."""
    return _find_terms(prompt, LIKENESS_TERMS)


def evaluate_rails(occasion: OccasionType, prompt: str) -> list[RailViolation]:
    """Evaluate every hard rail for a generation request.

    Returns an (possibly empty) list of :class:`RailViolation`. An empty
    list means the request is clear of all rails. The CLI refuses when
    the list is non-empty unless the user passes the override flag.
    """
    violations: list[RailViolation] = []

    if not ai_imagery_allowed(occasion):
        violations.append(
            RailViolation(
                category="occasion",
                reason=(
                    f"{occasion.value!r} is a sympathy-class occasion; AI "
                    "imagery composed by no one is a small additional cruelty "
                    "on top of the loss."
                ),
                matched=[occasion.value],
            )
        )

    trademark_hits = check_trademarks(prompt)
    if trademark_hits:
        violations.append(
            RailViolation(
                category="trademark",
                reason=(
                    "prompt names trademarked / brand material "
                    f"({', '.join(trademark_hits)}); generating it risks a "
                    "DMCA action against anyone who prints or sells the card."
                ),
                matched=trademark_hits,
            )
        )

    religious_hits = check_religious_iconography(prompt)
    if religious_hits:
        violations.append(
            RailViolation(
                category="religious_iconography",
                reason=(
                    "prompt requests religious iconography "
                    f"({', '.join(religious_hits)}); models hallucinate "
                    "wrong-branched menorahs and six-fingered figures."
                ),
                matched=religious_hits,
            )
        )

    likeness_hits = check_likeness(prompt)
    if likeness_hits:
        violations.append(
            RailViolation(
                category="likeness",
                reason=(
                    "prompt requests a recognizable likeness or a photo "
                    f"replacement ({', '.join(likeness_hits)}); a photo card's "
                    "point is the actual photo of the actual person."
                ),
                matched=likeness_hits,
            )
        )

    return violations
