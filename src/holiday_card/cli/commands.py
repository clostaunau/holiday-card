"""CLI commands for holiday-card application.

This module implements the Typer CLI interface following Unix conventions.
All commands support both human-readable and JSON output formats.
"""

import json
import os
import sys
import warnings
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn

import typer
from pydantic import ValidationError
from typer.core import TyperGroup

from holiday_card import __version__
from holiday_card.cli.exit_codes import EXIT_CODES_HELP, ExitCode
from holiday_card.core.ai_provenance import ai_disclosure_label
from holiday_card.core.ai_providers import PROVIDERS, AIProvider, make_image_client
from holiday_card.core.card_request import (
    BuildReport,
    CardRequest,
    UnknownExportTargetError,
    build_card,
    build_card_with_report,
    plan_output,
    unwrap_validation_error,
    validation_message,
)
from holiday_card.core.compiler import (
    SafeZoneWarning,
    UnsupportedFeatureError,
    embedded_ai_assets,
)
from holiday_card.core.export_targets import (
    REGISTRY as EXPORT_TARGET_REGISTRY,
)
from holiday_card.core.export_targets import (
    ExportTargetNotFoundError,
    get_target,
)
from holiday_card.core.generators import CardGenerator, PhotoSlotError
from holiday_card.core.images import ImageSourceError, LowResolutionWarning
from holiday_card.core.models import Card, OccasionType
from holiday_card.core.template_checks import check_template
from holiday_card.core.template_schema import render_template_schema
from holiday_card.core.templates import (
    TemplateLoadError,
    TemplateNotFoundError,
    discover_templates,
    resolve_template,
    template_search_path,
    templates_with_photo_slots,
    user_templates_dir,
)
from holiday_card.core.themes import discover_themes, get_themes_dir
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer


def _exit_quietly_on_broken_pipe() -> NoReturn:
    # The reader closed stdout (e.g. `| grep -q`): not a failure (#92).
    # Point fd 1 at /dev/null so the interpreter's final flush can't raise.
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except (OSError, ValueError):
        pass
    raise typer.Exit(ExitCode.OK)


class _CLIGroup(TyperGroup):
    """Root command group that turns a closed stdout pipe into a quiet exit 0."""

    # ``Any``: the base's Context type is click's or typer's vendored copy
    # depending on the typer version.
    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except BrokenPipeError:
            _exit_quietly_on_broken_pipe()


# Create main Typer app
app = typer.Typer(
    name="holiday-card",
    help="Greeting cards as code: compile YAML templates to print-ready PDF, SVG, and PNG previews.",
    add_completion=False,
    cls=_CLIGroup,
    epilog=EXIT_CODES_HELP,
    pretty_exceptions_show_locals=False,  # never print api keys / headers from frames
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        # Eager option: runs while parsing, outside _CLIGroup.invoke.
        try:
            typer.echo(f"holiday-card version {__version__}")
        except BrokenPipeError:
            _exit_quietly_on_broken_pipe()
        raise typer.Exit()


# Set by the root callback on every invocation (``--debug`` / HOLIDAY_CARD_DEBUG).
_debug = False


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        envvar="HOLIDAY_CARD_DEBUG",
        help="Re-raise unexpected errors with a full traceback.",
    ),
) -> None:
    """Holiday Card Generator - Create printable greeting cards.

    Compile YAML templates into print-ready PDF (home printing or POD
    targets via ``--export-for``), self-contained SVG, and PNG previews
    (``preview``).
    """
    del version  # handled by the eager version_callback
    global _debug
    _debug = debug


