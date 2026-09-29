"""CMYK colour operators emitted by ``IRReportLabRenderer(color_space="cmyk")`` (#70, D9).

* Every colour goes through ``CMYKConverter`` (sRGB → GRACoL2013 via
  LittleCMS, relative colorimetric + BPC, 300% ink cap), with the draw's
  role: text and strokes of pure black are K-only, a pure-black fill of
  at least 1 in² (bbox area) is rich black 60/40/40/100, smaller fills and
  paths (no bbox) are K-only.
* No ``k``/``K`` operator in any shipped template's ``moo-a6`` output has
  C+M+Y+K > 3.0.
* ``letter`` (sRGB) output is untouched: each template's page content
  stream hashes to the golden captured before this change
  (``__golden__/letter_content_sha256.json``). Regenerate it only on
  purpose: ``HOLIDAY_CARD_REGEN_LETTER_CONTENT_GOLDEN=1 uv run pytest <this file>``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pikepdf
import pytest

from holiday_card.core.card_request import CardRequest, build_card
from holiday_card.core.color_management import CMYKConverter
from holiday_card.core.compiler import compile_card
from holiday_card.core.generators import CardGenerator
from holiday_card.core.render_ir import (
    RGBA,
    BeginPage,
    DrawFoldLine,
    DrawShape,
    DrawText,
    EndPage,
    GradientStop,
    LinearGradientPaint,
    PathGeom,
    PathOp,
    PatternPaint,
    Point,
    RectGeom,
    RenderCommand,
    SolidPaint,
    Stroke,
    TextRun,
)
from holiday_card.core.templates import discover_templates
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer

_GOLDEN = Path(__file__).resolve().parent / "__golden__" / "letter_content_sha256.json"
_REGEN = "HOLIDAY_CARD_REGEN_LETTER_CONTENT_GOLDEN"

_BLACK = RGBA(r=0, g=0, b=0)
_BLUE = RGBA(r=0, g=0, b=1)
_K_ONLY = [0.0, 0.0, 0.0, 1.0]
_RICH_BLACK = [0.6, 0.4, 0.4, 1.0]


def _p(x: float, y: float) -> Point:
    return Point(x=x, y=y)


def _page(*body: RenderCommand) -> list[RenderCommand]:
    return [BeginPage(width=300, height=300, bleed=0), *body, EndPage()]


def _content(pdf_path: Path) -> bytes:
    with pikepdf.open(pdf_path) as pdf:
        contents = pdf.pages[0].Contents
        streams = contents if isinstance(contents, pikepdf.Array) else [contents]
        return b"".join(s.read_bytes() for s in streams)


def _color_ops(pdf_path: Path) -> list[tuple[str, list[float]]]:
    """Every ``k``/``K``/``rg``/``RG`` operator on page 1, operands as floats."""
    with pikepdf.open(pdf_path) as pdf:
        return [
            (str(op), [float(o) for o in operands])
            for operands, op in pikepdf.parse_content_stream(pdf.pages[0])
            if str(op) in ("k", "K", "rg", "RG")
        ]


def _cmyk_ops(commands: list[RenderCommand], tmp_path: Path) -> list[tuple[str, list[float]]]:
    out = tmp_path / "out.pdf"
    IRReportLabRenderer(color_space="cmyk").render(commands, out)
    return _color_ops(out)


def _rect(w: float, h: float, *, fill: RGBA | None = _BLACK, stroke: RGBA | None = None) -> DrawShape:
    return DrawShape(
        geometry=RectGeom(x=10, y=10, width=w, height=h),
        fill=SolidPaint(color=fill) if fill is not None else None,
        stroke=Stroke(color=stroke, width=2) if stroke is not None else None,
    )


# ---------------------------------------------------------------------------
# Roles and area
# ---------------------------------------------------------------------------


def test_black_text_emits_exactly_k_only(tmp_path: Path) -> None:
    run = TextRun(text="Hi", origin=_p(20, 20), font_id="Helvetica", size_pt=200, color=_BLACK)
    out = tmp_path / "out.pdf"
    IRReportLabRenderer(color_space="cmyk").render(_page(DrawText(run=run)), out)
    assert b"0 0 0 1 k" in _content(out)
    assert _color_ops(out) == [("k", _K_ONLY)]


def test_large_black_fill_is_rich_black(tmp_path: Path) -> None:
    assert _cmyk_ops(_page(_rect(100, 100)), tmp_path) == [("k", _RICH_BLACK)]


def test_black_fill_at_exactly_one_square_inch_is_rich_black(tmp_path: Path) -> None:
    assert _cmyk_ops(_page(_rect(72, 72)), tmp_path) == [("k", _RICH_BLACK)]


def test_small_black_fill_is_k_only(tmp_path: Path) -> None:
    assert _cmyk_ops(_page(_rect(72, 71)), tmp_path) == [("k", _K_ONLY)]


def test_black_circle_area_uses_its_bbox(tmp_path: Path) -> None:
    # r = 36 → bbox 72 × 72 = 1 in², although the disc itself is smaller.
    from holiday_card.core.render_ir import CircleGeom

    shape = DrawShape(geometry=CircleGeom(center=_p(100, 100), radius=36), fill=SolidPaint(color=_BLACK))
    assert _cmyk_ops(_page(shape), tmp_path) == [("k", _RICH_BLACK)]


def test_black_path_fill_counts_as_small(tmp_path: Path) -> None:
    ops = tuple(
        PathOp(op=o, points=pts)  # type: ignore[arg-type]
        for o, pts in (
            ("move", (_p(0, 0),)),
            ("line", (_p(300, 0),)),
            ("line", (_p(300, 300),)),
            ("close", ()),
        )
    )
    shape = DrawShape(geometry=PathGeom(ops=ops), fill=SolidPaint(color=_BLACK))
    assert _cmyk_ops(_page(shape), tmp_path) == [("k", _K_ONLY)]


def test_black_stroke_on_large_shape_is_k_only(tmp_path: Path) -> None:
    ops = _cmyk_ops(_page(_rect(200, 200, fill=None, stroke=_BLACK)), tmp_path)
    assert ops == [("K", _K_ONLY)]


def test_solid_fill_uses_icc_not_naive(tmp_path: Path) -> None:
    (op, (c, m, y, k)), = _cmyk_ops(_page(_rect(50, 50, fill=_BLUE)), tmp_path)
    assert op == "k"
    assert [c, m, y, k] == pytest.approx([1.0, 0.855, 0.0, 0.0], abs=0.02)


def test_fold_line_uses_the_converter(tmp_path: Path) -> None:
    fold = DrawFoldLine(start=_p(0, 150), end=_p(300, 150), style="dashed")
    (op, operands), = _cmyk_ops(_page(fold), tmp_path)
    assert op == "K"
    expected = CMYKConverter().convert(0.7, 0.7, 0.7, role="stroke")
    assert operands == pytest.approx(list(expected), abs=0.005)
    assert operands != pytest.approx([0.0, 0.0, 0.0, 0.3], abs=0.01)  # naive


def test_pattern_colours_use_icc(tmp_path: Path) -> None:
    shape = DrawShape(
        geometry=RectGeom(x=0, y=0, width=100, height=100),
        fill=PatternPaint(pattern="dots", colors=(_BLUE, RGBA(r=1, g=1, b=1)), spacing=20),
    )
    ops = _cmyk_ops(_page(shape), tmp_path)
    assert ops[0][0] == "k"
    assert ops[0][1] == pytest.approx([1.0, 0.855, 0.0, 0.0], abs=0.02)


def test_gradient_stops_use_icc(tmp_path: Path) -> None:
    shape = DrawShape(
        geometry=RectGeom(x=0, y=0, width=100, height=100),
        fill=LinearGradientPaint(
            start=_p(0, 0),
            end=_p(100, 0),
            stops=(
                GradientStop(position=0.0, color=_BLUE),
                GradientStop(position=1.0, color=RGBA(r=1, g=1, b=1)),
            ),
        ),
    )
    out = tmp_path / "out.pdf"
    IRReportLabRenderer(color_space="cmyk").render(_page(shape), out)
    with pikepdf.open(out) as pdf:
        shadings = pdf.pages[0].Resources.Shading
        (shading,) = (shadings[k] for k in shadings)
        assert str(shading.ColorSpace) == "/DeviceCMYK"
        c0 = [float(v) for v in shading.Function.C0]
    assert c0 == pytest.approx([1.0, 0.855, 0.0, 0.0], abs=0.02)


# ---------------------------------------------------------------------------
# Shipped templates
# ---------------------------------------------------------------------------


def _template_ids() -> list[str]:
    return sorted(t["id"] for t in discover_templates())


@pytest.fixture(scope="module")
def moo_outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[Path]]:
    root = tmp_path_factory.mktemp("moo-a6-cmyk")
    gen = CardGenerator()
    return {
        tid: gen.generate(gen.create_card(tid), root / tid, target="moo-a6")
        for tid in _template_ids()
    }


@pytest.mark.parametrize("template_id", _template_ids())
def test_moo_a6_ink_never_exceeds_300(
    moo_outputs: dict[str, list[Path]], template_id: str
) -> None:
    over = [
        (pdf.name, op, operands)
        for pdf in moo_outputs[template_id]
        for op, operands in _color_ops(pdf)
        if op in ("k", "K") and sum(operands) > 3.0 + 1e-6
    ]
    assert over == []


def _letter_content_sha256(template_id: str, tmp_path: Path) -> str:
    out = tmp_path / f"{template_id}.pdf"
    IRReportLabRenderer().render(compile_card(build_card(CardRequest(template=template_id))), out)
    return hashlib.sha256(_content(out)).hexdigest()


def _load_golden() -> dict[str, str]:
    data: dict[str, str] = json.loads(_GOLDEN.read_text())
    return data


def test_letter_golden_covers_every_shipped_template() -> None:
    if os.environ.get(_REGEN):
        pytest.skip("regenerating golden")
    assert sorted(_load_golden()) == _template_ids()


@pytest.mark.parametrize("template_id", _template_ids())
def test_letter_srgb_content_stream_unchanged(template_id: str, tmp_path: Path) -> None:
    digest = _letter_content_sha256(template_id, tmp_path)
    if os.environ.get(_REGEN):
        golden = _load_golden() if _GOLDEN.exists() else {}
        golden[template_id] = digest
        _GOLDEN.write_text(json.dumps(dict(sorted(golden.items())), indent=1) + "\n")
        return
    assert digest == _load_golden()[template_id]
