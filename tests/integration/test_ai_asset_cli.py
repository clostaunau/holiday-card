"""Integration tests for the ``holiday-card ai-asset generate`` subcommand.

The model call is injected by monkeypatching ``make_image_client`` so no
network or ``OPENAI_API_KEY`` is needed. Consent is isolated by pointing
``XDG_CONFIG_HOME`` at a tmp dir and using the non-interactive
``--accept-ai-terms`` flag.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

import holiday_card.cli.commands as commands
from holiday_card.cli.commands import app
from holiday_card.core.ai_assets import GeneratedImage
from holiday_card.core.ai_openai import AIDependencyError


@dataclass
class FakeImageClient:
    calls: list[dict] = field(default_factory=list)

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        width_px: int,
        height_px: int,
        moderation: str,
        seed: int | None,
    ) -> GeneratedImage:
        self.calls.append(
            {
                "prompt": prompt,
                "reference_path": reference_path,
                "width_px": width_px,
                "height_px": height_px,
                "moderation": moderation,
                "seed": seed,
            }
        )
        buf = io.BytesIO()
        # Tiny stand-in; orchestration re-encodes and records real dims.
        Image.new("RGB", (16, 16), (10, 120, 60)).save(buf, format="PNG")
        return GeneratedImage(png_bytes=buf.getvalue(), cost_usd=0.04, model_version="2027-01")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def reference_png(tmp_path: Path) -> Path:
    path = tmp_path / "ref.png"
    Image.new("RGB", (32, 32), (200, 30, 30)).save(path, format="PNG")
    return path


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the consent store at a tmp config dir."""
    cfg = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    return cfg


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeImageClient:
    client = FakeImageClient()
    monkeypatch.setattr(commands, "make_image_client", lambda: client)
    return client


def _generate_args(reference: Path | None, out: Path, *, subject: str, occasion: str, extra: list[str] | None = None) -> list[str]:
    args = ["ai-asset", "generate", "--subject", subject, "--occasion", occasion, "--out", str(out)]
    if reference is not None:
        args += ["--reference", str(reference)]
    args += extra or []
    return args


@pytest.mark.usefixtures("isolated_config")
class TestHappyPath:
    def test_generates_asset_and_sidecar(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        fake_client: FakeImageClient,
    ) -> None:
        out = tmp_path / "out" / "border.png"
        result = runner.invoke(
            app,
            _generate_args(
                reference_png,
                out,
                subject="watercolor balloons in pastel colors",
                occasion="birthday",
                extra=["--export-for", "moo-a6", "--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        assert out.with_suffix(".license.yaml").exists()
        # The print-aware size was used (A6 trim+bleed >> 1024).
        assert fake_client.calls[0]["width_px"] > 1024
        assert fake_client.calls[0]["moderation"] == "auto"
        # Cost surfaced to the user.
        assert "0.04" in result.output


@pytest.mark.usefixtures("isolated_config", "fake_client")
class TestReferenceRequired:
    def test_missing_reference_errors(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            _generate_args(
                None,
                tmp_path / "x.png",
                subject="balloons",
                occasion="birthday",
                extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code != 0
        assert "reference" in result.output.lower()


@pytest.mark.usefixtures("isolated_config")
class TestMissingDependency:
    def test_missing_key_or_extra_is_a_clean_error_not_a_traceback(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def boom() -> object:
            raise AIDependencyError("OPENAI_API_KEY is not set.")

        monkeypatch.setattr(commands, "make_image_client", boom)
        result = runner.invoke(
            app,
            _generate_args(
                reference_png,
                tmp_path / "x.png",
                subject="balloons",
                occasion="birthday",
                extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 4
        assert "OPENAI_API_KEY" in result.output
        # No traceback leaked to the user.
        assert "Traceback" not in result.output


@pytest.mark.usefixtures("isolated_config", "fake_client")
class TestConsentGate:
    def test_refuses_without_consent_flag(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path
    ) -> None:
        result = runner.invoke(
            app,
            _generate_args(
                reference_png, tmp_path / "x.png", subject="balloons", occasion="birthday"
            ),
        )
        assert result.exit_code != 0
        assert "consent" in result.output.lower() or "accept-ai-terms" in result.output.lower()


@pytest.mark.usefixtures("isolated_config")
class TestHardRails:
    def test_sympathy_occasion_refused(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        fake_client: FakeImageClient,
    ) -> None:
        out = tmp_path / "s.png"
        result = runner.invoke(
            app,
            _generate_args(
                reference_png,
                out,
                subject="a calm field of wildflowers",
                occasion="sympathy",
                extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code != 0
        assert "sympathy" in result.output.lower()
        assert "--i-know-what-im-doing" in result.output
        assert not out.exists()
        assert not fake_client.calls

    @pytest.mark.usefixtures("fake_client")
    def test_override_proceeds(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path
    ) -> None:
        out = tmp_path / "s.png"
        result = runner.invoke(
            app,
            _generate_args(
                reference_png,
                out,
                subject="a calm field of wildflowers",
                occasion="sympathy",
                extra=["--accept-ai-terms", "--i-know-what-im-doing"],
            ),
        )
        assert result.exit_code == 0, result.output
        assert out.exists()

    @pytest.mark.usefixtures("fake_client")
    def test_trademark_prompt_refused(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path
    ) -> None:
        result = runner.invoke(
            app,
            _generate_args(
                reference_png,
                tmp_path / "m.png",
                subject="mickey mouse in a santa hat",
                occasion="christmas",
                extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code != 0
        assert "trademark" in result.output.lower()