def _unexpected_error(prefix: str, e: Exception) -> NoReturn:
    # The catch-all of every command: --debug re-raises the original error.
    if _debug:
        raise e
    typer.secho(
        f"{prefix}: {e} (re-run with --debug for a traceback)",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(ExitCode.ERROR) from e


def _fail(message: str) -> NoReturn:
    # A bad or contradictory input: fail loud with exit 2 (D4).
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(ExitCode.USAGE)


def _canonical_fold_type(value: str) -> str:
    # ``half_fold`` is the legacy spelling of the 4-up quarter fold (#58).
    return "quarter_fold" if value == "half_fold" else value


class ListFormat(StrEnum):
    """``--format`` of the listing commands; anything else is a usage error (D4)."""

    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


_LIST_FORMAT_OPTION = typer.Option(
    ListFormat.TABLE, "--format", help="Output format: table, json or yaml."
)


def _echo_table(headers: list[str], rows: list[list[str]]) -> None:
    # Left-aligned columns sized to their widest cell; nothing is truncated.
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows, strict=True)]
    for row in [headers, *rows]:
        typer.echo("  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip())


@app.command()
def templates(
    occasion: str | None = typer.Option(None, "--occasion", help="Filter by occasion type"),
    fold_type: str | None = typer.Option(
        None, "--fold-type", "-f", help="Filter by fold type"
    ),
    format: ListFormat = _LIST_FORMAT_OPTION,
) -> None:
    """List available card templates.

    The ID column is what ``create``, ``preview`` and ``validate`` take.
    """
    try:
        templates_list = discover_templates()
        if not any(t["source"] == "builtin" for t in templates_list) and not (
            occasion or fold_type
        ):
            _fail_empty_catalog("templates", template_search_path()[-1][1])

        # Filter by occasion if specified
        if occasion:
            templates_list = [t for t in templates_list if t["occasion"] == occasion]

        # Filter by fold type if specified
        if fold_type:
            wanted = _canonical_fold_type(fold_type)
            templates_list = [
                t for t in templates_list if _canonical_fold_type(t["fold_type"]) == wanted
            ]

        if not templates_list:
            typer.echo("No templates found.")
            if occasion or fold_type:
                typer.echo("Try removing filters to see all templates.")
            raise typer.Exit(ExitCode.OK)

        # Output in requested format
        if format is ListFormat.JSON:
            typer.echo(json.dumps({"templates": templates_list}, indent=2))
        elif format is ListFormat.YAML:
            for t in templates_list:
                typer.echo(f"- id: {t['id']}")
                typer.echo(f"  name: {t['name']}")
                typer.echo(f"  occasion: {t['occasion']}")
                typer.echo(f"  fold_type: {t['fold_type']}")
                if t.get("description"):
                    typer.echo(f"  description: {t['description']}")
        else:
            # SOURCE only when a user / env layer contributes (#79).
            with_source = any(t["source"] != "builtin" for t in templates_list)
            rows = [
                [t["id"], t["occasion"], t["fold_type"], *([t["source"]] if with_source else []), t["name"]]
                for t in sorted(templates_list, key=lambda t: (t["occasion"], t["id"]))
            ]
            _echo_table(["ID", "OCCASION", "FOLD", *(["SOURCE"] if with_source else []), "NAME"], rows)
            typer.echo(f"\n{len(templates_list)} template(s) found.")

    except (typer.Exit, BrokenPipeError):
        # Preserve intentional exit codes (e.g. Exit(0) for "no results");
        # a closed stdout pipe is handled by _CLIGroup, not reported here.
        raise
    except Exception as e:
        _unexpected_error("Error listing templates", e)


def _fail_empty_catalog(kind: str, directory: Path) -> NoReturn:
    # An unfiltered empty catalog means a broken install (D4: fail loud).
    typer.echo(
        f"Error: no {kind} found in {directory} — installation is missing bundled data",
        err=True,
    )
    raise typer.Exit(ExitCode.ERROR)


@app.command(name="themes")
def list_themes(
    occasion: str | None = typer.Option(None, "--occasion", help="Filter by occasion type"),
    format: ListFormat = _LIST_FORMAT_OPTION,
) -> None:
    """List available color themes.

    The ID column is what ``--theme`` takes.
    """
    try:
        themes_list = discover_themes()
        if not themes_list and not occasion:
            _fail_empty_catalog("themes", get_themes_dir())

        # Filter by occasion if specified
        if occasion:
            themes_list = [t for t in themes_list if t["occasion"] == occasion]

        if not themes_list:
            typer.echo("No themes found.")
            if occasion:
                typer.echo("Try removing filters to see all themes.")
            raise typer.Exit(ExitCode.OK)

        # Output in requested format
        if format is ListFormat.JSON:
            typer.echo(json.dumps({"themes": themes_list}, indent=2))
        elif format is ListFormat.YAML:
            for t in themes_list:
                typer.echo(f"- id: {t['id']}")
                typer.echo(f"  name: {t['name']}")
                typer.echo(f"  occasion: {t['occasion']}")
                if t.get("description"):
                    typer.echo(f"  description: {t['description']}")
        else:
            rows = [
                [t["id"], t["occasion"], t["name"]]
                for t in sorted(themes_list, key=lambda t: (t["occasion"], t["id"]))
            ]
            _echo_table(["ID", "OCCASION", "NAME"], rows)
            typer.echo(f"\n{len(themes_list)} theme(s) found.")

    except (typer.Exit, BrokenPipeError):
        # Preserve intentional exit codes (e.g. Exit(0) for "no results");
        # a closed stdout pipe is handled by _CLIGroup, not reported here.
        raise
    except Exception as e:
        _unexpected_error("Error listing themes", e)


# --- content options shared by ``create`` and ``preview`` (#78: same names, same short flags),
# grouped into the same help panels on both commands (#80).

_CONTENT = "Content"
_LETTER = "Inside letter"
_LAYOUT = "Layout"
_OUTPUT = "Output"

_MESSAGE_OPTION = typer.Option(
    None, "--message", "-m", help="Greeting message text", rich_help_panel=_CONTENT
)
_FOLD_TYPE_OPTION = typer.Option(
    None, "--fold-type", "-f", help="Override fold type: half_fold, quarter_fold, tri_fold",
    rich_help_panel=_LAYOUT,
)
_IMAGE_OPTION = typer.Option(
    None,
    "--image",
    "-i",
    help=(
        "Photo for the template's photo slots (PNG/JPEG, any path). "
        "Repeat to fill slot 2, 3, …; unfilled slots keep the placeholder."
    ),
    rich_help_panel=_CONTENT,
)
_THEME_OPTION = typer.Option(
    None, "--theme", "-t", help="Color theme to apply (e.g., christmas-red-green)",
    rich_help_panel=_CONTENT,
)
_INSIDE_MESSAGE_OPTION = typer.Option(
    None, "--inside-message", help="Message for the inside panel",
    rich_help_panel=_CONTENT,
)
_INSIDE_MESSAGE_MD_OPTION = typer.Option(
    None,
    "--inside-message-md",
    help=(
        "Path to a Markdown file for the inside panel ('Christmas "
        "letter' mode). Supports paragraphs, **bold**, *italic*, "
        "***bold-italic*** and hard line breaks. Mutually exclusive "
        "with --inside-message and overrides --voice's inside pick. "
        "Cormorant and PlayfairDisplay render every style; Lato has "
        "Bold only; Inter, Caveat and Comfortaa render regular."
    ),
    rich_help_panel=_CONTENT,
)
_VOICE_OPTION = typer.Option(
    None,
    "--voice",
    help=(
        "Pick a curated cover greeting and inside message in the "
        "given voice. One of: warm, witty, spare, devotional, "
        "irreverent. Explicit --message / --inside-message override "
        "the picked sentiment."
    ),
    rich_help_panel=_CONTENT,
)
_BLANK_INSIDE_OPTION = typer.Option(
    False,
    "--blank-inside",
    help="Render the inside panel with no message text.",
    rich_help_panel=_CONTENT,
)
_SEED_OPTION = typer.Option(
    None,
    "--seed",
    help=(
        "Reproducible sentiment selection: same seed + same template "
        "+ same voice → same picked line. Default is random."
    ),
    rich_help_panel=_CONTENT,
)
_SALUTATION_OPTION = typer.Option(
    None,
    "--salutation",
    help=(
        "Inside-letter salutation, e.g. 'Dear Aunt Margaret,'. "
        "Renders as the top line of the inside panel."
    ),
    rich_help_panel=_LETTER,
)
_SIGNOFF_OPTION = typer.Option(
    None,
    "--signoff",
    help=(
        "Inside-letter signoff line, e.g. 'Love,' or 'Always,'. "
        "Renders below the body with extra vertical breathing room."
    ),
    rich_help_panel=_LETTER,
)
_SIGNATURE_OPTION = typer.Option(
    None,
    "--signature",
    help=(
        "Inside-letter signature (the writer's name). Pair with "
        "--signature-font for the handwritten-feel convention."
    ),
    rich_help_panel=_LETTER,
)
_PS_OPTION = typer.Option(
    None,
    "--ps",
    help=(
        "Inside-letter P.S. line — renders at 85% of body size, "
        "below the signature. Conventionally the most-read line."
    ),
    rich_help_panel=_LETTER,
)
_SIGNATURE_FONT_OPTION = typer.Option(
    None,
    "--signature-font",
    help=(
        "Font family for the signature line. Defaults to the "
        "template's inside font; 'Caveat' (curated handwritten) "
        "is the conventional pick."
    ),
    rich_help_panel=_LETTER,
)


@app.command()
def create(
    template: str = typer.Argument(..., help="Template name or path"),
    message: str | None = _MESSAGE_OPTION,
    inside_message: str | None = _INSIDE_MESSAGE_OPTION,
    inside_message_md: Path | None = _INSIDE_MESSAGE_MD_OPTION,
    voice: str | None = _VOICE_OPTION,
    seed: int | None = _SEED_OPTION,
    blank_inside: bool = _BLANK_INSIDE_OPTION,
    theme: str | None = _THEME_OPTION,
    image: list[Path] | None = _IMAGE_OPTION,
    salutation: str | None = _SALUTATION_OPTION,
    signoff: str | None = _SIGNOFF_OPTION,
    signature: str | None = _SIGNATURE_OPTION,
    ps: str | None = _PS_OPTION,
    signature_font: str | None = _SIGNATURE_FONT_OPTION,
    fold_type: str | None = _FOLD_TYPE_OPTION,
    panel_fit: str | None = typer.Option(
        None,
        "--panel-fit",
        help=(
            "How a fixed-trim target (moo-a6) maps each panel onto its trim: "
            "'fill' (the default) scales the art to cover the trim and crops "
            "the overflow; 'letterbox' fits it whole and leaves paper bands. "
            "Refused for targets that keep the panel's native size."
        ),
        rich_help_panel=_LAYOUT,
    ),
    with_fold_marks: bool | None = typer.Option(
        None,
        "--with-fold-marks/--no-fold-marks",
        help=(
            "Emit (or suppress) the dashed grey fold-line guide. "
            "Default depends on --export-for: 'letter' emits the guide "
            "(home printer needs it for accurate folding); per-panel "
            "POD targets suppress it (each output is a finished card "
            "and the guide would print on the product)."
        ),
        rich_help_panel=_LAYOUT,
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Output file (.pdf/.svg), or directory for per-panel --export-for targets",
        rich_help_panel=_OUTPUT,
    ),
    output_format: str = typer.Option(
        "auto",
        "--format",
        help="Output format: 'pdf', 'svg', or 'auto' (infers from --output extension).",
        rich_help_panel=_OUTPUT,
    ),
    export_for: str = typer.Option(
        "letter",
        "--export-for",
        help=(
            "Print target preset. 'letter' (default) emits a single "
            "imposed sheet; 'per-panel-pdf' and 'moo-a6' emit one file "
            "per panel into a directory. See README for the full "
            "registry."
        ),
        rich_help_panel=_OUTPUT,
    ),
    allow_low_res: bool = typer.Option(
        False,
        "--allow-low-res",
        help=(
            "Render PDF output even when a photo is below the 150 PPI print "
            "minimum (it is reported as a warning instead). For proofs only: "
            "the print will be soft. 300 PPI is recommended."
        ),
        rich_help_panel=_OUTPUT,
    ),
    debug_emit_ir: bool = typer.Option(
        False,
        "--debug-emit-ir",
        hidden=True,
        help="(Wave 2 dev flag) Compile to RenderCommand IR and print as JSON; skip PDF output.",
    ),
) -> None:
    """Create a new card from a template.

    Examples:

        holiday-card create christmas-classic -m "Merry Christmas!"

        holiday-card create christmas-classic --message "Happy Holidays!" --output ./cards/holiday.pdf

        holiday-card create christmas-classic --format svg --output ./cards/holiday.svg

        holiday-card create christmas-classic --export-for moo-a6 --output ./moo-card/
    """
    try:
        request = _build_request(
            template=template,
            message=message,
            inside_message=inside_message,
            inside_message_md=inside_message_md,
            voice=voice,
            seed=seed,
            blank_inside=blank_inside,
            salutation=salutation,
            signoff=signoff,
            signature=signature,
            postscript=ps,
            signature_font=signature_font,
            theme=theme,
            fold_type=fold_type,
            images=image,
            output=output,
            output_format=output_format,
            export_for=export_for,
            fold_marks=with_fold_marks,
            panel_fit=panel_fit,
            allow_low_res=allow_low_res,
        )
        if debug_emit_ir:
            _emit_ir_debug(request)
            return

        plan = plan_output(request, now=datetime.now())
        output = plan.path
        target = plan.target

        typer.echo(f"Creating card from template: {template}")

        card, report = build_card_with_report(request)
        generator = CardGenerator(renderer=_make_renderer(plan.output_format))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", SafeZoneWarning)
            warnings.simplefilter("always", LowResolutionWarning)
            written = generator.generate(
                card, plan.path, target, emit_fold_lines=request.fold_marks,
                allow_low_res=request.allow_low_res,
            )
        for warning in caught:
            if issubclass(warning.category, SafeZoneWarning | LowResolutionWarning):
                typer.secho(f"Warning: {warning.message}", fg=typer.colors.YELLOW, err=True)
            else:
                warnings.showwarning(
                    warning.message, warning.category, warning.filename, warning.lineno,
                )

        # Success output
        if target.layout == "per-panel":
            typer.secho(f"Card created ({len(written)} files): {plan.path}", fg=typer.colors.GREEN)
            for path in written:
                typer.echo(f"  - {path.name}")
        else:
            typer.secho(f"Card created: {written[0]}", fg=typer.colors.GREEN)
        typer.echo(f"  Template: {template}")
        typer.echo(f"  Fold: {card.fold_type.value}")
        typer.echo(f"  Target: {target.name} ({target.layout})")
        _echo_content_summary(request, report, card)

    except (typer.Exit, BrokenPipeError):
        # Preserve intentional exit codes from inner validation
        # (invalid fold type, missing image, etc.).
        raise

    except PermissionError as e:
        typer.secho(f"Error: Cannot write to {output}", fg=typer.colors.RED, err=True)
        typer.echo("Check that you have write permission to the output directory.", err=True)
        raise typer.Exit(ExitCode.ENVIRONMENT) from e

    except Exception as e:
        _exit_for_card_error("Error creating card", e)


@app.command()
def preview(
    template: str = typer.Argument(..., help="Template name or path"),
    message: str | None = _MESSAGE_OPTION,
    inside_message: str | None = _INSIDE_MESSAGE_OPTION,
    inside_message_md: Path | None = _INSIDE_MESSAGE_MD_OPTION,
    voice: str | None = _VOICE_OPTION,
    seed: int | None = _SEED_OPTION,
    blank_inside: bool = _BLANK_INSIDE_OPTION,
    theme: str | None = _THEME_OPTION,
    image: list[Path] | None = _IMAGE_OPTION,
    salutation: str | None = _SALUTATION_OPTION,
    signoff: str | None = _SIGNOFF_OPTION,
    signature: str | None = _SIGNATURE_OPTION,
    ps: str | None = _PS_OPTION,
    signature_font: str | None = _SIGNATURE_FONT_OPTION,
    fold_type: str | None = _FOLD_TYPE_OPTION,
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output PNG file path",
        rich_help_panel=_OUTPUT,
    ),
    dpi: int = typer.Option(
        144, "--dpi", "-d", help="Preview resolution (dots per inch)",
        rich_help_panel=_OUTPUT,
    ),
    open_after: bool = typer.Option(
        True, "--open/--no-open", help="Open the preview in your default image viewer.",
        rich_help_panel=_OUTPUT,
    ),
) -> None:
    """Generate a fast PNG preview of a card and open it in your default viewer.

    Takes every content option ``create`` takes (message, inside text,
    Markdown, letter parts, voice, theme, fold type, photos) and builds
    the card through the same pipeline, so the preview shows the card
    ``create`` would write for the same flags. It renders the default
    ``letter`` sheet; ``--export-for`` and ``--format`` are ``create``-only.

    Examples:

        holiday-card preview christmas-classic

        holiday-card preview christmas-classic -m "Merry Christmas!" --dpi 300

        holiday-card preview christmas-classic --voice spare --seed 1 --no-open -o out/preview.png
    """
    from holiday_card.core.compiler import compile_card
    from holiday_card.renderers.png_backend import PNGRenderer

    try:
        request = _build_request(
            template=template,
            message=message,
            inside_message=inside_message,
            inside_message_md=inside_message_md,
            voice=voice,
            seed=seed,
            blank_inside=blank_inside,
            salutation=salutation,
            signoff=signoff,
            signature=signature,
            postscript=ps,
            signature_font=signature_font,
            theme=theme,
            fold_type=fold_type,
            images=image,
        )

        # Default output path
        if output is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            output = Path("output") / f"{template}-preview-{timestamp}.png"

        # Ensure .png suffix (Pillow infers format from extension)
        if not str(output).lower().endswith(".png"):
            output = Path(f"{output}.png")

        typer.echo(f"Generating preview for template: {template}")

        card, report = build_card_with_report(request)
        commands = compile_card(card)
        output.parent.mkdir(parents=True, exist_ok=True)
        PNGRenderer(dpi=dpi).render(commands, output)

        typer.secho(f"Preview generated: {output}", fg=typer.colors.GREEN)
        typer.echo(f"  Template: {template}")
        typer.echo(f"  Resolution: {dpi} DPI")
        _echo_content_summary(request, report, card)

        if open_after:
            _open_in_default_viewer(output)

    except (typer.Exit, BrokenPipeError):
        raise

    except Exception as e:
        _exit_for_card_error("Error generating preview", e)


