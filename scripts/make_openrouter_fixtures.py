"""Generate the image-bearing OpenRouter test fixtures (#149).

Writes, deterministically (fixed pixels, ``optimize=False``, no PNG
``tIME`` / text chunks), every fixture under ``tests/fixtures/openrouter/``
that embeds image bytes, plus the golden request body. The error-body
fixtures next to them are hand-written. ``bomb_png.json`` holds a PNG
assembled by hand: signature + IHDR(20000, 20000, 8, 2) + one IDAT of
``zlib.compress(b"")`` + IEND, with correct CRCs.

Dev-only, never run in CI (a test runs it into a temp dir as a drift
guard). Run from the repo root:

    python scripts/make_openrouter_fixtures.py [--out DIR]
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

from PIL import Image

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = _REPO / "tests" / "fixtures" / "openrouter"

SIZE = 8
GOLDEN_PROMPT = "watercolor pine bough border, sage green and burgundy"
_JSON = {"content-type": "application/json"}


def _pixels() -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE))
    img.putdata([(x * 32, y * 32, 128) for y in range(SIZE) for x in range(SIZE)])
    return img


def _encode(fmt: str) -> bytes:
    buf = io.BytesIO()
    options: dict[str, Any] = {
        "PNG": {"optimize": False},
        "JPEG": {"quality": 75, "optimize": False, "subsampling": 0},
        "WEBP": {"lossless": True, "quality": 0, "method": 0},
    }[fmt]
    _pixels().save(buf, format=fmt, **options)
    return buf.getvalue()


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def bomb_png() -> bytes:
    """A PNG whose IHDR declares 20000x20000 RGB (400 MP) with an empty IDAT."""
    ihdr = struct.pack(">IIBBBBB", 20000, 20000, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b""))
        + _chunk(b"IEND", b"")
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _ok(data: list[dict[str, Any]], usage: dict[str, Any], **headers: str) -> dict[str, Any]:
    return {
        "status": 200,
        "headers": {**_JSON, **headers},
        "body": {"created": 1790000000, "data": data, "usage": usage},
    }


def fixtures() -> dict[str, bytes | dict[str, Any]]:
    """Every generated file name -> its bytes or its JSON value."""
    png, jpeg, webp = _encode("PNG"), _encode("JPEG"), _encode("WEBP")
    tokens = {"prompt_tokens": 12, "completion_tokens": 1120, "total_tokens": 1132}
    golden = {
        "model": "google/gemini-3-pro-image",
        "prompt": GOLDEN_PROMPT,
        "n": 1,
        "aspect_ratio": "3:4",
        "resolution": "2K",
        "input_references": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + _b64(png)}}
        ],
        "provider": {"only": ["google-ai-studio/global"], "allow_fallbacks": False},
    }
    return {
        "reference_8x8.png": png,
        "request_moo_a6.json": golden,
        "ok_png.json": _ok(
            [{"b64_json": _b64(png), "media_type": "image/png"}],
            {**tokens, "cost": 0.1344},
            **{"x-generation-id": "gen-TEST123"},
        ),
        "ok_jpeg.json": _ok([{"b64_json": _b64(jpeg), "media_type": "image/jpeg"}], tokens),
        "ok_webp.json": _ok([{"b64_json": _b64(webp)}], {**tokens, "cost": 0.04}),
        "two_images.json": _ok(
            [{"b64_json": _b64(png), "media_type": "image/png"}] * 2, {**tokens, "cost": 0.2}
        ),
        "svg.json": _ok(
            [{"b64_json": _b64(b"<svg/>"), "media_type": "image/svg+xml"}], {**tokens, "cost": 0.04}
        ),
        "mime_mismatch.json": _ok(
            [{"b64_json": _b64(jpeg), "media_type": "image/png"}], {**tokens, "cost": 0.04}
        ),
        "bomb_png.json": _ok(
            [{"b64_json": _b64(bomb_png()), "media_type": "image/png"}], {**tokens, "cost": 0.04}
        ),
    }


def write(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, value in fixtures().items():
        path = out / name
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    for path in write(args.out):
        print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
