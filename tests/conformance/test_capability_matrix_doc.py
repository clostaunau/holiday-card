"""``docs/conformance-matrix.md`` is generated from ``CAPABILITIES`` (#67).

Regenerate with::

    python -m tests.conformance.capabilities > docs/conformance-matrix.md
"""

from __future__ import annotations

from pathlib import Path

from capabilities import CAPABILITIES, Cap, render_markdown

DOC = Path(__file__).resolve().parents[2] / "docs" / "conformance-matrix.md"


def test_doc_matches_generated_matrix() -> None:
    assert DOC.is_file(), f"{DOC} is missing; regenerate it"
    assert DOC.read_text(encoding="utf-8") == render_markdown(CAPABILITIES), (
        "docs/conformance-matrix.md is stale or hand-edited; regenerate with "
        "`python -m tests.conformance.capabilities > docs/conformance-matrix.md`"
    )


def test_render_markdown_lists_each_case_with_owner() -> None:
    md = render_markdown({"x_case": {"pdf": Cap("match"), "png": Cap("known_diff", "#1")}})
    assert "| `x_case` | match | known_diff (#1) |" in md