@app.command()
def init(
    name: str = typer.Argument(..., help="Template name (e.g., my-template)"),
    occasion: str = typer.Option(
        "generic", "--occasion", help=f"Occasion type: {', '.join(o.value for o in OccasionType)}"
    ),
    fold_type: str = typer.Option(
        "quarter_fold", "--fold-type", "-f", help="Fold type: quarter_fold (half_fold is an alias), tri_fold"
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for template file (default: the user template "
        "dir, $XDG_DATA_HOME/holiday-card/templates/<occasion>)",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite an existing template file"
    ),
) -> None:
    """Initialize a new custom template.

    Creates a starter template YAML file that you can customize. By default
    it goes in the user template dir, which ``create`` searches, so
    ``holiday-card create <name>`` finds it.

    Examples:

        holiday-card init my-custom-card

        holiday-card init wedding-invite --occasion generic --fold-type quarter_fold
    """
    import shlex

    import yaml

    valid_occasions = [o.value for o in OccasionType]
    if occasion not in valid_occasions:
        _fail(
            f"unknown occasion {occasion!r}. Valid occasions: "
            f"{', '.join(valid_occasions)}"
        )

    if output_dir is None:
        output_dir = user_templates_dir() / occasion
    template_path = output_dir / f"{name}.yaml"
    if template_path.exists() and not force:
        _fail(f"{template_path} already exists (use --force to overwrite)")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate template content. Panel x/y/rotation are computed from the
    # fold type by the compiler (D6), so the scaffold leaves them out.
    template_data = {
        "id": name,
        "name": name.replace("-", " ").title(),
        "occasion": occasion,
        "fold_type": fold_type,
        "description": f"Custom {occasion} card template",
        "panels": [
            {
                "id": "front",
                "position": "front",
                "width": 4.25,
                "height": 5.5,
                "background_color": {"r": 0.9, "g": 0.9, "b": 0.9},
                "text_elements": [
                    {
                        "id": "greeting",
                        "content": "Your Greeting Here",
                        "x": 2.125,
                        "y": 2.75,
                        "font_family": "PlayfairDisplay",
                        "font_size": 28,
                        "alignment": "center",
                        "color": {"r": 0.2, "g": 0.2, "b": 0.2},
                    }
                ],
            },
            {
                "id": "back",
                "position": "back",
                "width": 4.25,
                "height": 5.5,
            },
            {
                "id": "inside_left",
                "position": "inside_left",
                "width": 4.25,
                "height": 5.5,
            },
            {
                "id": "inside_right",
                "position": "inside_right",
                "width": 4.25,
                "height": 5.5,
                "text_elements": [
                    {
                        "id": "message",
                        "content": "Your message here",
                        "x": 0.5,
                        "y": 3.0,
                        "width": 3.25,
                        "font_family": "Lato",
                        "font_size": 14,
                        "color": {"r": 0.3, "g": 0.3, "b": 0.3},
                    }
                ],
            },
        ],
    }

    with open(template_path, "w") as f:
        yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)

    # Suggest the id only when it resolves to this file (it's on a search
    # layer and nothing earlier shadows it); otherwise suggest the path.
    try:
        found = resolve_template(name)[1].resolve() == template_path.resolve()
    except (TemplateNotFoundError, TemplateLoadError):
        found = False
    ref = name if found else str(template_path)
    typer.secho(f"Template created: {template_path}", fg=typer.colors.GREEN)
    typer.echo("\nEdit the file to customize your template, then use:")
    typer.echo(f"  holiday-card create {shlex.quote(ref)} -m \"Your message\"")


