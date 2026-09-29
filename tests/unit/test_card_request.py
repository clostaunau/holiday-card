"""``core/card_request.py``: the one frozen request + builder behind the CLI (#78, D15).

One test per precedence rule 1-18 extracted from ``create()`` (numbered in
the test names), plus the model's shape (``extra="forbid"``, frozen). The
exit-2 messages asserted here are the ones the CLI printed on ``main``;
the CLI prefixes them with ``Error: ``.
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from holiday_card.core.card_request import (
    BuildReport,
    CardRequest,
    OutputPlan,
    build_card,
    build_card_with_report,
    plan_output,
    validation_message,
)
from holiday_card.core.export_targets import get_target
from holiday_card.core.generators import CardGenerator, PhotoSlotError
from holiday_card.core.images import ImageSourceError
from holiday_card.core.letter import LetterContent
from holiday_card.core.models import Card, FoldType, TextElement
from holiday_card.core.sentiments import pick_sentiment
from holiday_card.core.templates import load_template
from holiday_card.core.themes import discover_themes, load_theme
from holiday_card.renderers.svg_backend import SVGRenderer

NOW = datetime(2026, 9, 28, 13, 5, 9)
CLASSIC = "christmas-classic"
PLACEHOLDER_PHOTO = (
    Path(__file__).resolve().parents[2]
    / "src/holiday_card/data/templates/christmas/placeholder-photo.jpg"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _panel(position: str, texts: str = "") -> str:
    return textwrap.dedent(
        f"""
          - id: "{position}"
            position: "{position}"
            width: 4.25
            height: 5.5
        """
    ) + (textwrap.indent(texts, "  ") if texts else "")


def _text(content: str, element_id: str | None = None) -> str:
    id_line = f'    id: "{element_id}"\n' if element_id else ""
    return (
        "text_elements:\n"
        f"  - content: \"{content}\"\n"
        + id_line
        + "    x: 2.0\n    y: 3.0\n    width: 3.5\n    font_family: \"Lato\"\n    font_size: 14\n"
    )


def _write_template(
    root: Path,
    *,
    occasion_dir: str,
    template_id: str,
    occasion: str,
    front_texts: str = "",
    inside_left_texts: str = "",
    inside_right_texts: str = "",
) -> Path:
    """Write a minimal four-panel template and return the templates dir."""
    body = (
        f'id: "{template_id}"\nname: "Fixture"\noccasion: "{occasion}"\n'
        'fold_type: "half_fold"\npanels:\n'
        + _panel("front", front_texts)
        + _panel("back")
        + _panel("inside_left", inside_left_texts)
        + _panel("inside_right", inside_right_texts)
    )
    directory = root / "templates" / occasion_dir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{template_id}.yaml").write_text(body)
    return root / "templates"


def _front_texts(card: Card) -> list[TextElement]:
    return next(p for p in card.panels if p.position.value == "front").text_elements


def _inside_target(card: Card) -> tuple[str, TextElement]:
    """The one inside element that carries content (rule 16)."""
    hits = [
        (p.position.value, t)
        for p in card.panels
        if p.position.value in ("inside_left", "inside_right")
        for t in p.text_elements
        if t.content or t.rich_content is not None or t.letter_content is not None
    ]
    assert len(hits) == 1, hits
    return hits[0]


def _refused_request(**kwargs: object) -> str:
    with pytest.raises(ValidationError) as excinfo:
        CardRequest(**kwargs)  # type: ignore[arg-type]
    return validation_message(excinfo.value)


# ---------------------------------------------------------------------------
# Model shape
# ---------------------------------------------------------------------------


class TestCardRequestModel:
    def test_extra_keys_are_forbidden(self) -> None:
        with pytest.raises(ValidationError, match="colour"):
            CardRequest(template=CLASSIC, colour="red")  # type: ignore[call-arg]

    def test_is_frozen(self) -> None:
        request = CardRequest(template=CLASSIC)
        with pytest.raises(ValidationError):
            request.message = "hi"  # type: ignore[misc]

    def test_defaults(self) -> None:
        request = CardRequest(template=CLASSIC)
        assert request.model_dump() == {
            "template": CLASSIC,
            "message": None,
            "inside_message": None,
            "inside_markdown": None,
            "voice": None,
            "seed": None,
            "blank_inside": False,
            "salutation": None,
            "signoff": None,
            "signature": None,
            "postscript": None,
            "signature_font": None,
            "theme": None,
            "fold_type": None,
            "images": (),
            "output": None,
            "output_format": "auto",
            "export_for": "letter",
            "fold_marks": None,
            "panel_fit": None,
        }

    def test_images_are_a_tuple_of_paths(self) -> None:
        request = CardRequest(template=CLASSIC, images=[Path("a.jpg"), "b.png"])  # type: ignore[list-item]
        assert request.images == (Path("a.jpg"), Path("b.png"))

    def test_validation_message_unwraps_the_original_error(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            CardRequest(template=CLASSIC, seed=3)
        assert validation_message(excinfo.value) == "--seed only applies with --voice"

    def test_build_card_is_the_card_of_build_card_with_report(self) -> None:
        request = CardRequest(template=CLASSIC, message="Hi", inside_message="There")
        card = build_card(request)
        with_report, report = build_card_with_report(request)
        assert isinstance(report, BuildReport)
        volatile = {"id", "name", "created_at", "updated_at"}
        assert card.model_dump(exclude=volatile) == with_report.model_dump(exclude=volatile)


# ---------------------------------------------------------------------------
# Flag conflicts shipped by #60 (pure, so they live on the model)
# ---------------------------------------------------------------------------


class TestFlagConflicts:
    def test_blank_inside_with_inside_message(self) -> None:
        assert _refused_request(
            template=CLASSIC, blank_inside=True, inside_message="HI"
        ) == "--blank-inside cannot be combined with --inside-message"

    def test_blank_inside_with_inside_markdown(self) -> None:
        assert _refused_request(
            template=CLASSIC, blank_inside=True, inside_markdown="Hello **there**."
        ) == "--blank-inside cannot be combined with --inside-message-md"

    def test_seed_without_voice(self) -> None:
        assert _refused_request(template=CLASSIC, seed=7) == "--seed only applies with --voice"

    def test_signature_font_without_signature(self) -> None:
        assert _refused_request(
            template=CLASSIC, signature_font="Caveat"
        ) == "--signature-font requires --signature"


# ---------------------------------------------------------------------------
# Precedence rules 1-18
# ---------------------------------------------------------------------------


class TestPrecedenceRules:
    def test_rule_01_unknown_export_target_is_refused_first(self) -> None:
        # Both the target and the voice are bad: the target is reported.
        # ExportTargetNotFoundError is a KeyError, so its str() is quoted;
        # the CLI has always printed it that way and the text is pinned.
        assert _refused_request(
            template=CLASSIC, export_for="nope", voice="yelling"
        ) == "\"unknown export target 'nope'. Available: letter, moo-a6, per-panel-pdf\""

    def test_rule_01_known_target_lands_on_the_plan(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC, export_for="moo-a6"), now=NOW)
        assert isinstance(plan, OutputPlan)
        assert plan.target is get_target("moo-a6")

    def test_rule_02_unknown_voice_lists_voices(self) -> None:
        assert _refused_request(template=CLASSIC, voice="yelling") == (
            "Unknown --voice value 'yelling'. "
            "Available: warm, witty, spare, devotional, irreverent"
        )

    def test_rule_03_inside_message_and_markdown_are_mutually_exclusive(self) -> None:
        assert _refused_request(
            template=CLASSIC, inside_message="a", inside_markdown="b"
        ) == "--inside-message and --inside-message-md are mutually exclusive (pick one)."

    @pytest.mark.parametrize(
        "part", ["salutation", "signoff", "signature", "postscript"]
    )
    def test_rule_04_letter_part_with_markdown_is_refused(self, part: str) -> None:
        assert _refused_request(template=CLASSIC, inside_markdown="Hi", **{part: "x"}) == (
            "--inside-message-md cannot be combined with "
            "--salutation / --signoff / --signature / --ps "
            "(letter parts use a separate authoring surface). "
            "Either drop the Markdown file or move the letter "
            "structure into the body of the Markdown."
        )

    def test_rule_05_unparsable_markdown_is_refused_before_building(self) -> None:
        # The CLI reads the file; the request refuses text that won't parse.
        message = _refused_request(template=CLASSIC, inside_markdown="   \n\n   ")
        assert "empty" in message.lower()

    def test_rule_06_explicit_format_wins(self) -> None:
        plan = plan_output(
            CardRequest(template=CLASSIC, output=Path("card"), output_format="svg"), now=NOW
        )
        assert plan.output_format == "svg"
        assert plan.path == Path("card.svg")

    def test_rule_06_auto_infers_from_output_suffix(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC, output=Path("x.SVG")), now=NOW)
        assert plan.output_format == "svg"

    def test_rule_06_default_is_pdf(self) -> None:
        assert plan_output(CardRequest(template=CLASSIC), now=NOW).output_format == "pdf"

    def test_rule_06_format_is_case_insensitive(self) -> None:
        assert CardRequest(template=CLASSIC, output_format="PDF").output_format == "pdf"  # type: ignore[arg-type]

    def test_rule_06_other_format_is_refused(self) -> None:
        assert _refused_request(template=CLASSIC, output_format="png") == (
            "--format must be one of ('pdf', 'svg') or 'auto', got 'png'"
        )

    def test_rule_07_default_output_is_timestamped_under_output(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC), now=NOW)
        assert plan.path == Path("output") / "christmas-classic-2026-09-28_130509.pdf"

    def test_rule_07_default_output_follows_the_format(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC, output_format="svg"), now=NOW)
        assert plan.path == Path("output") / "christmas-classic-2026-09-28_130509.svg"

    def test_rule_07_default_output_is_a_directory_for_per_panel(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC, export_for="moo-a6"), now=NOW)
        assert plan.path == Path("output") / "christmas-classic-2026-09-28_130509"

    def test_rule_08_suffixless_output_gets_the_extension(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC, output=Path("out/card")), now=NOW)
        assert plan.path == Path("out/card.pdf")

    def test_rule_08_matching_suffix_is_kept(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC, output=Path("card.pdf")), now=NOW)
        assert plan.path == Path("card.pdf")

    def test_rule_08_format_conflicting_with_suffix_is_refused(self) -> None:
        request = CardRequest(template=CLASSIC, output=Path("x.svg"), output_format="pdf")
        with pytest.raises(ValueError, match=r"^--format pdf conflicts with output extension '\.svg'$"):
            plan_output(request, now=NOW)

    def test_rule_08_unsupported_suffix_is_refused(self) -> None:
        request = CardRequest(template=CLASSIC, output=Path("x.docx"))
        with pytest.raises(
            ValueError, match=r"^unsupported output extension '\.docx' \(use \.pdf or \.svg\)$"
        ):
            plan_output(request, now=NOW)

    def test_rule_08_png_suffix_points_at_preview(self) -> None:
        request = CardRequest(template=CLASSIC, output=Path("card.png"))
        with pytest.raises(ValueError) as excinfo:
            plan_output(request, now=NOW)
        assert str(excinfo.value) == (
            "unsupported output extension '.png' "
            "(use .pdf or .svg; use 'holiday-card preview' for PNG)"
        )

    def test_rule_08_per_panel_target_needs_a_directory(self, tmp_path: Path) -> None:
        request = CardRequest(
            template=CLASSIC, export_for="moo-a6", output=tmp_path / "single.pdf"
        )
        with pytest.raises(ValueError) as excinfo:
            plan_output(request, now=NOW)
        assert str(excinfo.value) == (
            "--export-for moo-a6 writes one file per panel; "
            f"-o must be a directory, not {str(tmp_path / 'single.pdf')!r}"
        )

    def test_rule_08_per_panel_target_accepts_an_existing_dotted_directory(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "moo.v2").mkdir()
        request = CardRequest(
            template=CLASSIC, export_for="per-panel-pdf", output=tmp_path / "moo.v2"
        )
        assert plan_output(request, now=NOW).path == tmp_path / "moo.v2"

    def test_rule_09_invalid_fold_type_lists_the_valid_values(self) -> None:
        assert _refused_request(template=CLASSIC, fold_type="octa_fold") == (
            "Invalid fold type 'octa_fold'. Valid options: half_fold, quarter_fold, tri_fold"
        )

    def test_rule_09_fold_type_string_becomes_the_enum(self) -> None:
        assert CardRequest(template=CLASSIC, fold_type="quarter_fold").fold_type is FoldType.QUARTER_FOLD  # type: ignore[arg-type]

    def test_rule_09_fold_type_defaults_to_the_template(self) -> None:
        card = build_card(CardRequest(template=CLASSIC))
        assert card.fold_type is load_template(CLASSIC).fold_type

    def test_rule_09_fold_type_override_wins(self) -> None:
        card = build_card(CardRequest(template=CLASSIC, fold_type=FoldType.QUARTER_FOLD))
        assert card.fold_type is FoldType.QUARTER_FOLD

    def test_rule_09_fold_type_must_fit_the_template_panels(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            build_card(CardRequest(template=CLASSIC, fold_type=FoldType.TRI_FOLD))
        assert str(excinfo.value) == (
            "fold type 'tri_fold' needs panels left/center/right; "
            "template has front/back/inside_left/inside_right"
        )

    def test_rule_10_missing_image_is_refused(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-such-image.jpg"
        with pytest.raises(ImageSourceError, match="not found"):
            build_card(CardRequest(template="christmas-family-photo", images=(missing,)))

    def test_rule_10_image_fills_the_photo_slot(self, tmp_path: Path) -> None:
        photo = tmp_path / "me.jpg"
        photo.write_bytes(PLACEHOLDER_PHOTO.read_bytes())
        card = build_card(CardRequest(template="christmas-family-photo", images=(photo,)))
        slotted = [e for p in card.panels for e in p.image_elements if e.slot == "photo"]
        assert slotted and all(e.source_path == str(photo.resolve()) for e in slotted)

    def test_rule_10_image_on_a_template_without_slots_is_refused(self) -> None:
        with pytest.raises(PhotoSlotError, match="has no photo slot"):
            build_card(CardRequest(template=CLASSIC, images=(PLACEHOLDER_PHOTO,)))

    def test_rule_11_voice_fills_both_slots_with_the_seed(self) -> None:
        card, report = build_card_with_report(CardRequest(template=CLASSIC, voice="warm", seed=3))
        cover = pick_sentiment("christmas", "warm", "cover", seed=3)
        inside = pick_sentiment("christmas", "warm", "inside", seed=3)
        assert (report.picked_cover, report.picked_inside) == (cover, inside)
        assert _front_texts(card)[0].content == cover
        assert _inside_target(card)[1].content == inside
        assert report.inside_mode == "plain"

    def test_rule_11_explicit_message_beats_the_voice_cover(self) -> None:
        card, report = build_card_with_report(
            CardRequest(template=CLASSIC, voice="warm", seed=3, message="Hi")
        )
        assert report.picked_cover is None
        assert _front_texts(card)[0].content == "Hi"
        assert report.picked_inside == pick_sentiment("christmas", "warm", "inside", seed=3)

    def test_rule_11_explicit_inside_beats_the_voice_inside(self) -> None:
        card, report = build_card_with_report(
            CardRequest(template=CLASSIC, voice="warm", seed=3, inside_message="Body")
        )
        assert report.picked_inside is None
        assert _inside_target(card)[1].content == "Body"

    def test_rule_11_blank_inside_skips_the_voice_inside(self) -> None:
        _, report = build_card_with_report(
            CardRequest(template=CLASSIC, voice="warm", seed=3, blank_inside=True)
        )
        assert report.picked_cover is not None
        assert report.picked_inside is None

    def test_rule_11_voice_not_shipped_for_the_occasion(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            build_card(CardRequest(template="sympathy-spare", voice="witty"))
        assert str(excinfo.value) == (
            "voice 'witty' is not available for occasion 'sympathy'. "
            "Available: devotional, spare, warm"
        )

    def test_rule_11_occasion_comes_from_the_template_not_its_directory(
        self, tmp_path: Path
    ) -> None:
        # A christmas-named directory holding a sympathy template: the
        # voice check must use Template.occasion.
        templates_dir = _write_template(
            tmp_path, occasion_dir="christmas", template_id="odd", occasion="sympathy"
        )
        with pytest.raises(ValueError, match="not available for occasion 'sympathy'"):
            build_card(CardRequest(template="odd", voice="witty"), templates_dir=templates_dir)

    def test_rule_11_missing_role_file_names_voice_role_and_occasion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from holiday_card.core.sentiments import get_sentiments_dir, reset_cache

        lib = tmp_path / "sentiments"
        (lib / "christmas" / "warm").mkdir(parents=True)
        (lib / "christmas" / "warm" / "cover.yaml").write_text(
            "voice: warm\noccasion: christmas\nrole: cover\nsentiments: [Hi]\n"
        )
        monkeypatch.setenv("HOLIDAY_CARD_SENTIMENTS", str(lib))
        reset_cache()
        try:
            with pytest.raises(ValueError) as excinfo:
                build_card(CardRequest(template=CLASSIC, voice="warm"))
        finally:
            reset_cache()
        assert str(excinfo.value) == (
            "voice 'warm' has no inside sentiment for occasion 'christmas'"
        )
        assert str(get_sentiments_dir()) not in str(excinfo.value)

    def test_rule_12_blank_inside_clears_the_inside_text(self) -> None:
        card, report = build_card_with_report(CardRequest(template=CLASSIC, blank_inside=True))
        inside = [
            t
            for p in card.panels
            if p.position.value in ("inside_left", "inside_right")
            for t in p.text_elements
        ]
        assert inside and all(t.content == "" for t in inside)
        assert report.inside_mode == "blank"

    def test_rule_13_letter_parts_wrap_the_effective_inside_as_body(self) -> None:
        card, report = build_card_with_report(
            CardRequest(
                template=CLASSIC,
                inside_message="Body text",
                salutation="Dear A,",
                signoff="Love,",
                signature="C",
                postscript="PS hi",
                signature_font="Caveat",
            )
        )
        _, target = _inside_target(card)
        assert target.content == ""
        assert target.rich_content is None
        assert target.letter_content == LetterContent(
            salutation="Dear A,",
            body="Body text",
            signoff="Love,",
            signature="C",
            postscript="PS hi",
            signature_font_family="Caveat",
        )
        assert report.inside_mode == "letter"

    def test_rule_13_letter_body_is_the_voice_pick(self) -> None:
        card, report = build_card_with_report(
            CardRequest(template=CLASSIC, voice="warm", seed=3, signature="C")
        )
        _, target = _inside_target(card)
        assert target.letter_content is not None
        assert target.letter_content.body == report.picked_inside

    def test_rule_13_letter_with_blank_inside_has_an_empty_body(self) -> None:
        card, report = build_card_with_report(
            CardRequest(template=CLASSIC, blank_inside=True, signature="C")
        )
        _, target = _inside_target(card)
        assert target.letter_content is not None
        assert target.letter_content.body == ""
        assert report.inside_mode == "letter"

    def test_rule_14_markdown_becomes_rich_content(self) -> None:
        card, report = build_card_with_report(
            CardRequest(template=CLASSIC, inside_markdown="Hello **there**.\n\nBye.")
        )
        _, target = _inside_target(card)
        assert target.content == ""
        assert target.letter_content is None
        assert target.rich_content is not None
        assert len(target.rich_content.paragraphs) == 2
        assert report.inside_mode == "markdown"

    def test_rule_14_markdown_beats_the_voice_inside(self) -> None:
        card, report = build_card_with_report(
            CardRequest(template=CLASSIC, voice="warm", seed=3, inside_markdown="Hi")
        )
        _, target = _inside_target(card)
        assert target.rich_content is not None
        assert target.content == ""
        assert report.picked_inside == pick_sentiment("christmas", "warm", "inside", seed=3)

    def test_rule_15_front_message_targets_the_greeting_element(self) -> None:
        card = build_card(CardRequest(template=CLASSIC, message="Hi"))
        greeting = [t for t in _front_texts(card) if t.id == "greeting"]
        assert [t.content for t in greeting] == ["Hi"]

    def test_rule_15_front_message_falls_back_to_the_first_front_text(
        self, tmp_path: Path
    ) -> None:
        templates_dir = _write_template(
            tmp_path,
            occasion_dir="generic",
            template_id="nogreeting",
            occasion="generic",
            front_texts=_text("one", "first") + _text("two").removeprefix("text_elements:\n"),
        )
        card = build_card(CardRequest(template="nogreeting", message="Hi"), templates_dir=templates_dir)
        assert [t.content for t in _front_texts(card)] == ["Hi", "two"]

    def test_rule_15_front_message_auto_adds_a_lato_element(self, tmp_path: Path) -> None:
        templates_dir = _write_template(
            tmp_path, occasion_dir="generic", template_id="nofront", occasion="generic"
        )
        card = build_card(CardRequest(template="nofront", message="Hi"), templates_dir=templates_dir)
        (added,) = _front_texts(card)
        assert (added.content, added.font_family, added.font_size) == ("Hi", "Lato", 24)

    def test_rule_15_no_message_leaves_the_template_greeting(self) -> None:
        card = build_card(CardRequest(template=CLASSIC))
        template_greeting = next(
            t.content
            for p in load_template(CLASSIC).panels
            if p.position.value == "front"
            for t in p.text_elements
            if t.id == "greeting"
        )
        assert _front_texts(card)[0].content == template_greeting

    def test_rule_16_inside_targets_the_message_element_on_inside_right(self) -> None:
        card = build_card(CardRequest(template=CLASSIC, inside_message="Body"))
        position, target = _inside_target(card)
        assert (position, target.id) == ("inside_right", "message")

    def test_rule_16_inside_targets_the_message_element_on_inside_left(
        self, tmp_path: Path
    ) -> None:
        templates_dir = _write_template(
            tmp_path,
            occasion_dir="generic",
            template_id="leftmsg",
            occasion="generic",
            inside_left_texts=_text("", "message"),
            inside_right_texts=_text("", "other"),
        )
        card = build_card(CardRequest(template="leftmsg", inside_message="Body"), templates_dir=templates_dir)
        position, target = _inside_target(card)
        assert (position, target.id, target.content) == ("inside_left", "message", "Body")

    def test_rule_16_inside_falls_back_to_the_first_inside_text(self, tmp_path: Path) -> None:
        templates_dir = _write_template(
            tmp_path,
            occasion_dir="generic",
            template_id="noid",
            occasion="generic",
            inside_left_texts=_text("", "left"),
            inside_right_texts=_text("", "right"),
        )
        card = build_card(CardRequest(template="noid", inside_message="Body"), templates_dir=templates_dir)
        position, target = _inside_target(card)
        assert (position, target.id) == ("inside_right", "right")

    def test_rule_16_inside_auto_adds_a_lato_element_on_inside_left(self, tmp_path: Path) -> None:
        templates_dir = _write_template(
            tmp_path, occasion_dir="generic", template_id="noinside", occasion="generic"
        )
        card = build_card(CardRequest(template="noinside", inside_message="Body"), templates_dir=templates_dir)
        position, target = _inside_target(card)
        assert (position, target.content, target.font_family) == ("inside_left", "Body", "Lato")

    def test_rule_17_theme_defaults_to_the_template_theme(self) -> None:
        card = build_card(CardRequest(template=CLASSIC))
        assert card.theme_id == load_template(CLASSIC).default_theme_id

    def test_rule_17_theme_overrides_text_colors_after_messages(self) -> None:
        theme = load_theme("christmas-red-green")
        card = build_card(CardRequest(template=CLASSIC, theme="christmas-red-green", message="Hi"))
        assert card.theme_id == "christmas-red-green"
        front = _front_texts(card)[0]
        assert (front.content, front.color) == ("Hi", theme.background)

    def test_rule_17_unknown_theme_lists_the_theme_ids(self) -> None:
        ids = sorted(t["id"] for t in discover_themes())
        with pytest.raises(ValueError) as excinfo:
            build_card(CardRequest(template=CLASSIC, theme="nope"))
        assert str(excinfo.value) == "Unknown theme 'nope'. Available: " + ", ".join(ids)

    @pytest.mark.parametrize(
        ("export_for", "dashed_lines"), [("letter", True), ("per-panel-pdf", False)]
    )
    def test_rule_18_fold_marks_none_means_the_target_default(
        self, tmp_path: Path, export_for: str, dashed_lines: bool
    ) -> None:
        request = CardRequest(
            template=CLASSIC, export_for=export_for, output=tmp_path / "out", output_format="svg"
        )
        assert request.fold_marks is None
        plan = plan_output(request, now=NOW)
        written = CardGenerator(renderer=SVGRenderer()).generate(
            build_card(request), plan.path, plan.target, emit_fold_lines=request.fold_marks
        )
        svg = "".join(p.read_text() for p in written)
        assert ("stroke-dasharray" in svg) is dashed_lines

    def test_template_mode_when_nothing_touches_the_inside(self) -> None:
        _, report = build_card_with_report(CardRequest(template=CLASSIC))
        assert report == BuildReport(picked_cover=None, picked_inside=None, inside_mode="template")


class TestPanelFit:
    """--panel-fit only applies to targets that fit panels (#73, D4)."""

    def test_default_keeps_the_registry_target(self) -> None:
        plan = plan_output(CardRequest(template=CLASSIC, export_for="moo-a6"), now=NOW)
        assert plan.target.panel_fit == "fill"

    def test_letterbox_override_lands_on_the_plan_target(self) -> None:
        plan = plan_output(
            CardRequest(template=CLASSIC, export_for="moo-a6", panel_fit="letterbox"), now=NOW,
        )
        assert plan.target.panel_fit == "letterbox"
        assert plan.target.name == "moo-a6"

    @pytest.mark.parametrize("target", ["letter", "per-panel-pdf"])
    def test_panel_fit_on_a_native_target_is_refused(self, target: str) -> None:
        assert _refused_request(
            template=CLASSIC, export_for=target, panel_fit="letterbox"
        ) == (
            f"--panel-fit only applies to targets that scale panels to a fixed trim "
            f"(moo-a6); --export-for {target} renders panels at their native size"
        )

    def test_unknown_panel_fit_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            CardRequest(template=CLASSIC, export_for="moo-a6", panel_fit="stretch")  # type: ignore[arg-type]
