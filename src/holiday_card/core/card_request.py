"""One frozen request + one builder behind ``create``, ``preview`` and ``--debug-emit-ir``.

Every card-building policy the CLI used to keep inside ``create()`` lives
here (expert-panel §P14, standing decision D15):

* :class:`CardRequest` — every input ``holiday-card create`` accepts, minus
  the ``--debug-emit-ir`` mode switch. Flag conflicts are refused at
  construction (a :class:`pydantic.ValidationError`; see
  :func:`validation_message`).
* :func:`build_card_with_report` / :func:`build_card` — the content half:
  template, voice picks, plain / blank / Markdown / letter inside modes,
  theme, fold type and photos, in the precedence ``create`` always had.
* :func:`plan_output` — the output half: export target, output format and
  the final path. Never consulted by ``build_card``.

Errors raised while building are plain :class:`ValueError` (or the
domain errors of the modules this one calls: ``TemplateNotFoundError``,
``ImageSourceError``, ``PhotoSlotError``, ...). Messages carry no
``Error:`` prefix; the CLI adds it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from holiday_card.core.export_targets import (
    REGISTRY,
    ExportTarget,
    ExportTargetNotFoundError,
    get_target,
)
from holiday_card.core.generators import CardGenerator
from holiday_card.core.letter import LetterContent
from holiday_card.core.markdown import parse_markdown
from holiday_card.core.models import Card, FoldType
from holiday_card.core.sentiments import (
    VOICES,
    SentimentNotFoundError,
    available_voices,
    pick_sentiment,
)
from holiday_card.core.templates import load_template
from holiday_card.core.themes import discover_themes

__all__ = [
    "BuildReport",
    "CardRequest",
    "OutputPlan",
    "UnknownExportTargetError",
    "build_card",
    "build_card_with_report",
    "plan_output",
    "unwrap_validation_error",
    "validation_message",
]

_SUPPORTED_FORMATS = ("pdf", "svg")
_FOLD_TYPE_VALUES = ", ".join(f.value for f in FoldType)
_FOLD_PANELS: dict[FoldType, tuple[str, ...]] = {
    FoldType.HALF_FOLD: ("front", "back", "inside_left", "inside_right"),
    FoldType.QUARTER_FOLD: ("front", "back", "inside_left", "inside_right"),
    FoldType.TRI_FOLD: ("left", "center", "right"),
}

InsideMode = Literal["template", "plain", "blank", "markdown", "letter"]


class UnknownExportTargetError(ValueError):
    """``--export-for`` names no registered target.

    ``str()`` is exactly ``str(ExportTargetNotFoundError)`` — a ``KeyError``,
    so the message renders quoted — because the CLI text is pinned.
    """


class CardRequest(BaseModel):
    """Every input ``holiday-card create`` accepts, minus the --debug-emit-ir mode switch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- content: consumed by build_card ---
    template: str                                   # positional: template id (paths: P6-2)
    message: str | None = None                      # -m / --message
    inside_message: str | None = None               # --inside-message
    inside_markdown: str | None = None              # TEXT of --inside-message-md (CLI reads the file)
    voice: str | None = None                        # --voice (must be in sentiments.VOICES)
    seed: int | None = None                         # --seed
    blank_inside: bool = False                      # --blank-inside
    salutation: str | None = None                   # --salutation
    signoff: str | None = None                      # --signoff
    signature: str | None = None                    # --signature
    postscript: str | None = None                   # --ps
    signature_font: str | None = None               # --signature-font
    theme: str | None = None                        # -t / --theme
    fold_type: FoldType | None = None               # -f / --fold-type
    images: tuple[Path, ...] = ()                   # -i / --image (repeatable)

    # --- output: consumed by plan_output, never by build_card ---
    output: Path | None = None                      # -o / --output
    output_format: Literal["auto", "pdf", "svg"] = "auto"   # --format
    export_for: str = "letter"                      # --export-for
    fold_marks: bool | None = None                  # --with-fold-marks / --no-fold-marks
    panel_fit: Literal["fill", "letterbox"] | None = None   # --panel-fit (None: target's)

    @field_validator("fold_type", mode="before")
    @classmethod
    def _parse_fold_type(cls, value: Any) -> Any:
        # Rule 9: the CLI passes the raw string; a bad one lists the values.
        if value is None or isinstance(value, FoldType):
            return value
        try:
            return FoldType(value)
        except ValueError as e:
            raise ValueError(
                f"Invalid fold type '{value}'. Valid options: {_FOLD_TYPE_VALUES}"
            ) from e

    @field_validator("output_format", mode="before")
    @classmethod
    def _parse_output_format(cls, value: Any) -> Any:
        # Rule 6: case-insensitive; anything but pdf / svg / auto is refused.
        if not isinstance(value, str):
            return value
        requested = value.lower()
        if requested in _SUPPORTED_FORMATS or requested == "auto":
            return requested
        raise ValueError(
            f"--format must be one of {_SUPPORTED_FORMATS} or 'auto', got {requested!r}"
        )

    @model_validator(mode="after")
    def _check_conflicts(self) -> CardRequest:
        """Refuse contradictory or unknown inputs, in ``create()``'s original order (D4)."""
        try:
            target = get_target(self.export_for)  # rule 1
        except ExportTargetNotFoundError as e:
            raise UnknownExportTargetError(str(e)) from e
        if self.panel_fit is not None and target.panel_fit == "native":  # D4, #73
            fitting = ", ".join(n for n, t in sorted(REGISTRY.items()) if t.panel_fit != "native")
            raise ValueError(
                f"--panel-fit only applies to targets that scale panels to a fixed trim "
                f"({fitting}); --export-for {self.export_for} renders panels at their "
                f"native size"
            )
        if self.voice is not None and self.voice not in VOICES:  # rule 2
            raise ValueError(
                f"Unknown --voice value {self.voice!r}. Available: {', '.join(VOICES)}"
            )
        if self.inside_message is not None and self.inside_markdown is not None:  # rule 3
            raise ValueError(
                "--inside-message and --inside-message-md are mutually exclusive (pick one)."
            )
        if self.blank_inside and self.inside_message is not None:
            raise ValueError("--blank-inside cannot be combined with --inside-message")
        if self.blank_inside and self.inside_markdown is not None:
            raise ValueError("--blank-inside cannot be combined with --inside-message-md")
        if self.seed is not None and self.voice is None:
            raise ValueError("--seed only applies with --voice")
        if self.signature_font is not None and self.signature is None:
            raise ValueError("--signature-font requires --signature")
        if self.letter_parts_set and self.inside_markdown is not None:  # rule 4
            raise ValueError(
                "--inside-message-md cannot be combined with "
                "--salutation / --signoff / --signature / --ps "
                "(letter parts use a separate authoring surface). "
                "Either drop the Markdown file or move the letter "
                "structure into the body of the Markdown."
            )
        if self.inside_markdown is not None:  # rule 5
            parse_markdown(self.inside_markdown)
        return self

    @property
    def letter_parts_set(self) -> bool:
        """True when any of --salutation / --signoff / --signature / --ps is given."""
        return any(
            v is not None
            for v in (self.salutation, self.signoff, self.signature, self.postscript)
        )


