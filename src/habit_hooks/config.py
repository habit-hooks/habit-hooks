"""Load the merged TOML config across the resolution chain.

Unknown keys are rejected at every level — project *and* plugin config — with a
``ConfigError`` (exit 2): a key nothing consumes is a typo or a
documented-but-dead key, and silently ignoring it is why both keep shipping
(#102). The allowed keys are the type's declared attrs fields (minus
loader-populated internals). The rejection names no binary, because all three
console scripts load a config here and one hardcoded name sends the other two's
users to the wrong tool; ``cli.run_console`` names it when it prints it. Loading
takes no argument for that name — a project's own transformer is a separate
process, and importing ``load_config`` is the only way one has to read
``[scope] branchBase``, so an argument here breaks every caller outside this
repository (#109).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from attrs import define, field, fields

from .cli import ConfigError
from .resolve import Resolver


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
    # Each active plugin's declared language (generic declares none). The mapper
    # reads it to prefer, for a finding of a given language, a plugin that speaks
    # it over the languageless fallback. Populated by the loader, never from TOML.
    plugin_languages: dict[str, str] = field(factory=dict, metadata={"internal": True})


# The keys a plugin ``config.toml`` may set: ``sensors``/``transformers``/
# ``language`` read in ``sensors/loader.py``; ``files``/``runners``/``language``
# read by the helpers below. Unlike the project config these are not one attrs
# type, so the allowed set is named here.
_PLUGIN_CONFIG_KEYS = frozenset({"sensors", "transformers", "language", "files", "runners"})


def _settable(cls: type) -> set[str]:
    """The keys a user may set on ``cls``: its attrs fields, minus internals."""
    return {f.name for f in fields(cls) if f.metadata.get("internal") is not True}


def _reject_unknown(allowed: frozenset[str] | set[str], data: dict, where: str) -> None:
    """Fail clearly on any key in ``data`` that ``where`` does not consume."""
    unknown = sorted(key for key in data if key not in allowed)
    if not unknown:
        return
    label = "key" if len(unknown) == 1 else "keys"
    names = ", ".join(repr(key) for key in unknown)
    raise ConfigError(
        f"unknown config {label} {names} in {where}; "
        f"known keys: {', '.join(sorted(allowed))}"
    )


def _build_mapping(cls: type, data: object, section: str) -> dict:
    if not isinstance(data, dict):
        return {}
    result: dict = {}
    for name, value in data.items():
        if not isinstance(value, dict):
            continue
        _reject_unknown(_settable(cls), value, f"[{section}.{name}]")
        result[name] = cls(**value)
    return result


def _build_config(data: dict) -> Config:
    _reject_unknown(_settable(Config), data, "the project config")
    known = dict(data)
    if isinstance(known.get("scope"), dict):
        _reject_unknown(_settable(ScopeDefaults), known["scope"], "[scope]")
        known["scope"] = ScopeDefaults(**known["scope"])
    if "sensors" in known:
        known["sensors"] = _build_mapping(SensorOverride, known["sensors"], "sensors")
    if "smells" in known:
        known["smells"] = _build_mapping(SmellOverride, known["smells"], "smells")
    return Config(**known)


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _plugin_configs(plugins: list[str], project_dir: Path) -> list[dict]:
    """Each active plugin's ``config.toml`` dict, in ``plugins`` order.

    The one read of the plugin-node configs both defaulted root keys share:
    ``files`` and ``[runners]`` are the keys a plugin supplies a default for, and
    both merge across the override chain the resolver walks.
    """
    resolver = Resolver.discover(project_dir)
    configs = []
    for plugin in plugins:
        path = resolver.in_plugin(plugin, "config.toml")
        data = _read_toml(path) if path else {}
        _reject_unknown(_PLUGIN_CONFIG_KEYS, data, f"the {plugin!r} plugin config")
        configs.append(data)
    return configs


def _plugin_files(configs: list[dict]) -> list[str]:
    """Every active plugin's declared source globs, unioned in ``plugins`` order.

    The union rather than the first hit: a project running ``python`` and
    ``typescript`` considers both languages' files source. Order is kept because
    pathspec reads the list in order, so a later pattern can negate an earlier
    one. A plugin that declares no ``files`` (``generic``) is stating no opinion,
    not "everything".
    """
    globs: list[str] = []
    for config in configs:
        globs.extend(glob for glob in config.get("files", []) if glob not in globs)
    return globs


def _plugin_languages(plugins: list[str], configs: list[dict]) -> dict[str, str]:
    """Each plugin's declared ``language``, for the plugins that declare one.

    ``generic`` declares none and is absent from the map; the mapper treats a
    plugin missing here as the languageless fallback (``generic`` last).
    """
    return {
        plugin: config["language"]
        for plugin, config in zip(plugins, configs)
        if isinstance(config.get("language"), str)
    }


def _plugin_runners(configs: list[dict]) -> dict[str, str]:
    """Every active plugin's registered fix runners, first plugin winning a key.

    ``plugins`` order is a priority — as it is for guide lookup — so an earlier
    plugin's runner for an extension wins over a later one's; the project's own
    ``[runners]`` then wins over all of them.
    """
    runners: dict[str, str] = {}
    for config in configs:
        for extension, command in config.get("runners", {}).items():
            runners.setdefault(extension, command)
    return runners


def load_config(project_dir: Path, config_path: Path | None = None) -> Config:
    """Merge the project's ``.habit-hooks/config.toml`` over the plugin defaults.

    ``files`` and ``[runners]`` are the root keys a plugin supplies a default for:
    a project that names no ``files`` inherits what its plugins call source (and
    naming its own replaces them wholesale), and plugin-shipped runners register
    under the project's, which win per extension.
    """
    path = config_path or project_dir / ".habit-hooks" / "config.toml"
    config = _build_config(_read_toml(path))
    plugin_configs = _plugin_configs(config.plugins, project_dir)
    if config.files is None:
        config.files = _plugin_files(plugin_configs) or None
    config.runners = {**_plugin_runners(plugin_configs), **config.runners}
    config.plugin_languages = _plugin_languages(config.plugins, plugin_configs)
    return config
