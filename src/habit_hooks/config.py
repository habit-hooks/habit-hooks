
from __future__ import annotations

from pathlib import Path
from importlib.metadata import version

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from .cli import ConfigError

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
    return read_toml(path) if path.is_file() else {}


def _plugin_config_label(plugin: str) -> str:
    return f"the {plugin!r} plugin config"


def _plugin_configs(plugins: list[str], project_dir: Path) -> list[dict]:
    resolver = Resolver.discover(project_dir)
    configs = []
    for plugin in plugins:
        path = resolver.in_plugin(plugin, "config.toml")
        data = _read_toml(path) if path else {}
        reject_unknown(PLUGIN_CONFIG_KEYS, data, _plugin_config_label(plugin))
        configs.append(data)
    return configs


def _plugin_files(configs: list[dict]) -> list[str]:
    positive: list[str] = []
    excluded: list[str] = []
    for config in configs:
        for glob in config.get("files", []):
            kind = excluded if glob.startswith("!") else positive
            if glob not in kind:
                kind.append(glob)
    return positive + excluded


def _plugin_languages(plugins: list[str], configs: list[dict]) -> dict[str, str]:
    return {
        plugin: config["language"]
        for plugin, config in zip(plugins, configs)
        if isinstance(config.get("language"), str)
    }


def _plugin_runners(configs: list[dict]) -> dict[str, str]:
    runners: dict[str, str] = {}
    for config in configs:
        for extension, command in config.get("runners", {}).items():
            runners.setdefault(extension, command)
    return runners


def _plugin_detectors(plugins: list[str], configs: list[dict]) -> list[Detector]:
    declared: dict[tuple[str, str], Detector] = {}
    for plugin, config in zip(plugins, configs):
        entries = config.get("detectors", [])
        reject_invalid_detectors(entries, _plugin_config_label(plugin))
        for entry in entries:
            detector = Detector(**entry)
            declared.setdefault((detector.kind, detector.name), detector)
    return list(declared.values())


def project_config_path(project_dir: Path) -> Path:
    return project_dir / ".habit-hooks" / "config.toml"


def declared_detectors(plugins: list[str], project_dir: Path) -> list[Detector]:
    return _plugin_detectors(plugins, _plugin_configs(plugins, project_dir))


def _validate_requires(requirement: str | None) -> None:
    if requirement is None:
        return
    if not isinstance(requirement, str):
        raise ConfigError("'requires' in the project config must be a version requirement string")
    try:
        required = SpecifierSet(requirement)
    except InvalidSpecifier:
        raise ConfigError(f"invalid 'requires' version requirement {requirement!r}") from None
    running = Version(version("habit-hooks"))
    if running not in required:
        raise ConfigError(f"project requires habit-hooks {requirement}, but running version is {running}")


def load_config(project_dir: Path, config_path: Path | None = None) -> Config:
    path = config_path or project_config_path(project_dir)
    config = _build_config(_read_toml(path))
    _validate_requires(config.requires)
    plugin_configs = _plugin_configs(config.plugins, project_dir)
    if config.files is None:
        config.files = _plugin_files(plugin_configs) or None
    config.runners = {**_plugin_runners(plugin_configs), **config.runners}
    config.plugin_languages = _plugin_languages(config.plugins, plugin_configs)
    config.plugin_detectors = _plugin_detectors(config.plugins, plugin_configs)
    return config
