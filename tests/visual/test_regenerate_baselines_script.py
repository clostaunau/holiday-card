"""``scripts/regenerate_visual_baselines.py`` refuses PNG baselines it cannot reproduce (#68).

The PNG backend's text layout depends on the host: Pillow uses libraqm
(kerning) only when the system has libfribidi, else its basic layout. The
committed PNG baselines are raqm renders from ubuntu-latest, so writing PNG
baselines on a host without raqm would bake the other layout in as truth.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import visual_gate
from PIL import features

pytestmark = pytest.mark.visual

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "regenerate_visual_baselines.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("regenerate_visual_baselines", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_png_layout_matches_baselines_iff_raqm_is_available() -> None:
    assert visual_gate.png_layout_matches_baselines() is features.check("raqm")


def test_script_refuses_png_without_raqm(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _load_script()
    monkeypatch.setattr(script, "png_layout_matches_baselines", lambda: False)
    before = visual_gate.baseline_path("png", "christmas-classic").read_bytes()

    code = script.main(["--backend", "png", "--template", "christmas-classic"])

    assert code == 2
    assert "raqm" in capsys.readouterr().err
    assert visual_gate.baseline_path("png", "christmas-classic").read_bytes() == before
