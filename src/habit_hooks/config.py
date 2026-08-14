"""Find, merge and resolve the TOML config across the resolution chain.

What a config *is* — the shape of each section, and the ``ConfigError`` that
refuses anything else — is :mod:`habit_hooks.config_schema` (and, for the
``detectors`` key, :mod:`habit_hooks.detectors`); this module is the loading
around it: the file it reads, the plugin defaults it merges, and the order they
win in.

Loading takes no argument for the running binary's name — a project's own
transformer is a separate process, and importing ``load_config`` is the only way
one has to read ``[scope] branchBase``, so an argument here breaks every caller
outside this repository (#109).
"""

from __future__ import annotations

from pathlib import Path

from .config_schema import (
    PLUGIN_CONFIG_KEYS,
    Config,
    ScopeDefaults,
    SensorOverride,
    SmellOverride,
    read_toml,
    reject_unknown,
    reject_unknown_uncoached_value,
    settable,
)
from .detectors import Detector, reject_invalid_detectors
from .resolve import Resolver


def _build_mapping(cls: type, data: object, section: str) -> dict:
    if not isinstance(data, dict):
        return {}
    result: dict = {}
    for name, value in data.items():
        if not isinstance(value, dict):
            continue
        reject_unknown(settable(cls), value, f"[{section}.{name}]")
        result[name] = cls(**value)
    return result


def _build_config(data: dict) -> Config:
    reject_unknown(settable(Config), data, "the project config")
    known = dict(data)
    if "uncoached" in known:
        reject_unknown_uncoached_value(known["uncoached"])
    if isinstance(known.get("scope"), dict):
        reject_unknown(settable(ScopeDefaults), known["scope"], "[scope]")
        known["scope"] = ScopeDefaults(**known["scope"])
    if "sensors" in known:
        known["sensors"] = _build_mapping(SensorOverride, known["sensors"], "sensors")
    if "smells" in known:
        known["smells"] = _build_mapping(SmellOverride, known["smells"], "smells")
    return Config(**known)


def _read_toml(path: Path) -> dict:
    """The file's contents, or nothing at all if there is no such file."""
    return read_toml(path) if path.is_file() else {}


def _plugin_config_label(plugin: str) -> str:
    """How a refusal names the config it is about: the plugin's, not a path.

    A plugin config is package data or a ``.habit-hooks/<plugin>/`` override, so
    the plugin is what the reader knows it by.
    """
    return f"the {plugin!r} plugin config"


def _plugin_configs(plugins: list[str], project_dir: Path) -> list[dict]:
    """Each active plugin's ``config.toml`` dict, in ``plugins`` order.

    The one read of the plugin-node configs every plugin-supplied root key
    shares: ``files``, ``[runners]`` and ``detectors`` all merge across the
    override chain the resolver walks.
    """
    resolver = Resolver.discover(project_dir)
    configs = []
    for plugin in plugins:
        path = resolver.in_plugin(plugin, "config.toml")
        data = _read_toml(path) if path else {}
        reject_unknown(PLUGIN_CONFIG_KEYS, data, _plugin_config_label(plugin))
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


def _plugin_detectors(plugins: list[str], configs: list[dict]) -> list[Detector]:
    """Every active plugin's declared detectors, in ``plugins`` order.

    Deduplicated by kind and name: two languages may need the same tool, and
    being told to install it twice is being told nothing twice. The first plugin
    to name it decides how it is installed, as it does for a runner. The kind is
    part of the identity because it is the question being asked — a package
    ``node`` can resolve is not answered by a binary of that name on ``PATH``.
    """
    declared: dict[tuple[str, str], Detector] = {}
    for plugin, config in zip(plugins, configs):
        entries = config.get("detectors", [])
        reject_invalid_detectors(entries, _plugin_config_label(plugin))
        for entry in entries:
            detector = Detector(**entry)
            declared.setdefault((detector.kind, detector.name), detector)
    return list(declared.values())


def project_config_path(project_dir: Path) -> Path:
    """Where a project's own config lives when a run does not name one."""
    return project_dir / ".habit-hooks" / "config.toml"


def declared_detectors(plugins: list[str], project_dir: Path) -> list[Detector]:
    """What ``plugins`` need installed, whether or not the project runs them yet.

    ``load_config`` answers this for the plugins a project already names; setting
    a project up asks it of the plugins it is about to switch on, and one answer
    is what keeps a setup's idea of "you have everything" from parting company
    with the run's.
    """
    return _plugin_detectors(plugins, _plugin_configs(plugins, project_dir))


def load_config(project_dir: Path, config_path: Path | None = None) -> Config:
    """Merge the project's ``.habit-hooks/config.toml`` over the plugin defaults.

    ``files`` and ``[runners]`` are the root keys a plugin supplies a default for:
    a project that names no ``files`` inherits what its plugins call source (and
    naming its own replaces them wholesale), and plugin-shipped runners register
    under the project's, which win per extension. ``detectors`` has no project
    half at all — what a plugin needs installed is the plugin's to say.
    """
    path = config_path or project_config_path(project_dir)
    config = _build_config(_read_toml(path))
    plugin_configs = _plugin_configs(config.plugins, project_dir)
    if config.files is None:
        config.files = _plugin_files(plugin_configs) or None
    config.runners = {**_plugin_runners(plugin_configs), **config.runners}
    config.plugin_languages = _plugin_languages(config.plugins, plugin_configs)
    config.plugin_detectors = _plugin_detectors(config.plugins, plugin_configs)
    return config
