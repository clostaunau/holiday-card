"""Integration tests for the ``holiday-card ai-asset generate`` subcommand.

The model call is injected by monkeypatching ``make_image_client`` so no
network or ``OPENAI_API_KEY`` is needed. Consent is isolated by pointing
``XDG_CONFIG_HOME`` at a tmp dir and using the non-interactive
``--accept-ai-terms`` flag.
"""

from __future__ import annotations

import io
import re
import shutil
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
from holiday_card.core.ai_assets import GeneratedImage, PixelSize, RequestShape
from holiday_card.core.ai_errors import ProviderError
from holiday_card.core.ai_openai import OpenAIImageClient
from holiday_card.core.ai_provenance import consent_notice, default_consent_path, has_consented
from holiday_card.core.ai_providers import AIDependencyError, AIProvider

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ai"


@dataclass
class FakeImageClient:
    calls: list[dict] = field(default_factory=list)
    model: str = "gpt-image-2"
    provider: AIProvider = AIProvider.OPENAI
    returns: tuple[int, int] | None = None
    raw: bytes | None = None
    cost_usd: float | None = 0.13

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        shape: RequestShape,
        seed: int | None,
        transparent: bool = False,
    ) -> GeneratedImage:
        self.calls.append({
            "prompt": prompt, "reference_path": reference_path, "shape": shape, "seed": seed,
            "transparent": transparent,
        })
        assert isinstance(shape, PixelSize)
        buf = io.BytesIO()
        size = self.returns or (shape.width_px, shape.height_px)
        Image.new("RGB", size, (10, 120, 60)).save(buf, format="PNG")
        return GeneratedImage(
            image_bytes=self.raw if self.raw is not None else buf.getvalue(),
            media_type="image/png",
            cost_usd=self.cost_usd,
            cost_source="reported" if self.cost_usd is not None else "unknown",
            model_version="2027-01",
            generation_id=None,
            provider_route=None,
        )


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
    monkeypatch.setattr(commands, "make_image_client", lambda **_: client)
    return client


def _generate_args(reference: Path | None, out: Path, *, subject: str, occasion: str, extra: list[str] | None = None) -> list[str]:
    args = ["ai-asset", "generate", "--subject", subject, "--occasion", occasion, "--output", str(out)]
    if reference is not None:
        args += ["--reference", str(reference)]
    args += extra or []
    return args


