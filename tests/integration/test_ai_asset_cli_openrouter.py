"""``ai-asset generate --provider openrouter`` end to end (issue #150).

Drives the real ``make_image_client`` and the real ``OpenRouterImageClient``;
only the transport is replaced (``ai_openrouter.urllib_transport``) by a
``FakeTransport`` fed from ``tests/fixtures/openrouter/``. The conftest
guard (#143) has already scrubbed both API keys; each test sets the
OpenRouter sentinel key unless it says otherwise. Row numbers are the
matrix in issue #150.
"""

from __future__ import annotations

import base64
import copy
import io
import json
import re
import shutil
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner, Result

from holiday_card.cli.commands import app
from holiday_card.core import ai_openrouter, ai_openrouter_models
from holiday_card.core.ai_errors import ProviderError
from holiday_card.core.ai_openrouter import HttpResponse
from openrouter_fixtures import (
    GOLDEN_REQUEST,
    REFERENCE_PNG,
    FakeTransport,
    fixture_raw,
    load_response,
    to_response,
)

KEY = "sk-or-v1-" + "ab" * 32
DEFAULT_MODEL = "google/gemini-3-pro-image"
PRIVACY_URL = "https://openrouter.ai/workspaces/default/settings"
TERMS_URL = "https://openrouter.ai/terms"
GEMINI_TERMS = "https://ai.google.dev/gemini-api/terms"
SUBJECT = "watercolor balloons"
LEGACY_CONSENT = Path(__file__).parent.parent / "fixtures" / "ai" / "v1.3.0-ai-consent.json"

# Row 15: fixture -> exit code.
ERROR_EXITS = {
    "err_400": 2,
    "err_401": 4,
    "err_402": 4,
    "err_402_in_flight": 7,
    "err_403_policy": 6,
    "err_403_refusal": 6,
    "err_403_permission": 4,
    "err_429": 7,
    "err_502": 7,
    "err_524": 7,
    "err_200_envelope": 7,
    "empty_data": 6,
    "two_images": 6,
    "remote_url": 6,
    "svg": 7,
    "mime_mismatch": 7,
    "bad_base64": 7,
    "bomb_png": 7,
    "not_json": 7,
}


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _flat(output: str) -> str:
    return " ".join(_plain(output).split())


def _chain_text(exc: BaseException | None) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        parts += [str(exc), repr(exc), "".join(traceback.format_exception(exc))]
        exc = exc.__cause__ or exc.__context__
    return "\n".join(parts)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    monkeypatch.delenv("HOLIDAY_CARD_AI_PROVIDER", raising=False)
    return cfg


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    return KEY


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    fake = FakeTransport()
    monkeypatch.setattr(ai_openrouter, "urllib_transport", fake)
    return fake


@pytest.fixture
def ref(tmp_path: Path) -> Path:
    path = tmp_path / "ref.png"
    shutil.copy(REFERENCE_PNG, path)
    return path


def _args(
    out: Path,
    *extra: str,
    reference: Path | None,
    provider: str | None = "openrouter",
    occasion: str = "birthday",
    accept: bool = True,
) -> list[str]:
    args = ["ai-asset", "generate", "--subject", SUBJECT, "--occasion", occasion,
            "--export-for", "moo-a6", "-o", str(out)]  # fmt: skip
    if provider is not None:
        args += ["--provider", provider]
    if reference is not None:
        args += ["--reference", str(reference)]
    if accept:
        args.append("--accept-ai-terms")
    return args + list(extra)


def _consent_file(config: Path) -> Path:
    return config / "holiday-card" / "ai-consent.json"


def _png_response(size: tuple[int, int]) -> HttpResponse:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 120, 60)).save(buf, format="PNG")
    body = {
        "data": [{"b64_json": base64.b64encode(buf.getvalue()).decode(), "media_type": "image/png"}],
        "usage": {"cost": 0.1344},
    }
    return HttpResponse(200, {"content-type": "application/json"}, json.dumps(body).encode())


def _assert_ok_bake(result: Result, out: Path, transport: FakeTransport) -> dict[str, Any]:
    assert result.exit_code == 0, result.output
    assert len(transport.calls) == 1
    with Image.open(out) as img:
        assert img.size == (1314, 1824)
        assert tuple(round(d) for d in img.info["dpi"]) == (300, 300)
    sidecar: dict[str, Any] = yaml.safe_load(out.with_suffix(".license.yaml").read_text())
    assert sidecar["provider"] == "openrouter"
    return sidecar


# --------------------------------------------------------------------------- happy path


