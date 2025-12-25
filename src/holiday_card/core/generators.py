"""Card generation orchestration.

This module provides the CardGenerator class that coordinates
template loading, content customization, and PDF rendering.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from holiday_card.core.models import (
    Card,
    Color,
    FoldType,
    ImageElement,
    Panel,
    Template,
    TextElement,
    Theme,
)
from holiday_card.core.templates import load_template
from holiday_card.core.themes import ThemeNotFoundError, load_theme
from holiday_card.renderers.reportlab_renderer import ReportLabRenderer
from holiday_card.utils.measurements import PAGE_HEIGHT, PAGE_WIDTH


class CardGenerator:
    """Orchestrates card generation from template to PDF output.

    This class coordinates the process of loading a template,
    applying customizations, and rendering the final PDF.
    """

    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        """Initialize the card generator.

        Args:
            templates_dir: Path to templates directory. Uses default if None.
        """
        self.templates_dir = templates_dir
        self.renderer = ReportLabRenderer()

    def create_card(
        self,
        template_id: str,
        message: Optional[str] = None,
        output_path: Optional[Path] = None,
        theme_id: Optional[str] = None,
        fold_type: Optional[FoldType] = None,
        images: Optional[list[ImageElement]] = None,
    ) -> Card:
        """Create a card from a template.

        Args:
            template_id: Template identifier.
            message: Optional greeting message to add.
            output_path: Output PDF file path.
            theme_id: Optional theme to apply.
            fold_type: Optional fold type override.
            images: Optional list of images to add.

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
            panels=self._copy_panels(template.panels),
            output_path=output_path,
        )

        # Apply message if provided
        if message:
            self._apply_message(card, message)

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

    def _apply_message(self, card: Card, message: str) -> None:
        """Apply a greeting message to the card.

        The message is typically placed on the front panel or
        inside panel, depending on the template design.

        Args:
            card: Card to modify.
            message: Greeting message to apply.
        """
        # Find the front panel or first panel with text
        for panel in card.panels:
            if panel.position.value == "front" and panel.text_elements:
                # Update the first text element with the message
                panel.text_elements[0].content = message
                return

        # If no text element on front, add one
        for panel in card.panels:
            if panel.position.value == "front":
                panel.text_elements.append(
                    TextElement(
                        content=message,
                        x=panel.width / 2,
                        y=panel.height / 2,
                        font_family="Helvetica",
                        font_size=24,
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
        """Generate a PDF file from a card.

        Args:
            card: Card to render.
            output_path: Output PDF file path.

        Returns:
            Path to generated PDF file.
        """
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup renderer
        self.renderer.setup_canvas(PAGE_WIDTH, PAGE_HEIGHT)
        self.renderer.create_canvas(output_path)

        # Render card
        self.renderer.render_card(card)

        # Save PDF
        self.renderer.save(output_path)

        return output_path

    def create_and_generate(
        self,
        template_id: str,
        output_path: Path,
        message: Optional[str] = None,
        fold_type: Optional[FoldType] = None,
        images: Optional[list[ImageElement]] = None,
        theme_id: Optional[str] = None,
    ) -> tuple[Card, Path]:
        """Create a card and generate the PDF in one step.

        Args:
            template_id: Template identifier.
            output_path: Output PDF file path.
            message: Optional greeting message.
            fold_type: Optional fold type override.
            images: Optional list of images to add.
            theme_id: Optional theme to apply.

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
        )

        pdf_path = self.generate_pdf(card, output_path)

        return card, pdf_path
