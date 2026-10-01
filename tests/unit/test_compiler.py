"""Tests for ``core.compiler.compile_card``.

Two flavors:

* **Structural unit tests** assert specific properties of the emitted
  command list (page bounds are open, panels are wrapped in groups,
  fold lines match fold type, ``assert_balanced`` passes, unsupported
  features raise loudly).
* **Snapshot tests** for shipped templates that use only the supported
  feature subset. The snapshot file is committed; any compiler change
  shows up as a JSON diff for human review. Regenerate with
  ``UPDATE_COMPILER_SNAPSHOTS=1 pytest tests/unit/test_compiler.py``.

This PR's compiler covers backgrounds, borders, basic shapes
(Rectangle/Circle/Triangle/Star/Line with solid fills only), text via
``core.text_fitting``, and fold lines. Templates using images, gradients,
patterns, clip masks, SVG paths, or decorative elements raise
``UnsupportedFeatureError`` — that's by design (Wave 2 follow-up PRs lift
each one in turn).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from holiday_card.core.compiler import (
    CompileContext,
    SafeZoneWarning,
    UnknownFontError,
    UnsupportedFeatureError,
    compile_card,
)
from holiday_card.core.generators import CardGenerator
from holiday_card.core.images import ImageSourceError
from holiday_card.core.models import (
    Card,
    Color,
    FoldType,
    Panel,
    PanelPosition,
    SVGPath,
    TextElement,
)
from holiday_card.core.render_ir import (
    BeginGroup,
    BeginPage,
    DrawFoldLine,
    DrawShape,
    DrawText,
    EndGroup,
    EndPage,
    RectGeom,
    SetMetadata,
    assert_balanced,
)
from holiday_card.utils.measurements import PageGeometry

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
UPDATE_SNAPSHOTS = os.environ.get("UPDATE_COMPILER_SNAPSHOTS") == "1"

# Templates whose compiled IR is snapshot-stable across machines.
# Templates with non-empty ``image_elements: source_path: ...`` are
# excluded because the loader resolves the source to an absolute
# path inside the installed template dir, and a committed snapshot would carry
# ``/Users/<dev>/...`` — diff noise on every contributor's machine
# and a CI failure as soon as the generating machine differs from the
# committing machine. The exclusion covers photo-ornament,
# family-photo, mothers-day-photo, birthday-photo, AND
# holiday-masterpiece (its decorative ``image_elements`` carry a
# placeholder-photo.jpg path even though the template's identity is the
# SVGPath illustration, not the photo). These templates have
# coverage via test_png_backend.py + test_svg_backend.py + the
# visual-regression suite instead.
SUPPORTED_SNAPSHOT_TEMPLATES = (
    "christmas-classic",
    "christmas-geometric",
    "christmas-modern",
    "christmas-artist",
    "christmas-festive-stripes",
    "christmas-holly-wreath",
    "christmas-metallic-ornaments",
    "christmas-winter-sky",
    "birthday-balloons",
    "hanukkah-menorah",
    "generic-celebration",
    "mothers-day",
    "sympathy-spare",
    "condolence-spare",
    "miscarriage-spare",
    "pet-loss-spare",
)


# Sympathy-class templates (panel L2 taxonomy). One restrained template
# per occasion; each compiles via the IR pipeline like the rest.
SYMPATHY_CLASS_TEMPLATES = (
    "sympathy-spare",
    "condolence-spare",
    "miscarriage-spare",
    "pet-loss-spare",
)


# ---------------------------------------------------------------------------
# Structural unit tests (don't require any specific template — build the
# Card directly via CardGenerator on a known-supported template)
# ---------------------------------------------------------------------------


@pytest.fixture
def classic_card() -> object:
    return CardGenerator().create_card(
        template_id="christmas-classic", message="Merry Christmas!"
    )


class TestStructure:
    def test_first_command_opens_a_page(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        assert isinstance(commands[0], BeginPage)
        assert commands[0].width > 0 and commands[0].height > 0

    def test_last_command_closes_the_page(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        assert isinstance(commands[-1], EndPage)

    def test_emits_metadata_for_template_and_fold(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        meta = [c for c in commands if isinstance(c, SetMetadata)]
        keys = {m.key for m in meta}
        assert "template_id" in keys
        assert "fold_type" in keys

    def test_each_panel_is_wrapped_in_a_group(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        begins = sum(1 for c in commands if isinstance(c, BeginGroup))
        ends = sum(1 for c in commands if isinstance(c, EndGroup))
        # christmas-classic is a half-fold card with 4 panels; the compiler
        # opens one group per panel.
        assert begins == ends == len(classic_card.panels)  # type: ignore[attr-defined]

    @pytest.mark.parametrize("fold_type", [FoldType.HALF_FOLD, FoldType.QUARTER_FOLD])
    def test_letter_fold_types_emit_both_fold_lines(
        self, classic_card: object, fold_type: FoldType
    ) -> None:
        """A 4-up single-sided letter sheet needs two folds (#58). The
        legacy ``half_fold`` spelling gets the same marks as ``quarter_fold``."""
        card = classic_card.model_copy(update={"fold_type": fold_type})  # type: ignore[attr-defined]
        commands = compile_card(card)
        folds = [c for c in commands if isinstance(c, DrawFoldLine)]
        assert len(folds) == 2
        orientations = {
            "horizontal" if f.start.y == f.end.y else "vertical" for f in folds
        }
        assert orientations == {"horizontal", "vertical"}

    def test_assert_balanced_passes_on_compiled_output(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        assert_balanced(commands)  # would raise on imbalance

    def test_text_lines_get_drawn(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        texts = [c for c in commands if isinstance(c, DrawText)]
        # christmas-classic ships with at least the front greeting + the
        # inside message.
        assert len(texts) >= 2
        assert any("Merry Christmas" in t.run.text for t in texts)

    def test_panel_backgrounds_become_draw_shapes(self, classic_card: object) -> None:
        commands = compile_card(classic_card)  # type: ignore[arg-type]
        # All four panels in christmas-classic declare a background_color.
        rect_fills = [
            c for c in commands
            if isinstance(c, DrawShape) and c.geometry.kind == "rect" and c.fill is not None
        ]
        assert len(rect_fills) >= 4


# ---------------------------------------------------------------------------
# Watch-dog: a card with an unsupported feature must raise loudly so we
# never silently ship a half-compiled PDF. Every shipped template compiles,
# so the watch-dog adds a known-unsupported feature (an SVG arc) to one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path_data", ["M 0 0 A 5 5 0 0 1 10 10", "M 0 0 a 5 5 0 0 1 10 10 Z"])
def test_unsupported_features_raise_loudly(path_data: str) -> None:
    card = CardGenerator().create_card(template_id="christmas-classic")
    compile_card(card)  # the unmodified card compiles
    front = next(p for p in card.panels if p.position == PanelPosition.FRONT)
    front.shape_elements.append(SVGPath(id="arc", path_data=path_data, x=1.0, y=1.0))
    with pytest.raises(UnsupportedFeatureError, match="arc"):
        compile_card(card)


@pytest.mark.parametrize("template_id", SYMPATHY_CLASS_TEMPLATES)
def test_sympathy_class_template_compiles_cleanly(template_id: str) -> None:
    """Every sympathy-class template (panel L2 taxonomy) compiles via
    the IR pipeline without raising UnsupportedFeatureError."""
    card = CardGenerator().create_card(template_id=template_id)
    commands = compile_card(card)
    assert any(isinstance(c, BeginPage) for c in commands)
    assert any(isinstance(c, EndPage) for c in commands)
    assert_balanced(commands)


# ---------------------------------------------------------------------------
# Snapshot tests — golden JSON for templates that currently compile
# ---------------------------------------------------------------------------


def _snapshot_path(template_id: str) -> Path:
    return SNAPSHOT_DIR / f"compile_card__{template_id}.json"


def _serialize(commands: list[object]) -> str:
    """Dump commands to deterministic JSON for diff-friendly snapshots."""
    payload = [json.loads(c.model_dump_json()) for c in commands]  # type: ignore[attr-defined]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize("template_id", SUPPORTED_SNAPSHOT_TEMPLATES)
def test_compiler_snapshot(template_id: str) -> None:
    card = CardGenerator().create_card(template_id=template_id)
    commands = compile_card(card)
    actual = _serialize(commands)

    path = _snapshot_path(template_id)

    if UPDATE_SNAPSHOTS:
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        path.write_text(actual)
        pytest.skip(f"snapshot updated: {path.name}")

    if not path.exists():
        pytest.fail(
            f"Missing snapshot {path}. "
            f"Generate with: UPDATE_COMPILER_SNAPSHOTS=1 pytest {__file__}"
        )

    expected = path.read_text()
    assert actual == expected, (
        f"Compiler output for {template_id!r} differs from snapshot at {path}.\n"
        f"If the change is intentional, regenerate with:\n"
        f"  UPDATE_COMPILER_SNAPSHOTS=1 pytest {__file__}"
    )


# ---------------------------------------------------------------------------
# Bleed extension — edge-aware background expansion
# ---------------------------------------------------------------------------


def _single_panel_card(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    rotation: float = 0.0,
    panel_bleed: float | None = None,
    card_bleed: float = 0.125,
) -> Card:
    """Build a minimal 1-panel card whose only feature is a red background.

    The compiler then emits exactly one DrawShape (the background) per
    panel, which is what the bleed tests inspect.
    """
    panel = Panel(
        position=PanelPosition.FRONT,
        x=x, y=y, width=width, height=height,
        rotation=rotation,
        bleed=panel_bleed,
        background_color=Color(r=1.0, g=0.0, b=0.0),
    )
    return Card(
        name="bleed-fixture",
        template_id="bleed-fixture",
        fold_type=FoldType.HALF_FOLD,
        bleed=card_bleed,
        panels=[panel],
    )


# Hand-placed fixture panels test the bleed-edge maths on arbitrary
# coordinates, so they opt out of the letter imposition (#58). The default
# letter geometry carries no bleed (#59), so the bleed tests ask for the
# industry 0.125" explicitly.
_NO_IMPOSE = CompileContext(
    geometry=PageGeometry.us_letter(bleed_in=0.125), impose=False
)


def _bg_rect(commands: list[object]) -> RectGeom:
    """Locate the (single) panel-background DrawShape's RectGeom."""
    rects = [
        c.geometry for c in commands  # type: ignore[attr-defined]
        if isinstance(c, DrawShape)
        and isinstance(c.geometry, RectGeom)
        and c.fill is not None
    ]
    assert len(rects) == 1, f"expected exactly one bg rect, got {len(rects)}"
    return rects[0]


class TestBleedExtension:
    """The compiler's bleed pass extends panel backgrounds on edges that
    touch the page trim. Page edges interior to the imposition (the
    fold line, panel-to-panel borders) do not get extended.
    """

    def test_panel_touching_all_four_edges_extends_on_all_four(self) -> None:
        # A full-page panel at (0, 0, 8.5, 11) touches every page edge.
        card = _single_panel_card(x=0, y=0, width=8.5, height=11.0)
        commands = compile_card(card, _NO_IMPOSE)
        rect = _bg_rect(commands)
        # 0.125" bleed = 9 pt extension on every side.
        assert rect.x == -9.0
        assert rect.y == -9.0
        assert rect.width == 612.0 + 18.0
        assert rect.height == 792.0 + 18.0

    def test_panel_touching_only_right_edge_extends_only_on_right(self) -> None:
        # Front panel of a half-fold: x=4.25, y=0 → touches right + bottom
        # but not left or top. Use a smaller height to drop the top touch.
        card = _single_panel_card(x=4.25, y=2.0, width=4.25, height=4.0)
        commands = compile_card(card, _NO_IMPOSE)
        rect = _bg_rect(commands)
        # x unchanged (left does NOT touch trim), width grows by 9 pt.
        assert rect.x == 4.25 * 72  # 306
        assert rect.width == 4.25 * 72 + 9.0  # 315
        # y unchanged (bottom does NOT touch trim), height unchanged.
        assert rect.y == 2.0 * 72  # 144
        assert rect.height == 4.0 * 72  # 288

    def test_no_bleed_when_card_bleed_and_panel_bleed_both_zero(self) -> None:
        card = _single_panel_card(
            x=0, y=0, width=8.5, height=11.0, card_bleed=0.0, panel_bleed=None
        )
        rect = _bg_rect(compile_card(card, _NO_IMPOSE))
        assert rect.x == 0.0 and rect.y == 0.0
        assert rect.width == 612.0 and rect.height == 792.0

    def test_panel_bleed_overrides_card_bleed_with_zero(self) -> None:
        # Card says 0.125 but panel says 0 — panel wins (explicit override).
        card = _single_panel_card(
            x=0, y=0, width=8.5, height=11.0, card_bleed=0.125, panel_bleed=0.0
        )
        rect = _bg_rect(compile_card(card, _NO_IMPOSE))
        # No extension despite card-level default.
        assert rect.x == 0.0 and rect.y == 0.0
        assert rect.width == 612.0 and rect.height == 792.0

    def test_panel_bleed_overrides_card_bleed_with_larger_value(self) -> None:
        card = _single_panel_card(
            x=0, y=0, width=8.5, height=11.0, card_bleed=0.125, panel_bleed=0.25
        )
        ctx = CompileContext(geometry=PageGeometry.us_letter(bleed_in=0.25), impose=False)
        rect = _bg_rect(compile_card(card, ctx))
        # 0.25" = 18 pt extension on every side.
        assert rect.x == -18.0 and rect.y == -18.0
        assert rect.width == 612.0 + 36.0
        assert rect.height == 792.0 + 36.0

    def test_extension_is_capped_at_the_page_geometry_bleed(self) -> None:
        # The panel asks for 0.25" but the page only has 0.125" of bleed
        # area: extending further would draw off the media box (#59).
        card = _single_panel_card(
            x=0, y=0, width=8.5, height=11.0, card_bleed=0.125, panel_bleed=0.25
        )
        rect = _bg_rect(compile_card(card, _NO_IMPOSE))
        assert rect.x == -9.0 and rect.y == -9.0
        assert rect.width == 612.0 + 18.0
        assert rect.height == 792.0 + 18.0

    def test_no_extension_on_a_page_without_bleed(self) -> None:
        # Card and panel both carry the template default of 0.125", but the
        # default letter geometry has no bleed, so nothing extends (#59).
        card = _single_panel_card(x=0, y=0, width=8.5, height=11.0)
        rect = _bg_rect(compile_card(card, CompileContext(impose=False)))
        assert rect.x == 0.0 and rect.y == 0.0
        assert rect.width == 612.0 and rect.height == 792.0

    def test_rotated_180_panel_extends_on_swapped_local_edges(self) -> None:
        # Inside-left of a half-fold: x=0, y=5.5, w=4.25, h=5.5, rotation=180.
        # Page-touches: left, top. After 180° rotation, those map to
        # panel-local right + bottom — meaning the LOCAL rect drawn inside
        # the BeginGroup extends rightward (+9 width) and downward (-9 y,
        # +9 height).
        card = _single_panel_card(x=0, y=5.5, width=4.25, height=5.5, rotation=180.0)
        rect = _bg_rect(compile_card(card, _NO_IMPOSE))
        # x stays 0 (local left edge does NOT touch); width grows by 9.
        assert rect.x == 0.0
        assert rect.width == 4.25 * 72 + 9.0  # 315
        # y drops by 9 (local bottom edge maps to page-top touch).
        assert rect.y == 5.5 * 72 - 9.0  # 387
        # height grows by 9 (local-bottom extension only; local-top did not).
        assert rect.height == 5.5 * 72 + 9.0  # 405

    def test_unsupported_rotation_with_bleed_fails_loudly(self) -> None:
        card = _single_panel_card(x=0, y=0, width=8.5, height=11.0, rotation=90.0)
        with pytest.raises(UnsupportedFeatureError, match="rotation"):
            compile_card(card, _NO_IMPOSE)


class TestBeginPageBleedFields:
    """``BeginPage`` now carries the bleed and safe-margin in points."""

    def test_default_geometry_emits_no_bleed(self) -> None:
        # Default CompileContext = PageGeometry.us_letter(): a true 8.5x11
        # home-printer page with no bleed (D7, #59).
        card = CardGenerator().create_card(template_id="christmas-classic")
        commands = compile_card(card)
        bp = commands[0]
        assert isinstance(bp, BeginPage)
        assert bp.width == 612.0
        assert bp.height == 792.0
        assert bp.bleed == 0.0
        assert bp.safe_margin == 18.0  # 0.25" in points

    def test_default_geometry_keeps_every_rect_inside_the_trim(self) -> None:
        # With no bleed there is nowhere to extend to: no background rect
        # may start below (0, 0) or reach past 612x792 (#59).
        card = CardGenerator().create_card(template_id="christmas-classic")
        rects = [
            c.geometry for c in compile_card(card)
            if isinstance(c, DrawShape) and isinstance(c.geometry, RectGeom)
        ]
        assert rects
        for rect in rects:
            assert rect.x >= 0.0 and rect.y >= 0.0, rect
            assert rect.x + rect.width <= 612.0, rect
            assert rect.y + rect.height <= 792.0, rect

    def test_explicit_bleed_geometry_still_extends_backgrounds(self) -> None:
        # The cap is geometry-driven: ask for 0.125" of bleed and the same
        # template's backgrounds extend past the trim again (#59).
        card = CardGenerator().create_card(template_id="christmas-classic")
        ctx = CompileContext(geometry=PageGeometry.us_letter(bleed_in=0.125))
        commands = compile_card(card, ctx)
        bp = commands[0]
        assert isinstance(bp, BeginPage)
        assert bp.bleed == 9.0
        rects = [
            c.geometry for c in commands
            if isinstance(c, DrawShape) and isinstance(c.geometry, RectGeom)
        ]
        assert any(rect.x < 0.0 or rect.y < 0.0 for rect in rects)

    def test_zero_bleed_geometry_zeros_the_field(self) -> None:
        card = CardGenerator().create_card(template_id="christmas-classic")
        ctx = CompileContext(geometry=PageGeometry.us_letter(bleed_in=0.0))
        bp = compile_card(card, ctx)[0]
        assert isinstance(bp, BeginPage)
        assert bp.bleed == 0.0


# ---------------------------------------------------------------------------
# Fail loud on unknown fonts / unsupported panel + text fields (#60)
# ---------------------------------------------------------------------------


def _text(**kwargs: object) -> TextElement:
    return TextElement(x=0.5, y=2.0, **kwargs)  # type: ignore[arg-type]


def _text_card(text: TextElement, **panel_kwargs: object) -> Card:
    panel = Panel(
        id="front-panel",
        position=PanelPosition.FRONT,
        x=4.25, y=0.0, width=4.25, height=5.5,
        text_elements=[text],
        **panel_kwargs,  # type: ignore[arg-type]
    )
    return Card(
        name="fail-loud-fixture",
        template_id="fail-loud-fixture",
        fold_type=FoldType.HALF_FOLD,
        panels=[panel],
    )


class TestFailLoud:
    def test_unknown_font_error_is_an_unsupported_feature_error(self) -> None:
        assert issubclass(UnknownFontError, UnsupportedFeatureError)

    def test_unknown_font_family_raises_naming_where_and_available(self) -> None:
        card = _text_card(_text(id="greeting", content="Hi", font_family="NotAFont"))
        with pytest.raises(UnknownFontError) as exc:
            compile_card(card)
        msg = str(exc.value)
        assert "unknown font 'NotAFont'" in msg
        assert "fail-loud-fixture/front/greeting" in msg
        assert "Available: Caveat, Comfortaa," in msg

    def test_unknown_font_raises_even_for_empty_content(self) -> None:
        card = _text_card(_text(id="blank", content="", font_family="NotAFont"))
        with pytest.raises(UnknownFontError):
            compile_card(card)

    def test_unknown_signature_font_raises(self) -> None:
        from holiday_card.core.letter import LetterContent

        text = _text(
            id="message", content="", font_family="Lato",
            letter_content=LetterContent(
                signature="C", signature_font_family="NotAFont",
            ),
        )
        with pytest.raises(UnknownFontError, match="unknown font 'NotAFont'"):
            compile_card(_text_card(text))

    def test_font_file_raises_unsupported(self) -> None:
        text = _text(id="t", content="Hi", font_file="fonts/Mine.ttf")
        with pytest.raises(UnsupportedFeatureError, match="font_file is not supported"):
            compile_card(_text_card(text))

    def test_relative_panel_background_image_raises_image_source_error(self) -> None:
        text = _text(id="t", content="Hi")
        card = _text_card(text, background_image="x.png")
        with pytest.raises(ImageSourceError) as exc:
            compile_card(card)
        assert "background_image" in str(exc.value)
        assert "front" in str(exc.value)

    def test_known_fonts_compile(self) -> None:
        for font in ("Helvetica", "Times-Roman", "Caveat", "Lato-Bold"):
            compile_card(_text_card(_text(id="t", content="Hi", font_family=font)))


# ---------------------------------------------------------------------------
# TextElement font_style + rotation are honoured, not dropped (#63)
# ---------------------------------------------------------------------------


def _draws(commands: list[object]) -> list[DrawText]:
    return [c for c in commands if isinstance(c, DrawText)]


class TestTextFontStyle:
    @pytest.mark.parametrize(
        ("family", "style", "expected"),
        [
            ("Cormorant", "italic", "Cormorant-Italic"),
            ("Cormorant", "bold", "Cormorant-Bold"),
            ("Cormorant", "bold_italic", "Cormorant-BoldItalic"),
            ("PlayfairDisplay", "italic", "PlayfairDisplay-Italic"),
            ("PlayfairDisplay", "bold", "PlayfairDisplay-Bold"),
            ("PlayfairDisplay", "bold_italic", "PlayfairDisplay-BoldItalic"),
            ("Helvetica", "bold", "Helvetica-Bold"),
            ("Cormorant", "normal", "Cormorant"),
        ],
    )
    def test_font_style_resolves_to_registered_variant(
        self, family: str, style: str, expected: str
    ) -> None:
        text = _text(id="t", content="Seasons greetings", font_family=family, font_style=style)
        draws = _draws(compile_card(_text_card(text)))
        assert draws
        assert {d.run.font_id for d in draws} == {expected}

    @pytest.mark.parametrize("family", ["Inter", "Caveat", "Comfortaa"])
    def test_family_without_variant_degrades_to_regular(self, family: str) -> None:
        text = _text(id="t", content="Hi", font_family=family, font_style="bold")
        draws = _draws(compile_card(_text_card(text)))
        assert {d.run.font_id for d in draws} == {family}

    def test_lato_italic_degrades_to_regular(self) -> None:
        text = _text(id="t", content="Hi", font_family="Lato", font_style="italic")
        assert {d.run.font_id for d in _draws(compile_card(_text_card(text)))} == {"Lato"}

    def test_wrapping_measures_the_resolved_font(self) -> None:
        # Bold Helvetica is wider than regular, so at a width tuned between the two
        # measured widths the bold copy wraps and the regular copy does not.
        from reportlab.pdfbase.pdfmetrics import stringWidth

        content = "Wishing you joy and peace"
        regular_w = stringWidth(content, "Helvetica", 12)
        bold_w = stringWidth(content, "Helvetica-Bold", 12)
        assert bold_w > regular_w
        width_in = (regular_w + bold_w) / 2 / 72

        def lines(style: str) -> int:
            text = _text(
                id="t", content=content, font_family="Helvetica", font_size=12,
                font_style=style, width=width_in, overflow_strategy="wrap",
            )
            return len(_draws(compile_card(_text_card(text))))

        assert lines("normal") == 1
        assert lines("bold") > 1

    def test_rich_content_ignores_font_style(self) -> None:
        from holiday_card.core.markdown import parse_markdown

        text = _text(
            id="t", content="", font_family="Cormorant", font_style="bold",
            width=3.0, rich_content=parse_markdown("plain *it*"),
        )
        ids = [d.run.font_id for d in _draws(compile_card(_text_card(text)))]
        assert ids == ["Cormorant", "Cormorant-Italic"]


def _styled_text_elements() -> list[tuple[str, str]]:
    from holiday_card.core.templates import discover_templates, load_template

    out = []
    for info in sorted(discover_templates(), key=lambda i: i["id"]):
        template = load_template(info["id"])
        for panel in template.panels:
            # Keyed by index: elements without an authored id get a random uuid.
            for index, element in enumerate(panel.text_elements):
                if element.font_style != "normal":
                    out.append((template.id, f"{panel.position.value}/{index}"))
    return out


class TestShippedTemplateFontStyles:
    def test_shipped_templates_ask_for_styled_text(self) -> None:
        assert len(_styled_text_elements()) >= 30

    @pytest.mark.parametrize(("template_id", "where"), _styled_text_elements())
    def test_styled_element_compiles_to_resolved_font_id(
        self, template_id: str, where: str
    ) -> None:
        from holiday_card.core.markdown import font_id_for_run

        card = CardGenerator().create_card(template_id=template_id)
        position, index = where.split("/", 1)
        panel = next(p for p in card.panels if p.position.value == position)
        element = panel.text_elements[int(index)]
        if not element.content:
            element = element.model_copy(update={"content": "Sample"})
        # Compile a card carrying only the element under test, so every
        # DrawText belongs to it.
        solo = card.model_copy(update={"panels": [
            panel.model_copy(update={
                "text_elements": [element], "shape_elements": [], "image_elements": [],
            })
        ]})
        draws = _draws(compile_card(solo))
        assert draws
        expected = font_id_for_run(
            element.font_family,
            bold=element.font_style in ("bold", "bold_italic"),
            italic=element.font_style in ("italic", "bold_italic"),
        )
        assert {d.run.font_id for d in draws} == {expected}


class TestTextRotation:
    _CTX = CompileContext(impose=False)

    def test_rotation_wraps_drawtext_in_group_pivoted_at_anchor(self) -> None:
        text = _text(id="t", content="Line one\nLine two", rotation=90)
        commands = compile_card(_text_card(text), self._CTX)
        assert_balanced(commands)
        start = next(
            i for i, c in enumerate(commands)
            if isinstance(c, BeginGroup) and c.transform is not None
            and c.transform.rotate_deg == 90
        )
        group = commands[start]
        assert isinstance(group, BeginGroup) and group.transform is not None
        # Panel at x=4.25", y=0; text anchor at (0.5", 2.0") within it.
        assert group.transform.pivot_x == pytest.approx((4.25 + 0.5) * 72)
        assert group.transform.pivot_y == pytest.approx(2.0 * 72)
        assert [type(c) for c in commands[start + 1:start + 4]] == [DrawText, DrawText, EndGroup]

    def test_zero_rotation_emits_no_text_group(self) -> None:
        text = _text(id="t", content="Hi")
        commands = compile_card(_text_card(text), self._CTX)
        rotating = [
            c for c in commands
            if isinstance(c, BeginGroup) and c.transform is not None
            and c.transform.rotate_deg != 0
        ]
        assert rotating == []

    def test_rotation_applies_to_letter_content(self) -> None:
        from holiday_card.core.letter import LetterContent

        text = _text(
            id="t", content="", rotation=-15,
            letter_content=LetterContent(salutation="Dear M,", body="Hello"),
        )
        commands = compile_card(_text_card(text), self._CTX)
        assert_balanced(commands)
        idx = next(
            i for i, c in enumerate(commands)
            if isinstance(c, BeginGroup) and c.transform is not None
            and c.transform.rotate_deg == -15
        )
        assert [type(c) for c in commands[idx + 1:idx + 4]] == [DrawText, DrawText, EndGroup]


# ---------------------------------------------------------------------------
# Per-panel fit: one compiler-emitted scale group (D8 / D14, #73)
# ---------------------------------------------------------------------------


_A6_W_PT = 4.13 * 72
_A6_H_PT = 5.83 * 72
_FILL_S = 5.83 / 5.5         # max(4.13/4.25, 5.83/5.5)
_LETTERBOX_S = 4.13 / 4.25   # min(...)


def _native_panel(**kwargs: object) -> Panel:
    return Panel(
        position=PanelPosition.FRONT,
        width=4.25, height=5.5,
        background_color=Color(r=1.0, g=0.0, b=0.0),
        **kwargs,  # type: ignore[arg-type]
    )


def _fit_card(*panels: Panel) -> Card:
    return Card(
        name="fit-fixture", template_id="fit-fixture",
        fold_type=FoldType.HALF_FOLD, panels=list(panels),
    )


def _fit_ctx(panel_fit: str) -> CompileContext:
    return CompileContext(
        geometry=PageGeometry.moo_a6(), emit_fold_lines=False,
        impose=False, panel_fit=panel_fit,  # type: ignore[arg-type]
    )


def _scale_groups(commands: list[object]) -> list[BeginGroup]:
    return [
        c for c in commands
        if isinstance(c, BeginGroup)
        and (c.transform.scale_x != 1.0 or c.transform.scale_y != 1.0)
    ]


class TestPanelFit:
    def test_native_is_the_default_and_emits_no_scale(self) -> None:
        assert CompileContext().panel_fit == "native"
        commands = compile_card(_fit_card(_native_panel()), _fit_ctx("native"))
        assert _scale_groups(commands) == []

    def test_fill_wraps_the_panel_in_one_centred_scale_group(self) -> None:
        commands = compile_card(_fit_card(_native_panel()), _fit_ctx("fill"))
        groups = _scale_groups(commands)
        assert len(groups) == 1
        t = groups[0].transform
        assert t.scale_x == pytest.approx(_FILL_S) and t.scale_y == pytest.approx(_FILL_S)
        assert t.scale_x == pytest.approx(1.0600, abs=1e-4)
        assert (t.pivot_x, t.pivot_y, t.rotate_deg) == (0.0, 0.0, 0.0)
        assert t.offset_x == pytest.approx((_A6_W_PT - 4.25 * 72 * _FILL_S) / 2)
        assert t.offset_x == pytest.approx(-0.1875 * 72, abs=0.01)
        assert t.offset_y == pytest.approx(0.0, abs=1e-9)
        # The group is the outermost one of the panel: every draw sits inside it.
        first_draw = next(i for i, c in enumerate(commands) if isinstance(c, DrawShape))
        assert commands.index(groups[0]) < first_draw

    def test_letterbox_scale_is_the_min_and_centres_vertically(self) -> None:
        commands = compile_card(_fit_card(_native_panel()), _fit_ctx("letterbox"))
        groups = _scale_groups(commands)
        assert len(groups) == 1
        t = groups[0].transform
        assert t.scale_x == pytest.approx(_LETTERBOX_S)
        assert t.scale_x == pytest.approx(0.9718, abs=1e-4)
        assert t.offset_x == pytest.approx(0.0, abs=1e-9)
        assert t.offset_y == pytest.approx((_A6_H_PT - 5.5 * 72 * _LETTERBOX_S) / 2)

    def test_fit_with_two_panels_raises(self) -> None:
        back = _native_panel().model_copy(update={"position": PanelPosition.BACK})
        with pytest.raises(ValueError, match="exactly one panel"):
            compile_card(_fit_card(_native_panel(), back), _fit_ctx("fill"))

    def test_fit_with_a_placed_panel_raises(self) -> None:
        with pytest.raises(ValueError, match="origin"):
            compile_card(_fit_card(_native_panel(x=1.0)), _fit_ctx("fill"))

    def test_fill_extends_the_background_by_bleed_over_s_on_all_sides(self) -> None:
        commands = compile_card(_fit_card(_native_panel()), _fit_ctx("fill"))
        rect = _bg_rect(commands)
        ext = 9.0 / _FILL_S
        assert rect.x == pytest.approx(-ext)
        assert rect.y == pytest.approx(-ext)
        assert rect.width == pytest.approx(4.25 * 72 + 2 * ext)
        assert rect.height == pytest.approx(5.5 * 72 + 2 * ext)

    def test_letterbox_extends_only_the_edges_that_reach_the_trim(self) -> None:
        commands = compile_card(_fit_card(_native_panel()), _fit_ctx("letterbox"))
        rect = _bg_rect(commands)
        ext = 9.0 / _LETTERBOX_S
        assert rect.x == pytest.approx(-ext)
        assert rect.width == pytest.approx(4.25 * 72 + 2 * ext)
        assert rect.y == pytest.approx(0.0)
        assert rect.height == pytest.approx(5.5 * 72)


class TestSafeZoneWarning:
    def _card(self, text: TextElement) -> Card:
        return _fit_card(_native_panel(id="front-panel", text_elements=[text]))

    def test_text_near_the_edge_warns_naming_panel_element_and_overshoot(self) -> None:
        text = TextElement(id="greeting", content="Edge", x=0.1, y=3.0, font_family="Lato")
        with pytest.warns(SafeZoneWarning) as record:
            compile_card(self._card(text), _fit_ctx("fill"))
        message = str(record[0].message)
        assert "front" in message
        assert "greeting" in message
        assert '"' in message  # overshoot in inches

    def test_centred_text_does_not_warn(self) -> None:
        import warnings

        text = TextElement(
            id="greeting", content="Centre", x=2.125, y=3.0,
            font_family="Lato", alignment="center",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", SafeZoneWarning)
            compile_card(self._card(text), _fit_ctx("fill"))

    def test_native_fit_never_warns(self) -> None:
        import warnings

        text = TextElement(id="greeting", content="Edge", x=0.0, y=3.0, font_family="Lato")
        with warnings.catch_warnings():
            warnings.simplefilter("error", SafeZoneWarning)
            compile_card(self._card(text), _fit_ctx("native"))
