"""Hand-built IR fixtures for the ReportLab (PDF) backend (issue #62).

Each fixture is a module-level ``list[RenderCommand]`` on a 200x200 pt
page. They are importable on purpose: the backend-parity matrix (#67)
reuses them against the SVG oracle (D12). Each test renders a fixture
with ``IRReportLabRenderer`` and inspects the content stream with
pikepdf through :func:`ops_with_alpha`.

The shipped-template check compares every paint operator's effective
``(ca, CA)`` against a golden captured before the fix
(``__golden__/pdf_alpha_sequence.json``). Regenerate it only on purpose:
``HOLIDAY_CARD_REGEN_PDF_ALPHA_GOLDEN=1 uv run pytest <this file>``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pikepdf
import pytest

from holiday_card.core.card_request import CardRequest, build_card
from holiday_card.core.compiler import compile_card
from holiday_card.core.render_ir import (
    RGBA,
    BeginGroup,
    BeginPage,
    DrawImage,
    DrawShape,
    DrawText,
    EndGroup,
    EndPage,
    ImageRef,
    PathGeom,
    PathOp,
    Point,
    RectGeom,
    RenderCommand,
    SolidPaint,
    Stroke,
    TextRun,
)
from holiday_card.core.templates import discover_templates
from holiday_card.renderers import reportlab_backend
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
_GOLDEN = Path(__file__).resolve().parent / "__golden__" / "pdf_alpha_sequence.json"
_PAINT_OPS = frozenset({"f", "F", "f*", "S", "s", "B", "B*", "b", "b*", "Tj", "TJ", "Do", "sh"})

_BLACK = RGBA(r=0, g=0, b=0)
_RED_HALF = RGBA(r=1, g=0, b=0, a=0.5)
_BLUE = RGBA(r=0, g=0, b=1)


def _page(*body: RenderCommand) -> list[RenderCommand]:
    return [BeginPage(width=200, height=200, bleed=0), *body, EndPage()]


def _p(x: float, y: float) -> Point:
    return Point(x=x, y=y)


def _path(*ops: tuple[str, tuple[Point, ...]]) -> PathGeom:
    return PathGeom(ops=tuple(PathOp(op=o, points=pts) for o, pts in ops))  # type: ignore[arg-type]


def _text(text: str, x: float, y: float, color: RGBA = _BLACK, opacity: float = 1.0) -> DrawText:
    run = TextRun(text=text, origin=_p(x, y), font_id="Helvetica", size_pt=24, color=color)
    return DrawText(run=run, opacity=opacity)


# ---------------------------------------------------------------------------
# Fixtures (importable; #67 reuses them)
# ---------------------------------------------------------------------------

QUAD_SIMPLE: list[RenderCommand] = _page(
    DrawShape(
        geometry=_path(("move", (_p(0, 0),)), ("quadratic", (_p(100, 200), _p(200, 0)))),
        stroke=Stroke(color=_BLACK, width=2),
    )
)

QUAD_AFTER_CLOSE: list[RenderCommand] = _page(
    DrawShape(
        geometry=_path(
            ("move", (_p(0, 0),)),
            ("line", (_p(50, 0),)),
            ("close", ()),
            ("quadratic", (_p(50, 100), _p(100, 0))),
        ),
        stroke=Stroke(color=_BLACK, width=2),
    )
)

QUAD_AFTER_CUBIC: list[RenderCommand] = _page(
    DrawShape(
        geometry=_path(
            ("move", (_p(0, 0),)),
            ("cubic", (_p(0, 50), _p(50, 50), _p(50, 0))),
            ("quadratic", (_p(100, 100), _p(150, 0))),
        ),
        stroke=Stroke(color=_BLACK, width=2),
    )
)

QUAD_WITHOUT_CURRENT_POINT: list[RenderCommand] = _page(
    DrawShape(
        geometry=_path(("quadratic", (_p(100, 200), _p(200, 0)))),
        stroke=Stroke(color=_BLACK, width=2),
    )
)

FILL_ALPHA_NO_LEAK: list[RenderCommand] = _page(
    DrawShape(geometry=RectGeom(x=0, y=0, width=100, height=100), fill=SolidPaint(color=_RED_HALF)),
    _text("Hi", 20, 150),
    DrawShape(geometry=RectGeom(x=100, y=100, width=50, height=50), fill=SolidPaint(color=_BLUE)),
)

ALPHA_MULTIPLY: list[RenderCommand] = _page(
    DrawShape(
        geometry=RectGeom(x=0, y=0, width=100, height=100),
        fill=SolidPaint(color=_RED_HALF),
        opacity=0.5,
    )
)

STROKE_ALPHA: list[RenderCommand] = _page(
    DrawShape(
        geometry=RectGeom(x=20, y=20, width=100, height=100),
        stroke=Stroke(color=RGBA(r=0, g=0, b=0, a=0.4), width=2),
    )
)

TEXT_ALPHA: list[RenderCommand] = _page(
    _text("Hi", 20, 150, color=RGBA(r=0, g=0, b=0, a=0.5), opacity=0.5),
    _text("Yo", 20, 50),
)

_PHOTO = _FIXTURES / "sample_photo.jpg"

IMAGE_OPACITY: list[RenderCommand] = _page(
    DrawImage(
        image=ImageRef(
            source=str(_PHOTO),
            rect=RectGeom(x=0, y=0, width=100, height=100),
            format="jpeg",
            width_px=400,
            height_px=400,
        ),
        opacity=0.5,
    ),
    DrawShape(geometry=RectGeom(x=100, y=100, width=50, height=50), fill=SolidPaint(color=_BLUE)),
)


def dash_fixture(dash: tuple[float, ...]) -> list[RenderCommand]:
    """A stroked rect with the given dash array."""
    return _page(
        DrawShape(
            geometry=RectGeom(x=20, y=20, width=100, height=100),
            stroke=Stroke(color=_BLACK, width=2, dash=dash),
        )
    )


DASH_ARRAYS: dict[tuple[float, ...], list[RenderCommand]] = {
    d: dash_fixture(d) for d in [(4.0,), (3.0, 3.0), (3.0, 1.0, 1.0, 1.0)]
}

GROUP_OPACITY: list[RenderCommand] = _page(
    BeginGroup(opacity=0.5),
    DrawShape(geometry=RectGeom(x=0, y=0, width=100, height=100), fill=SolidPaint(color=_BLUE)),
    EndGroup(),
)


# ---------------------------------------------------------------------------
# Content-stream inspection
# ---------------------------------------------------------------------------


def _plain(operand: object) -> object:
    if isinstance(operand, pikepdf.Array):
        return [_plain(o) for o in operand]
    try:
        return float(operand)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(operand)


def ops_with_alpha(pdf_path: Path) -> list[tuple[str, list[object], float, float]]:
    """Walk page 1 tracking a q/Q stack of (ca, CA).

    On ``gs`` the named ExtGState's ``/ca`` and ``/CA`` (when present)
    replace the current values. Returns ``(operator, operands, ca, CA)``
    for every operator; numbers become floats, arrays become lists.
    """
    with pikepdf.open(pdf_path) as pdf:
        page = pdf.pages[0]
        ext = page.Resources.get("/ExtGState", pikepdf.Dictionary())
        stack: list[tuple[float, float]] = []
        ca, big_ca = 1.0, 1.0
        out: list[tuple[str, list[object], float, float]] = []
        for operands, operator in pikepdf.parse_content_stream(page):
            op = str(operator)
            if op == "q":
                stack.append((ca, big_ca))
            elif op == "Q":
                ca, big_ca = stack.pop()
            elif op == "gs":
                gs = ext[str(operands[0])]
                if "/ca" in gs:
                    ca = float(gs["/ca"])
                if "/CA" in gs:
                    big_ca = float(gs["/CA"])
            out.append((op, [_plain(o) for o in operands], ca, big_ca))
        return out


def _render(commands: list[RenderCommand], tmp_path: Path, name: str = "out.pdf") -> Path:
    out = tmp_path / name
    IRReportLabRenderer().render(commands, out)
    return out


def _ops(commands: list[RenderCommand], tmp_path: Path) -> list[tuple[str, list[object], float, float]]:
    return ops_with_alpha(_render(commands, tmp_path))


_Op = tuple[str, list[object], float, float]


def _only(ops: list[_Op], *names: str) -> list[_Op]:
    return [o for o in ops if o[0] in names]


def _fills(ops: list[_Op]) -> list[_Op]:
    # ReportLab paints fills with the even-odd operator f*.
    return _only(ops, "f", "f*")


# ---------------------------------------------------------------------------
# Quadratic curves
# ---------------------------------------------------------------------------


def _assert_operands(actual: list[object], expected: list[float]) -> None:
    assert actual == pytest.approx(expected, abs=0.01)


def test_quad_simple_lifts_from_current_point(tmp_path: Path) -> None:
    curves = _only(_ops(QUAD_SIMPLE, tmp_path), "c")
    assert len(curves) == 1
    _assert_operands(curves[0][1], [66.667, 133.333, 133.333, 133.333, 200, 0])


def test_quad_after_close_starts_at_subpath_start(tmp_path: Path) -> None:
    curves = _only(_ops(QUAD_AFTER_CLOSE, tmp_path), "c")
    assert len(curves) == 1
    _assert_operands(curves[0][1], [33.333, 66.667, 66.667, 66.667, 100, 0])


def test_quad_after_cubic_starts_at_cubic_end(tmp_path: Path) -> None:
    curves = _only(_ops(QUAD_AFTER_CUBIC, tmp_path), "c")
    assert len(curves) == 2
    _assert_operands(curves[1][1], [83.333, 66.667, 116.667, 66.667, 150, 0])


def test_quad_without_current_point_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="current point"):
        _render(QUAD_WITHOUT_CURRENT_POINT, tmp_path)


def test_backend_no_longer_probes_for_contour() -> None:
    assert "contour" not in Path(reportlab_backend.__file__).read_text()


# ---------------------------------------------------------------------------
# Alpha is scoped state
# ---------------------------------------------------------------------------


def test_fill_alpha_does_not_leak(tmp_path: Path) -> None:
    ops = _ops(FILL_ALPHA_NO_LEAK, tmp_path)
    fills = _fills(ops)
    texts = _only(ops, "Tj")
    assert len(fills) == 2 and len(texts) == 1
    assert fills[0][2] == pytest.approx(0.5)
    assert texts[0][2] == pytest.approx(1.0)
    assert fills[1][2] == pytest.approx(1.0)


def test_fill_alpha_multiplies_with_opacity(tmp_path: Path) -> None:
    fills = _fills(_ops(ALPHA_MULTIPLY, tmp_path))
    assert len(fills) == 1
    assert fills[0][2] == pytest.approx(0.25)


def test_stroke_color_alpha_is_applied(tmp_path: Path) -> None:
    strokes = _only(_ops(STROKE_ALPHA, tmp_path), "S")
    assert len(strokes) == 1
    assert strokes[0][3] == pytest.approx(0.4)


def test_text_color_alpha_multiplies_and_is_scoped(tmp_path: Path) -> None:
    texts = _only(_ops(TEXT_ALPHA, tmp_path), "Tj")
    assert len(texts) == 2
    assert texts[0][2] == pytest.approx(0.25)
    assert texts[1][2] == pytest.approx(1.0)


def test_image_opacity_is_applied_and_scoped(tmp_path: Path) -> None:
    ops = _ops(IMAGE_OPACITY, tmp_path)
    images = _only(ops, "Do")
    fills = _fills(ops)
    assert len(images) == 1 and len(fills) == 1
    assert images[0][2] == pytest.approx(0.5)
    assert fills[0][2] == pytest.approx(1.0)


def test_group_opacity_raises(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError, match="group opacity"):
        _render(GROUP_OPACITY, tmp_path)


# ---------------------------------------------------------------------------
# Dash arrays
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dash", list(DASH_ARRAYS), ids=lambda d: "x".join(f"{v:g}" for v in d))
def test_dash_array_emitted_verbatim(tmp_path: Path, dash: tuple[float, ...]) -> None:
    ops = _ops(DASH_ARRAYS[dash], tmp_path)
    dashes = [o for o in _only(ops, "d") if o[1][0]]
    assert len(dashes) == 1
    assert dashes[0][1] == [list(dash), 0.0]


# ---------------------------------------------------------------------------
# No regression on shipped templates
# ---------------------------------------------------------------------------


def _template_ids() -> list[str]:
    return sorted(t["id"] for t in discover_templates())


def alpha_sequence(pdf_path: Path) -> list[list[object]]:
    """``[op, ca, CA]`` for every paint operator on page 1 (rounded)."""
    return [
        [op, round(ca, 6), round(big_ca, 6)]
        for op, _, ca, big_ca in ops_with_alpha(pdf_path)
        if op in _PAINT_OPS
    ]


def _template_alpha_sequence(template_id: str, tmp_path: Path) -> list[list[object]]:
    card = build_card(CardRequest(template=template_id))
    return alpha_sequence(_render(compile_card(card), tmp_path, f"{template_id}.pdf"))


def _load_golden() -> dict[str, list[list[object]]]:
    data: dict[str, list[list[object]]] = json.loads(_GOLDEN.read_text())
    return data


def test_golden_covers_every_shipped_template() -> None:
    if os.environ.get("HOLIDAY_CARD_REGEN_PDF_ALPHA_GOLDEN"):
        pytest.skip("regenerating golden")
    assert sorted(_load_golden()) == _template_ids()


@pytest.mark.parametrize("template_id", _template_ids())
def test_shipped_template_alpha_sequence_unchanged(template_id: str, tmp_path: Path) -> None:
    seq = _template_alpha_sequence(template_id, tmp_path)
    if os.environ.get("HOLIDAY_CARD_REGEN_PDF_ALPHA_GOLDEN"):
        golden = _load_golden() if _GOLDEN.exists() else {}
        golden[template_id] = seq
        _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{json.dumps(k)}: {json.dumps(v)}" for k, v in sorted(golden.items())]
        _GOLDEN.write_text("{\n" + ",\n".join(lines) + "\n}\n")
        return
    assert seq == _load_golden()[template_id]
