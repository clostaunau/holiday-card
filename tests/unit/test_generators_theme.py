"""``CardGenerator.create_card`` fails loud on an unknown theme (#60)."""

import pytest

from holiday_card.core.generators import CardGenerator
from holiday_card.core.themes import ThemeNotFoundError


def test_unknown_theme_raises() -> None:
    with pytest.raises(ThemeNotFoundError, match="nope"):
        CardGenerator().create_card("christmas-classic", theme_id="nope")


def test_known_theme_applies() -> None:
    card = CardGenerator().create_card("christmas-classic", theme_id="christmas-red-green")
    assert card.theme_id == "christmas-red-green"
