"""A closed stdout pipe is a quiet, successful exit (issue #92).

``holiday-card themes | grep -q christmas`` closes the pipe as soon as
grep matches. The CLI must not report that as ``Error listing themes``
and exit 1 — under ``set -o pipefail`` that fails the whole pipeline.

The subprocess gets a pipe whose read end is already closed, so every
write raises EPIPE deterministically instead of racing the reader.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _run_with_closed_stdout(*args: str) -> subprocess.CompletedProcess[bytes]:
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    try:
        return subprocess.run(
            [sys.executable, "-m", "holiday_card", *args],
            stdout=write_fd,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    finally:
        os.close(write_fd)


@pytest.mark.parametrize(
    "args",
    [
        ("templates",),
        ("templates", "--format", "json"),
        ("themes",),
        ("--version",),
    ],
    ids=lambda a: " ".join(a),
)
def test_closed_stdout_exits_zero_silently(args: tuple[str, ...]) -> None:
    result = _run_with_closed_stdout(*args)
    assert result.stderr.decode() == ""
    assert result.returncode == 0
