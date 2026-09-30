"""Property tests for the hand-written parsers (#84, #149).

``SVGPathParser.parse`` and ``parse_markdown`` take author / user text, so
their contract is checked over generated input: well-formed input
round-trips, and arbitrary input either parses or raises ``ValueError``.
``parse_images_response`` takes an untrusted HTTP response: it returns a
``GeneratedImage`` or raises ``ProviderError``, and nothing else.
"""

from __future__ import annotations

import base64
import contextlib
import functools
import json
import math
from collections.abc import Callable
from typing import Any

from hypothesis import example, given, settings
from hypothesis import strategies as st

from holiday_card.core.ai_assets import GeneratedImage
from holiday_card.core.ai_errors import ProviderError
from holiday_card.core.ai_openrouter import HttpResponse, parse_images_response
from holiday_card.core.ai_openrouter_models import OPENROUTER_IMAGE_MODELS
from holiday_card.core.markdown import parse_markdown
from holiday_card.utils.svg_parser import SVGCommand, SVGPathParser
from openrouter_fixtures import load_response, response_fixture_names

_SETTINGS = settings(max_examples=200, deadline=None)

# Parameter count per command letter; arcs are outside the generated set.
_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "Z": 0}

_coord = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6)


@st.composite
def _command(draw: st.DrawFn) -> tuple[str, list[float]]:
    letter = draw(st.sampled_from(sorted(_ARITY)))
    if draw(st.booleans()):
        letter = letter.lower()
    params = draw(st.lists(_coord, min_size=_ARITY[letter.upper()], max_size=_ARITY[letter.upper()]))
    return letter, params


def _render(commands: list[tuple[str, list[float]]], sep: str) -> str:
    return " ".join(
        letter + ("" if not params else " " + sep.join(repr(p) for p in params))
        for letter, params in commands
    )


class TestSVGPathParser:
    @_SETTINGS
    @given(
        st.lists(_command(), min_size=1, max_size=12),
        st.sampled_from([" ", ",", ", "]),
    )
    def test_well_formed_paths_round_trip(
        self, commands: list[tuple[str, list[float]]], sep: str
    ) -> None:
        parsed = SVGPathParser().parse(_render(commands, sep))

        assert len(parsed) == len(commands)
        for got, (letter, params) in zip(parsed, commands, strict=True):
            assert got.command == SVGCommand(letter)
            assert len(got.params) == len(params)
            for a, b in zip(got.params, params, strict=True):
                assert math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)

    @_SETTINGS
    @given(st.text())
    def test_arbitrary_text_parses_or_raises_value_error(self, source: str) -> None:
        with contextlib.suppress(ValueError):
            SVGPathParser().parse(source)

    @_SETTINGS
    @given(st.text(alphabet="MmLlHhVvCcSsQqTtAaZz0123456789.-+eE, \n"))
    @example("Z0")  # was ZeroDivisionError: Z has no parameters (found by this test)
    def test_path_alphabet_parses_or_raises_value_error(self, source: str) -> None:
        with contextlib.suppress(ValueError):
            SVGPathParser().parse(source)


# A line with no Markdown markers, no newline and some visible text.
_plain_line = st.text(
    alphabet=st.characters(blacklist_characters="*_\n", blacklist_categories=("Cs",)),
    min_size=1,
).filter(lambda s: s.strip() != "")


