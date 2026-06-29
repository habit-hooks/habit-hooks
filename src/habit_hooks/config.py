"""Load and validate the merged TOML config across the resolution chain."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SmellOverride(BaseModel):
    model_config = ConfigDict(extra="allow")

    severity: str | None = None
    guide: str | None = None
    disabled: bool | None = None
    title: str | None = None


class Config(BaseModel):
    model_config = ConfigDict(extra="allow")

    plugins: list[str] = ["generic"]
    runners: dict[str, str] = {}
    smells: dict[str, SmellOverride] = {}


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def load_config(project_dir: Path) -> Config:
    """Merge the project's ``.habit-hooks/config.toml`` over plugin defaults."""
    merged = _read_toml(project_dir / ".habit-hooks" / "config.toml")
    return Config(**merged)
