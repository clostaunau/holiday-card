"""Integration tests for the ``holiday-card ai-asset generate`` subcommand.

The model call is injected by monkeypatching ``make_image_client`` so no
network or ``OPENAI_API_KEY`` is needed. Consent is isolated by pointing
``XDG_CONFIG_HOME`` at a tmp dir and using the non-interactive
``--accept-ai-terms`` flag.
"""

from __future__ import annotations

import io
import re
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import SecretStr
from typer.testing import CliRunner, Result

import holiday_card.cli.commands as commands
import openai_sdk_stub as sdk
from holiday_card.cli.commands import app
from holiday_card.core.ai_assets import GeneratedImage
from holiday_card.core.ai_errors import ProviderError
from holiday_card.core.ai_openai import AIDependencyError, OpenAIImageClient


@dataclass
class FakeImageClient:
    calls: list[dict] = field(default_factory=list)
    model: str = "gpt-image-2"
    returns: tuple[int, int] | None = None

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
        size = self.returns or (width_px, height_px)
        Image.new("RGB", size, (10, 120, 60)).save(buf, format="PNG")
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
    args = ["ai-asset", "generate", "--subject", subject, "--occasion", occasion, "--output", str(out)]
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
        # The written size, not the request size, is reported.
        assert "1314x1824px" in result.output
        assert "300.0 PPI native" in result.output
        assert "below 300" not in result.output
        with Image.open(out) as img:
            assert img.size == (1314, 1824)

    def test_low_native_ppi_is_warned_and_written_size_reported(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = FakeImageClient(model="gpt-image-1", returns=(1024, 1536))
        monkeypatch.setattr(commands, "make_image_client", lambda: client)
        out = tmp_path / "low.png"
        result = runner.invoke(
            app,
            _generate_args(
                reference_png,
                out,
                subject="watercolor balloons",
                occasion="birthday",
                extra=["--export-for", "moo-a6", "--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 0, result.output
        assert (client.calls[0]["width_px"], client.calls[0]["height_px"]) == (1024, 1536)
        assert "1314x1824px" in result.output
        assert "1024x1536" not in result.output.split("Size:")[1].splitlines()[0]
        assert "233.8 PPI" in result.output
        assert "below 300" in result.output
        # The asset is still written.
        with Image.open(out) as img:
            assert img.size == (1314, 1824)


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


# ---------------------------------------------------------------------------
# Provider errors: exit 6 / 7 / 4 / 2 by kind, redacted, no traceback (#142)
# ---------------------------------------------------------------------------


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _chain_text(exc: BaseException | None) -> str:
    """Every message and formatted traceback along __cause__ / __context__."""
    parts: list[str] = []
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        parts += [str(exc), repr(exc), "".join(traceback.format_exception(exc))]
        exc = exc.__cause__ or exc.__context__
    return "\n".join(parts)


@dataclass
class RaisingImageClient:
    exc: BaseException
    model: str = "gpt-image-2"

    def generate(self, **_kwargs: object) -> GeneratedImage:
        raise self.exc


def _run(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    client: object,
    tmp_path: Path,
    reference: Path,
    *,
    debug: bool = False,
) -> Result:
    monkeypatch.setattr(commands, "make_image_client", lambda: client)
    args = _generate_args(
        reference,
        tmp_path / "x.png",
        subject="watercolor balloons",
        occasion="birthday",
        extra=["--accept-ai-terms"],
    )
    return runner.invoke(app, (["--debug"] if debug else []) + args)


@pytest.mark.usefixtures("isolated_config")
class TestProviderErrors:
    @pytest.mark.parametrize("debug", [False, True], ids=["plain", "debug"])
    @pytest.mark.parametrize(
        ("kind", "code"),
        [("refused", 6), ("transient", 7), ("environment", 4), ("usage", 2)],
    )
    def test_exit_code_by_kind(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
        kind: str,
        code: int,
        debug: bool,
    ) -> None:
        client = RaisingImageClient(ProviderError("nope", kind=kind, status=400))  # type: ignore[arg-type]
        result = _run(runner, monkeypatch, client, tmp_path, reference_png, debug=debug)
        assert result.exit_code == code, result.output
        text = _plain(result.output)
        assert "Traceback" not in text
        assert "Error:" in text
        assert "(HTTP 400): nope" in text
        assert not (tmp_path / "x.png").exists()

    def test_retry_after_is_printed(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
    ) -> None:
        err = ProviderError("slow down", kind="transient", status=429, retry_after_s=20.0)
        result = _run(runner, monkeypatch, RaisingImageClient(err), tmp_path, reference_png)
        assert result.exit_code == 7
        assert "Retry after 20 s." in _plain(result.output)

    def test_no_status_no_http_suffix(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
    ) -> None:
        err = ProviderError("Request timed out.", kind="transient")
        result = _run(runner, monkeypatch, RaisingImageClient(err), tmp_path, reference_png)
        assert result.exit_code == 7
        text = _plain(result.output)
        assert "HTTP" not in text
        assert "Retry after" not in text
        assert "Request timed out." in text

    def test_unexpected_error_exits_1_with_debug_hint(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
    ) -> None:
        client = RaisingImageClient(RuntimeError("kaboom"))
        result = _run(runner, monkeypatch, client, tmp_path, reference_png)
        assert result.exit_code == 1
        text = _plain(result.output)
        assert "kaboom" in text
        assert "re-run with --debug" in text
        assert "Traceback" not in text

    def test_unexpected_error_reraises_under_debug(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
    ) -> None:
        client = RaisingImageClient(RuntimeError("kaboom"))
        result = _run(runner, monkeypatch, client, tmp_path, reference_png, debug=True)
        assert isinstance(result.exception, RuntimeError)
        assert result.exit_code == 1


def test_tracebacks_never_show_locals() -> None:
    assert app.pretty_exceptions_show_locals is False
    assert commands.ai_asset_app.pretty_exceptions_show_locals is False
    # Explicit on both apps: typer>=0.12 admits versions that default it on.
    source = Path(commands.__file__).read_text()
    assert source.count("typer.Typer(") == 2
    assert source.count("pretty_exceptions_show_locals=False") == 2


_SENTINEL = "sk-proj-" + "S3nt1nelKey" * 3 + "Zz9_-abc"  # 8 + 41 chars


@pytest.mark.usefixtures("stub_openai")
class TestSecretSentinel:
    """The env key never reaches output, exceptions, tracebacks or config files."""

    @pytest.fixture
    def stub_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "openai", sdk.make_module())

    @pytest.mark.parametrize("debug", [False, True], ids=["plain", "debug"])
    @pytest.mark.parametrize(
        ("make_exc", "code"),
        [
            (lambda m: sdk.status_error(401, m, code="invalid_api_key"), 4),
            (lambda m: sdk.status_error(429, m, code="rate_limit_exceeded"), 7),
            (lambda m: sdk.status_error(400, m, code="moderation_blocked"), 6),
        ],
        ids=["auth", "rate-limit", "moderation"],
    )
    def test_sentinel_absent(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
        isolated_config: Path,
        make_exc: object,
        code: int,
        debug: bool,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", _SENTINEL)
        message = f"\x1b[31mIncorrect API key provided: {_SENTINEL}\x1b[0m"
        exc = make_exc(message)  # type: ignore[operator]
        sdk_client = SimpleNamespace(images=SimpleNamespace(edit=_raiser(exc), generate=_raiser(exc)))
        client = OpenAIImageClient(sdk_client, api_key=SecretStr(_SENTINEL))
        result = _run(runner, monkeypatch, client, tmp_path, reference_png, debug=debug)
        assert result.exit_code == code, result.output
        surfaces = [result.output, _chain_text(result.exception)]
        surfaces += [p.read_text(errors="replace") for p in isolated_config.rglob("*") if p.is_file()]
        for text in surfaces:
            assert _SENTINEL not in text


def _raiser(exc: BaseException) -> Callable[..., object]:
    def raise_(**_kwargs: object) -> object:
        raise exc

    return raise_
