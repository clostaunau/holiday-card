"""Opt-in live smoke: one real ``ai-asset generate --provider openrouter`` call (#150).

THIS COSTS REAL MONEY: about $0.14 per run at 2026-09-30 prices (the
default model, one 2K image). It never runs in CI: it is skipped unless
``HOLIDAY_CARD_LIVE_OPENROUTER=1`` and ``OPENROUTER_API_KEY`` is set, and
``tests/unit/test_workflow_policy.py`` keeps both out of every workflow.
#151 adds ``--max-cost`` to this invocation.

    HOLIDAY_CARD_LIVE_OPENROUTER=1 OPENROUTER_API_KEY=... uv run pytest tests/live -m live_ai
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner

from holiday_card.cli.commands import app

pytestmark = pytest.mark.live_ai

_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
if os.environ.get("HOLIDAY_CARD_LIVE_OPENROUTER") != "1" or not _KEY:
    pytest.skip(
        "live OpenRouter smoke (costs money): set HOLIDAY_CARD_LIVE_OPENROUTER=1 "
        "and OPENROUTER_API_KEY to run it",
        allow_module_level=True,
    )

REFERENCE = Path(__file__).parent.parent / "fixtures" / "openrouter" / "reference_8x8.png"


def test_openrouter_default_model_bakes_a_moo_a6_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("HOLIDAY_CARD_AI_PROVIDER", raising=False)
    out = tmp_path / "live.png"
    result = CliRunner().invoke(
        app,
        [
            "ai-asset", "generate", "--provider", "openrouter",
            "--subject", "watercolor pine bough border, sage green and burgundy",
            "--reference", str(REFERENCE), "--occasion", "christmas",
            "--export-for", "moo-a6", "--accept-ai-terms", "--max-cost", "0.25",
            "-o", str(out),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    with Image.open(out) as img:
        assert img.size == (1314, 1824)
    sidecar_text = out.with_suffix(".license.yaml").read_text()
    sidecar = yaml.safe_load(sidecar_text)
    assert sidecar["provider"] == "openrouter"
    assert sidecar["provider_route"]
    assert _KEY not in result.output
    assert _KEY not in sidecar_text