@pytest.mark.usefixtures("config", "key")
class TestBake:
    def test_row01_default_model_moo_a6(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref))
        sidecar = _assert_ok_bake(result, out, transport)

        golden = json.loads((REFERENCE_PNG.parent / GOLDEN_REQUEST).read_text())
        body = transport.body
        assert body["prompt"] == SUBJECT
        assert {**body, "prompt": golden["prompt"]} == golden

        assert sidecar["requested_model"] == sidecar["model"] == DEFAULT_MODEL
        assert sidecar["provider_route"] == "google-ai-studio/global"
        assert sidecar["request_shape"] == {"aspect_ratio": "3:4", "resolution": "2K"}
        assert sidecar["generation_id"] == "gen-TEST123"
        assert sidecar["cost_usd"] == 0.1344
        assert sidecar["cost_source"] == "reported"
        assert sidecar["media_type"] == "image/png"
        assert {TERMS_URL, PRIVACY_URL, GEMINI_TERMS} <= set(sidecar["policy_urls"])

        text = _plain(result.output)
        assert "Provider: openrouter (route: google-ai-studio/global)" in text
        assert f"Model: {DEFAULT_MODEL}" in text
        assert "1314x1824px @ 300 DPI (sRGB)" in text
        assert "PPI native" in text
        assert "below 300" in text  # the 8x8 fixture image is far under 300 PPI
        assert "Cost: $0.13 (reported)" in text
        for url in (TERMS_URL, PRIVACY_URL, GEMINI_TERMS):
            assert f"Policy: {url}" in text
        assert "Personal use only" in text

    def test_row02_env_default_selects_openrouter(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOLIDAY_CARD_AI_PROVIDER", "openrouter")
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref, provider=None))
        _assert_ok_bake(result, out, transport)
        assert transport.body["model"] == DEFAULT_MODEL

    def test_row03_seed_capable_model_sends_the_seed(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        out = tmp_path / "x.png"
        result = runner.invoke(
            app,
            _args(out, "--model", "black-forest-labs/flux.2-pro", "--seed", "7", reference=ref),
        )
        sidecar = _assert_ok_bake(result, out, transport)
        assert transport.body["seed"] == 7
        assert "resolution" not in transport.body
        assert sidecar["seed"] == 7
        assert sidecar["request_shape"] == {"aspect_ratio": "3:4"}

    def test_row17_low_resolution_output_warns_and_still_bakes(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        transport.responses.append(_png_response((768, 1024)))
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref))
        sidecar = _assert_ok_bake(result, out, transport)
        assert "below 300" in _plain(result.output)
        assert sidecar["generated_width_px"] == 768

    def test_unknown_cost_is_printed_as_unknown(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        raw = fixture_raw("ok_png")
        del raw["body"]["usage"]
        transport.responses.append(to_response(raw))
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref))
        _assert_ok_bake(result, out, transport)
        assert "Cost: unknown" in _plain(result.output)


# --------------------------------------------------------------------------- refusals before any call


