"""Cross-backend conformance: every case × backend against the SVG oracle (#67, D12).

For each ``(case, backend)`` the capability matrix says what must happen:

* ``match``: the backend's raster is within tolerance of the SVG raster.
* ``raises``: the backend raises ``NotImplementedError`` (D4).
* ``known_diff``: the backend is **outside** tolerance. Once the owning issue
  fixes it this test fails, forcing the matrix entry to flip to ``match``
  (explicit strict-xfail).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import get_args

import pytest
from capabilities import CAPABILITIES, Backend
from cases import CASES, CASES_BY_ID, Case
from PIL import Image

from holiday_card.core.render_ir import RenderCommand
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer

BACKENDS: tuple[Backend, ...] = get_args(Backend)
DPI = 144


@pytest.fixture(scope="session")
def svg_oracle(
    tmp_path_factory: pytest.TempPathFactory,
    rasterize_svg: Callable[[Path, int], Image.Image],
) -> Callable[[Case], Image.Image]:
    out_dir = tmp_path_factory.mktemp("conformance-svg")

    @cache
    def _oracle(case: Case) -> Image.Image:
        out = out_dir / f"{case.id}.svg"
        SVGRenderer().render(list(case.commands), out)
        return rasterize_svg(out, DPI)

    return _oracle


@pytest.fixture
def render_backend(
    tmp_path: Path,
    rasterize_pdf: Callable[[Path, int], Image.Image],
    render_png: Callable[..., Image.Image],
) -> Callable[[Backend, list[RenderCommand], str], Image.Image]:
    def _render(backend: Backend, commands: list[RenderCommand], name: str) -> Image.Image:
        if backend == "pdf":
            out = tmp_path / f"{name}.pdf"
            IRReportLabRenderer().render(commands, out)
            return rasterize_pdf(out, DPI)
        return render_png(commands, DPI, name)

    return _render


@pytest.fixture(scope="session")
def compare(
    raster_matches: Callable[[Image.Image, Image.Image, float], tuple[bool, str]],
    text_matches: Callable[[Image.Image, Image.Image], tuple[bool, str]],
    tolerance: dict[str, float],
) -> Callable[[Case, Backend, Image.Image, Image.Image], tuple[bool, str]]:
    def _compare(
        case: Case, backend: Backend, oracle: Image.Image, actual: Image.Image
    ) -> tuple[bool, str]:
        if case.is_text:
            return text_matches(oracle, actual)
        return raster_matches(oracle, actual, tolerance[backend])

    return _compare


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("case_id", [c.id for c in CASES])
def test_backend_conforms_to_svg_oracle(
    case_id: str,
    backend: Backend,
    svg_oracle: Callable[[Case], Image.Image],
    render_backend: Callable[[Backend, list[RenderCommand], str], Image.Image],
    compare: Callable[[Case, Backend, Image.Image, Image.Image], tuple[bool, str]],
) -> None:
    case = CASES_BY_ID[case_id]
    cap = CAPABILITIES[case_id][backend]
    commands = list(case.commands)

    if cap.status == "raises":
        with pytest.raises(NotImplementedError):
            render_backend(backend, commands, case_id)
        return

    oracle = svg_oracle(case)
    actual = render_backend(backend, commands, case_id)
    matched, detail = compare(case, backend, oracle, actual)
    if cap.status == "match":
        assert matched, f"{case_id}/{backend} drifted from the SVG oracle: {detail}"
    else:
        assert not matched, (
            f"{case_id}/{backend} now matches the SVG oracle ({detail}); "
            f"{cap.owner} fixed it — flip the entry to 'match' in capabilities.py "
            "and regenerate docs/conformance-matrix.md"
        )


# ---------------------------------------------------------------------------
# Drift guards on the matrix itself
# ---------------------------------------------------------------------------


def test_every_case_has_an_entry_for_every_backend() -> None:
    missing = [
        f"{c.id}/{b}" for c in CASES for b in BACKENDS if b not in CAPABILITIES.get(c.id, {})
    ]
    assert missing == []


def test_matrix_has_no_orphan_entries() -> None:
    orphans = sorted(set(CAPABILITIES) - set(CASES_BY_ID))
    assert orphans == []
    extra = [f"{k}/{b}" for k, row in CAPABILITIES.items() for b in row if b not in BACKENDS]
    assert extra == []


def test_every_known_diff_names_an_owner() -> None:
    ownerless = [
        f"{k}/{b}" for k, row in CAPABILITIES.items() for b, cap in row.items()
        if cap.status == "known_diff" and not cap.owner
    ]
    assert ownerless == []


def test_case_ids_are_unique() -> None:
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))


def test_suite_covers_at_least_35_cases() -> None:
    assert len(CASES) >= 35


# ---------------------------------------------------------------------------
# Metric sensitivity: a thin feature in the wrong colour must not "match"
# ---------------------------------------------------------------------------


def _vline(grey: int) -> Image.Image:
    img = Image.new("RGB", (288, 288), (255, 255, 255))
    for y in range(288):
        img.putpixel((144, y), (grey, grey, grey))
    return img


@pytest.mark.parametrize("backend", BACKENDS)
def test_thin_line_in_wrong_colour_is_a_mismatch(
    backend: Backend,
    compare: Callable[[Case, Backend, Image.Image, Image.Image], tuple[bool, str]],
) -> None:
    case = CASES_BY_ID["fold_line_dashed"]
    assert compare(case, backend, _vline(178), _vline(178))[0]
    matched, detail = compare(case, backend, _vline(178), _vline(77))
    assert not matched, detail


def test_svg_oracle_draws_nothing_for_an_unregistered_font_family(
    tmp_path: Path, rasterize_svg: Callable[[Path, int], Image.Image]
) -> None:
    # resvg's default-family fallback differs by host (Linux resolved it to a
    # bundled serif, macOS drew nothing), so the oracle must refuse fallback.
    svg = tmp_path / "unknown_font.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144">'
        '<text x="72" y="84" font-family="Cormorant" font-size="32" '
        'text-anchor="middle">Hello</text></svg>',
        encoding="utf-8",
    )
    img = rasterize_svg(svg, DPI)
    assert img.convert("L").getextrema() == (255, 255)