@app.command()
def validate(
    template: str = typer.Argument(..., help="Template name or path to validate"),
) -> None:
    """Validate a template: schema, fonts, element bounds, theme, and a compile.

    Lists every problem at once as `  - <path>: <message>` and exits 2, or
    prints `Template valid` and a summary. Run it before `create`.

    Examples:

        holiday-card validate christmas-classic

        holiday-card validate ./my-template.yaml
    """
    try:
        try:
            loaded, template_path = resolve_template(template)
        except TemplateLoadError as e:
            _report_invalid(template, e.problems or [("<file>", str(e))])
        problems = check_template(loaded)
        if problems:
            _report_invalid(template, [(p.path, p.message) for p in problems])
        typer.secho(f"Template valid: {template}", fg=typer.colors.GREEN)
        typer.echo(f"  Path: {template_path}")
        typer.echo(f"  Name: {loaded.name}")
        typer.echo(f"  Occasion: {loaded.occasion.value}")
        typer.echo(f"  Fold type: {loaded.fold_type.value}")
        typer.echo(f"  Panels: {len(loaded.panels)}")

    except (typer.Exit, BrokenPipeError):
        raise

    except TemplateNotFoundError as e:
        typer.secho(f"Template not found: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.USAGE) from e

    except Exception as e:
        _unexpected_error("Validation error", e)


def _report_invalid(source: str, problems: list[tuple[str, str]]) -> NoReturn:
    typer.secho(f"Template invalid: {source}", fg=typer.colors.RED)
    for path, message in problems:
        typer.echo(f"  - {path}: {message}")
    raise typer.Exit(ExitCode.USAGE)


@app.command()
def schema(
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the schema here instead of stdout."
    ),
) -> None:
    """Print the template JSON Schema (generated from the models).

    Point an editor at it for completion and checking, e.g. a first line of
    `# yaml-language-server: $schema=<path>/template-schema.json`.

    Examples:

        holiday-card schema -o template-schema.json
    """
    text = render_template_schema()
    if output is None:
        typer.echo(text, nl=False)
        return
    try:
        output.write_text(text)
    except OSError as e:
        _fail(f"cannot write {output}: {e}")
    typer.echo(f"Wrote {output}", err=True)