@dataclass(frozen=True)
class BuildReport:
    """What :func:`build_card_with_report` decided, for the CLI summary."""

    picked_cover: str | None
    picked_inside: str | None
    inside_mode: InsideMode


@dataclass(frozen=True)
class OutputPlan:
    """Where and how the card is written."""

    target: ExportTarget
    output_format: Literal["pdf", "svg"]
    path: Path            # file for imposition layouts, directory for per-panel layouts


# ---------------------------------------------------------------------------
# ValidationError helpers
# ---------------------------------------------------------------------------


def unwrap_validation_error(exc: ValidationError) -> Exception:
    """Return the error behind a :class:`CardRequest` refusal.

    A validator's ``ValueError`` comes back as raised (so ``isinstance``
    checks work); any other Pydantic error becomes a ``ValueError``
    carrying Pydantic's message.
    """
    first = exc.errors()[0]
    original = (first.get("ctx") or {}).get("error")
    if isinstance(original, Exception):
        return original
    return ValueError(first["msg"])


def validation_message(exc: ValidationError) -> str:
    """The one-line message for a :class:`CardRequest` refusal."""
    return str(unwrap_validation_error(exc))


# ---------------------------------------------------------------------------
# Content: build_card
# ---------------------------------------------------------------------------


def build_card(request: CardRequest, *, templates_dir: Path | None = None) -> Card:
    """Build the :class:`Card` for ``request``; see :func:`build_card_with_report`."""
    return build_card_with_report(request, templates_dir=templates_dir)[0]


