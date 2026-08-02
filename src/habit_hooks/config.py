"""Load the merged TOML config across the resolution chain.

Unknown keys are ignored at every level: each raw dict is filtered to the
type's declared attrs fields before construction.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from attrs import define, field, fields

from .resolve import Resolver


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
    # Snooze is on by default so a checked-in index takes effect without wiring;
    # naming `transformers` replaces the list wholesale, which is how a project
    # drops it or orders it against its own steps.
    transformers: list[str] = field(factory=lambda: ["snooze"])
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


def _plugin_files(plugins: list[str], project_dir: Path) -> list[str]:
    """Every active plugin's declared source globs, in ``plugins`` order.

    The union rather than the first hit: a project running ``python`` and
    ``typescript`` considers both languages' files source. Order is kept because
    pathspec reads the list in order, so a later pattern can negate an earlier
    one. A plugin that declares no ``files`` (``generic``) is stating no opinion,
    not "everything".
    """
    resolver = Resolver.discover(project_dir)
    globs: list[str] = []
    for plugin in plugins:
        path = resolver.in_plugin(plugin, "config.toml")
        declared = _read_toml(path).get("files", []) if path else []
        globs.extend(glob for glob in declared if glob not in globs)
    return globs


def load_config(project_dir: Path, config_path: Path | None = None) -> Config:
    """Merge the project's ``.habit-hooks/config.toml`` over the plugin defaults.

    ``files`` is the one root key a plugin supplies a default for: a project that
    names none inherits what its plugins call source, and a project that names
    its own replaces them wholesale — its answer is the authoritative one.
    """
    path = config_path or project_dir / ".habit-hooks" / "config.toml"
    config = _build_config(_read_toml(path))
    if config.files is None:
        config.files = _plugin_files(config.plugins, project_dir) or None
    return config