# ---------------------------------------------------------------------------
# ai-asset — authoring-time AI imagery (Leapfrog 3)
# ---------------------------------------------------------------------------

ai_asset_app = typer.Typer(
    name="ai-asset",
    help=(
        "Authoring-time AI imagery (personal use only). Bakes one image "
        "to disk with a provenance sidecar; never runs at render time. "
        "Choose the provider with --provider or HOLIDAY_CARD_AI_PROVIDER: "
        "openai (the default) needs `pip install holiday-card\\[ai]` and "
        "OPENAI_API_KEY; openrouter needs only OPENROUTER_API_KEY."
    ),
    pretty_exceptions_show_locals=False,  # never print api keys / headers from frames
)
app.add_typer(ai_asset_app, name="ai-asset")


# ProviderError.kind -> exit code and what to tell the user (#142).
_PROVIDER_EXIT = {
    "refused": ExitCode.PROVIDER_REFUSED,
    "transient": ExitCode.PROVIDER_ERROR,
    "environment": ExitCode.ENVIRONMENT,
    "usage": ExitCode.USAGE,
}
_PROVIDER_WHAT = {
    "refused": "the AI provider refused the request",
    "transient": "the AI provider request failed (retryable)",
    "environment": "the AI provider rejected the API key, account or region",
    "usage": "the AI provider rejected the request as invalid",
}


