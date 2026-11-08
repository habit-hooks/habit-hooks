
from __future__ import annotations

from pathlib import Path

from attrs import frozen

from . import git_listing
from .config import declared_detectors, load_config, project_config_path
from .config_schema import Config
from .detectors import Detector
from .missing_tools import missing_tools
from .plugin_install import install_commands
from .recommend import used_languages
from .resolve import Resolver



LANGUAGE_AGNOSTIC_PLUGIN = "generic"


@frozen
class Plan:
    languages: tuple[str, ...]
    plugins: tuple[str, ...]
    already_configured: bool
    missing_tools: tuple[Detector, ...]
    uninstalled_plugins: tuple[str, ...]
    plugin_installs: tuple[str, ...]

    @property
    def needs_a_new_plugin(self) -> bool:
        beyond_the_languageless = set(self.plugins) - {LANGUAGE_AGNOSTIC_PLUGIN}
        return not self.languages and not beyond_the_languageless

    @property
    def installs(self) -> tuple[str, ...]:
        return (
            *self.plugin_installs,
            *(detector.install for detector in self.missing_tools),
        )


def plan(project_dir: Path) -> Plan:
    files = git_listing.project_files(project_dir)
    languages = tuple(used_languages(project_dir, files))
    config = _project_config(project_dir)
    plugins = _plugins(languages, config)
    declared = _declared_tools(plugins, project_dir, config)
    missing = missing_tools(declared, project_dir)
    resolver = Resolver.discover(project_dir)
    uninstalled = _uninstalled_plugins(plugins, resolver)
    return Plan(
        languages,
        plugins,
        config is not None,
        missing,
        uninstalled,
        install_commands(_packaged_plugins(plugins, resolver), uninstalled),
    )


def _uninstalled_plugins(
    plugins: tuple[str, ...], resolver: Resolver
) -> tuple[str, ...]:
    return tuple(plugin for plugin in plugins if not resolver.has_plugin(plugin))


def _packaged_plugins(
    plugins: tuple[str, ...], resolver: Resolver
) -> tuple[str, ...]:
    installed = tuple(resolver.package_dirs)
    return (*installed, *_uninstalled_plugins(plugins, resolver))


def _project_config(project_dir: Path) -> Config | None:
    if not project_config_path(project_dir).is_file():
        return None
    return load_config(project_dir)


def _plugins(languages: tuple[str, ...], config: Config | None) -> tuple[str, ...]:
    if config is not None:
        return tuple(config.plugins)
    return (*languages, LANGUAGE_AGNOSTIC_PLUGIN)


def _declared_tools(
    plugins: tuple[str, ...], project_dir: Path, config: Config | None
) -> list[Detector]:
    if config is not None:
        return config.plugin_detectors
    return declared_detectors(list(plugins), project_dir)
