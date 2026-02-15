"""CLI commands for holiday-card application.

This module implements the Typer CLI interface following Unix conventions.
All commands support both human-readable and JSON output formats.
"""

import json
from datetime import datetime
from pathlib import Path

import typer

from holiday_card import __version__
from holiday_card.core.generators import CardGenerator
from holiday_card.core.models import FoldType, ImageElement
from holiday_card.core.templates import (
    TemplateLoadError,
    TemplateNotFoundError,
    discover_templates,
    load_template_from_file,
)
from holiday_card.core.themes import discover_themes
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

    except Exception as e:
        typer.secho(f"Error listing templates: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


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

    except Exception as e:
        typer.secho(f"Error listing themes: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def create(
    template: str = typer.Argument(..., help="Template name or path"),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Greeting message text"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output PDF file path"
    ),
    name: str | None = typer.Option(
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
) -> None:
    """Create a new card from a template.

    Examples:

        holiday-card create christmas-classic -m "Merry Christmas!"

        holiday-card create christmas-classic --message "Happy Holidays!" --output ./cards/holiday.pdf

        holiday-card create birthday-balloons -m "Happy Birthday!" --image ./photo.jpg
    """
    try:
        # Generate default output path if not specified
        if output is None:
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            output = output_dir / f"{template}-{timestamp}.pdf"

        # Ensure output has .pdf extension
        if not str(output).lower().endswith(".pdf"):
            output = Path(f"{output}.pdf")

        # Create card generator
        generator = CardGenerator()

        typer.echo(f"Creating card from template: {template}")

        # Parse fold type if provided
        fold_type_enum = None
        if fold_type:
            try:
                fold_type_enum = FoldType(fold_type)
            except ValueError:
                typer.secho(
                    f"Error: Invalid fold type '{fold_type}'. "
                    f"Valid options: half_fold, quarter_fold, tri_fold",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(2)

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
                    raise typer.Exit(2)

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
        card, pdf_path = generator.create_and_generate(
            template_id=template,
            output_path=output,
            message=message,
            fold_type=fold_type_enum,
            images=image_elements if image_elements else None,
            theme_id=theme,
            inside_message=inside_message,
        )

        # Success output
        typer.secho(f"Card created: {pdf_path}", fg=typer.colors.GREEN)
        typer.echo(f"  Template: {template}")
        typer.echo(f"  Fold: {card.fold_type.value}")
        typer.echo("  Size: 8.5\" x 11\"")
        if message:
            msg_preview = message[:50] + "..." if len(message) > 50 else message
            typer.echo(f"  Message: {msg_preview}")

    except TemplateNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        typer.echo("\nAvailable templates:", err=True)
        templates_list = discover_templates()
        for t in templates_list[:5]:
            typer.echo(f"  - {t['id']}", err=True)
        if len(templates_list) > 5:
            typer.echo(f"  ... and {len(templates_list) - 5} more", err=True)
        typer.echo("\nRun 'holiday-card templates' to see all options.", err=True)
        raise typer.Exit(2)

    except TemplateLoadError as e:
        typer.secho(f"Error loading template: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    except PermissionError:
        typer.secho(f"Error: Cannot write to {output}", fg=typer.colors.RED, err=True)
        typer.echo("Check that you have write permission to the output directory.", err=True)
        raise typer.Exit(4)

    except Exception as e:
        typer.secho(f"Error creating card: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def preview(
    template: str = typer.Argument(..., help="Template name or path"),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Greeting message text"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output image file path"
    ),
    dpi: int = typer.Option(
        150, "--dpi", "-d", help="Preview resolution (dots per inch)"
    ),
    format: str = typer.Option(
        "png", "--format", "-f", help="Output format: png, jpg"
    ),
    show_guides: bool = typer.Option(
        True, "--show-guides/--no-guides", help="Show fold line guides"
    ),
) -> None:
    """Generate a preview image of a card.

    Creates a raster image showing how the card will look when printed.

    Examples:

        holiday-card preview christmas-classic

        holiday-card preview christmas-classic -m "Merry Christmas!" --dpi 300

        holiday-card preview christmas-classic --no-guides --format jpg
    """
    from holiday_card.renderers.preview_renderer import generate_preview

    try:
        # Generate default output path if not specified
        if output is None:
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            ext = "jpg" if format.lower() in ("jpg", "jpeg") else "png"
            output = output_dir / f"{template}-preview-{timestamp}.{ext}"

        # Validate format
        if format.lower() not in ("png", "jpg", "jpeg"):
            typer.secho(
                f"Error: Invalid format '{format}'. Valid options: png, jpg",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)

        # Create card generator
        generator = CardGenerator()

        typer.echo(f"Generating preview for template: {template}")

        # Create the card (without generating PDF)
        card = generator.create_card(
            template_id=template,
            message=message,
        )

        # Generate preview
        preview_path = generate_preview(
            card=card,
            output_path=output,
            dpi=dpi,
            format=format,
            show_guides=show_guides,
        )

        # Success output
        typer.secho(f"Preview generated: {preview_path}", fg=typer.colors.GREEN)
        typer.echo(f"  Template: {template}")
        typer.echo(f"  Resolution: {dpi} DPI")
        typer.echo(f"  Format: {format.upper()}")
        typer.echo(f"  Fold guides: {'shown' if show_guides else 'hidden'}")

    except TemplateNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    except Exception as e:
        typer.secho(f"Error generating preview: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


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

    except TemplateNotFoundError as e:
        typer.secho(f"Template not found: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    except TemplateLoadError as e:
        typer.secho(f"Template invalid: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    except Exception as e:
        typer.secho(f"Validation error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
