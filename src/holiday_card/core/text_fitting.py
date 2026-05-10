"""Text overflow strategies — pure functions, no canvas state outside the
explicit ``canvas`` parameter.

These functions decide *what* gets drawn (final font size, the resulting
lines, whether content was truncated), not *how*. They were extracted from
``ReportLabRenderer`` (Wave 2 Step 2a) so the future compiler
(``core/compiler.py``) can call the same logic without going through a
half-initialized renderer.

The functions still depend on ReportLab's ``canvas.Canvas`` for text
measurement — the same dependency ``text_utils.py`` already has. Replacing
that with a backend-neutral ``TextMeasurer`` Protocol is a Wave 3 typography
concern; doing it here would scope-creep.
"""

from __future__ import annotations

from reportlab.pdfgen import canvas

from holiday_card.core.models import (
    AdjustmentResult,
    OverflowStrategy,
    Panel,
    TextElement,
)
from holiday_card.core.text_utils import measure_text, shrink_to_fit, wrap_text
from holiday_card.utils.measurements import inches_to_points

__all__ = [
    "truncate_to_fit",
    "select_auto_strategy",
    "apply_shrink_strategy",
    "apply_wrap_strategy",
    "apply_truncate_strategy",
    "fit_text_element",
]


def truncate_to_fit(
    pdf_canvas: canvas.Canvas,
    content: str,
    font_name: str,
    font_size: int,
    max_width: float,
) -> str:
    """Truncate ``content`` with an ellipsis so it fits within ``max_width``.

    If the original text already fits, returns it unchanged. Otherwise
    progressively drops trailing characters until ``content + "..."`` fits.
    """
    text_width = pdf_canvas.stringWidth(content, font_name, font_size)
    if text_width <= max_width:
        return content

    ellipsis = "..."
    ellipsis_width = pdf_canvas.stringWidth(ellipsis, font_name, font_size)
    available_width = max_width - ellipsis_width

    truncated = content
    while (
        pdf_canvas.stringWidth(truncated, font_name, font_size) > available_width
        and len(truncated) > 0
    ):
        truncated = truncated[:-1]

    return truncated.rstrip() + ellipsis


def select_auto_strategy(text: TextElement) -> OverflowStrategy:
    """Pick a concrete overflow strategy when the element asks for AUTO.

    Heuristic preserved from the original renderer:
    short text shrinks (preserves visual impact),
    long text with a width-and-height bound wraps (readability wins),
    long text without a height bound falls back to shrink-to-single-line.
    """
    text_length = len(text.content)
    has_height = text.width is not None  # historical: height was tracked via width

    if text_length < 30:
        return OverflowStrategy.SHRINK
    if text_length >= 30 and has_height:
        return OverflowStrategy.WRAP
    return OverflowStrategy.SHRINK


def apply_shrink_strategy(
    pdf_canvas: canvas.Canvas,
    text: TextElement,
    font_name: str,
) -> tuple[int, str]:
    """Shrink ``text`` until it fits in its declared width; truncate as a
    last resort if shrinking to ``min_font_size`` is still too wide.
    """
    if text.width is None:
        return (text.font_size, text.content)

    max_width_pts = inches_to_points(text.width)
    final_size = shrink_to_fit(
        pdf_canvas,
        text.content,
        font_name,
        text.font_size,
        max_width_pts,
        text.min_font_size,
    )

    if final_size == text.min_font_size:
        metrics = measure_text(
            pdf_canvas,
            text.content,
            font_name,
            final_size,
            max_width_pts,
        )
        if not metrics.fits_within_bounds:
            content = truncate_to_fit(
                pdf_canvas,
                text.content,
                font_name,
                final_size,
                max_width_pts,
            )
            return (final_size, content)

    return (final_size, text.content)


def apply_wrap_strategy(
    pdf_canvas: canvas.Canvas,
    text: TextElement,
    panel: Panel,
    font_name: str,
) -> tuple[int, list[str]]:
    """Wrap ``text`` to fit width; if a panel height is available, binary-search
    for the largest font size that fits both width AND height.
    """
    if text.width is None:
        return (text.font_size, [text.content])

    max_width_pts = inches_to_points(text.width)
    font_size = text.font_size

    lines = wrap_text(
        pdf_canvas,
        text.content,
        font_name,
        font_size,
        max_width_pts,
        text.max_lines,
    )

    if text.width and hasattr(panel, "height"):
        max_height_pts = inches_to_points(panel.height) if panel.height else None
        if max_height_pts:
            metrics = measure_text(
                pdf_canvas,
                text.content,
                font_name,
                font_size,
                max_width_pts,
                max_height_pts,
                lines,
            )

            if not metrics.fits_within_bounds and font_size > text.min_font_size:
                low = text.min_font_size
                high = font_size
                best_size = text.min_font_size
                best_lines = lines

                while low <= high:
                    mid = (low + high) // 2
                    test_lines = wrap_text(
                        pdf_canvas,
                        text.content,
                        font_name,
                        mid,
                        max_width_pts,
                        text.max_lines,
                    )
                    test_metrics = measure_text(
                        pdf_canvas,
                        text.content,
                        font_name,
                        mid,
                        max_width_pts,
                        max_height_pts,
                        test_lines,
                    )

                    if test_metrics.fits_within_bounds:
                        best_size = mid
                        best_lines = test_lines
                        low = mid + 1
                    else:
                        high = mid - 1

                return (best_size, best_lines)

    return (font_size, lines)


def apply_truncate_strategy(
    pdf_canvas: canvas.Canvas,
    text: TextElement,
    font_name: str,
) -> tuple[int, str]:
    """Hard-truncate with ellipsis at the original font size."""
    if text.width is None:
        return (text.font_size, text.content)

    max_width_pts = inches_to_points(text.width)
    content = truncate_to_fit(
        pdf_canvas,
        text.content,
        font_name,
        text.font_size,
        max_width_pts,
    )
    return (text.font_size, content)


def fit_text_element(
    pdf_canvas: canvas.Canvas,
    text: TextElement,
    panel: Panel,
    font_name: str,
) -> tuple[int, list[str], AdjustmentResult]:
    """Fit ``text`` using its declared overflow strategy.

    Returns the final font size, the resulting lines, and an
    ``AdjustmentResult`` describing what (if anything) was changed. The
    return shape is unchanged from the original ``ReportLabRenderer``
    method so the renderer's call site does not change semantically.
    """
    strategy = text.overflow_strategy
    if strategy == OverflowStrategy.AUTO:
        strategy = select_auto_strategy(text)

    original_font_size = text.font_size

    if strategy == OverflowStrategy.SHRINK:
        final_size, content = apply_shrink_strategy(pdf_canvas, text, font_name)
        lines = [content]
        truncated = content != text.content and content.endswith("...")
    elif strategy == OverflowStrategy.WRAP:
        final_size, lines = apply_wrap_strategy(pdf_canvas, text, panel, font_name)
        truncated = False
    elif strategy == OverflowStrategy.TRUNCATE:
        final_size, content = apply_truncate_strategy(pdf_canvas, text, font_name)
        lines = [content]
        truncated = content != text.content
    else:
        final_size = text.font_size
        lines = [text.content]
        truncated = False

    was_adjusted = (final_size != original_font_size) or truncated or (len(lines) > 1)
    result = AdjustmentResult(
        was_adjusted=was_adjusted,
        strategy_applied=strategy,
        original_font_size=original_font_size,
        final_font_size=final_size,
        lines_used=len(lines),
        content_truncated=truncated,
    )

    return (final_size, lines, result)
