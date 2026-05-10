"""Measurement constants and conversion utilities for print-accurate PDF generation.

All measurements use inches as the primary unit, converted to PDF points (72 pts/inch)
only at render time. This ensures print accuracy per Constitution Principle IV.

The :class:`PageGeometry` dataclass models a printable page as four
nested boxes (sheet → bleed/media → trim → safe), the same model used by
PDF/X and every commercial RIP. Backends consume the precomputed point
tuples; the compiler converts inches → points exactly once via
``inches_to_points``.
"""

from __future__ import annotations

from dataclasses import dataclass

# Page dimensions (US Letter)
PAGE_WIDTH: float = 8.5  # inches
PAGE_HEIGHT: float = 11.0  # inches

# Safety margins
SAFE_MARGIN: float = 0.25  # inches - minimum margin from all edges

# Default bleed extension past the trim edge. 0.125" is the industry
# default that every POD service (MOO, Vistaprint, Catprint, Printful)
# accepts. Cards opt into a different value via Card.bleed / Panel.bleed.
DEFAULT_BLEED: float = 0.125  # inches

# PDF conversion
POINTS_PER_INCH: float = 72.0  # PDF points per inch

# Line widths (in points)
FOLD_LINE_WIDTH: float = 0.5  # points
CUT_LINE_WIDTH: float = 1.0  # points

# Image quality
MIN_DPI: int = 150  # minimum DPI for print quality (enforced by utils.validators)

# Fold type dimensions (folded sizes in inches)
HALF_FOLD_WIDTH: float = PAGE_HEIGHT / 2  # 5.5 inches when folded
HALF_FOLD_HEIGHT: float = PAGE_WIDTH  # 8.5 inches

QUARTER_FOLD_WIDTH: float = PAGE_WIDTH / 2  # 4.25 inches when folded
QUARTER_FOLD_HEIGHT: float = PAGE_HEIGHT / 2  # 5.5 inches

TRI_FOLD_PANEL_WIDTH: float = PAGE_WIDTH / 3  # ~2.83 inches per panel
TRI_FOLD_HEIGHT: float = PAGE_HEIGHT  # 11 inches


def inches_to_points(inches: float) -> float:
    """Convert inches to PDF points.

    Args:
        inches: Measurement in inches.

    Returns:
        Measurement in PDF points (72 points = 1 inch).
    """
    return inches * POINTS_PER_INCH


def points_to_inches(points: float) -> float:
    """Convert PDF points to inches.

    Args:
        points: Measurement in PDF points.

    Returns:
        Measurement in inches.
    """
    return points / POINTS_PER_INCH


def validate_within_page(x: float, y: float, width: float, height: float) -> bool:
    """Check if a rectangle fits within the page bounds with safe margins.

    Args:
        x: X position in inches from left edge.
        y: Y position in inches from bottom edge.
        width: Width in inches.
        height: Height in inches.

    Returns:
        True if rectangle fits within safe area, False otherwise.
    """
    if x < SAFE_MARGIN or y < SAFE_MARGIN:
        return False
    if x + width > PAGE_WIDTH - SAFE_MARGIN:
        return False
    return not y + height > PAGE_HEIGHT - SAFE_MARGIN


def validate_within_panel(
    x: float,
    y: float,
    width: float,
    height: float,
    panel_width: float,
    panel_height: float
) -> bool:
    """Check if a rectangle fits within a panel with safe margins.

    Args:
        x: X position in inches from panel left edge.
        y: Y position in inches from panel bottom edge.
        width: Width in inches.
        height: Height in inches.
        panel_width: Panel width in inches.
        panel_height: Panel height in inches.

    Returns:
        True if rectangle fits within panel safe area, False otherwise.
    """
    if x < SAFE_MARGIN or y < SAFE_MARGIN:
        return False
    if x + width > panel_width - SAFE_MARGIN:
        return False
    return not y + height > panel_height - SAFE_MARGIN


