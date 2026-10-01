#!/usr/bin/env python3
"""Compare the curated OpenRouter image allowlist with the live catalogue (#148).

Dev-only; never run in CI. It reads three public, unauthenticated endpoints
(no credentials are read or sent):

* ``GET /api/v1/images/models``
* ``GET /api/v1/images/models/{author}/{slug}/endpoints``
* ``GET /api/v1/providers``

and prints either a Markdown drift table (``--emit table``, the default) or
ready-to-paste ``OpenRouterModel(...)`` literals (``--emit python``). It
never writes under ``src/``: a human reviews the output, edits
``core/ai_openrouter_models.py`` and the snapshot doc, and opens a PR.

``--from-dir DIR`` replays a recording instead of the network;
``--save-dir DIR`` records what was read in that same layout::

    DIR/images_models.json
    DIR/endpoints/<author>__<slug>.json
    DIR/providers.json

Exit codes: 0 = no drift, 1 = drift found (still printed), 2 = usage or
fetch error.

Usage::

    uv run python scripts/refresh_openrouter_models.py --save-dir /tmp/or
    uv run python scripts/refresh_openrouter_models.py --from-dir /tmp/or --emit python
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any

from holiday_card.core.ai_openrouter_models import (
    OPENROUTER_IMAGE_MODELS,
    OpenRouterModel,
    OpenRouterPrice,
)

API = "https://openrouter.ai/api/v1"
TIMEOUT_S = 30
TODO_REVIEW = "TODO-REVIEW"
GONE = "GONE: no endpoint with this provider_tag"
# Reviewed values, carried over from the committed entry and never drift: the
# terms review may replace the catalogue's URL with the page that governs
# output ownership, and the --max-cost bounds come from cited vendor pages,
# not the catalogue (#151).
REVIEWED_FIELDS = (
    "upstream_terms_url",
    "max_output_megapixels",
    "output_image_tokens",
    "input_image_tokens",
    "output_text_tokens",
    "output_text_usd_per_token",
    "bound_source",
)
_NOT_COMPARED = {"snapshot_date", *REVIEWED_FIELDS}


class UsageError(Exception):
    """A bad argument or an unreadable catalogue: exit 2."""


@dataclass(frozen=True)
class FieldDiff:
    model: str
    provider_tag: str
    field: str
    in_code: str
    live: str


def fetch_json(url: str) -> Any:
    """GET ``url`` (https only) and parse it as JSON. No credentials are sent."""
    if not url.startswith("https://"):
        raise ValueError(f"refusing a non-https URL: {url}")
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "holiday-card-refresh"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (https only)
        return json.load(response)


def _endpoint_file(model_id: str) -> str:
    return model_id.replace("/", "__") + ".json"


class Catalogue:
    """The three catalogue documents, from the network or a recording."""

    def __init__(self, from_dir: Path | None, save_dir: Path | None) -> None:
        if from_dir is not None and not from_dir.is_dir():
            raise UsageError(f"--from-dir {from_dir} is not a directory")
        self._from_dir = from_dir
        self._save_dir = save_dir

    def _read(self, rel: str, url: str) -> Any:
        if self._from_dir is not None:
            path = self._from_dir / rel
            if not path.is_file():
                raise UsageError(f"missing recording {path}")
            data = json.loads(path.read_text())
        else:
            try:
                data = fetch_json(url)
            except (OSError, ValueError) as e:
                raise UsageError(f"could not fetch {url}: {e}") from e
        if self._save_dir is not None:
            out = self._save_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(data, indent=2) + "\n")
        return data

    def models(self) -> list[dict[str, Any]]:
        return list(self._read("images_models.json", f"{API}/images/models")["data"])

    def providers(self) -> list[dict[str, Any]]:
        return list(self._read("providers.json", f"{API}/providers")["data"])

    def endpoints(self, model_id: str) -> list[dict[str, Any]]:
        rel = f"endpoints/{_endpoint_file(model_id)}"
        return list(self._read(rel, f"{API}/images/models/{model_id}/endpoints")["endpoints"])


def _enum(params: dict[str, Any], name: str) -> tuple[str, ...]:
    spec = params.get(name)
    return tuple(spec["values"]) if spec else ()


def _entry_fields(
    model: dict[str, Any],
    endpoint: dict[str, Any],
    providers: Sequence[dict[str, Any]],
    *,
    snapshot_date: str,
) -> dict[str, Any]:
    params = endpoint["supported_parameters"]
    refs = params.get("input_references", {"min": 0, "max": 0})
    tag = endpoint["provider_tag"]
    base_slug = tag.split("/", 1)[0]
    terms = next((p["terms_of_service_url"] for p in providers if p["slug"] == base_slug), None)
    return {
        "id": model["id"],
        "provider_tag": tag,
        "aspect_ratios": tuple(r for r in _enum(params, "aspect_ratio") if r != "auto"),
        "resolutions": _enum(params, "resolution"),
        "input_refs_min": int(refs["min"]),
        "input_refs_max": int(refs["max"]),
        "seed": "seed" in params,
        "output_formats": _enum(params, "output_format"),
        "background_transparent": "transparent" in _enum(params, "background"),
        "passthrough": tuple(endpoint.get("allowed_passthrough_parameters") or ()),
        "pricing": tuple(
            OpenRouterPrice(row["billable"], row["unit"], float(row["cost_usd"]))
            for row in endpoint["pricing"]
        ),
        "upstream_terms_url": terms or TODO_REVIEW,
        "snapshot_date": snapshot_date,
    }


def entry_from_catalogue(
    model: dict[str, Any],
    endpoint: dict[str, Any],
    providers: list[dict[str, Any]],
    *,
    snapshot_date: str,
) -> OpenRouterModel:
    """The allowlist entry the catalogue describes for one endpoint.

    ``upstream_terms_url`` is the ``/providers`` ``terms_of_service_url`` of
    the tag's base slug; a null one raises (the entry needs a terms review).
    """
    return OpenRouterModel(**_entry_fields(model, endpoint, providers, snapshot_date=snapshot_date))


def carry_reviewed(current: OpenRouterModel, live_resolutions: tuple[str, ...]) -> dict[str, Any]:
    """The :data:`REVIEWED_FIELDS` of ``current``, kept for a live entry.

    A token bound for a tier the endpoint no longer offers is dropped (the
    ``resolutions`` row reports that drift); with no bound left, so is the
    source.
    """
    kept = {f: getattr(current, f) for f in REVIEWED_FIELDS}
    tokens = current.output_image_tokens
    if tokens is not None:
        allowed = set(live_resolutions) or {"default"}
        trimmed = {k: v for k, v in tokens.items() if k in allowed}
        kept["output_image_tokens"] = MappingProxyType(trimmed) if trimmed else None
    bounds = (
        "max_output_megapixels", "output_image_tokens", "input_image_tokens", "output_text_tokens"
    )
    if all(kept[b] is None for b in bounds):
        kept["bound_source"] = None
    return kept


def _fmt(value: Any) -> str:
    if isinstance(value, tuple):
        return "; ".join(_fmt(v) for v in value) if any(
            isinstance(v, OpenRouterPrice) for v in value
        ) else " ".join(_fmt(v) for v in value)
    if isinstance(value, OpenRouterPrice):
        return f"{value.billable}/{value.unit}/{value.cost_usd:g}"
    return str(value)


def diff_entry(current: OpenRouterModel, live: OpenRouterModel | None) -> list[FieldDiff]:
    """The fields of ``current`` the live endpoint no longer matches.

    ``live is None`` (the pinned endpoint is gone) is one ``endpoint`` row.
    ``snapshot_date`` and the :data:`REVIEWED_FIELDS` are not compared.
    """
    if live is None:
        return [FieldDiff(current.id, current.provider_tag, "endpoint", "pinned", GONE)]
    return [
        FieldDiff(current.id, current.provider_tag, f.name, _fmt(old), _fmt(new))
        for f in fields(OpenRouterModel)
        if f.name not in _NOT_COMPARED
        and (old := getattr(current, f.name)) != (new := getattr(live, f.name))
    ]


def render_table(
    diffs: Sequence[FieldDiff],
    *,
    fetched: str,
    snapshot: str,
    curated: int,
    uncurated: int,
) -> str:
    """The Markdown drift report for a review PR."""
    lines = [
        f"# OpenRouter image allowlist drift: fetched {fetched} (entries snapshot {snapshot})",
        "",
        "| model | provider_tag | field | in code | live |",
        "|---|---|---|---|---|",
        *(f"| {d.model} | {d.provider_tag} | {d.field} | {d.in_code} | {d.live} |" for d in diffs),
        "",
        f"{len(diffs)} differences in {curated} curated models. "
        f"{uncurated} catalogue models are not curated (use --add ID to render one).",
    ]
    return "\n".join(lines) + "\n"


def _py(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, OpenRouterPrice):
        return f"OpenRouterPrice({_py(value.billable)}, {_py(value.unit)}, {value.cost_usd!r})"
    if isinstance(value, MappingProxyType):
        return "MappingProxyType({" + ", ".join(
            f"{_py(k)}: {_py(v)}" for k, v in value.items()
        ) + "})"
    if isinstance(value, tuple):
        if len(value) == 1:
            return f"({_py(value[0])},)"
        return "(" + ", ".join(_py(v) for v in value) + ")"
    return repr(value)


def render_python(entries: Sequence[dict[str, Any]]) -> str:
    """One ready-to-paste ``OpenRouterModel(...)`` literal per field mapping."""
    blocks = []
    for entry in entries:
        body = "".join(f"    {name}={_py(entry[name])},\n" for name in entry)
        blocks.append(f"OpenRouterModel(\n{body}),\n")
    return "\n".join(blocks)


def _select(
    catalogue: Catalogue, spec: str, known_ids: set[str]
) -> tuple[str, dict[str, Any]]:
    model_id, _, tag = spec.partition("@")
    if model_id not in known_ids:
        raise UsageError(f"--add {spec}: {model_id!r} is not in the image catalogue")
    endpoints = catalogue.endpoints(model_id)
    tags = [e["provider_tag"] for e in endpoints]
    if tag:
        match = [e for e in endpoints if e["provider_tag"] == tag]
        if not match:
            raise UsageError(f"--add {spec}: no endpoint tagged {tag!r}; available: {', '.join(tags)}")
        return model_id, match[0]
    if len(endpoints) != 1:
        raise UsageError(
            f"--add {spec}: {len(endpoints)} endpoints; pick one with "
            f"{model_id}@TAG from: {', '.join(tags) or '(none)'}"
        )
    return model_id, endpoints[0]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--from-dir", type=Path, help="replay a recording instead of the network")
    parser.add_argument("--save-dir", type=Path, help="record what was read in the --from-dir layout")
    parser.add_argument(
        "--add",
        action="append",
        default=[],
        metavar="MODEL_ID[@PROVIDER_TAG]",
        help="also render an uncurated model (its endpoint must be unambiguous)",
    )
    parser.add_argument("--emit", choices=("table", "python"), default="table")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    today = date.today().isoformat()
    try:
        catalogue = Catalogue(args.from_dir, args.save_dir)
        models = {m["id"]: m for m in catalogue.models()}
        providers = catalogue.providers()
        added = [_select(catalogue, spec, set(models)) for spec in args.add]

        diffs: list[FieldDiff] = []
        emitted: list[dict[str, Any]] = []
        gone: list[str] = []
        for current in OPENROUTER_IMAGE_MODELS.values():
            endpoint = None
            if current.id in models:
                endpoint = next(
                    (e for e in catalogue.endpoints(current.id)
                     if e["provider_tag"] == current.provider_tag),
                    None,
                )  # fmt: skip
            if endpoint is None:
                diffs += diff_entry(current, None)
                gone.append(current.id)
                continue
            live = _entry_fields(models[current.id], endpoint, providers, snapshot_date=today)
            live |= carry_reviewed(current, live["resolutions"])
            diffs += diff_entry(current, OpenRouterModel(**live))
            emitted.append(live)
        for model_id, endpoint in added:
            live = _entry_fields(models[model_id], endpoint, providers, snapshot_date=today)
            diffs.append(FieldDiff(model_id, endpoint["provider_tag"], "entry", "—", "new: not curated"))
            emitted.append(live)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.emit == "python":
        for model_id in gone:
            print(f"# {model_id}: {GONE}")
        print(render_python(emitted), end="")
    else:
        snapshot = ", ".join(sorted({e.snapshot_date for e in OPENROUTER_IMAGE_MODELS.values()}))
        print(
            render_table(
                diffs,
                fetched=today,
                snapshot=snapshot,
                curated=len(OPENROUTER_IMAGE_MODELS),
                uncurated=len(set(models) - set(OPENROUTER_IMAGE_MODELS)),
            ),
            end="",
        )
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
