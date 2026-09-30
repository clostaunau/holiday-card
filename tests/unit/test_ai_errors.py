"""The provider-neutral AI error type redacts and sanitises (issue #142).

``ProviderError`` stores only sanitised text, so no code path can carry a
raw provider message (which may echo a key) into output or a traceback.
"""

from __future__ import annotations

import ast
import re
import sys
import traceback
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holiday_card.core.ai_errors import (
    MAX_PROVIDER_TEXT,
    ProviderError,
    parse_retry_after,
    redact,
    sanitize_provider_text,
)

_OR_KEY = "sk-or-v1-" + "0123456789abcdef" * 4
_PROJ_KEY = "sk-proj-" + "A1b2C3d4E5" * 4
_MASKED = "sk-proj-****************************abcd"
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


class TestRedact:
    def test_literal_secret(self) -> None:
        assert redact("key is hunter2hunter2!", secrets=["hunter2hunter2"]) == "key is [REDACTED]!"

    def test_short_literal_is_not_a_secret(self) -> None:
        # Fewer than 8 characters would redact ordinary words.
        assert redact("the cat", secrets=["cat"]) == "the cat"

    @pytest.mark.parametrize("key", [_OR_KEY, _PROJ_KEY, _MASKED])
    def test_key_patterns(self, key: str) -> None:
        out = redact(f"Incorrect API key provided: {key}. See docs.")
        assert key not in out
        assert "[REDACTED]" in out

    def test_openai_masked_form_with_ellipsis(self) -> None:
        # The pattern stops at U+2026, so the masked token itself goes.
        out = redact("Incorrect API key provided: sk-proj-****…abcd")
        assert "sk-proj-****" not in out


class TestSanitize:
    def test_strips_csi_osc_and_c1(self) -> None:
        text = "\x1b[31mred\x1b[0m \x1b]8;;http://x\x07link\x1b]8;;\x07 \x9bcsi"
        out = sanitize_provider_text(text)
        assert "\x1b" not in out
        assert "\x9b" not in out
        assert "\x07" not in out
        assert "red" in out and "link" in out

    def test_keeps_newline_and_tab(self) -> None:
        assert sanitize_provider_text("a\n\tb\x00c") == "a\n\tbc"

    def test_truncates(self) -> None:
        out = sanitize_provider_text("x" * 2000)
        assert len(out) <= MAX_PROVIDER_TEXT + 1
        assert out.endswith("…")

    def test_short_text_is_not_marked_truncated(self) -> None:
        assert sanitize_provider_text("ok") == "ok"

    def test_key_split_by_an_escape_is_still_redacted(self) -> None:
        # Stripping first means the glued-back key is seen by redact().
        split = _PROJ_KEY[:6] + "\x1b[0m" + _PROJ_KEY[6:]
        out = sanitize_provider_text(f"bad key {split}")
        assert _PROJ_KEY not in out
        assert "[REDACTED]" in out

    def test_redacts_before_truncating(self) -> None:
        # A key straddling the cut must not leave a >= 8 char fragment.
        text = "x" * (MAX_PROVIDER_TEXT - 12) + _PROJ_KEY
        out = sanitize_provider_text(text)
        assert _PROJ_KEY[:12] not in out

    @settings(max_examples=200, deadline=None)
    @given(st.text())
    def test_property_no_controls_and_bounded(self, text: str) -> None:
        out = sanitize_provider_text(text)
        assert "\x1b" not in out
        assert not _CONTROLS.search(out)
        assert len(out) <= MAX_PROVIDER_TEXT + 1


class TestProviderError:
    def test_fields(self) -> None:
        e = ProviderError("slow down", kind="transient", status=429, retry_after_s=20.0)
        assert (e.kind, e.status, e.retry_after_s) == ("transient", 429, 20.0)
        assert str(e) == "slow down"
        assert e.args == ("slow down",)

    def test_defaults(self) -> None:
        e = ProviderError("nope", kind="refused")
        assert e.status is None
        assert e.retry_after_s is None

    def test_secret_absent_everywhere(self) -> None:
        key = "sentinel-secret-value-1234"
        msg = f"\x1b[31mIncorrect API key provided: {key} and {_PROJ_KEY}\x1b[0m"
        e = ProviderError(msg, kind="environment", status=401, secrets=[key])
        try:
            raise e
        except ProviderError as caught:
            formatted = "".join(traceback.format_exception(caught))
        for surface in (str(e), repr(e), repr(e.args), formatted):
            assert key not in surface
            assert _PROJ_KEY not in surface
            assert "\x1b" not in surface


class TestParseRetryAfter:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("20", 20.0), (" 3 ", 3.0), ("0", 0.0), ("1.5", 1.5)],
    )
    def test_delta_seconds(self, value: str, expected: float) -> None:
        assert parse_retry_after(value) == expected

    @pytest.mark.parametrize(
        "value", [None, "", "Wed, 21 Oct 2026 07:28:00 GMT", "-5", "soon", "nan", "inf"]
    )
    def test_anything_else_is_none(self, value: str | None) -> None:
        assert parse_retry_after(value) is None


def test_module_imports_only_the_standard_library() -> None:
    import holiday_card.core.ai_errors as mod

    tree = ast.parse(Path(mod.__file__).read_text())
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            names.append(node.module or "")
    assert names
    for name in names:
        top = name.split(".")[0]
        assert top == "__future__" or top in sys.stdlib_module_names, name
