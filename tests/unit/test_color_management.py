"""ICC-managed sRGB → CMYK conversion (#70, D9).

Expected values were computed on 2026-09-26 with Pillow 12.3.0 /
LittleCMS 2.19 against the bundled ``GRACoL2013_CRPC6.icc``, relative
colorimetric + black-point compensation. Each is an 8-bit result
× 100/255. If a Pillow/LCMS bump in ``uv.lock`` moves a value more than
the tolerance, regenerate the table with::

    from PIL import Image, ImageCms
    from holiday_card.core.color_management import default_cmyk_icc_path
    t = ImageCms.buildTransform(
        ImageCms.createProfile("sRGB"), str(default_cmyk_icc_path()),
        "RGB", "CMYK",
        renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
        flags=ImageCms.Flags.BLACKPOINTCOMPENSATION,
    )
    px = ImageCms.applyTransform(Image.new("RGB", (1, 1), rgb), t).getpixel((0, 0))
    print([round(v * 100 / 255, 1) for v in px])

and justify the change in the PR.
"""

from __future__ import annotations

import inspect
import io
import itertools
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from holiday_card.core import color_management
from holiday_card.core.color_management import (
    CMYKConverter,
    ICCProfileNotFoundError,
)

# ±2.0 percentage points per channel: tight enough to tell BPC from no-BPC
# (#CC1C1C without BPC is 0/100/100/10.2) and from the naive formula.
_TOL = 0.02

_RICH_BLACK = (0.60, 0.40, 0.40, 1.00)
_ONE_SQ_INCH = 72.0 * 72.0