@ai_asset_app.command("generate")
def ai_asset_generate(
    subject: str = typer.Option(
        ...,
        "--subject",
        "--prompt",
        help="What to generate, e.g. 'watercolor pine bough border, sage green'.",
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Output PNG path."),
    occasion: str = typer.Option(
        "generic",
        "--occasion",
        help=(
            "Occasion the asset is for. Drives the hard category rails: "
            "sympathy / condolence / miscarriage / pet_loss refuse AI by "
            "default."
        ),
    ),
    reference: Path | None = typer.Option(
        None,
        "--reference",
        help=(
            "Curated reference image to anchor style (image-reference mode, "
            "the default). Required unless --unsafe-no-style-anchor is set."
        ),
    ),
    unsafe_no_style_anchor: bool = typer.Option(
        False,
        "--unsafe-no-style-anchor",
        help="Allow free text-to-image with no style anchor (discouraged).",
    ),
    style: str | None = typer.Option(
        None, "--style", help="Enumerated style tag recorded in provenance, e.g. 'watercolor'."
    ),
    export_for: str = typer.Option(
        "moo-a6",
        "--export-for",
        help="Print target whose geometry sizes the image (trim+bleed at 300 PPI).",
    ),
    provider: AIProvider = typer.Option(
        AIProvider.OPENAI,
        "--provider",
        envvar="HOLIDAY_CARD_AI_PROVIDER",
        help=(
            "Image provider: openai (key OPENAI_API_KEY, needs the \\[ai] extra) or "
            "openrouter (key OPENROUTER_API_KEY). Default: $HOLIDAY_CARD_AI_PROVIDER, "
            "else openai. Never inferred from --model."
        ),
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Model id for --provider (default: "
        + ", ".join(f"{info.default_model} for {p.value}" for p, info in PROVIDERS.items())
        + ").",
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        help=(
            "Seed, for models that support one (recorded in provenance). "
            "Refused for models without a seed."
        ),
    ),
    i_know_what_im_doing: bool = typer.Option(
        False,
        "--i-know-what-im-doing",
        help="Override the hard category rails. Prints every reason first.",
    ),
    accept_ai_terms: bool = typer.Option(
        False,
        "--accept-ai-terms",
        help="Non-interactively record the one-time AI consent acknowledgement.",
    ),
) -> None:
    """Generate one AI image asset to disk with a provenance sidecar.

    Example:

        holiday-card ai-asset generate \\
          --subject "watercolor pine bough border, sage green and burgundy" \\
          --reference path/to/reference.png --style watercolor \\
          --occasion christmas --export-for moo-a6 -o assets/ai/border.png

    Through OpenRouter (OPENROUTER_API_KEY; no install extra):

        holiday-card ai-asset generate --provider openrouter \\
          --subject "watercolor pine bough border, sage green and burgundy" \\
          --reference path/to/reference.png --occasion christmas -o assets/ai/border.png
    """
    from holiday_card.core.ai_assets import (
        ConsentRequiredError,
        ImagePayloadError,
        RailRefusedError,
        build_ai_request,
        generate_ai_asset,
    )
    from holiday_card.core.ai_errors import ProviderError
    from holiday_card.core.ai_provenance import (
        consent_notice,
        default_consent_path,
        has_consented,
        record_consent,
    )
    from holiday_card.core.images import ImageSourceError, probe_image

    # Validate occasion early.
    try:
        occasion_enum = OccasionType(occasion)
    except ValueError as e:
        typer.secho(
            f"Error: unknown occasion {occasion!r}.", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(ExitCode.USAGE) from e

    # Usage errors come before consent, so they never record it as a side effect.
    from holiday_card.core.ai_providers import (
        UnknownModelError,
        reference_limits,
        resolve_model,
        supports_seed,
    )

    try:
        resolved_model = resolve_model(provider, model)
    except UnknownModelError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    if seed is not None and not supports_seed(provider, resolved_model):
        typer.secho(
            f"Error: --seed is not supported by {provider.value} model {resolved_model!r} "
            "(it takes no seed, so the image could not be reproduced). Omit --seed.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(ExitCode.USAGE)

    # S2 per model: a model that takes no reference can only run unanchored,
    # and one that needs a reference cannot.
    min_refs, max_refs = reference_limits(provider, resolved_model)
    if max_refs == 0 and (reference is not None or not unsafe_no_style_anchor):
        typer.secho(
            f"Error: {provider.value} model {resolved_model!r} accepts no reference image, "
            "so it cannot be style-anchored. Pass --unsafe-no-style-anchor without "
            "--reference to use it, or choose another --model.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(ExitCode.USAGE)
    if min_refs >= 1 and reference is None:
        typer.secho(
            f"Error: {provider.value} model {resolved_model!r} needs a --reference image; "
            "--unsafe-no-style-anchor cannot be used with it.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(ExitCode.USAGE)

    # Image-reference mode is the default; a missing reference is an error
    # unless the user explicitly opts into the unsafe no-anchor path.
    if reference is None and not unsafe_no_style_anchor:
        typer.secho(
            "Error: --reference is required (image-reference mode is the "
            "default style anchor). Pass --unsafe-no-style-anchor to "
            "generate with no anchor (discouraged: produces voiceless slop).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(ExitCode.USAGE)
    # The reference is uploaded as-is, so it must really be a PNG / JPEG:
    # a typo such as `--reference .env` would otherwise exfiltrate the file.
    reference_path: str | None = None
    if reference is not None:
        try:
            reference_path = str(probe_image(reference).path)
        except ImageSourceError as e:
            typer.secho(f"Error: --reference: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(ExitCode.USAGE) from e

    # First-use consent gate.
    consent_path = default_consent_path()
    if not has_consented(consent_path, provider):
        notice = consent_notice(provider, path=consent_path, model=resolved_model)
        if accept_ai_terms:
            record_consent(consent_path, provider)
            typer.echo(notice)
        else:
            typer.secho(
                f"Error: AI imagery with --provider {provider.value} requires a one-time "
                "consent acknowledgement. Re-run with --accept-ai-terms after "
                "reading the notice below.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.echo(notice, err=True)
            raise typer.Exit(ExitCode.CONSENT_REQUIRED)

    # Resolve print geometry → pixel dims.
    try:
        target = get_target(export_for)
    except ExportTargetNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    geom = target.geometry
    if geom is None:
        typer.secho(
            f"Error: --export-for {export_for!r} has no fixed geometry to "
            "size against. Use a target with a defined trim (e.g. moo-a6).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(ExitCode.USAGE)

    if i_know_what_im_doing:
        from holiday_card.core.ai_rails import evaluate_rails

        violations = evaluate_rails(occasion_enum, subject)
        if violations:
            typer.secho(
                "WARNING: overriding hard category rails:", fg=typer.colors.YELLOW
            )
            for v in violations:
                typer.secho(f"  [{v.category}] {v.reason}", fg=typer.colors.YELLOW)

    from holiday_card.core.ai_providers import AIDependencyError

    try:
        client = make_image_client(provider=provider, model=resolved_model)
    except AIDependencyError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.ENVIRONMENT) from e
    except ProviderError as e:  # e.g. a key with whitespace inside it, refused before any call
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(_PROVIDER_EXIT[e.kind]) from e

    # Size for the model the client actually calls (#87).
    request = build_ai_request(
        prompt=subject,
        trim_width_in=geom.trim_width_in,
        trim_height_in=geom.trim_height_in,
        bleed_in=geom.bleed_in,
        reference_path=reference_path,
        provider=client.provider,
        model=client.model,
    )

    try:
        result = generate_ai_asset(
            prompt=subject,
            occasion=occasion_enum,
            out_path=output,
            request=request,
            client=client,
            consent_path=consent_path,
            timestamp=datetime.now().isoformat(),
            style=style,
            seed=seed,
            override=i_know_what_im_doing,
        )
    except ConsentRequiredError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.CONSENT_REQUIRED) from e
    except RailRefusedError as e:
        typer.secho("Error: AI imagery refused by hard category rails:", fg=typer.colors.RED, err=True)
        for v in e.violations:
            typer.secho(f"  [{v.category}] {v.reason}", fg=typer.colors.RED, err=True)
        typer.echo(
            "\nThese categories default to refuse. If you are certain, "
            "re-run with --i-know-what-im-doing.",
            err=True,
        )
        raise typer.Exit(ExitCode.RAIL_REFUSED) from e
    except ProviderError as e:  # never re-raised, even under --debug: the exit code is the contract
        what = _PROVIDER_WHAT[e.kind]
        status = f" (HTTP {e.status})" if e.status is not None else ""
        typer.secho(f"Error: {what}{status}: {e}", fg=typer.colors.RED, err=True)
        if e.retry_after_s is not None:
            typer.echo(f"Retry after {e.retry_after_s:g} s.", err=True)
        raise typer.Exit(_PROVIDER_EXIT[e.kind]) from e
    except ImagePayloadError as e:  # like ProviderError: an exit code, never a traceback
        typer.secho(f"Error: the model's image was refused: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.PROVIDER_ERROR) from e
    except (typer.Exit, BrokenPipeError):
        raise
    except Exception as e:
        _unexpected_error("Error generating AI asset", e)

    typer.secho(f"AI asset written: {result.asset_path}", fg=typer.colors.GREEN)
    typer.echo(f"  Provenance: {result.sidecar_path.name}")
    route = f" (route: {result.provider_route})" if result.provider_route else ""
    typer.echo(f"  Provider: {client.provider.value}{route}")
    typer.echo(f"  Model: {client.model}")
    typer.echo(
        f"  Size: {result.width_px}x{result.height_px}px @ {request.dpi} DPI (sRGB), "
        f"{result.native_ppi:.1f} PPI native"
    )
    if result.native_ppi < request.dpi:
        typer.secho(
            f"  Warning: the model's output is {result.native_ppi:.1f} PPI at the "
            f"print size, below {request.dpi}; it was upscaled and may print soft.",
            fg=typer.colors.YELLOW,
        )
    if result.cost_usd is not None:
        typer.echo(f"  Cost: ${result.cost_usd:.2f} (reported)")
    else:
        typer.echo("  Cost: unknown (the provider did not report one)")
    for url in result.policy_urls:
        typer.echo(f"  Policy: {url}")
    typer.echo(
        "  Personal use only — AI imagery is not recommended for cards you sell."
    )


def _open_in_default_viewer(path: Path) -> None:
    """Open ``path`` in the OS's default viewer for that file type.

    Best-effort and silent on failure — preview is a developer
    convenience, not a guaranteed contract.
    """
    import subprocess

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", str(path)], check=False)
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001 — preview is best-effort
        typer.secho(f"  (could not auto-open: {e})", fg=typer.colors.YELLOW, err=True)


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _read_markdown(path: Path) -> str:
    """Read ``--inside-message-md`` up front so a bad file fails before anything renders."""
    from holiday_card.core.markdown import parse_markdown

    if not path.exists():
        _fail(f"--inside-message-md file not found: {path}")
    try:
        text = path.read_text()
        parse_markdown(text)
    except (OSError, ValueError) as e:
        typer.secho(f"Error reading {path}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    return text


def _build_request(
    *,
    inside_message_md: Path | None,
    images: list[Path] | None,
    **fields: Any,
) -> CardRequest:
    """Turn parsed options into a :class:`CardRequest`; a refusal is exit 2."""
    inside_markdown = _read_markdown(inside_message_md) if inside_message_md is not None else None
    try:
        return CardRequest(inside_markdown=inside_markdown, images=tuple(images or ()), **fields)
    except ValidationError as e:
        error = unwrap_validation_error(e)
        if isinstance(error, UnknownExportTargetError):
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            typer.echo("\nAvailable --export-for targets:", err=True)
            for name in sorted(EXPORT_TARGET_REGISTRY):
                typer.echo(f"  {name}: {EXPORT_TARGET_REGISTRY[name].description}", err=True)
            raise typer.Exit(ExitCode.USAGE) from e
        _fail(str(error))


def _exit_for_card_error(prefix: str, e: Exception) -> NoReturn:
    """Map a card-building error to its exit code (the shared tail of create / preview)."""
    if isinstance(e, TemplateNotFoundError):
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        typer.echo("\nAvailable templates:", err=True)
        templates_list = discover_templates()
        for t in templates_list[:5]:
            typer.echo(f"  - {t['id']}", err=True)
        if len(templates_list) > 5:
            typer.echo(f"  ... and {len(templates_list) - 5} more", err=True)
        typer.echo("\nRun 'holiday-card templates' to see all options.", err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    if isinstance(e, TemplateLoadError):
        typer.secho(f"Error loading template: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    if isinstance(e, PhotoSlotError):
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        slotted = templates_with_photo_slots()
        if slotted:
            typer.echo(f"Templates with photo slots: {', '.join(slotted)}", err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    from holiday_card.renderers.pdfx_preflight import PDFXConformanceError  # pikepdf: lazy

    if isinstance(e, PDFXConformanceError):
        # The self-check after PDF/X post-processing (#71): list every violation.
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    if isinstance(e, ImageSourceError | UnsupportedFeatureError | ValidationError | ValueError):
        # Bad or contradictory input (D4): the message is already user-facing.
        message = validation_message(e) if isinstance(e, ValidationError) else str(e)
        typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(ExitCode.USAGE) from e
    _unexpected_error(prefix, e)


def _echo_content_summary(request: CardRequest, report: BuildReport, card: Card) -> None:
    """The per-content lines of the success summary, shared by create / preview."""
    if request.voice:
        typer.echo(f"  Voice: {request.voice}")
        if report.picked_cover is not None:
            typer.echo(f"  Picked cover: {_truncate(report.picked_cover, 60)}")
        if report.picked_inside is not None:
            typer.echo(f"  Picked inside: {_truncate(report.picked_inside, 60)}")
    if request.blank_inside:
        typer.echo("  Inside: (blank)")
    inside = next(
        (
            t
            for p in card.panels
            for t in p.text_elements
            if t.rich_content is not None or t.letter_content is not None
        ),
        None,
    )
    if report.inside_mode == "markdown" and inside is not None and inside.rich_content is not None:
        n_paragraphs = len(inside.rich_content.paragraphs)
        typer.echo(f"  Inside: Markdown ({n_paragraphs} paragraph{'s' if n_paragraphs != 1 else ''})")
    if report.inside_mode == "letter" and inside is not None and inside.letter_content is not None:
        letter = inside.letter_content
        parts = [
            name for name, val in (
                ("salutation", letter.salutation),
                ("body", letter.body),
                ("signoff", letter.signoff),
                ("signature", letter.signature),
                ("P.S.", letter.postscript),
            ) if val
        ]
        typer.echo(f"  Inside: letter ({', '.join(parts)})")
    front_message = request.message if request.message is not None else report.picked_cover
    if front_message and not request.voice:
        typer.echo(f"  Message: {_truncate(front_message, 50)}")
    ai_labels = sorted({ai_disclosure_label(use.record) for use in embedded_ai_assets(card)})
    if ai_labels:
        typer.echo(f"  AI imagery: {'; '.join(ai_labels)} (disclosed in file metadata)")


def _make_renderer(output_format: str) -> "IRReportLabRenderer | SVGRenderer":
    """Construct the right renderer for the chosen output format."""
    if output_format == "svg":
        return SVGRenderer()
    return IRReportLabRenderer()


def _emit_ir_debug(request: CardRequest) -> None:
    """The hidden ``--debug-emit-ir`` flag: print ``compile_card(build_card(request))`` as JSON."""
    from holiday_card.core.compiler import compile_card

    commands = compile_card(build_card(request))
    payload = [json.loads(c.model_dump_json()) for c in commands]
    typer.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":
    app()
