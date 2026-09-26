"""Resolve the bundled data directories shipped inside the package.

Templates, themes, sentiments, fonts and the CMYK ICC profile live under
``holiday_card/data/`` and ship in the wheel as plain package data. This
module is the single place that locates them (spec §P1, decision D1):

* ``templates``, ``themes`` and ``sentiments`` honor an env-var override
  (``HOLIDAY_CARD_TEMPLATES`` etc.) that **replaces** the bundled
  directory. An override that isn't an existing directory is an error.
* Otherwise the directory is resolved via ``importlib.resources``.

There is deliberately no walking up from the module path and no
current-working-directory fallback: a broken install fails loud instead of
silently finding nothing.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path
from typing import Final, Literal

__all__ = ["ENV_OVERRIDES", "DataKind", "DataPathError", "data_path"]

DataKind = Literal["templates", "themes", "sentiments", "fonts", "icc"]

ENV_OVERRIDES: Final[Mapping[DataKind, str]] = {
    "templates": "HOLIDAY_CARD_TEMPLATES",
    "themes": "HOLIDAY_CARD_THEMES",
    "sentiments": "HOLIDAY_CARD_SENTIMENTS",
}


class DataPathError(FileNotFoundError):
    """Raised when a bundled or overridden data directory is unavailable."""


def data_path(kind: DataKind) -> Path:
    """Return the directory holding the bundled data of ``kind``.

    Raises:
        DataPathError: the env override names a non-directory, or the
            bundled directory isn't on the real filesystem (e.g. a zipped
            install).
    """
    env_var = ENV_OVERRIDES.get(kind)
    override = os.environ.get(env_var) if env_var else None
    if override:
        path = Path(override).expanduser()
        if not path.is_dir():
            raise DataPathError(
                f"{env_var}={override!r} does not point to an existing "
                f"directory: {path}"
            )
        return path

    path = Path(str(files("holiday_card") / "data" / kind))
    if not path.is_dir():
        raise DataPathError(
            f"Bundled {kind} data directory not found at {path}; the "
            "installation is missing bundled data (zipped installs are "
            "not supported)."
        )
    return path
