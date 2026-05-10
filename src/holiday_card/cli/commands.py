"""CLI commands for holiday-card application.

This module implements the Typer CLI interface following Unix conventions.
All commands support both human-readable and JSON output formats.
"""

import json
from datetime import datetime
from pathlib import Path

import typer

from holiday_card import __version__
from holiday_card.core.export_targets import (
    REGISTRY as EXPORT_TARGET_REGISTRY,
)
from holiday_card.core.export_targets import (
    ExportTargetNotFoundError,
    get_target,
)
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import FoldType, ImageElement
from holiday_card.core.templates import (
    TemplateLoadError,
    TemplateNotFoundError,
    discover_templates,
    load_template_from_file,
)
from holiday_card.core.themes import discover_themes
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer
from holiday_card.utils.validators import ValidationError, validate_image_format

# Create main Typer app
app = typer.Typer(
    name="holiday-card",
    help="Create printable holiday greeting cards optimized for laser printing.",
    add_completion=False,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"holiday-card version {__version__}")
        raise typer.Exit()


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
) -> None:
    """Holiday Card Generator - Create printable greeting cards.

    Generate PDF greeting cards optimized for color laser printing
    on standard 8.5" x 11" paper. Supports multiple fold formats
    and customizable templates.
    """
    pass


@app.command()
def templates(
    occasion: str | None = typer.Option(
        None, "--occasion", "-o", help="Filter by occasion type"
    ),
    fold_type: str | None = typer.Option(
        None, "--fold-type", "-f", help="Filter by fold type"
    ),
    format: str = typer.Option(
        "table", "--format", help="Output format: table, json, yaml"
    ),
) -> None:
    """List available card templates."""
    try:
        templates_list = discover_templates()

        # Filter by occasion if specified
        if occasion:
            templates_list = [t for t in templates_list if t["occasion"] == occasion]

        # Filter by fold type if specified
        if fold_type:
            templates_list = [t for t in templates_list if t["fold_type"] == fold_type]

        if not templates_list:
            typer.echo("No templates found.")
            if occasion or fold_type:
                typer.echo("Try removing filters to see all templates.")
            raise typer.Exit(0)

        # Output in requested format
        if format == "json":
            typer.echo(json.dumps({"templates": templates_list}, indent=2))
        elif format == "yaml":
            for t in templates_list:
                typer.echo(f"- id: {t['id']}")
                typer.echo(f"  name: {t['name']}")
                typer.echo(f"  occasion: {t['occasion']}")
                typer.echo(f"  fold_type: {t['fold_type']}")
                if t.get("description"):
                    typer.echo(f"  description: {t['description']}")
        else:  # table format
            # Print header
            typer.echo(f"{'NAME':<25} {'OCCASION':<12} {'FOLD TYPE':<15} {'DESCRIPTION'}")
            typer.echo("-" * 80)

            # Print each template
            for t in templates_list:
                name = t["name"][:24] if len(t["name"]) > 24 else t["name"]
                desc = t.get("description", "")[:30] if t.get("description") else ""
                typer.echo(f"{name:<25} {t['occasion']:<12} {t['fold_type']:<15} {desc}")

            typer.echo(f"\n{len(templates_list)} template(s) found.")

    except typer.Exit:
        # Preserve intentional exit codes (e.g. Exit(0) for "no results").
        raise
    except Exception as e:
        typer.secho(f"Error listing templates: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e


@app.command(name="themes")
def list_themes(
    occasion: str | None = typer.Option(
        None, "--occasion", "-o", help="Filter by occasion type"
    ),
    format: str = typer.Option(
        "table", "--format", help="Output format: table, json, yaml"
    ),
) -> None:
    """List available color themes."""
    try:
        themes_list = discover_themes()

        # Filter by occasion if specified
        if occasion:
            themes_list = [t for t in themes_list if t["occasion"] == occasion]

        if not themes_list:
            typer.echo("No themes found.")
            if occasion:
                typer.echo("Try removing filters to see all themes.")
            raise typer.Exit(0)

        # Output in requested format
        if format == "json":
            typer.echo(json.dumps({"themes": themes_list}, indent=2))
        elif format == "yaml":
            for t in themes_list:
                typer.echo(f"- id: {t['id']}")
                typer.echo(f"  name: {t['name']}")
                typer.echo(f"  occasion: {t['occasion']}")
                if t.get("description"):
                    typer.echo(f"  description: {t['description']}")
        else:  # table format
            # Print header
            typer.echo(f"{'NAME':<25} {'OCCASION':<12} {'DESCRIPTION'}")
            typer.echo("-" * 70)

            # Print each theme
            for t in themes_list:
                name = t["name"][:24] if len(t["name"]) > 24 else t["name"]
                desc = t.get("description", "")[:30] if t.get("description") else ""
                typer.echo(f"{name:<25} {t['occasion']:<12} {desc}")

            typer.echo(f"\n{len(themes_list)} theme(s) found.")

    except typer.Exit:
        # Preserve intentional exit codes (e.g. Exit(0) for "no results").
        raise
    except Exception as e:
        typer.secho(f"Error listing themes: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e


@app.command()
def create(
    template: str = typer.Argument(..., help="Template name or path"),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Greeting message text"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output PDF file path"
    ),
    name: str | None = typer.Option(  # noqa: ARG001 (TODO: wire `name` into Card.name)
        None, "--name", "-n", help="Card name for identification"
    ),
    fold_type: str | None = typer.Option(
        None, "--fold-type", "-f", help="Override fold type: half_fold, quarter_fold, tri_fold"
    ),
    image: list[Path] | None = typer.Option(
        None, "--image", "-i", help="Add image to card (can be repeated)"
    ),
    theme: str | None = typer.Option(
        None, "--theme", "-t", help="Color theme to apply (e.g., christmas-red-green)"
    ),
    inside_message: str | None = typer.Option(
        None, "--inside-message", help="Message for the inside panel"
    ),
    debug_emit_ir: bool = typer.Option(
        False,
        "--debug-emit-ir",
        hidden=True,
        help="(Wave 2 dev flag) Compile to RenderCommand IR and print as JSON; skip PDF output.",
    ),
    output_format: str = typer.Option(
        "auto",
        "--format",
        help="Output format: 'pdf', 'svg', or 'auto' (infers from --output extension).",
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
        if debug_emit_ir:
            _emit_ir_debug(template, message, theme, fold_type, inside_message)
            return

        # Resolve the export target up-front; bad target = early exit.
        try:
            target = get_target(export_for)
        except ExportTargetNotFoundError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
            typer.echo("\nAvailable --export-for targets:", err=True)
            for name in sorted(EXPORT_TARGET_REGISTRY):
                typer.echo(f"  {name}: {EXPORT_TARGET_REGISTRY[name].description}", err=True)
            raise typer.Exit(2) from e

        # Resolve output format and extension
        chosen_format = _resolve_output_format(output_format, output)
        ext = ".pdf" if chosen_format == "pdf" else ".svg"

        # Generate default output path if not specified
        if output is None:
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            if target.layout == "per-panel":
                # Per-panel mode writes a directory of files; the timestamp
                # becomes the directory name.
                output = output_dir / f"{template}-{timestamp}"
            else:
                output = output_dir / f"{template}-{timestamp}{ext}"

        # Single-file mode: ensure the path has the expected extension.
        # Per-panel mode: path is a directory; extension is appended per
        # panel filename inside _generate_per_panel.
        if target.layout == "imposition" and not str(output).lower().endswith(ext):
            output = Path(f"{output}{ext}")

        generator = CardGenerator(renderer=_make_renderer(chosen_format))

        typer.echo(f"Creating card from template: {template}")

        # Parse fold type if provided
        fold_type_enum = None
        if fold_type:
            try:
                fold_type_enum = FoldType(fold_type)
            except ValueError as e:
                typer.secho(
                    f"Error: Invalid fold type '{fold_type}'. "
                    f"Valid options: half_fold, quarter_fold, tri_fold",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(2) from e

        # Validate and prepare images if provided
        image_elements: list[ImageElement] = []
        if image:
            for idx, img_path in enumerate(image):
                # Check file exists
                if not img_path.exists():
                    typer.secho(
                        f"Error: Image file not found: {img_path}",
                        fg=typer.colors.RED,
                        err=True,
                    )
                    raise typer.Exit(2)

                # Validate format
                try:
                    validate_image_format(img_path)
                except ValidationError as e:
                    typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
                    raise typer.Exit(2) from e

                # Create image element with default positioning
                # Images are placed on the front panel, stacked vertically
                image_elements.append(
                    ImageElement(
                        source_path=str(img_path.absolute()),
                        x=0.5,
                        y=1.0 + (idx * 2.0),  # Stack images vertically
                        width=3.0,
                        preserve_aspect=True,
                    )
                )

        # Generate the card
        card = generator.create_card(
            template_id=template,
            message=message,
            output_path=output,
            theme_id=theme,
            fold_type=fold_type_enum,
            images=image_elements if image_elements else None,
            inside_message=inside_message,
        )
        written = generator.generate(card, output, target)

        # Success output
        if target.layout == "per-panel":
            typer.secho(f"Card created ({len(written)} files): {output}", fg=typer.colors.GREEN)
            for path in written:
                typer.echo(f"  - {path.name}")
        else:
            typer.secho(f"Card created: {written[0]}", fg=typer.colors.GREEN)
        typer.echo(f"  Template: {template}")
        typer.echo(f"  Fold: {card.fold_type.value}")
        typer.echo(f"  Target: {target.name} ({target.layout})")
        if message:
            msg_preview = message[:50] + "..." if len(message) > 50 else message
            typer.echo(f"  Message: {msg_preview}")

    except typer.Exit:
        # Preserve intentional exit codes from inner validation
        # (invalid fold type, missing image, etc.).
        raise

    except TemplateNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        typer.echo("\nAvailable templates:", err=True)
        templates_list = discover_templates()
        for t in templates_list[:5]:
            typer.echo(f"  - {t['id']}", err=True)
        if len(templates_list) > 5:
            typer.echo(f"  ... and {len(templates_list) - 5} more", err=True)
        typer.echo("\nRun 'holiday-card templates' to see all options.", err=True)
        raise typer.Exit(2) from e

    except TemplateLoadError as e:
        typer.secho(f"Error loading template: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    except PermissionError as e:
        typer.secho(f"Error: Cannot write to {output}", fg=typer.colors.RED, err=True)
        typer.echo("Check that you have write permission to the output directory.", err=True)
        raise typer.Exit(4) from e

    except Exception as e:
        typer.secho(f"Error creating card: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e


@app.command()
def preview(
    template: str = typer.Argument(..., help="Template name or path"),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Greeting message text"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output PNG file path"
    ),
    dpi: int = typer.Option(
        144, "--dpi", "-d", help="Preview resolution (dots per inch)"
    ),
    open_after: bool = typer.Option(
        True, "--open/--no-open", help="Open the preview in your default image viewer."
    ),
) -> None:
    """Generate a fast PNG preview of a card and open it in your default viewer.

    Uses the same Wave 2 RenderCommand IR as the PDF and SVG backends, so
    what you see in the preview is what you'll get when you print.

    Examples:

        holiday-card preview christmas-classic

        holiday-card preview christmas-classic -m "Merry Christmas!" --dpi 300

        holiday-card preview christmas-classic --no-open -o out/preview.png
    """
    from holiday_card.core.compiler import compile_card
    from holiday_card.renderers.png_backend import PNGRenderer

    try:
        # Default output path
        if output is None:
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            output = output_dir / f"{template}-preview-{timestamp}.png"

        # Ensure .png suffix (Pillow infers format from extension)
        if not str(output).lower().endswith(".png"):
            output = Path(f"{output}.png")

        typer.echo(f"Generating preview for template: {template}")

        card = CardGenerator().create_card(template_id=template, message=message)
        commands = compile_card(card)
        PNGRenderer(dpi=dpi).render(commands, output)

        typer.secho(f"Preview generated: {output}", fg=typer.colors.GREEN)
        typer.echo(f"  Template: {template}")
        typer.echo(f"  Resolution: {dpi} DPI")

        if open_after:
            _open_in_default_viewer(output)

    except typer.Exit:
        raise

    except TemplateNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    except Exception as e:
        typer.secho(f"Error generating preview: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e


@app.command()
def init(
    name: str = typer.Argument(..., help="Template name (e.g., my-template)"),
    occasion: str = typer.Option(
        "generic", "--occasion", "-o", help="Occasion type: christmas, hanukkah, birthday, generic"
    ),
    fold_type: str = typer.Option(
        "half_fold", "--fold-type", "-f", help="Fold type: half_fold, quarter_fold, tri_fold"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output", help="Output directory for template file"
    ),
) -> None:
    """Initialize a new custom template.

    Creates a starter template YAML file that you can customize.

    Examples:

        holiday-card init my-custom-card

        holiday-card init wedding-invite --occasion generic --fold-type quarter_fold
    """
    import yaml

    if output_dir is None:
        output_dir = Path("templates") / occasion

    # Create directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate template content
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
                "x": 4.25,
                "y": 0,
                "width": 4.25,
                "height": 5.5,
                "background_color": {"r": 0.9, "g": 0.9, "b": 0.9},
                "text_elements": [
                    {
                        "id": "greeting",
                        "content": "Your Greeting Here",
                        "x": 2.125,
                        "y": 2.75,
                        "font_family": "Helvetica",
                        "font_size": 28,
                        "alignment": "center",
                        "color": {"r": 0.2, "g": 0.2, "b": 0.2},
                    }
                ],
            },
            {
                "id": "back",
                "position": "back",
                "x": 0,
                "y": 0,
                "width": 4.25,
                "height": 5.5,
            },
            {
                "id": "inside_left",
                "position": "inside_left",
                "x": 0,
                "y": 5.5,
                "width": 4.25,
                "height": 5.5,
            },
            {
                "id": "inside_right",
                "position": "inside_right",
                "x": 4.25,
                "y": 5.5,
                "width": 4.25,
                "height": 5.5,
                "text_elements": [
                    {
                        "id": "message",
                        "content": "Your message here",
                        "x": 0.5,
                        "y": 3.0,
                        "width": 3.25,
                        "font_family": "Helvetica",
                        "font_size": 14,
                        "color": {"r": 0.3, "g": 0.3, "b": 0.3},
                    }
                ],
            },
        ],
    }

    # Write template file
    template_path = output_dir / f"{name}.yaml"
    with open(template_path, "w") as f:
        yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)

    typer.secho(f"Template created: {template_path}", fg=typer.colors.GREEN)
    typer.echo("\nEdit the file to customize your template, then use:")
    typer.echo(f"  holiday-card create {name} -m \"Your message\"")


@app.command()
def validate(
    template: str = typer.Argument(..., help="Template name or path to validate"),
) -> None:
    """Validate a template file.

    Checks that a template YAML file is correctly formatted and can be loaded.

    Examples:

        holiday-card validate christmas-classic

        holiday-card validate ./my-template.yaml
    """
    from holiday_card.core.templates import load_template

    try:
        template_path = Path(template)

        if template_path.exists() and template_path.suffix in (".yaml", ".yml"):
            # Load from file path
            loaded = load_template_from_file(template_path)
            typer.secho(f"Template valid: {template_path}", fg=typer.colors.GREEN)
        else:
            # Load by ID
            loaded = load_template(template)
            typer.secho(f"Template valid: {template}", fg=typer.colors.GREEN)

        typer.echo(f"  Name: {loaded.name}")
        typer.echo(f"  Occasion: {loaded.occasion.value}")
        typer.echo(f"  Fold type: {loaded.fold_type.value}")
        typer.echo(f"  Panels: {len(loaded.panels)}")

    except typer.Exit:
        raise

    except TemplateNotFoundError as e:
        typer.secho(f"Template not found: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    except TemplateLoadError as e:
        typer.secho(f"Template invalid: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    except Exception as e:
        typer.secho(f"Validation error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e


def _open_in_default_viewer(path: Path) -> None:
    """Open ``path`` in the OS's default viewer for that file type.

    Best-effort and silent on failure — preview is a developer
    convenience, not a guaranteed contract.
    """
    import subprocess
    import sys

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", str(path)], check=False)
        elif sys.platform.startswith("win"):
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001 — preview is best-effort
        typer.secho(f"  (could not auto-open: {e})", fg=typer.colors.YELLOW, err=True)


_SUPPORTED_FORMATS = ("pdf", "svg")


def _resolve_output_format(requested: str, output: Path | None) -> str:
    """Pick the actual output format from --format and the output path.

    Precedence:
    - explicit ``--format pdf|svg`` wins
    - ``--format auto`` infers from the output path's suffix
    - default is ``pdf``
    """
    requested = requested.lower()
    if requested in _SUPPORTED_FORMATS:
        return requested
    if requested != "auto":
        typer.secho(
            f"Error: --format must be one of {_SUPPORTED_FORMATS} or 'auto', got {requested!r}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if output is not None:
        suffix = output.suffix.lower().lstrip(".")
        if suffix in _SUPPORTED_FORMATS:
            return suffix
    return "pdf"


def _make_renderer(output_format: str) -> "IRReportLabRenderer | SVGRenderer":
    """Construct the right renderer for the chosen output format."""
    if output_format == "svg":
        return SVGRenderer()
    return IRReportLabRenderer()


def _emit_ir_debug(
    template: str,
    message: str | None,
    theme: str | None,
    fold_type: str | None,
    inside_message: str | None,
) -> None:
    """Implementation of the hidden ``--debug-emit-ir`` flag.

    Loads the template, builds a Card via CardGenerator (no PDF written),
    runs the Wave 2 compiler, and prints the resulting RenderCommand list
    as a JSON array to stdout. For developer use only — Wave 2 follow-up
    PRs validate the output via snapshot tests.
    """
    from holiday_card.core.compiler import compile_card

    fold_type_enum = FoldType(fold_type) if fold_type else None
    generator = CardGenerator()
    card = generator.create_card(
        template_id=template,
        message=message,
        theme_id=theme,
        fold_type=fold_type_enum,
        inside_message=inside_message,
    )
    commands = compile_card(card)
    payload = [json.loads(c.model_dump_json()) for c in commands]
    typer.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":
    app()
