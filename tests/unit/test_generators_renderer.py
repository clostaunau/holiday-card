"""``CardGenerator`` talks to backends through the core ``Renderer`` Protocol (#75)."""

from __future__ import annotations

from pathlib import Path

import pytest

from holiday_card.core.export_targets import get_target
from holiday_card.core.generators import CardGenerator, Renderer
from holiday_card.core.render_ir import RenderCommand
from holiday_card.renderers.png_backend import PNGRenderer
from holiday_card.renderers.reportlab_backend import IRReportLabRenderer
from holiday_card.renderers.svg_backend import SVGRenderer


class _RecordingRenderer:
    """A backend the core has never heard of."""

    file_extension = ".json"
    color_space = "srgb"

    def __init__(self) -> None:
        self.rendered: list[Path] = []

    def render(self, commands: list[RenderCommand], output_path: Path) -> None:
        self.rendered.append(output_path)
        output_path.write_text(str(len(commands)))


@pytest.mark.parametrize(
    "renderer", [IRReportLabRenderer(), SVGRenderer(), PNGRenderer()], ids=type
)
def test_every_backend_satisfies_the_protocol(renderer: object) -> None:
    assert isinstance(renderer, Renderer)
    assert renderer.color_space in {"srgb", "cmyk"}  # type: ignore[attr-defined]


def test_default_renderer_is_srgb_pdf() -> None:
    renderer = CardGenerator().renderer
    assert (renderer.file_extension, renderer.color_space) == (".pdf", "srgb")


def test_cmyk_target_swaps_in_a_cmyk_pdf_renderer() -> None:
    swapped = CardGenerator()._renderer_for(get_target("moo-a6"))
    assert (swapped.file_extension, swapped.color_space) == (".pdf", "cmyk")


@pytest.mark.parametrize("renderer", [SVGRenderer(), _RecordingRenderer()], ids=type)
def test_cmyk_target_leaves_a_non_pdf_renderer_alone(renderer: Renderer) -> None:
    assert CardGenerator(renderer=renderer)._renderer_for(get_target("moo-a6")) is renderer


def test_a_protocol_only_renderer_generates(tmp_path: Path) -> None:
    renderer = _RecordingRenderer()
    generator = CardGenerator(renderer=renderer)
    card = generator.create_card("christmas-classic")
    paths = generator.generate(card, tmp_path / "card.json")
    assert paths == [tmp_path / "card.json"] == renderer.rendered