def build_card_with_report(
    request: CardRequest, *, templates_dir: Path | None = None
) -> tuple[Card, BuildReport]:
    """Build the :class:`Card` for ``request`` and report what was decided.

    Precedence (rules 9-17 of #78): an unknown theme is refused before the
    template loads; ``--voice`` fills only the cover / inside slots left
    unset; ``--blank-inside`` empties the inside; letter parts wrap the
    effective inside text as the letter body and win over plain text;
    Markdown wins over plain text; the theme is applied last.

    Raises:
        ValueError: unknown theme, a voice the occasion doesn't ship, a
            missing sentiment file, or a fold type the template's panels
            can't satisfy.
        TemplateNotFoundError / TemplateLoadError: from the template loader.
        ImageSourceError / PhotoSlotError: from the photo slots.
    """
    if request.theme is not None:  # rule 17 (#60: fail loud)
        theme_ids = sorted(t["id"] for t in discover_themes())
        if request.theme not in theme_ids:
            raise ValueError(
                f"Unknown theme {request.theme!r}. Available: {', '.join(theme_ids)}"
            )

    template = load_template(request.template, templates_dir)

    # Rule 11: --voice fills only the slots the user left unset.
    effective_message = request.message
    effective_inside = request.inside_message
    picked_cover: str | None = None
    picked_inside: str | None = None
    if request.voice is not None:
        occasion = template.occasion.value
        shipped = available_voices(occasion)
        if request.voice not in shipped:
            raise ValueError(
                f"voice {request.voice!r} is not available for occasion "
                f"{occasion!r}. Available: {', '.join(shipped) or '(none)'}"
            )
        if effective_message is None:
            picked_cover = _pick_voice_line(occasion, request.voice, "cover", request.seed)
            effective_message = picked_cover
        if effective_inside is None and not request.blank_inside:
            picked_inside = _pick_voice_line(occasion, request.voice, "inside", request.seed)
            effective_inside = picked_inside
    if request.blank_inside:  # rule 12
        effective_inside = ""

    rich_inside = (
        parse_markdown(request.inside_markdown) if request.inside_markdown is not None else None
    )
    letter: LetterContent | None = None
    if request.letter_parts_set:  # rule 13
        letter = LetterContent(
            salutation=request.salutation or "",
            body=effective_inside or "",
            signoff=request.signoff or "",
            signature=request.signature or "",
            postscript=request.postscript or "",
            signature_font_family=request.signature_font,
        )

    generator = CardGenerator(templates_dir=templates_dir)
    card = generator.create_card_from_template(
        template,
        message=effective_message,
        theme_id=request.theme,
        fold_type=request.fold_type,
        photos=request.images,
        # Rule 14: Markdown and the letter carry the inside themselves.
        inside_message=(
            None if (rich_inside is not None or letter is not None) else effective_inside
        ),
    )
    if request.fold_type is not None:  # rule 9
        _check_fold_type_fits(request.fold_type, card)
    if rich_inside is not None:
        generator.apply_inside_rich_content(card, rich_inside)
    if letter is not None:
        generator.apply_inside_letter(card, letter)

    inside_mode: InsideMode
    if letter is not None:
        inside_mode = "letter"
    elif rich_inside is not None:
        inside_mode = "markdown"
    elif request.blank_inside:
        inside_mode = "blank"
    elif effective_inside is not None:
        inside_mode = "plain"
    else:
        inside_mode = "template"
    return card, BuildReport(
        picked_cover=picked_cover, picked_inside=picked_inside, inside_mode=inside_mode
    )