def _hex(h: str) -> tuple[float, float, float]:
    return tuple(int(h[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


@pytest.fixture(scope="module")
def conv() -> CMYKConverter:
    return CMYKConverter()


_TABLE: list[tuple[str, tuple[float, float, float], tuple[float, float, float, float]]] = [
    ("white", _hex("#FFFFFF"), (0.0, 0.0, 0.0, 0.0)),
    ("blue", _hex("#0000FF"), (100.0, 85.5, 0.0, 0.0)),
    ("cc1c1c", _hex("#CC1C1C"), (0.0, 98.0, 91.0, 12.5)),
    ("red", _hex("#FF0000"), (0.0, 93.3, 98.4, 0.0)),
    ("green", _hex("#1B5E20"), (72.9, 2.7, 98.4, 58.8)),
    ("grey", _hex("#808080"), (47.5, 38.8, 37.6, 16.9)),
    ("gold", _hex("#FFD700"), (1.2, 11.0, 91.0, 0.4)),
    ("classic-front-bg", (0.8, 0.1, 0.1), (0.0, 98.8, 92.5, 12.2)),
    ("near-black-capped", _hex("#0A0A0A"), (77.3, 69.5, 59.0, 94.1)),
]


@pytest.mark.parametrize(
    ("rgb", "expected_pct"), [t[1:] for t in _TABLE], ids=[t[0] for t in _TABLE]
)
def test_convert_matches_icc_table(
    conv: CMYKConverter,
    rgb: tuple[float, float, float],
    expected_pct: tuple[float, float, float, float],
) -> None:
    got = conv.convert(*rgb)
    assert got == pytest.approx(tuple(v / 100 for v in expected_pct), abs=_TOL)


def test_pure_blue_is_not_naive_purple(conv: CMYKConverter) -> None:
    # The naive formula gave 100/100/0/0, which prints purple.
    _, m, _, _ = conv.convert(0.0, 0.0, 1.0)
    assert m == pytest.approx(0.855, abs=_TOL)


def test_white_is_exactly_zero(conv: CMYKConverter) -> None:
    assert conv.convert(1.0, 1.0, 1.0) == (0.0, 0.0, 0.0, 0.0)


def test_near_black_is_capped_at_exactly_300(conv: CMYKConverter) -> None:
    c, m, y, k = conv.convert(*_hex("#0A0A0A"))
    assert c + m + y + k == pytest.approx(3.0, abs=1e-9)
    assert k == pytest.approx(0.941, abs=_TOL)  # K is preserved by the cap


def test_ink_cap_holds_over_a_9x9x9_grid(conv: CMYKConverter) -> None:
    steps = [i / 8 for i in range(9)]
    worst = max(
        sum(conv.convert(r, g, b, role=role, area_pt2=1e9))
        for r, g, b in itertools.product(steps, repeat=3)
        for role in ("text", "stroke", "fill")
    )
    assert worst <= 3.0 + 1e-9


def test_custom_total_ink_limit() -> None:
    c, m, y, k = CMYKConverter(total_ink_limit=2.6).convert(*_hex("#0A0A0A"))
    assert c + m + y + k == pytest.approx(2.6, abs=1e-9)
    assert k == pytest.approx(0.941, abs=_TOL)


# ---------------------------------------------------------------------------
# Pure black
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["text", "stroke"])
def test_pure_black_text_and_stroke_are_k_only(conv: CMYKConverter, role: str) -> None:
    assert conv.convert(0.0, 0.0, 0.0, role=role) == (0.0, 0.0, 0.0, 1.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("role", ["text", "stroke"])
def test_pure_black_text_and_stroke_ignore_area(conv: CMYKConverter, role: str) -> None:
    got = conv.convert(0.0, 0.0, 0.0, role=role, area_pt2=1e6)  # type: ignore[arg-type]
    assert got == (0.0, 0.0, 0.0, 1.0)


def test_large_black_fill_is_rich_black(conv: CMYKConverter) -> None:
    assert conv.convert(0.0, 0.0, 0.0, role="fill", area_pt2=2 * _ONE_SQ_INCH) == _RICH_BLACK


def test_black_fill_at_exactly_one_square_inch_is_rich_black(conv: CMYKConverter) -> None:
    assert conv.convert(0.0, 0.0, 0.0, area_pt2=5184.0) == _RICH_BLACK


def test_black_fill_just_under_one_square_inch_is_k_only(conv: CMYKConverter) -> None:
    assert conv.convert(0.0, 0.0, 0.0, area_pt2=5183.99) == (0.0, 0.0, 0.0, 1.0)


def test_black_fill_without_area_counts_as_small(conv: CMYKConverter) -> None:
    assert conv.convert(0.0, 0.0, 0.0) == (0.0, 0.0, 0.0, 1.0)


def test_custom_rich_black_and_threshold() -> None:
    conv = CMYKConverter(rich_black=(0.5, 0.5, 0.5, 1.0), rich_black_min_area_pt2=100.0)
    assert conv.convert(0.0, 0.0, 0.0, area_pt2=100.0) == (0.5, 0.5, 0.5, 1.0)
    assert conv.convert(0.0, 0.0, 0.0, area_pt2=99.0) == (0.0, 0.0, 0.0, 1.0)


def test_near_black_does_not_get_black_rules(conv: CMYKConverter) -> None:
    # Only exact 0/0/0 is special-cased; #0A0A0A goes through the ICC transform.
    assert conv.convert(*_hex("#0A0A0A"), role="text") != (0.0, 0.0, 0.0, 1.0)


def test_out_of_range_inputs_are_clamped(conv: CMYKConverter) -> None:
    assert conv.convert(-0.5, 0.5, 1.5) == conv.convert(0.0, 0.5, 1.0)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


def test_missing_profile_raises(tmp_path: Path) -> None:
    with pytest.raises(ICCProfileNotFoundError):
        CMYKConverter(tmp_path / "nope.icc")


def test_non_cmyk_profile_raises(tmp_path: Path) -> None:
    srgb = tmp_path / "srgb.icc"
    srgb.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    with pytest.raises(ValueError, match="CMYK"):
        CMYKConverter(srgb)


def test_unreadable_profile_raises(tmp_path: Path) -> None:
    junk = tmp_path / "junk.icc"
    junk.write_bytes(b"not an icc profile")
    with pytest.raises(ValueError):
        CMYKConverter(junk)


def test_naive_formula_is_deleted() -> None:
    # D17: the naive "black removal" function is gone, not kept as a fallback.
    public_functions = {
        name
        for name, obj in vars(color_management).items()
        if not name.startswith("_") and inspect.isfunction(obj)
        and obj.__module__ == color_management.__name__
    }
    assert public_functions == {"default_cmyk_icc_path"}


# ---------------------------------------------------------------------------
# Raster images (the #71 seam)
# ---------------------------------------------------------------------------


def _quad() -> Image.Image:
    img = Image.new("RGB", (2, 2))
    img.putdata([(0, 0, 255), (204, 28, 28), (0, 0, 0), (255, 255, 255)])
    return img


def test_convert_image_returns_cmyk(conv: CMYKConverter) -> None:
    out = conv.convert_image(_quad())
    assert out.mode == "CMYK"
    assert out.size == (2, 2)


def test_convert_image_matches_convert_for_non_black(conv: CMYKConverter) -> None:
    out = conv.convert_image(_quad())
    blue = tuple(v / 255 for v in out.getpixel((0, 0)))  # type: ignore[union-attr]
    assert blue == pytest.approx(conv.convert(0.0, 0.0, 1.0), abs=1 / 255 + 1e-9)


def test_convert_image_does_not_apply_black_rules_but_caps_ink(conv: CMYKConverter) -> None:
    out = conv.convert_image(_quad())
    black = out.getpixel((0, 1))
    assert black != (0, 0, 0, 255)
    raw = out.tobytes()
    for i in range(0, len(raw), 4):
        assert sum(raw[i : i + 4]) <= 3.0 * 255


def test_convert_image_honours_embedded_icc_profile(conv: CMYKConverter) -> None:
    # P3 primaries differ from sRGB, so the same pixel values convert differently.
    tagged = _quad()
    tagged.info["icc_profile"] = _display_p3_profile()
    untagged = _quad()
    assert conv.convert_image(tagged).tobytes() != conv.convert_image(untagged).tobytes()


def test_convert_image_accepts_rgba_and_palette(conv: CMYKConverter) -> None:
    assert conv.convert_image(_quad().convert("RGBA")).mode == "CMYK"
    assert conv.convert_image(_quad().convert("P")).mode == "CMYK"


def _display_p3_profile() -> bytes:
    """Display-P3 ICC bytes: Pillow's sRGB profile with P3 (D50-adapted) colorants.

    Pillow can't synthesise arbitrary RGB profiles, so this rewrites the
    rXYZ/gXYZ/bXYZ tags of its sRGB matrix profile.
    """
    p3_d50 = {
        b"rXYZ": (0.515102, 0.241196, -0.001053),
        b"gXYZ": (0.291965, 0.692236, 0.041882),
        b"bXYZ": (0.157153, 0.066574, 0.784073),
    }
    data = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    (count,) = struct.unpack(">I", data[128:132])
    for i in range(count):
        sig, off, _size = struct.unpack(">4sII", data[132 + 12 * i : 144 + 12 * i])
        if sig in p3_d50:
            xyz = p3_d50[sig]
            data[off + 8 : off + 20] = b"".join(
                struct.pack(">i", round(v * 65536)) for v in xyz
            )
    # Zero the profile ID (MD5) so LittleCMS doesn't reject the edited bytes.
    data[84:100] = bytes(16)
    buf = io.BytesIO(bytes(data))
    _ = ImageCms.ImageCmsProfile(buf)  # must parse
    return bytes(data)
