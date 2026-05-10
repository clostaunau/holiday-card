"""Renderer implementations for card output generation.

After Wave 2 Step 5 there is one production renderer:
``IRReportLabRenderer``, which consumes a ``RenderCommand`` stream
produced by ``holiday_card.core.compiler.compile_card``.
"""

from holiday_card.renderers.reportlab_backend import IRReportLabRenderer

__all__ = ["IRReportLabRenderer"]