class TestParseMarkdown:
    @_SETTINGS
    @given(st.lists(_plain_line, min_size=1, max_size=8))
    def test_plain_lines_round_trip_as_unstyled_runs(self, lines: list[str]) -> None:
        doc = parse_markdown("\n".join(lines))

        hard_lines = [line for p in doc.paragraphs for line in p.hard_lines]
        assert ["".join(run.text for run in line) for line in hard_lines] == [
            line.strip() for line in lines
        ]
        assert not any(run.bold or run.italic for line in hard_lines for run in line)

    @_SETTINGS
    @given(st.text())
    def test_arbitrary_text_parses_or_raises_value_error(self, source: str) -> None:
        with contextlib.suppress(ValueError):
            parse_markdown(source)

    @_SETTINGS
    @given(st.text(alphabet="*_ ab\n"))
    def test_marker_soup_parses_or_raises_value_error(self, source: str) -> None:
        with contextlib.suppress(ValueError):
            parse_markdown(source)

    @_SETTINGS
    @given(_plain_line.map(str.strip))
    def test_triple_star_is_one_bold_italic_run(self, inner: str) -> None:
        doc = parse_markdown(f"***{inner}***")

        [paragraph] = doc.paragraphs
        [line] = paragraph.hard_lines
        [run] = line
        assert run.text == inner
        assert run.bold and run.italic


_json_scalar = st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=20)
_json = st.recursive(
    _json_scalar,
    lambda inner: (
        st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=8), inner, max_size=4)
    ),
    max_leaves=12,
)
_b64ish = st.one_of(
    st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=", max_size=64
    ),
    st.binary(max_size=48).map(lambda b: base64.b64encode(b).decode()),
    st.sampled_from(["iVBORw0KGgo=", "/9j/4AAQ", "UklGRgAAAABXRUJQ", "https://x/y.png", "data:,"]),
    st.text(max_size=16),
)
_datum = st.fixed_dictionaries(
    {},
    optional={
        "b64_json": _b64ish | st.none(),
        "url": st.text(max_size=16) | st.none(),
        "media_type": st.sampled_from(["image/png", "image/jpeg", "image/webp", "image/svg+xml"])
        | st.text(max_size=12),
    },
)
_error = st.fixed_dictionaries(
    {"code": st.integers(0, 999) | st.none(), "message": st.text(max_size=40)},
    optional={
        "metadata": st.fixed_dictionaries(
            {},
            optional={
                "error_type": st.sampled_from(["refusal", "content_policy_violation"])
                | st.text(max_size=12),
                "limit_source": st.sampled_from(["openrouter_in_flight_budget"])
                | st.text(max_size=12),
                "reasons": st.lists(st.text(max_size=12), max_size=3),
                "remedy_hint": st.text(max_size=12),
                "provider_code": st.integers() | st.text(max_size=8),
            },
        )
        | _json
    },
)
_envelope = st.fixed_dictionaries(
    {},
    optional={
        "data": st.lists(_datum, max_size=3) | _json,
        "error": _error | _json,
        "usage": st.fixed_dictionaries({}, optional={"cost": _json_scalar}) | _json,
        "created": _json_scalar,
    },
)
_body = st.one_of(
    st.binary(max_size=2048),
    _json.map(lambda v: json.dumps(v).encode()),
    _envelope.map(lambda v: json.dumps(v).encode()),
)
_headers = st.dictionaries(
    st.sampled_from(["content-type", "retry-after", "x-generation-id"]),
    st.text(max_size=40) | st.sampled_from(["application/json", "application/json; charset=utf-8"]),
    max_size=3,
)
_responses = st.builds(
    HttpResponse,
    status=st.integers(100, 599) | st.sampled_from([200, 200, 200]),
    headers=_headers,
    body=_body,
)
_ENTRY = OPENROUTER_IMAGE_MODELS["google/gemini-3-pro-image"]


def _with_fixture_examples(test: Callable[..., None]) -> Callable[..., None]:
    return functools.reduce(
        lambda t, name: example(load_response(name))(t), response_fixture_names(), test
    )


class TestOpenRouterResponseParser:
    @_SETTINGS
    @_with_fixture_examples
    @given(_responses)
    def test_returns_an_image_or_raises_provider_error(self, response: HttpResponse) -> None:
        try:
            result: Any = parse_images_response(response, entry=_ENTRY, redact=lambda t: t)
        except ProviderError as e:
            assert e.kind in {"refused", "environment", "usage", "transient"}
            return
        assert isinstance(result, GeneratedImage)
        assert result.provider_route == _ENTRY.provider_tag