@pytest.mark.usefixtures("config", "key")
class TestUsage:
    def test_row04_seed_on_a_seedless_model(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        result = runner.invoke(app, _args(tmp_path / "x.png", "--seed", "7", reference=ref))
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert DEFAULT_MODEL in text
        assert "--seed" in text
        assert transport.calls == []

    def test_row05_unknown_model_lists_the_curated_ids(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        result = runner.invoke(app, _args(tmp_path / "x.png", "--model", "foo/bar", reference=ref))
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert "foo/bar" in text
        for model_id in ai_openrouter_models.OPENROUTER_IMAGE_MODELS:
            assert model_id in text
        assert transport.calls == []

    def test_row06_unknown_provider_flag(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        result = runner.invoke(app, _args(tmp_path / "x.png", reference=ref, provider="bogus"))
        assert result.exit_code == 2, result.output
        assert transport.calls == []

    def test_row07_unknown_provider_env(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        result = runner.invoke(
            app,
            _args(tmp_path / "x.png", reference=ref, provider=None),
            env={"HOLIDAY_CARD_AI_PROVIDER": "bogus"},
        )
        assert result.exit_code == 2, result.output
        assert "HOLIDAY_CARD_AI_PROVIDER" in _flat(result.output)
        assert transport.calls == []

    def test_row14_rails_refuse_before_any_call(
        self, runner: CliRunner, tmp_path: Path, ref: Path, transport: FakeTransport
    ) -> None:
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref, occasion="sympathy"))
        assert result.exit_code == 5, result.output
        assert transport.calls == []
        assert not out.exists()


@pytest.mark.usefixtures("config")
class TestKey:
    @pytest.mark.parametrize("value", [None, "   "], ids=["unset", "blank"])
    def test_row08_missing_key_is_an_environment_error(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
        value: str | None,
    ) -> None:
        if value is not None:
            monkeypatch.setenv("OPENROUTER_API_KEY", value)
        result = runner.invoke(app, _args(tmp_path / "x.png", reference=ref))
        assert result.exit_code == 4, result.output
        text = _flat(result.output)
        assert "OPENROUTER_API_KEY" in text
        assert "pip install holiday-card[ai]" not in text
        assert "Traceback" not in text
        assert transport.calls == []

    def test_a_malformed_key_is_an_environment_error_not_a_traceback(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bad = "sk-or-v1 " + "ab" * 32  # whitespace inside: refused when the headers are built
        monkeypatch.setenv("OPENROUTER_API_KEY", bad)
        result = runner.invoke(app, _args(tmp_path / "x.png", reference=ref))
        assert result.exit_code == 4, result.output
        text = _plain(result.output)
        assert "Traceback" not in text
        assert bad not in text
        assert "ab" * 32 not in _chain_text(result.exception)
        assert transport.calls == []

    def test_row09_an_openai_key_does_not_cross_providers(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        result = runner.invoke(app, _args(tmp_path / "x.png", reference=ref))
        assert result.exit_code == 4, result.output
        assert "OPENROUTER_API_KEY" in _flat(result.output)
        assert transport.calls == []


# --------------------------------------------------------------------------- consent


@pytest.mark.usefixtures("key")
class TestConsent:
    def test_row10_openai_only_consent_does_not_cover_openrouter(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        config: Path,
    ) -> None:
        consent = _consent_file(config)
        consent.parent.mkdir(parents=True)
        shutil.copy(LEGACY_CONSENT, consent)
        result = runner.invoke(app, _args(tmp_path / "x.png", reference=ref, accept=False))
        assert result.exit_code == 3, result.output
        text = _plain(result.output)
        lowered = text.lower()
        assert "OpenRouter" in text
        assert "account-level" in lowered
        assert PRIVACY_URL in text
        assert "not screened" in lowered
        assert "Google (AI Studio)" in text
        assert transport.calls == []
        assert consent.read_bytes() == LEGACY_CONSENT.read_bytes()

    def test_row11_accepting_adds_openrouter_beside_openai(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        config: Path,
    ) -> None:
        consent = _consent_file(config)
        consent.parent.mkdir(parents=True)
        openai_entry = {
            "acknowledged": True,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "policy_urls": ["https://openai.com/policies/usage-policies"],
        }
        consent.write_text(json.dumps({"providers": {"openai": openai_entry}}))
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref))
        _assert_ok_bake(result, out, transport)
        providers = json.loads(consent.read_text())["providers"]
        assert providers["openai"] == openai_entry
        assert providers["openrouter"]["acknowledged"] is True
        assert PRIVACY_URL in providers["openrouter"]["policy_urls"]
        assert KEY not in consent.read_text()


# --------------------------------------------------------------------------- style anchor (S2)


def _with_entry(monkeypatch: pytest.MonkeyPatch, model_id: str, **changes: Any) -> str:
    base = ai_openrouter_models.OPENROUTER_IMAGE_MODELS[DEFAULT_MODEL]
    entry = replace(base, id=model_id, **changes)
    patched = {**ai_openrouter_models.OPENROUTER_IMAGE_MODELS, model_id: entry}
    monkeypatch.setattr(ai_openrouter_models, "OPENROUTER_IMAGE_MODELS", patched)
    return model_id


@pytest.mark.usefixtures("config", "key")
class TestStyleAnchor:
    def test_row12_no_reference_model_refuses_a_reference(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        model = _with_entry(monkeypatch, "test/no-refs", input_refs_max=0)
        result = runner.invoke(app, _args(tmp_path / "x.png", "--model", model, reference=ref))
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert "test/no-refs" in text
        assert "accepts no reference image" in text
        assert transport.calls == []

    def test_no_reference_model_without_the_unsafe_flag_names_the_model(
        self,
        runner: CliRunner,
        tmp_path: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
        config: Path,
    ) -> None:
        model = _with_entry(monkeypatch, "test/no-refs", input_refs_max=0)
        result = runner.invoke(app, _args(tmp_path / "x.png", "--model", model, reference=None))
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert "test/no-refs" in text
        assert "accepts no reference image" in text
        assert "--unsafe-no-style-anchor" in text
        assert transport.calls == []
        assert not _consent_file(config).exists(), "consent was recorded"

    def test_row13_no_reference_model_with_the_unsafe_flag(
        self,
        runner: CliRunner,
        tmp_path: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        model = _with_entry(monkeypatch, "test/no-refs", input_refs_max=0)
        out = tmp_path / "x.png"
        result = runner.invoke(
            app,
            _args(out, "--model", model, "--unsafe-no-style-anchor", reference=None),
        )
        _assert_ok_bake(result, out, transport)
        assert "input_references" not in transport.body

    def test_reference_required_model_refuses_the_unsafe_flag_alone(
        self,
        runner: CliRunner,
        tmp_path: Path,
        transport: FakeTransport,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        model = _with_entry(monkeypatch, "test/needs-ref", input_refs_min=1)
        result = runner.invoke(
            app,
            _args(tmp_path / "x.png", "--model", model, "--unsafe-no-style-anchor", reference=None),
        )
        assert result.exit_code == 2, result.output
        text = _flat(result.output)
        assert "test/needs-ref" in text
        assert "--reference" in text
        assert transport.calls == []


# --------------------------------------------------------------------------- provider errors


def _surfaces(result: Result, config: Path) -> list[str]:
    surfaces = [result.output, result.stdout, result.stderr, _chain_text(result.exception)]
    consent = _consent_file(config)
    if consent.exists():
        surfaces.append(consent.read_text())
    return surfaces


def _no_files_left_with_the_key(root: Path) -> None:
    hits = [p for p in root.rglob("*") if p.is_file() and KEY.encode() in p.read_bytes()]
    assert hits == []


@pytest.mark.usefixtures("config", "key")
class TestProviderErrors:
    @pytest.mark.parametrize(("name", "code"), sorted(ERROR_EXITS.items()))
    def test_row15_fixture_maps_to_exit_code(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        name: str,
        code: int,
    ) -> None:
        transport.responses.append(load_response(name))
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref))
        assert result.exit_code == code, result.output
        assert len(transport.calls) == 1  # never retried
        assert not out.exists()
        assert not out.with_suffix(".license.yaml").exists()
        text = _plain(result.output)
        assert "Traceback" not in text
        retry_after = load_response(name).headers.get("retry-after")
        if name in ("err_429", "err_402_in_flight"):
            assert retry_after is not None
            assert f"Retry after {retry_after} s." in text

    def test_row15_timeout_is_retryable(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
    ) -> None:
        transport.responses.append(ProviderError("Request timed out.", kind="transient"))
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref))
        assert result.exit_code == 7, result.output
        assert len(transport.calls) == 1
        assert not out.exists()
        assert "Traceback" not in _plain(result.output)

    @pytest.mark.parametrize("debug", [False, True], ids=["plain", "debug"])
    @pytest.mark.parametrize(
        "name", sorted(n for n in ERROR_EXITS if "error" in fixture_raw(n).get("body", {}))
    )
    def test_row16_the_key_never_surfaces(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        config: Path,
        name: str,
        debug: bool,
    ) -> None:
        raw = copy.deepcopy(fixture_raw(name))
        error = raw["body"]["error"]
        error["message"] = f"upstream said {KEY} was bad"
        error.setdefault("metadata", {})["reasons"] = [f"reason {KEY}"]
        transport.responses.append(to_response(raw))
        out = tmp_path / "x.png"
        result = runner.invoke(app, (["--debug"] if debug else []) + _args(out, reference=ref))
        assert result.exit_code == ERROR_EXITS[name], result.output
        for surface in _surfaces(result, config):
            assert KEY not in surface
        if debug:
            chain: BaseException | None = result.exception
            kinds = []
            while chain is not None:
                kinds.append(type(chain))
                chain = chain.__cause__ or chain.__context__
            assert ProviderError in kinds
        _no_files_left_with_the_key(tmp_path)

    def test_row16_the_key_is_not_in_a_successful_bake(
        self,
        runner: CliRunner,
        tmp_path: Path,
        ref: Path,
        transport: FakeTransport,
        config: Path,
    ) -> None:
        out = tmp_path / "x.png"
        result = runner.invoke(app, _args(out, reference=ref))
        _assert_ok_bake(result, out, transport)
        for surface in _surfaces(result, config):
            assert KEY not in surface
        _no_files_left_with_the_key(tmp_path)


# --------------------------------------------------------------------------- help (row 18)


class TestHelp:
    # Wide enough that Rich does not truncate HOLIDAY_CARD_AI_PROVIDER in the options box.
    def test_row18_group_help(self, runner: CliRunner) -> None:
        text = _flat(runner.invoke(app, ["ai-asset", "--help"], env={"COLUMNS": "200"}).output)
        assert "OPENROUTER_API_KEY" in text
        assert "--provider" in text
        assert "HOLIDAY_CARD_AI_PROVIDER" in text
        assert "AI card generator" not in text

    def test_row18_generate_help(self, runner: CliRunner) -> None:
        text = _flat(runner.invoke(app, ["ai-asset", "generate", "--help"], env={"COLUMNS": "200"}).output)
        assert "OPENROUTER_API_KEY" in text
        assert "--provider" in text
        assert "HOLIDAY_CARD_AI_PROVIDER" in text
        assert "/16" not in text
        assert "trim+bleed at 300 PPI" in text
        assert "--provider openrouter" in text
