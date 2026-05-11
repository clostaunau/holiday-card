"""Card generation orchestration.

This module provides the CardGenerator class that coordinates
template loading, content customization, and PDF rendering.
"""

from datetime import datetime

__all__ = ["CardGenerator"]
from pathlib import Path

from holiday_card.core.compiler import compile_card
from holiday_card.core.export_targets import ExportTarget, get_target
from holiday_card.core.models import (
    Card,
    FoldType,
    ImageElement,
    Panel,
    TextElement,
    Theme,
)
from holiday_card.core.per_panel import (
    build_per_panel_card,
    build_per_panel_context,
)
from holiday_card.core.templates import load_template
from holiday_card.core.themes import ThemeNotFoundError, load_theme
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer

# Type alias for any renderer the generator can dispatch to. All three
# implementations expose the same minimal interface
# (``render(commands, output_path)``).
Renderer = IRReportLabRenderer | SVGRenderer | PNGRenderer

# The four canonical panel filenames for per-panel layout. Order matches
# the natural panel reading order on a half-fold card (front, back,
# inside-left, inside-right). Position-name → filename-stem mapping
# avoids leaking the underscore-style enum values to the file system
# while staying recognizable.
_PER_PANEL_FILENAMES: dict[str, str] = {
    "front": "front",
    "back": "back",
    "inside_left": "inside-left",
    "inside_right": "inside-right",
}