@pytest.mark.usefixtures("isolated_config")
class TestMaxCost:
    """No OpenAI model has a verified upper bound recorded (#151 scope 3)."""

    def test_openai_without_a_recorded_price_exits_2_before_the_call(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        fake_client: FakeImageClient,
    ) -> None:
        out_dir = tmp_path / "out"
        result = runner.invoke(
            app,
            _generate_args(
                reference_png, out_dir / "border.png", subject="watercolor balloons",
                occasion="birthday",
                extra=["--provider", "openai", "--max-cost", "1", "--accept-ai-terms"],
            ),
        )  # fmt: skip
        assert result.exit_code == 2, result.output
        assert fake_client.calls == []
        assert not out_dir.exists()
        assert (
            "Error: no price on record for gpt-image-2 (openai); --max-cost cannot be checked. "
            "Omit --max-cost or pick a model with a recorded price."
        ) in " ".join(_plain(result.output).split())


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
        assert fake_client.calls[0]["shape"] == PixelSize(1328, 1824)
        # The provider-reported cost is surfaced as such.
        assert "Cost: $0.13 (reported)" in _plain(result.output)
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
        monkeypatch.setattr(commands, "make_image_client", lambda **_: client)
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
        assert client.calls[0]["shape"] == PixelSize(1024, 1536)
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
        def boom(**_: object) -> object:
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
        assert result.exit_code == 3
        assert "Error: AI imagery with --provider openai requires a one-time consent" in _plain(
            result.output
        )
        consent_path = default_consent_path()
        assert consent_notice(AIProvider.OPENAI, path=consent_path) in result.stderr
        assert not consent_path.exists()

    def test_v1_3_0_consent_file_still_counts_and_is_not_rewritten(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path, isolated_config: Path
    ) -> None:
        consent_path = isolated_config / "holiday-card" / "ai-consent.json"
        consent_path.parent.mkdir(parents=True)
        shutil.copy(FIXTURES / "v1.3.0-ai-consent.json", consent_path)
        before = consent_path.read_bytes()
        result = runner.invoke(
            app,
            _generate_args(
                reference_png, tmp_path / "x.png", subject="balloons", occasion="birthday"
            ),
        )
        assert result.exit_code == 0, result.output
        assert "first-use acknowledgement" not in result.output
        assert consent_path.read_bytes() == before

    def test_accepting_records_openai_consent(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path
    ) -> None:
        result = runner.invoke(
            app,
            _generate_args(
                reference_png, tmp_path / "x.png", subject="balloons", occasion="birthday",
                extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 0, result.output
        consent_path = default_consent_path()
        assert has_consented(consent_path, AIProvider.OPENAI)
        assert consent_notice(AIProvider.OPENAI, path=consent_path) in result.output


def test_cli_hard_codes_no_openai_policy() -> None:
    source = Path(commands.__file__).read_text()
    assert "OpenAI policy:" not in source
    assert "openai.com" not in source


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
    provider: AIProvider = AIProvider.OPENAI

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
    monkeypatch.setattr(commands, "make_image_client", lambda **_: client)
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
        client = OpenAIImageClient(sdk_client, model="gpt-image-2", api_key=SecretStr(_SENTINEL))
        result = _run(runner, monkeypatch, client, tmp_path, reference_png, debug=debug)
        assert result.exit_code == code, result.output
        surfaces = [result.output, _chain_text(result.exception)]
        surfaces += [p.read_text(errors="replace") for p in isolated_config.rglob("*") if p.is_file()]
        for text in surfaces:
            assert _SENTINEL not in text


    def test_sentinel_absent_from_a_successful_bake(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
        isolated_config: Path,
    ) -> None:
        # #147: the sidecar and the consent file have no field that could hold the key.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-SENTINEL-DO-NOT-LEAK-0123456789")
        monkeypatch.setattr(commands, "make_image_client", lambda **_: FakeImageClient())
        out = tmp_path / "x.png"
        result = runner.invoke(
            app,
            _generate_args(
                reference_png, out, subject="watercolor balloons", occasion="birthday",
                extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 0, result.output
        consent = isolated_config / "holiday-card" / "ai-consent.json"
        surfaces = [result.stdout, result.stderr, out.with_suffix(".license.yaml").read_text(),
                    consent.read_text()]
        for text in surfaces:
            assert "SENTINEL" not in text


def _raiser(exc: BaseException) -> Callable[..., object]:
    def raise_(**_kwargs: object) -> object:
        raise exc

    return raise_


# ---------------------------------------------------------------------------
# #141: model output is untrusted, the cost is never invented, the
# reference is content-checked before anything is uploaded
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("isolated_config")
class TestUntrustedPayload:
    def test_unreported_cost_prints_unknown(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
    ) -> None:
        result = _run(runner, monkeypatch, FakeImageClient(cost_usd=None), tmp_path, reference_png)
        assert result.exit_code == 0, result.output
        text = _plain(result.output)
        assert "Cost: unknown (the provider did not report one)" in text
        assert "$0.04" not in text
        sidecar = (tmp_path / "x.license.yaml").read_text()
        assert "cost_usd: null" in sidecar
        assert "cost_source: unknown" in sidecar
        assert "0.04" not in sidecar

    @pytest.mark.parametrize("debug", [False, True], ids=["plain", "debug"])
    def test_refused_image_exits_7_and_writes_nothing(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
        debug: bool,
    ) -> None:
        eps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n"
        client = FakeImageClient(raw=eps)
        result = _run(runner, monkeypatch, client, tmp_path, reference_png, debug=debug)
        assert result.exit_code == 7, result.output
        text = _plain(result.output)
        assert "Error: the model's image was refused:" in text
        assert "Traceback" not in text
        assert not (tmp_path / "x.png").exists()
        assert not (tmp_path / "x.license.yaml").exists()


@pytest.mark.usefixtures("isolated_config")
class TestReferenceIsProbed:
    def _no_client(self, **_: object) -> object:
        raise AssertionError("an image client was built")

    def test_text_file_named_png_is_refused_before_any_client(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(commands, "make_image_client", self._no_client)
        secrets = tmp_path / "ref.png"
        secrets.write_text("OPENAI_API_KEY=sk-not-an-image\n")
        result = runner.invoke(
            app,
            _generate_args(
                secrets, tmp_path / "x.png", subject="balloons", occasion="birthday",
                extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 2, result.output
        text = _plain(result.output)
        assert "Error: --reference:" in text
        assert "sk-not-an-image" not in text
        assert not (tmp_path / "x.png").exists()

    def test_missing_reference_file_is_refused(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(commands, "make_image_client", self._no_client)
        result = runner.invoke(
            app,
            _generate_args(
                tmp_path / "nope.png", tmp_path / "x.png", subject="balloons",
                occasion="birthday", extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 2, result.output
        assert "Error: --reference: image file not found" in _plain(result.output)

    def test_resolved_reference_path_is_sent(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        reference_png: Path,
    ) -> None:
        client = FakeImageClient()
        monkeypatch.setattr(commands, "make_image_client", lambda **_: client)
        monkeypatch.chdir(reference_png.parent)
        result = runner.invoke(
            app,
            _generate_args(
                Path(reference_png.name), tmp_path / "x.png", subject="balloons",
                occasion="birthday", extra=["--accept-ai-terms"],
            ),
        )
        assert result.exit_code == 0, result.output
        assert client.calls[0]["reference_path"] == str(reference_png.resolve())


# ---------------------------------------------------------------------------
# --provider / --model, and --seed refused for seedless models (#146)
# ---------------------------------------------------------------------------


def _flat(output: str) -> str:
    # Rich wraps its error box; compare on single-spaced plain text.
    return " ".join(_plain(output).split())


@pytest.fixture
def factory(monkeypatch: pytest.MonkeyPatch) -> tuple[list[dict[str, object]], FakeImageClient]:
    """A recording ``make_image_client`` whose client reports the model it was asked for."""
    calls: list[dict[str, object]] = []
    client = FakeImageClient()

    def make(**kwargs: object) -> FakeImageClient:
        calls.append(kwargs)
        client.model = str(kwargs["model"])
        return client

    monkeypatch.setattr(commands, "make_image_client", make)
    monkeypatch.delenv("HOLIDAY_CARD_AI_PROVIDER", raising=False)
    return calls, client


def _moo_args(reference: Path, out: Path, *extra: str) -> list[str]:
    return _generate_args(
        reference, out, subject="watercolor balloons", occasion="birthday",
        extra=["--export-for", "moo-a6", "--accept-ai-terms", *extra],
    )


@pytest.mark.usefixtures("isolated_config")
class TestProviderAndModel:
    def test_defaults_to_openai_and_its_default_model(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path, factory: tuple
    ) -> None:
        calls, client = factory
        result = runner.invoke(app, _moo_args(reference_png, tmp_path / "x.png"))
        assert result.exit_code == 0, result.output
        assert calls == [{"provider": AIProvider.OPENAI, "model": "gpt-image-2"}]
        assert client.calls[0]["shape"] == PixelSize(1328, 1824)

    def test_model_flag_sizes_for_that_model(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path, factory: tuple
    ) -> None:
        calls, client = factory
        result = runner.invoke(
            app, _moo_args(reference_png, tmp_path / "x.png", "--model", "gpt-image-1")
        )
        assert result.exit_code == 0, result.output
        assert calls == [{"provider": AIProvider.OPENAI, "model": "gpt-image-1"}]
        assert client.calls[0]["shape"] == PixelSize(1024, 1536)

    def test_unknown_model_is_a_usage_error(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path, factory: tuple
    ) -> None:
        calls, _ = factory
        result = runner.invoke(
            app, _moo_args(reference_png, tmp_path / "x.png", "--model", "dall-e-9")
        )
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert "Error: unknown openai image model 'dall-e-9'; known:" in text
        assert "gpt-image-2" in text
        assert calls == []

    def test_unknown_provider_flag_is_a_usage_error(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path, factory: tuple
    ) -> None:
        calls, _ = factory
        result = runner.invoke(
            app, _moo_args(reference_png, tmp_path / "x.png", "--provider", "bogus")
        )
        assert result.exit_code == 2, result.output
        assert calls == []

    def test_unknown_provider_env_names_the_variable(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path, factory: tuple
    ) -> None:
        calls, _ = factory
        result = runner.invoke(
            app,
            _moo_args(reference_png, tmp_path / "x.png"),
            env={"HOLIDAY_CARD_AI_PROVIDER": "bogus"},
        )
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert "HOLIDAY_CARD_AI_PROVIDER" in text
        assert "bogus" in text
        assert calls == []

    @pytest.mark.parametrize("value", ["openai", ""], ids=["openai", "empty"])
    def test_provider_env_openai_or_empty_works(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        factory: tuple,
        value: str,
    ) -> None:
        calls, _ = factory
        result = runner.invoke(
            app,
            _moo_args(reference_png, tmp_path / "x.png"),
            env={"HOLIDAY_CARD_AI_PROVIDER": value},
        )
        assert result.exit_code == 0, result.output
        assert calls == [{"provider": AIProvider.OPENAI, "model": "gpt-image-2"}]


class TestSeedRefused:
    def test_seed_is_refused_before_consent_and_client(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        isolated_config: Path,
        factory: tuple,
    ) -> None:
        calls, _ = factory
        out = tmp_path / "x.png"
        result = runner.invoke(app, _moo_args(reference_png, out, "--seed", "42"))
        assert result.exit_code == 2, result.output
        assert (
            "Error: --seed is not supported by openai model 'gpt-image-2' (it takes no seed, "
            "so the image could not be reproduced). Omit --seed."
        ) in _flat(result.output)
        assert calls == []
        assert not out.exists()
        assert not any(isolated_config.rglob("*")), "consent was recorded"


class TestTransparentRefused:
    def test_transparent_is_refused_for_direct_openai_before_consent_and_client(
        self,
        runner: CliRunner,
        tmp_path: Path,
        reference_png: Path,
        isolated_config: Path,
        factory: tuple,
    ) -> None:
        # #169: no silent opaque fallback; #179 enabled sunburst on OpenRouter only.
        calls, _ = factory
        out = tmp_path / "x.png"
        result = runner.invoke(app, _moo_args(reference_png, out, "--transparent"))
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert (
            "Error: --transparent is not supported by openai model 'gpt-image-2'"
        ) in text
        assert "Models that do: openrouter openai/gpt-image-2.5-sunburst." in text
        assert calls == []
        assert not out.exists()
        assert not any(isolated_config.rglob("*")), "consent was recorded"


@pytest.mark.usefixtures("isolated_config", "fake_client")
class TestPanelBackground:
    """``--for-panel-background`` sizes the bake for a panel on the fit target (#168)."""

    def _run(
        self, runner: CliRunner, reference: Path, out: Path, extra: list[str]
    ) -> Result:
        return runner.invoke(
            app,
            _generate_args(
                reference, out, subject="watercolor pine boughs", occasion="christmas",
                extra=["--accept-ai-terms", *extra],
            ),
        )  # fmt: skip

    def test_moo_a6_bake_covers_the_fitted_panel(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path
    ) -> None:
        from holiday_card.core.ai_provenance import read_sidecar

        out = tmp_path / "bg.png"
        result = self._run(
            runner, reference_png, out, ["--export-for", "moo-a6", "--for-panel-background"]
        )
        assert result.exit_code == 0, result.output
        assert "1427x1824px" in result.output
        with Image.open(out) as img:
            assert img.size == (1427, 1824)
        record = read_sidecar(out)
        assert (record.purpose, record.export_target) == ("panel_background", "moo-a6")

    def test_page_bake_records_its_purpose(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path
    ) -> None:
        from holiday_card.core.ai_provenance import read_sidecar

        out = tmp_path / "page.png"
        result = self._run(runner, reference_png, out, ["--export-for", "moo-a6"])
        assert result.exit_code == 0, result.output
        with Image.open(out) as img:
            assert img.size == (1314, 1824)
        record = read_sidecar(out)
        assert (record.purpose, record.export_target) == ("page", "moo-a6")

    def test_panel_size_overrides_the_quarter_fold_panel(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path
    ) -> None:
        out = tmp_path / "bg.png"
        result = self._run(
            runner, reference_png, out,
            ["--export-for", "moo-a6", "--for-panel-background", "--panel-size", "5x7"],
        )
        assert result.exit_code == 0, result.output
        with Image.open(out) as img:
            # s = 5.83/7; 5·s + 0.25 = 4.414 in → 1325 px; 7·s + 0.25 = 6.08 in.
            assert img.size == (1325, 1824)

    def test_panel_size_needs_for_panel_background(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path,
        fake_client: FakeImageClient,
    ) -> None:
        result = self._run(runner, reference_png, tmp_path / "bg.png", ["--panel-size", "5x7"])
        assert result.exit_code == 2, result.output
        assert "--for-panel-background" in _plain(result.output)
        assert fake_client.calls == []

    @pytest.mark.parametrize("value", ["5", "5x", "axb", "0x7", "-1x7", "infx7"])
    def test_bad_panel_size_is_a_usage_error(
        self, runner: CliRunner, tmp_path: Path, reference_png: Path,
        fake_client: FakeImageClient, value: str,
    ) -> None:
        result = self._run(
            runner, reference_png, tmp_path / "bg.png",
            ["--for-panel-background", "--panel-size", value],
        )
        assert result.exit_code == 2, result.output
        assert "--panel-size" in _plain(result.output)
        assert fake_client.calls == []
