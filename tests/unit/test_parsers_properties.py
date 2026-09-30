"""Property tests for the two hand-written parsers (#84).

``SVGPathParser.parse`` and ``parse_markdown`` take author / user text, so
their contract is checked over generated input: well-formed input
round-trips, and arbitrary input either parses or raises ``ValueError``.
"""

from __future__ import annotations

import contextlib
import math

from hypothesis import example, given, settings
from hypothesis import strategies as st

from holiday_card.core.markdown import parse_markdown
from holiday_card.utils.svg_parser import SVGCommand, SVGPathParser

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