@dataclass(frozen=True)
class PageGeometry:
    """Print-pipeline page geometry: sheet → bleed/media → trim → safe.

    Models a single printable page as four nested rectangles, matching
    the PDF/X box model and what every commercial RIP expects to find:

    * **Sheet** — the physical paper the press feeds (e.g. US Letter
      8.5×11). For home-printer workflows ``sheet == trim``; for
      multi-up imposition (``--export-for moo-a6``, future) sheet is
      larger than trim.
    * **Trim** — the finished card after cutting. Coordinates inside the
      compiler/IR are expressed relative to the trim box's bottom-left
      corner.
    * **Bleed (== Media for now)** — the trim box extended outward by
      ``bleed_in`` on every side. Background fills must reach this edge
      so cutter wobble doesn't expose white paper. ``MediaBox == BleedBox``
      until a slug area is added (see ``slug_in``, currently always 0).
    * **Safe / Art** — the trim box inset by ``safe_margin_in``.
      Important content (text, faces, logos) must stay inside this
      rectangle to survive aggressive cutter trim.

    All ``*_box_pts`` properties return ``(x, y, width, height)`` in
    PDF points, with the **media box** as the canvas — i.e. the bleed
    extension shifts the trim box origin to ``(bleed_pts, bleed_pts)``.
    Backends draw to media-box coords and consult these tuples to
    declare PDF /MediaBox /TrimBox /BleedBox /ArtBox or to size SVG /
    PNG canvases.
    """

    sheet_width_in: float
    sheet_height_in: float
    trim_width_in: float
    trim_height_in: float
    bleed_in: float = 0.0
    safe_margin_in: float = SAFE_MARGIN

    @classmethod
    def us_letter(cls, bleed_in: float = DEFAULT_BLEED) -> PageGeometry:
        """US Letter (8.5×11) sheet == trim, with the requested bleed.

        Default bleed is 0.125" (industry standard). Pass ``bleed_in=0``
        for the legacy "no bleed" behavior used in tests that need
        byte-stable output independent of the bleed pass.
        """
        return cls(
            sheet_width_in=PAGE_WIDTH,
            sheet_height_in=PAGE_HEIGHT,
            trim_width_in=PAGE_WIDTH,
            trim_height_in=PAGE_HEIGHT,
            bleed_in=bleed_in,
        )

    @classmethod
    def moo_a6(cls) -> PageGeometry:
        """A6 (4.13×5.83) folded card with MOO's required 0.125" bleed.

        Stub for the upcoming ``--export-for moo-a6`` PR; no current
        caller, but ships here so the geometry registry has its first
        entry.
        """
        return cls(
            sheet_width_in=4.13,
            sheet_height_in=5.83,
            trim_width_in=4.13,
            trim_height_in=5.83,
            bleed_in=0.125,
        )

    @property
    def bleed_pts(self) -> float:
        return inches_to_points(self.bleed_in)

    @property
    def safe_margin_pts(self) -> float:
        return inches_to_points(self.safe_margin_in)

    @property
    def trim_width_pts(self) -> float:
        return inches_to_points(self.trim_width_in)

    @property
    def trim_height_pts(self) -> float:
        return inches_to_points(self.trim_height_in)

    @property
    def media_box_pts(self) -> tuple[float, float, float, float]:
        """``(x, y, width, height)`` of the MediaBox — the canvas the
        backends draw onto. Always anchored at ``(0, 0)``.
        """
        b = self.bleed_pts
        return (0.0, 0.0, self.trim_width_pts + 2 * b, self.trim_height_pts + 2 * b)

    @property
    def trim_box_pts(self) -> tuple[float, float, float, float]:
        """``(x, y, width, height)`` of the TrimBox in media-box coords.

        Origin is ``(bleed, bleed)`` so that IR coordinates (which are
        in trim-relative coords with bottom-left origin) land correctly
        once the backend translates by ``+bleed``.
        """
        b = self.bleed_pts
        return (b, b, self.trim_width_pts, self.trim_height_pts)

    @property
    def bleed_box_pts(self) -> tuple[float, float, float, float]:
        """The bleed extent. Equal to MediaBox until a slug area is
        added (no current need, but the box stays distinct in the API
        so PDF/X-aware code keeps working as the model grows).
        """
        return self.media_box_pts

    @property
    def art_box_pts(self) -> tuple[float, float, float, float]:
        """``(x, y, width, height)`` of the ArtBox / safe area in
        media-box coords. The safe margin is inset from the trim edge
        on all sides.
        """
        b = self.bleed_pts
        m = self.safe_margin_pts
        return (b + m, b + m, self.trim_width_pts - 2 * m, self.trim_height_pts - 2 * m)
