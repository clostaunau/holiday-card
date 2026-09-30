"""Holiday Card Generator - Create printable greeting cards."""

from holiday_card.core.text_measure import TextMeasurer, set_default_text_measurer

__version__ = "1.3.0"
__author__ = "Holiday Card Team"


def _reportlab_text_measurer() -> TextMeasurer:
    # Lazy: importing holiday_card must not import ReportLab (#75).
    from holiday_card.renderers.reportlab_measurer import ReportLabTextMeasurer

    return ReportLabTextMeasurer()


# Composition root: the default measurer compile_card() uses without a ctx.measurer.
set_default_text_measurer(_reportlab_text_measurer)
