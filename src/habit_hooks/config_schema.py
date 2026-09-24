
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import define, field, fields

from .catalogue import UNCOACHED_POLICIES, UNCOACHED_SUGGEST
from .cli import ConfigError

if TYPE_CHECKING:
    from .detectors import Detector


@define
class SmellOverride:
    severity: str | None = None
    guide: str | None = None
    disabled: bool | None = None


@define
class ScopeDefaults:
    changedOnly: bool = False
    autoBranchOffMain: bool = False
    branchBase: str = "main"
    mainBranch: str = "main"


@define
class SensorOverride:
    disabled: bool | None = None
    files: list[str] | None = None
    args: list[str] | None = None


@define
class Config:
    requires: str | None = None
    plugins: list[str] = field(factory=lambda: ["generic"])
    transformers: list[str] = field(factory=lambda: ["snooze"])
    files: list[str] | None = None
    uncoached: str = UNCOACHED_SUGGEST
    scope: ScopeDefaults = field(factory=ScopeDefaults)
    sensors: dict[str, SensorOverride] = field(factory=dict)
    runners: dict[str, str] = field(factory=dict)
    smells: dict[str, SmellOverride] = field(factory=dict)
    plugin_languages: dict[str, str] = field(factory=dict, metadata={"internal": True})
    plugin_detectors: list[Detector] = field(factory=list, metadata={"internal": True})


PLUGIN_CONFIG_KEYS = frozenset(
    {"sensors", "transformers", "language", "files", "runners", "detectors"}
)


def read_toml(path: Path) -> dict:
    with path.open("rb") as file:
        try:
            return tomllib.load(file)
        except tomllib.TOMLDecodeError as invalid:
            raise ConfigError(f"{path}: invalid TOML: {invalid}") from None


def settable(cls: type) -> set[str]:
    return {f.name for f in fields(cls) if f.metadata.get("internal") is not True}


def named_keys(keys: list[str]) -> str:
    label = "key" if len(keys) == 1 else "keys"
    return f"{label} {', '.join(repr(key) for key in keys)}"


def reject_unknown(allowed: frozenset[str] | set[str], data: dict, where: str) -> None:
    unknown = sorted(key for key in data if key not in allowed)
    if not unknown:
        return
    raise ConfigError(
        f"unknown config {named_keys(unknown)} in {where}; "
        f"known keys: {', '.join(sorted(allowed))}"
    )


def reject_unknown_uncoached_value(value: object) -> None:
    if value in UNCOACHED_POLICIES:
        return
    known = ", ".join(repr(policy) for policy in sorted(UNCOACHED_POLICIES))
    raise ConfigError(
        f"unknown 'uncoached' value {value!r} in the project config; "
        f"known values: {known}"
    )
