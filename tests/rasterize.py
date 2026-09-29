"""Host-independent rasterizers shared by the conformance suite and the visual gate.

``pypdfium2`` ships its rasterizer in the wheel, so a PDF rasterizes the same
way on every CI runner. Importable from any test as ``rasterize`` because
``tests/conftest.py`` puts ``tests/`` on ``sys.path``.
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


def to_rgb_on_white(img: Image.Image) -> Image.Image:
    """Flatten any alpha onto white and return an RGB image."""
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(base, rgba).convert("RGB")
    return img.convert("RGB")


def rasterize_pdf(path: Path, dpi: int) -> Image.Image:
    """Rasterize page 1 of ``path`` at ``dpi`` with pdfium, as RGB on white."""
    doc = pdfium.PdfDocument(str(path))
    try:
        return to_rgb_on_white(doc[0].render(scale=dpi / 72).to_pil())
    finally:
        doc.close()
