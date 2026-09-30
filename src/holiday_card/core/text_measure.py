"""The injectable text-measurement seam (spec §4, issue #75).

The compiler decides line breaks, shrink-to-fit sizes and safe-zone
overshoot from text widths, but it must not depend on a rendering backend
to get them. ``TextMeasurer`` is the Protocol it measures through, in the
same style as ``core.ai_assets.ImageClient``: the ReportLab implementation
lives in ``renderers/reportlab_measurer.py`` and tests inject fakes via
``CompileContext(measurer=...)``.

The package ``__init__`` registers a lazy default factory, so
``compile_card(card)`` keeps working with no argument while importing
``holiday_card`` never imports ReportLab. With nothing registered,
``default_text_measurer()`` raises rather than guessing (D4).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

__all__ = ["TextMeasurer", "default_text_measurer", "set_default_text_measurer"]


class TextMeasurer(Protocol):
    """Font metrics for IR ``font_id``s, in points."""

    def string_width(self, text: str, font_id: str, size_pt: float) -> float:
        """Advance width of ``text`` set in ``font_id`` at ``size_pt``."""
        ...

    def ascent_descent(self, font_id: str, size_pt: float) -> tuple[float, float]:
        """``(ascent, descent)`` above / below the baseline; descent is negative."""
        ...

    def known_font_ids(self) -> frozenset[str]:
        """Every ``font_id`` this measurer (and so the backends) can handle."""
        ...


_default_factory: Callable[[], TextMeasurer] | None = None


def set_default_text_measurer(factory: Callable[[], TextMeasurer]) -> None:
    """Register the factory ``default_text_measurer()`` calls."""
    global _default_factory
    _default_factory = factory


def default_text_measurer() -> TextMeasurer:
    """The registered default measurer; ``RuntimeError`` if none is registered."""
    if _default_factory is None:
        raise RuntimeError(
            "no TextMeasurer registered: pass CompileContext(measurer=...) or call "
            "set_default_text_measurer()"
        )
    return _default_factory()
