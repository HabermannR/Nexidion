"""The running application's version, from pyproject.toml (the single source).

The image copies pyproject.toml to /app, so the file is read in production too;
installed package metadata is only a fallback, because in a development venv it
can lag behind the checkout.
"""
from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@lru_cache(maxsize=1)
def app_version() -> str:
    try:
        with PYPROJECT.open("rb") as handle:
            return tomllib.load(handle)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        pass
    try:
        return version("nexidion-backend")
    except PackageNotFoundError:
        return "unknown"
