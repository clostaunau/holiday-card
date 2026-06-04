"""Hard-rail tests for AI imagery (Leapfrog 3 / consensus-ai-feature.md).

The panel's verdict (docs/industry-review/consensus-ai-feature.md, "The
hard rails" section) requires default-on refusal for sympathy-class
occasions, religious iconography, trademark/likeness prompts, and
photo-card replacement — overridable only via an explicit flag plus a
printed reason. These tests pin that gate.
"""

from __future__ import annotations

import pytest

from holiday_card.core.ai_rails import (
    RailViolation,
    ai_imagery_allowed,
    check_likeness,
    check_religious_iconography,
    check_trademarks,
    evaluate_rails,
)
from holiday_card.core.models import OccasionType


class TestOccasionGate:
    @pytest.mark.parametrize(
        "occasion",
        [
            OccasionType.SYMPATHY,
            OccasionType.CONDOLENCE,
            OccasionType.MISCARRIAGE,
            OccasionType.PET_LOSS,
        ],
    )
    def test_sympathy_class_occasions_refuse_ai(self, occasion: OccasionType) -> None:
        assert ai_imagery_allowed(occasion) is False

    @pytest.mark.parametrize(
        "occasion",
        [
            OccasionType.CHRISTMAS,
            OccasionType.BIRTHDAY,
            OccasionType.GENERIC,
        ],
    )
    def test_non_sympathy_occasions_allow_ai(self, occasion: OccasionType) -> None:
        assert ai_imagery_allowed(occasion) is True


class TestTrademarkBlocklist:
    def test_flags_mickey_mouse(self) -> None:
        assert "mickey mouse" in check_trademarks("a happy mickey mouse on a sled")

    def test_flags_are_case_insensitive(self) -> None:
        assert "disney" in check_trademarks("DISNEY castle at night")

    def test_flags_hyphenated_brand(self) -> None:
        assert "coca-cola" in check_trademarks("a coca-cola santa")

    def test_clean_prompt_has_no_trademark_hits(self) -> None:
        assert check_trademarks("a watercolor pine bough border in sage green") == []

    def test_does_not_false_positive_on_substring(self) -> None:
        # "marioness" must not trip "mario"; word boundaries only.
        assert check_trademarks("a marionette puppet") == []


class TestReligiousIconographyBlocklist:
    def test_flags_nativity(self) -> None:
        assert "nativity" in check_religious_iconography("a nativity scene with the manger")

    def test_flags_menorah(self) -> None:
        assert "menorah" in check_religious_iconography("a glowing menorah")

    def test_generic_winter_is_clean(self) -> None:
        # The panel explicitly carves out generic winter from Nativity.
        assert check_religious_iconography("snowy pine trees and a cardinal") == []


class TestLikenessBlocklist:
    def test_flags_photo_of_a_person(self) -> None:
        assert check_likeness("a photo of my grandmother smiling") != []

    def test_flags_named_public_figure(self) -> None:
        assert check_likeness("taylor swift waving") != []

    def test_abstract_motif_is_clean(self) -> None:
        assert check_likeness("an abstract geometric snowflake pattern") == []


class TestEvaluateRails:
    def test_clean_birthday_prompt_passes(self) -> None:
        violations = evaluate_rails(
            OccasionType.BIRTHDAY,
            "watercolor balloons in pastel colors",
        )
        assert violations == []

    def test_sympathy_occasion_produces_occasion_violation(self) -> None:
        violations = evaluate_rails(
            OccasionType.SYMPATHY,
            "a calm field of wildflowers",
        )
        assert any(v.category == "occasion" for v in violations)
        # Every violation carries a human-readable reason for the override prompt.
        assert all(v.reason for v in violations)

    def test_trademark_prompt_produces_trademark_violation(self) -> None:
        violations = evaluate_rails(
            OccasionType.CHRISTMAS,
            "mickey mouse in a santa hat",
        )
        assert any(v.category == "trademark" for v in violations)

    def test_multiple_rails_accumulate(self) -> None:
        violations = evaluate_rails(
            OccasionType.SYMPATHY,
            "a photo of jesus with mickey mouse",
        )
        categories = {v.category for v in violations}
        assert {"occasion", "religious_iconography", "trademark", "likeness"} <= categories

    def test_violation_is_a_dataclass_with_category_and_reason(self) -> None:
        v = RailViolation(category="occasion", reason="because", matched=["sympathy"])
        assert v.category == "occasion"
        assert v.reason == "because"
        assert v.matched == ["sympathy"]
