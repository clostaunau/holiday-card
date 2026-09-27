"""Generate ``placeholder-photo.jpg`` for the shipped photo templates (#65).

The placeholder fills every photo slot until the user passes ``-i/--image``.
It is neutral (warm greys, no people) and reads as a placeholder at a
glance: a generic "picture" glyph (frame, hills, sun) on a flat ground.
1200x1200 px is 375 PPI at the largest shipped slot (3.2") and 353 PPI at
the tallest (mothers-day-photo, 3.4").

Own work, dedicated to the public domain (CC0 1.0). Pillow only; the output
is deterministic for a given Pillow build. The same bytes are written next
to every template directory that references it.

Run from the repo root:

    python scripts/make_placeholder_photo.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1200
SUPERSAMPLE = 2
GROUND = (217, 213, 206)
INK = (160, 154, 146)
INK_LIGHT = (189, 184, 176)
TEMPLATE_DIRS = ("christmas", "birthday", "mothers_day")
FILENAME = "placeholder-photo.jpg"

_REPO = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO / "src" / "holiday_card" / "data" / "templates"


def render() -> bytes:
    """Return the placeholder as JPEG bytes."""
    s = SIZE * SUPERSAMPLE
    img = Image.new("RGB", (s, s), GROUND)
    draw = ImageDraw.Draw(img)

    def box(x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int, int]:
        return (round(x0 * s), round(y0 * s), round(x1 * s), round(y1 * s))

    # Picture-frame glyph, centred and kept inside the 0.3-0.7 band so it
    # survives the circle / star / ellipse clips the templates apply.
    frame = box(0.30, 0.34, 0.70, 0.66)
    draw.rounded_rectangle(frame, radius=round(0.02 * s), outline=INK, width=round(0.014 * s))
    draw.ellipse(box(0.57, 0.39, 0.63, 0.45), fill=INK)
    draw.polygon(
        [(round(x * s), round(y * s)) for x, y in (
            (0.33, 0.63), (0.45, 0.47), (0.53, 0.57), (0.58, 0.52), (0.67, 0.63),
        )],
        fill=INK,
    )
    # Corner crop marks: "a photo goes here".
    arm, inset, w = 0.08, 0.06, round(0.008 * s)
    for cx, dx in ((inset, 1), (1 - inset, -1)):
        for cy, dy in ((inset, 1), (1 - inset, -1)):
            draw.line(box(cx, cy, cx + dx * arm, cy), fill=INK_LIGHT, width=w)
            draw.line(box(cx, cy, cx, cy + dy * arm), fill=INK_LIGHT, width=w)

    img = img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, subsampling=0, optimize=True)
    return buf.getvalue()


def main() -> int:
    data = render()
    for name in TEMPLATE_DIRS:
        out = _TEMPLATES / name / FILENAME
        out.write_bytes(data)
        print(f"wrote {out.relative_to(_REPO)} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
