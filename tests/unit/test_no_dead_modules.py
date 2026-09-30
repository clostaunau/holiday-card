"""Guard: dead modules and APIs deleted by #83 stay deleted (D17)."""

import importlib

import pytest

from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import TextElement

DELETED_MODULES = [
    "holiday_card.core.validators",
    "holiday_card.utils.gradient_utils",
    "holiday_card.renderers.image_effects",
    "holiday_card.utils.validators",
]


@pytest.mark.parametrize("name", DELETED_MODULES)
def test_dead_module_is_gone(name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)


@pytest.mark.parametrize(
    "owner, attr",
    [
        (TextElement, "set_adjustment_result"),
        (TextElement, "get_adjustment_result"),
        (CardGenerator, "create_and_generate"),
        (CardGenerator, "generate_pdf"),
    ],
)
def test_dead_api_is_gone(owner: type, attr: str) -> None:
    assert not hasattr(owner, attr)