def _pick_voice_line(occasion: str, voice: str, role: str, seed: int | None) -> str:
    try:
        return pick_sentiment(occasion, voice, role, seed=seed)
    except SentimentNotFoundError as e:
        # The library error names the absolute path; keep it out of the message.
        raise ValueError(
            f"voice {voice!r} has no {role} sentiment for occasion {occasion!r}"
        ) from e


def _check_fold_type_fits(fold_type: FoldType, card: Card) -> None:
    needed = _FOLD_PANELS[fold_type]
    has = [p.position.value for p in card.panels]
    if set(has) != set(needed):
        raise ValueError(
            f"fold type {fold_type.value!r} needs panels {'/'.join(needed)}; "
            f"template has {'/'.join(has)}"
        )


# ---------------------------------------------------------------------------
# Output: plan_output
# ---------------------------------------------------------------------------


def plan_output(request: CardRequest, *, now: datetime) -> OutputPlan:
    """Resolve the export target, output format and final path (rules 1, 6-8).

    ``now`` stamps the default path ``output/<template>-<YYYY-mm-dd_HHMMSS><ext>``
    (no extension for per-panel targets, which write a directory).

    Raises:
        ValueError: ``-o`` clashes with the format or the target.
    """
    target = get_target(request.export_for)
    if request.panel_fit is not None:
        target = replace(target, panel_fit=request.panel_fit)
    output_format = _resolve_output_format(request)
    ext = f".{output_format}"
    output = request.output
    if output is None:
        stamp = now.strftime("%Y-%m-%d_%H%M%S")
        stem = f"{request.template}-{stamp}"
        output = Path("output") / (stem if target.layout == "per-panel" else f"{stem}{ext}")
    return OutputPlan(
        target=target,
        output_format=output_format,
        path=_validate_output_path(output, output_format, target),
    )


def _resolve_output_format(request: CardRequest) -> Literal["pdf", "svg"]:
    if request.output_format != "auto":
        return request.output_format
    if request.output is not None:
        suffix = request.output.suffix.lower().lstrip(".")
        if suffix == "svg":
            return "svg"
    return "pdf"


def _validate_output_path(output: Path, fmt: str, target: ExportTarget) -> Path:
    """Check ``-o`` against the output format and target; return the final path.

    Per-panel targets need a directory. Single-file targets need a
    ``.pdf``/``.svg`` suffix matching ``fmt``; a path with no suffix
    gets one appended.
    """
    if target.layout == "per-panel":
        if output.is_file() or (output.suffix and not output.is_dir()):
            raise ValueError(
                f"--export-for {target.name} writes one file per panel; "
                f"-o must be a directory, not {str(output)!r}"
            )
        return output
    ext = f".{fmt}"
    suffix = output.suffix.lower()
    if not suffix:
        return Path(f"{output}{ext}")
    if suffix == ext:
        return output
    if suffix in {f".{f}" for f in _SUPPORTED_FORMATS}:
        raise ValueError(f"--format {fmt} conflicts with output extension {output.suffix!r}")
    hint = "; use 'holiday-card preview' for PNG" if suffix == ".png" else ""
    raise ValueError(
        f"unsupported output extension {output.suffix!r} (use .pdf or .svg{hint})"
    )
