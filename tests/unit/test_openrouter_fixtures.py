"""The committed OpenRouter fixtures are small, well-formed and reproducible (#149)."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from openrouter_fixtures import FIXTURES_DIR, GOLDEN_REQUEST, fixture_raw, response_fixture_names

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "make_openrouter_fixtures.py"

EXPECTED = {
    "ok_png", "ok_jpeg", "ok_webp", "two_images", "empty_data", "svg", "mime_mismatch",
    "bad_base64", "remote_url", "bomb_png", "not_json", "err_400", "err_401", "err_402",
    "err_402_in_flight", "err_403_policy", "err_403_refusal", "err_403_permission",
    "err_429", "err_502", "err_524", "err_200_envelope",
}  # fmt: skip


def _top_level_files() -> list[Path]:
    return sorted(p for p in FIXTURES_DIR.iterdir() if p.is_file())


def test_every_fixture_the_issue_lists_is_committed() -> None:
    assert set(response_fixture_names()) == EXPECTED
    assert (FIXTURES_DIR / GOLDEN_REQUEST).is_file()
    assert (FIXTURES_DIR / "reference_8x8.png").is_file()


@pytest.mark.parametrize("path", _top_level_files(), ids=lambda p: p.name)
def test_fixture_is_at_most_2_kib(path: Path) -> None:
    assert path.stat().st_size <= 2048


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_response_fixture_has_the_envelope_shape(name: str) -> None:
    raw = fixture_raw(name)
    assert isinstance(raw["status"], int)
    assert all(k == k.lower() and isinstance(v, str) for k, v in raw["headers"].items())
    assert ("body" in raw) != ("body_text" in raw)
    assert set(raw) <= {"status", "headers", "body", "body_text"}


def test_generator_reproduces_the_committed_image_fixtures(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path)], check=True, timeout=120)
    written = sorted(p.name for p in tmp_path.iterdir())
    assert {"reference_8x8.png", GOLDEN_REQUEST, "ok_png.json", "bomb_png.json"} <= set(written)
    for name in written:
        assert (tmp_path / name).read_bytes() == (FIXTURES_DIR / name).read_bytes(), name


def test_bomb_png_declares_20000_by_20000() -> None:
    import base64

    data = base64.b64decode(fixture_raw("bomb_png")["body"]["data"][0]["b64_json"])
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    length, tag = struct.unpack(">I4s", data[8:16])
    assert (length, tag) == (13, b"IHDR")
    assert struct.unpack(">II", data[16:24]) == (20000, 20000)


def test_golden_request_embeds_the_reference_png() -> None:
    import base64

    golden = json.loads((FIXTURES_DIR / GOLDEN_REQUEST).read_text(encoding="utf-8"))
    url = golden["input_references"][0]["image_url"]["url"]
    prefix = "data:image/png;base64,"
    assert url.startswith(prefix)
    assert base64.b64decode(url[len(prefix) :]) == (FIXTURES_DIR / "reference_8x8.png").read_bytes()