class CardGenerator:
    """Orchestrates card generation from template to PDF output.

    Coordinates template loading, customization, and rendering via the
    Wave 2 IR pipeline (``Card → compile_card → Renderer``). The default
    backend is ``IRReportLabRenderer`` (PDF); pass ``renderer=SVGRenderer()``
    for SVG output. New backends plug in here.
    """

    def __init__(
        self,
        templates_dir: Path | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize the card generator.

        Args:
            templates_dir: Path to templates directory. Uses default if None.
            renderer: Backend to render with. Defaults to PDF
                (``IRReportLabRenderer``); pass ``SVGRenderer()`` for SVG.
        """
        self.templates_dir = templates_dir
        self.renderer = renderer or IRReportLabRenderer()

    def create_card(
        self,
        template_id: str,
        message: str | None = None,
        output_path: Path | None = None,
        theme_id: str | None = None,
        fold_type: FoldType | None = None,
        images: list[ImageElement] | None = None,
        front_message: str | None = None,
        inside_message: str | None = None,
    ) -> Card:
        """Create a card from a template.

        Args:
            template_id: Template identifier.
            message: Optional greeting message (applied to front, for backwards compatibility).
            output_path: Output PDF file path.
            theme_id: Optional theme to apply.
            fold_type: Optional fold type override.
            images: Optional list of images to add.
            front_message: Optional message for the front panel greeting.
            inside_message: Optional message for the inside panel.

        Returns:
            Created Card object.
        """
        # Load template
        template = load_template(template_id, self.templates_dir)

        # Create card from template
        card = Card(
            name=f"{template.name} - {datetime.now().strftime('%Y-%m-%d')}",
            template_id=template.id,
            fold_type=fold_type or template.fold_type,
            theme_id=theme_id or template.default_theme_id,
            bleed=template.bleed,
            panels=self._copy_panels(template.panels),
            output_path=output_path,
        )

        # Apply front message (front_message takes precedence over message).
        # Empty string is a valid intentional value (e.g. --voice with no
        # cover sentiment found, or a blank-cover deliberate choice), so
        # we distinguish None ("not provided") from "" ("intentionally empty").
        if front_message is not None:
            self._apply_front_message(card, front_message)
        elif message is not None:
            self._apply_front_message(card, message)

        # Apply inside message — same None-vs-empty distinction. ""
        # actively clears the template's default inside text (used by
        # --blank-inside).
        if inside_message is not None:
            self._apply_inside_message(card, inside_message)

        # Apply images if provided
        if images:
            self._apply_images(card, images)

        # Apply theme if specified
        if theme_id:
            try:
                theme = load_theme(theme_id)
                self._apply_theme(card, theme)
            except ThemeNotFoundError:
                pass  # Use template default colors if theme not found

        return card

    def _copy_panels(self, panels: list[Panel]) -> list[Panel]:
        """Create copies of template panels for the card.

        Args:
            panels: Template panels to copy.

        Returns:
            List of copied panels.
        """
        return [panel.model_copy(deep=True) for panel in panels]

    def _apply_front_message(self, card: Card, message: str) -> None:
        """Apply a greeting message to the front panel.

        Args:
            card: Card to modify.
            message: Greeting message to apply.
        """
        # Find the front panel
        for panel in card.panels:
            if panel.position.value == "front":
                # Look for a text element with id "greeting" or use the first one
                for text in panel.text_elements:
                    if text.id == "greeting":
                        text.content = message
                        return
                # Fall back to first text element
                if panel.text_elements:
                    panel.text_elements[0].content = message
                    return
                # No text element, add one. "Lato" is a curated font
                # shipped in fonts/curated/ — friendly geometric sans
                # that works as a default cover greeting across voices.
                panel.text_elements.append(
                    TextElement(
                        content=message,
                        x=panel.width / 2,
                        y=panel.height / 2,
                        width=panel.width - 0.5,  # Leave margins
                        font_family="Lato",
                        font_size=24,
                    )
                )
                return

    def _apply_inside_message(self, card: Card, message: str) -> None:
        """Apply a message to the inside panel.

        Args:
            card: Card to modify.
            message: Inside message to apply.
        """
        # Find the inside_left panel (for book-style opening, this becomes
        # the right page when opened, which is the natural reading position)
        for panel in card.panels:
            if panel.position.value == "inside_left":
                # Look for a text element with id "message" or use the first one
                for text in panel.text_elements:
                    if text.id == "message":
                        text.content = message
                        return
                # Fall back to first text element
                if panel.text_elements:
                    panel.text_elements[0].content = message
                    return
                # No text element, add one. "Lato" matches the cover
                # auto-add default; together they're the safe fallback
                # when a template doesn't already carry text slots.
                panel.text_elements.append(
                    TextElement(
                        content=message,
                        x=0.5,
                        y=panel.height / 2,
                        width=panel.width - 1.0,  # Leave margins
                        font_family="Lato",
                        font_size=14,
                    )
                )
                return

    def _apply_images(self, card: Card, images: list[ImageElement]) -> None:
        """Apply images to the card.

        Images are added to the front panel by default.

        Args:
            card: Card to modify.
            images: List of images to add.
        """
        # Find the front panel
        for panel in card.panels:
            if panel.position.value == "front":
                panel.image_elements.extend(images)
                return

        # If no front panel, add to first panel
        if card.panels:
            card.panels[0].image_elements.extend(images)

    def _apply_theme(self, card: Card, theme: Theme) -> None:
        """Apply a color theme to the card.

        Updates panel colors and text colors based on the theme.

        Args:
            card: Card to modify.
            theme: Theme to apply.
        """
        for panel in card.panels:
            # Apply background color based on panel position
            if panel.position.value == "front":
                panel.background_color = theme.primary
            elif panel.position.value == "back":
                panel.background_color = theme.background
            else:
                # Inside panels use background color
                panel.background_color = theme.background

            # Update text colors
            for text in panel.text_elements:
                if panel.position.value == "front":
                    # Use contrasting color for front panel text
                    text.color = theme.background
                else:
                    text.color = theme.text

    def generate_pdf(self, card: Card, output_path: Path) -> Path:
        """Generate a PDF file from a card via the IR pipeline.

        Args:
            card: Card to render.
            output_path: Output PDF file path.

        Returns:
            Path to generated PDF file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        commands = compile_card(card)
        self.renderer.render(commands, output_path)
        return output_path

    def generate(
        self,
        card: Card,
        output: Path,
        target: ExportTarget | str = "letter",
        *,
        emit_fold_lines: bool | None = None,
    ) -> list[Path]:
        """Render a card to one or more files based on the export target.

        Dispatches on ``target.layout``:

        * ``imposition`` — emit one file at ``output``. ``output`` is
          treated as a file path; its parent directory is created.
        * ``per-panel`` — emit one file per panel inside ``output``.
          ``output`` is treated as a directory; it (and its parents)
          are created. Per-panel filenames are
          ``{position}.{ext}`` (e.g. ``front.pdf``,
          ``inside-left.pdf``).

        ``emit_fold_lines`` overrides the target's default
        (``letter``: True; per-panel: False). The CLI surfaces this
        as ``--with-fold-marks`` / ``--no-fold-marks``. None means
        "use the target default."

        Returns the list of written paths, in panel-iteration order.
        Single-file mode returns a one-element list for uniform handling
        by callers.
        """
        if isinstance(target, str):
            target = get_target(target)
        fold_marks = (
            emit_fold_lines
            if emit_fold_lines is not None
            else target.fold_marks_default
        )
        if target.layout == "imposition":
            return [self._generate_imposition(card, output, target, fold_marks)]
        if target.layout == "per-panel":
            return self._generate_per_panel(card, output, target, fold_marks)
        raise ValueError(f"unknown layout {target.layout!r} on target {target.name!r}")

    def _generate_imposition(
        self,
        card: Card,
        output_path: Path,
        target: ExportTarget,
        emit_fold_lines: bool,
    ) -> Path:
        from holiday_card.core.compiler import CompileContext  # local: avoid top-level cycle risk

        if target.geometry is None:
            raise ValueError(
                f"target {target.name!r} has layout='imposition' but no geometry"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ctx = CompileContext(geometry=target.geometry, emit_fold_lines=emit_fold_lines)
        commands = compile_card(card, ctx)
        self.renderer.render(commands, output_path)
        return output_path

    def _generate_per_panel(
        self,
        card: Card,
        output_dir: Path,
        target: ExportTarget,
        emit_fold_lines: bool,
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = self.renderer.file_extension  # ".pdf" / ".svg" / ".png"
        written: list[Path] = []
        for panel in card.panels:
            per_card = build_per_panel_card(card, panel, target)
            ctx = build_per_panel_context(panel, target)
            # Per-panel mode: respect the override if the user explicitly
            # passed --with-fold-marks. Otherwise build_per_panel_context's
            # default (False) wins because there's no fold to mark.
            if emit_fold_lines and not ctx.emit_fold_lines:
                from dataclasses import replace
                ctx = replace(ctx, emit_fold_lines=True)
            commands = compile_card(per_card, ctx)
            stem = _PER_PANEL_FILENAMES.get(panel.position.value, panel.position.value)
            out = output_dir / f"{stem}{ext}"
            self.renderer.render(commands, out)
            written.append(out)
        return written

    def create_and_generate(
        self,
        template_id: str,
        output_path: Path,
        message: str | None = None,
        fold_type: FoldType | None = None,
        images: list[ImageElement] | None = None,
        theme_id: str | None = None,
        front_message: str | None = None,
        inside_message: str | None = None,
    ) -> tuple[Card, Path]:
        """Create a card and generate the PDF in one step.

        Args:
            template_id: Template identifier.
            output_path: Output PDF file path.
            message: Optional greeting message (applied to front, for backwards compatibility).
            fold_type: Optional fold type override.
            images: Optional list of images to add.
            theme_id: Optional theme to apply.
            front_message: Optional message for the front panel greeting.
            inside_message: Optional message for the inside panel.

        Returns:
            Tuple of (Card object, Path to PDF file).
        """
        card = self.create_card(
            template_id=template_id,
            message=message,
            output_path=output_path,
            theme_id=theme_id,
            fold_type=fold_type,
            images=images,
            front_message=front_message,
            inside_message=inside_message,
        )

        pdf_path = self.generate_pdf(card, output_path)

        return card, pdf_path
