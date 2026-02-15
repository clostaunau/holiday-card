#!/usr/bin/env python3
"""
Holiday Card Creator - Example Script
This script demonstrates how to create a simple holiday card using both
Pillow (for image-based cards) and ReportLab (for PDF cards).
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

# Create output directory if it doesn't exist
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def create_pillow_card():
    """Create a simple holiday card using Pillow."""
    print("Creating image-based holiday card with Pillow...")

    # Card size: 8.5" x 5.5" at 300 DPI for print quality
    width, height = 2550, 1650

    # Create blank card with a festive background color
    card = Image.new('RGB', (width, height), color='#2C5F2D')  # Forest green
    draw = ImageDraw.Draw(card)

    # Add a white border
    border_width = 50
    draw.rectangle(
        [border_width, border_width, width - border_width, height - border_width],
        outline='white',
        width=15
    )

    # Add text
    try:
        # Try to use a nice font
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 120)
        message_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
    except Exception:
        # Fall back to default font
        print("  Note: Using default font. Install custom fonts for better results.")
        title_font = ImageFont.load_default()
        message_font = ImageFont.load_default()

    # Main greeting
    title_text = "Happy Holidays!"
    draw.text(
        (width // 2, height // 2 - 100),
        title_text,
        fill='white',
        font=title_font,
        anchor='mm'
    )

    # Subtitle
    subtitle_text = "Wishing you joy and peace"
    draw.text(
        (width // 2, height // 2 + 100),
        subtitle_text,
        fill='#FFD700',  # Gold
        font=message_font,
        anchor='mm'
    )

    # Add decorative stars
    star_positions = [
        (width // 4, height // 4),
        (3 * width // 4, height // 4),
        (width // 4, 3 * height // 4),
        (3 * width // 4, 3 * height // 4),
    ]

    for x, y in star_positions:
        draw.text((x, y), "✨", font=title_font, anchor='mm')

    # Save the card
    output_path = OUTPUT_DIR / "holiday_card_pillow.png"
    card.save(output_path, dpi=(300, 300))
    print(f"  ✓ Saved: {output_path}")

    return output_path


def create_reportlab_card():
    """Create a simple holiday card PDF using ReportLab."""
    print("Creating PDF holiday card with ReportLab...")

    output_path = OUTPUT_DIR / "holiday_card_reportlab.pdf"

    # Create PDF with letter size
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    # Set background color (forest green)
    c.setFillColorRGB(0.17, 0.37, 0.18)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Add white border
    c.setStrokeColorRGB(1, 1, 1)
    c.setLineWidth(3)
    c.rect(0.5 * inch, 0.5 * inch, width - 1 * inch, height - 1 * inch, fill=0, stroke=1)

    # Add title text
    c.setFillColorRGB(1, 1, 1)  # White
    c.setFont("Helvetica-Bold", 48)
    c.drawCentredString(width / 2, height / 2 + 0.5 * inch, "Happy Holidays!")

    # Add subtitle
    c.setFillColorRGB(1, 0.84, 0)  # Gold
    c.setFont("Helvetica", 24)
    c.drawCentredString(width / 2, height / 2 - 0.5 * inch, "Wishing you joy and peace")

    # Add decorative elements
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 36)
    c.drawString(1.5 * inch, height - 1.5 * inch, "❄")
    c.drawString(width - 2 * inch, height - 1.5 * inch, "❄")
    c.drawString(1.5 * inch, 1.5 * inch, "❄")
    c.drawString(width - 2 * inch, 1.5 * inch, "❄")

    # Add footer
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, 0.75 * inch, "Season's Greetings from Your Family")

    c.save()
    print(f"  ✓ Saved: {output_path}")

    return output_path


def create_folded_card():
    """Create a folded card template (front and inside on same sheet)."""
    print("Creating folded card template with ReportLab...")

    output_path = OUTPUT_DIR / "folded_card.pdf"

    # Create PDF with letter size (will be folded in half horizontally)
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    # Calculate midpoint for folding
    mid_height = height / 2

    # --- FRONT OF CARD (Bottom Half) ---
    c.setFillColorRGB(0.8, 0.1, 0.1)  # Red
    c.rect(0, 0, width, mid_height, fill=1, stroke=0)

    # Front text
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 42)
    c.drawCentredString(width / 2, mid_height / 2 + 0.5 * inch, "Season's")
    c.drawCentredString(width / 2, mid_height / 2 - 0.5 * inch, "Greetings")

    # Decorative elements
    c.setFont("Helvetica", 60)
    c.drawCentredString(width / 2, mid_height / 2 + 1.5 * inch, "🎄")

    # --- INSIDE OF CARD (Top Half) ---
    c.setFillColorRGB(1, 1, 1)  # White background
    c.rect(0, mid_height, width, mid_height, fill=1, stroke=0)

    # Inside text
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica", 18)
    c.drawCentredString(width / 2, mid_height + 2 * inch, "Wishing you a wonderful holiday season")
    c.drawCentredString(width / 2, mid_height + 1.5 * inch, "filled with love, laughter, and joy!")

    # Personal message area
    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(width / 2, mid_height + 0.75 * inch, "With warm wishes,")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, mid_height + 0.5 * inch, "[Your Name]")

    # Add fold line guide
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.setDash(3, 3)
    c.line(0.25 * inch, mid_height, width - 0.25 * inch, mid_height)
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(0.3 * inch, mid_height + 0.05 * inch, "← fold here →")

    c.save()
    print(f"  ✓ Saved: {output_path}")
    print(f"  Note: Print this card and fold along the dashed line to create a greeting card!")

    return output_path


def main():
    """Create all example cards."""
    print("\n" + "=" * 60)
    print("Holiday Card Creator - Example Script")
    print("=" * 60 + "\n")

    # Create different types of cards
    pillow_card = create_pillow_card()
    reportlab_card = create_reportlab_card()
    folded_card = create_folded_card()

    print("\n" + "=" * 60)
    print("✓ All cards created successfully!")
    print("=" * 60)
    print(f"\nGenerated files:")
    print(f"  1. {pillow_card} (PNG image)")
    print(f"  2. {reportlab_card} (PDF)")
    print(f"  3. {folded_card} (Folded card PDF)")
    print("\nYou can view these files in VS Code or open them with your system viewer.")
    print("PDFs are print-ready at high quality!\n")


if __name__ == "__main__":
    main()
