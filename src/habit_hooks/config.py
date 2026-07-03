"""Load the merged TOML config across the resolution chain.

Unknown keys are ignored at every level: each raw dict is filtered to the
type's declared attrs fields before construction.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from attrs import define, field, fields


@define
class SmellOverride:
    severity: str | None = None
    guide: str | None = None
    disabled: bool | None = None
    title: str | None = None


@define
class ScopeDefaults:
    changedOnly: bool = False
    autoBranchOffMain: bool = False
    branchBase: str = "main"
    mainBranch: str = "main"


@define
class SensorOverride:
    disabled: bool | None = None
    command: str | None = None
    language: str | None = None
    files: list[str] | None = None
    args: list[str] | None = None


@define
class Config:
    plugins: list[str] = field(factory=lambda: ["generic"])
    transformers: list[str] = field(factory=list)
    files: list[str] | None = None
    scope: ScopeDefaults = field(factory=ScopeDefaults)
    sensors: dict[str, SensorOverride] = field(factory=dict)
    runners: dict[str, str] = field(factory=dict)
    smells: dict[str, SmellOverride] = field(factory=dict)


def _known(cls: type, data: dict) -> dict:
    names = {f.name for f in fields(cls)}
    return {key: value for key, value in data.items() if key in names}


def _build_mapping(cls: type, data: object) -> dict:
    if not isinstance(data, dict):
        return {}
    return {key: cls(**_known(cls, value)) for key, value in data.items() if isinstance(value, dict)}


def _build_config(data: dict) -> Config:
    known = _known(Config, data)
    if isinstance(known.get("scope"), dict):
        known["scope"] = ScopeDefaults(**_known(ScopeDefaults, known["scope"]))
    if "sensors" in known:
        known["sensors"] = _build_mapping(SensorOverride, known["sensors"])
    if "smells" in known:
        known["smells"] = _build_mapping(SmellOverride, known["smells"])
    return Config(**known)


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def load_config(project_dir: Path, config_path: Path | None = None) -> Config:
    """Merge the project's ``.habit-hooks/config.toml`` over plugin defaults."""
    path = config_path or project_dir / ".habit-hooks" / "config.toml"
    return _build_config(_read_toml(path))
