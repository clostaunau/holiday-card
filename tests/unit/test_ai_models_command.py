"""``holiday-card ai-asset models``: the curated image models, offline (#152).

The JSON document is a contract: ``MODELS_JSON_SCHEMA`` below forbids extra
keys and requires every documented one, so adding, removing or renaming a
key fails here.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import typer.main
import yaml
from typer.testing import CliRunner

from holiday_card.cli import commands
from holiday_card.cli.commands import app
from holiday_card.core import ai_providers
from holiday_card.core.ai_providers import (
    PROVIDERS,
    AIProvider,
    list_models,
    model_listing_payload,
)

MODELS_JSON_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "models"],
    "properties": {
        "schema_version": {"const": 1},
        "models": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["provider", "id", "default", "route", "upstream", "input_references",
                             "aspect_ratios", "resolutions", "pixel_sizes", "seed", "transparent",
                             "output_formats", "pricing", "terms_urls", "snapshot_date"],
                "properties": {
                    "provider": {"enum": ["openai", "openrouter"]},
                    "id": {"type": "string", "minLength": 1},
                    "default": {"type": "boolean"},
                    "route": {"type": "string", "minLength": 1},
                    "upstream": {"type": "string", "minLength": 1},
                    "input_references": {
                        "type": "object", "additionalProperties": False, "required": ["min", "max"],
                        "properties": {"min": {"type": "integer", "minimum": 0},
                                       "max": {"type": "integer", "minimum": 0}},
                    },
                    "aspect_ratios": {"type": ["array", "null"],
                                      "items": {"type": "string",
                                                "pattern": r"^[0-9]+(\.[0-9]+)?:[0-9]+(\.[0-9]+)?$"}},
                    "resolutions": {"type": ["array", "null"],
                                    "items": {"enum": ["512", "768", "1K", "2K", "4K"]}},
                    "pixel_sizes": {
                        "type": ["object", "null"], "additionalProperties": False,
                        "required": ["fixed", "multiple", "max_edge", "max_aspect", "min_pixels",
                                     "max_pixels"],
                        "properties": {
                            "fixed": {"type": ["array", "null"],
                                      "items": {"type": "array",
                                                "prefixItems": [{"type": "integer"},
                                                                {"type": "integer"}],
                                                "minItems": 2, "maxItems": 2}},
                            "multiple": {"type": ["integer", "null"]},
                            "max_edge": {"type": ["integer", "null"]},
                            "max_aspect": {"type": ["number", "null"]},
                            "min_pixels": {"type": ["integer", "null"]},
                            "max_pixels": {"type": ["integer", "null"]},
                        },
                    },
                    "seed": {"type": "boolean"},
                    "transparent": {"type": "boolean"},
                    "output_formats": {"type": "array",
                                       "items": {"enum": ["png", "jpeg", "webp", "svg"]}},
                    "pricing": {
                        "type": "array",
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "required": ["billable", "unit", "usd"],
                            "properties": {
                                "billable": {"enum": ["output_image", "input_image",
                                                      "input_reference", "input_text"]},
                                "unit": {"enum": ["image", "megapixel", "token"]},
                                "usd": {"type": "number", "minimum": 0},
                            },
                        },
                    },
                    "terms_urls": {"type": "array", "minItems": 1,
                                   "items": {"type": "string", "pattern": "^https://"}},
                    "snapshot_date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                },
            },
        },
    },
}  # fmt: skip

KEY_ORDER = [
    "provider", "id", "default", "route", "upstream", "input_references", "aspect_ratios",
    "resolutions", "pixel_sizes", "seed", "transparent", "output_formats", "pricing", "terms_urls",
    "snapshot_date",
]  # fmt: skip

HEADER = "PROVIDER ID DEFAULT ROUTE REFS ASPECTS TIERS SEED TRANSPARENT PRICE TERMS SNAPSHOT"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _models(runner: CliRunner, *args: str, env: dict[str, str] | None = None) -> str:
    result = runner.invoke(app, ["ai-asset", "models", *args], env=env)
    assert result.exit_code == 0, result.output
    return _plain(result.stdout)


def _table_rows(text: str) -> dict[str, list[str]]:
    # ID -> the row's cells, sliced at the header's column starts (empty cells kept).
    lines = text.splitlines()
    starts = [m.start() for m in re.finditer(r"\S+", lines[0])]
    bounds = list(zip(starts, [*starts[1:], None], strict=True))
    body = lines[1 : lines.index("")]
    rows = [[line[a:b].strip() for a, b in bounds] for line in body]
    return {cells[1]: cells for cells in rows}


# --- table ----------------------------------------------------------------------------


def test_table_header_and_one_row_per_model(runner: CliRunner) -> None:
    text = _models(runner)
    lines = text.splitlines()
    assert " ".join(lines[0].split()) == HEADER
    assert sorted(_table_rows(text)) == sorted(r.id for r in list_models())


@pytest.mark.parametrize("provider", list(AIProvider))
def test_table_default_column_marks_the_registry_default(
    runner: CliRunner, provider: AIProvider
) -> None:
    text = _models(runner, "--provider", provider.value)
    starred = [cells[1] for cells in _table_rows(text).values() if cells[2] == "*"]
    assert starred == [PROVIDERS[provider].default_model]


def test_table_cells_of_an_openrouter_row(runner: CliRunner) -> None:
    cells = _table_rows(_models(runner))["google/gemini-3-pro-image"]
    assert cells == [
        "openrouter",
        "google/gemini-3-pro-image",
        "*",
        "google-ai-studio/global",
        "0-14",
        "1:1,2:3,3:2,3:4,4:3,4:5,5:4,9:16,16:9,21:9",
        "1K,2K,4K",
        "no",
        "no",
        "$0.00012/tok out-img + $0.000002/tok in-img",
        "https://ai.google.dev/gemini-api/terms",
        "2026-09-30",
    ]


def test_table_shows_dash_for_no_tiers_and_a_single_price_without_suffix(
    runner: CliRunner,
) -> None:
    cells = _table_rows(_models(runner))["black-forest-labs/flux.2-pro"]
    assert cells[2] == ""  # no default marker: the empty cell keeps its column
    assert cells[6:10] == ["-", "yes", "no", "$0.03/MP"]


def test_table_cells_of_openai_flexible_and_fixed_rows(runner: CliRunner) -> None:
    rows = _table_rows(_models(runner, "--provider", "openai"))
    assert rows["gpt-image-2"][3:10] == [
        "openai", "0-1", "any 1:3..3:1", "WxH /16 ≤3840", "no", "no", "-",
    ]  # fmt: skip
    assert rows["gpt-image-1"][5:7] == ["1:1,3:2,2:3", "1024x1024,1536x1024,1024x1536"]


def test_table_never_truncates_the_longest_aspect_list(runner: CliRunner) -> None:
    longest = max(
        (",".join(r.aspect_ratios) for r in list_models() if r.aspect_ratios), key=len
    )
    assert longest in _models(runner)


def test_table_footer_counts_rows_and_lists_each_providers_policy_urls(
    runner: CliRunner,
) -> None:
    text = _models(runner)
    footer = text.split("\n\n", 1)[1].splitlines()
    assert footer[0] == f"{len(list_models())} model(s)."
    assert footer[1:] == [
        f"{p.value} policy: {url}" for p in AIProvider for url in PROVIDERS[p].policy_urls
    ]


def test_provider_filter_footer_names_only_that_provider(runner: CliRunner) -> None:
    text = _models(runner, "--provider", "openrouter")
    assert {cells[0] for cells in _table_rows(text).values()} == {"openrouter"}
    assert "openai policy:" not in text
    assert f"{len(list_models(AIProvider.OPENROUTER))} model(s)." in text


def test_price_with_a_recorded_openai_max_price(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from holiday_card.core import ai_assets

    priced = replace(ai_assets.MODEL_SIZE_POLICIES["gpt-image-2"], max_price_usd=0.25)
    monkeypatch.setitem(ai_assets.MODEL_SIZE_POLICIES, "gpt-image-2", priced)
    rows = _table_rows(_models(runner, "--provider", "openai"))
    assert rows["gpt-image-2"][9] == "$0.25/image"


# --- json / yaml ----------------------------------------------------------------------


def test_json_validates_against_the_contract_schema(runner: CliRunner) -> None:
    payload = json.loads(_models(runner, "--format", "json"))
    jsonschema.validate(payload, MODELS_JSON_SCHEMA)
    assert payload["schema_version"] == 1


def test_json_equals_the_listing(runner: CliRunner) -> None:
    payload = json.loads(_models(runner, "--format", "json"))
    assert payload == model_listing_payload(list_models())


def test_json_key_order_is_the_documented_order(runner: CliRunner) -> None:
    payload = json.loads(_models(runner, "--format", "json"))
    assert list(payload) == ["schema_version", "models"]
    assert all(list(row) == KEY_ORDER for row in payload["models"])


def test_json_is_indented_with_a_trailing_newline(runner: CliRunner) -> None:
    text = _models(runner, "--format", "json")
    assert text == json.dumps(model_listing_payload(list_models()), indent=2) + "\n"


def test_yaml_is_the_same_payload_as_json(runner: CliRunner) -> None:
    as_yaml = yaml.safe_load(_models(runner, "--format", "yaml"))
    as_json = json.loads(_models(runner, "--format", "json"))
    assert as_yaml == as_json


def test_json_provider_filter(runner: CliRunner) -> None:
    payload = json.loads(_models(runner, "--provider", "openrouter", "--format", "json"))
    assert {row["provider"] for row in payload["models"]} == {"openrouter"}


# --- usage errors, environment ---------------------------------------------------------


@pytest.mark.parametrize("args", [("--provider", "bogus"), ("--format", "xml")])
def test_unknown_choice_is_a_usage_error(runner: CliRunner, args: tuple[str, str]) -> None:
    result = runner.invoke(app, ["ai-asset", "models", *args])
    assert result.exit_code == 2, result.output


def test_provider_env_var_does_not_filter_the_listing(runner: CliRunner) -> None:
    text = _models(runner, env={"HOLIDAY_CARD_AI_PROVIDER": "openrouter"})
    assert {cells[0] for cells in _table_rows(text).values()} == {"openai", "openrouter"}


def test_runs_without_keys_consent_or_network(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The conftest guard already scrubs both keys and blocks non-loopback sockets.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    for fmt in ("table", "json", "yaml"):
        _models(runner, "--format", fmt)
    assert list(tmp_path.iterdir()) == []  # no consent file


def test_loads_no_adapter_no_http_client_and_needs_no_ai_extra() -> None:
    code = (
        "import sys\n"
        "sys.modules['openai'] = None  # the [ai] extra is not installed\n"
        "from typer.testing import CliRunner\n"
        "from holiday_card.cli.commands import app\n"
        "for fmt in ('table', 'json', 'yaml'):\n"
        "    r = CliRunner().invoke(app, ['ai-asset', 'models', '--format', fmt])\n"
        "    assert r.exit_code == 0, r.output\n"
        "bad = [m for m in ('holiday_card.core.ai_openrouter', 'holiday_card.core.ai_openai',\n"
        "                   'urllib.request') if m in sys.modules]\n"
        "assert not bad, bad\n"
        "assert sys.modules['openai'] is None\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=120)


def test_unexpected_error_is_reported_and_exits_1(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_provider: AIProvider | None = None) -> list[ai_providers.ModelListing]:
        raise RuntimeError("table is corrupt")

    monkeypatch.setattr(commands, "list_models", boom)
    result = runner.invoke(app, ["ai-asset", "models"])
    assert result.exit_code == 1
    assert "Error listing AI models: table is corrupt" in _plain(result.output)


# --- help and params -------------------------------------------------------------------


def _models_command() -> Any:
    group = typer.main.get_command(app)
    return group.commands["ai-asset"].commands["models"]  # type: ignore[attr-defined]


def test_options_are_exactly_provider_and_format() -> None:
    cmd = _models_command()
    opts = sorted(opt for param in cmd.params for opt in param.opts)
    assert opts == ["--format", "--provider"]  # no --all, no -o
    assert cmd.get_help_option(cmd.make_context("models", [])).opts == ["--help"]


def test_ai_asset_help_lists_models(runner: CliRunner) -> None:
    result = runner.invoke(app, ["ai-asset", "--help"], env={"COLUMNS": "120"})
    assert result.exit_code == 0
    assert re.search(r"^\W*models\b", _plain(result.output), re.MULTILINE)


def test_models_help_says_no_network_and_never_generator(runner: CliRunner) -> None:
    result = runner.invoke(app, ["ai-asset", "models", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    text = " ".join(_plain(result.output).split())
    assert (
        "Lists the image models this version of holiday-card supports "
        "(a curated, reviewed list). No network." in text
    )
    assert "generator" not in text.lower()


@pytest.mark.parametrize("provider", list(AIProvider))
def test_every_model_generate_accepts_is_listed_and_nothing_else(
    runner: CliRunner, provider: AIProvider, tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        ["ai-asset", "generate", "--subject", "x", "--occasion", "christmas",
         "--provider", provider.value, "--model", "no-such-model", "-o", str(tmp_path / "x.png")],
    )  # fmt: skip
    assert result.exit_code == 2, result.output
    flat = " ".join(_plain(result.output).split())
    known = flat.split("known: ", 1)[1].split(", ")
    payload = json.loads(_models(runner, "--provider", provider.value, "--format", "json"))
    assert sorted(row["id"] for row in payload["models"]) == sorted(known)
