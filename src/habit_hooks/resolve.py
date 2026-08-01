"""Resolve plugin files across the override chain.

A plugin's files are looked up project-override
(``.habit-hooks/<plugin>/``) before package default (the plugin's installed
package data). Plugins are installed packages, discovered at runtime through the
``habit_hooks.plugins`` entry-point group; the configured ``plugins`` list
selects and orders them. Plugins are walked in the configured order, so an
earlier plugin's guide wins over a later one's.

A plugin that a project configures but neither overrides under ``.habit-hooks/``
nor installs as a package raises a clear error naming it and its install command.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib.metadata import entry_points
from importlib.resources import files
from pathlib import Path

PLUGIN_ENTRY_POINT_GROUP = "habit_hooks.plugins"

# The core ships baseline guides (clean.md, uncoached.md) as the final fallback, so
# the mapper still coaches and never crashes when no configured plugin supplies them
# (for example a project that drops the generic plugin).
CORE_GUIDES = Path(__file__).parent / "guides"

# The core package root, searched last for a `<kind>/<name>.toml` part. It is what
# lets the default `transformers = ["snooze"]` resolve whichever plugins a project
# happens to configure; `transformers/snooze.toml` is the only part shipped here.
CORE_PACKAGE_DIR = Path(__file__).parent


@cache
def installed_plugin_dirs() -> dict[str, Path]:
    """Map each installed plugin's name to its package data directory.

    Discovered through the ``habit_hooks.plugins`` entry-point group: each entry
    point's name is the plugin name and its value the import package whose
    bundled files (``config.toml``, ``sensors/``, ``guides/``, …) are the
    plugin's defaults.
    """
    dirs: dict[str, Path] = {}
    for entry_point in entry_points(group=PLUGIN_ENTRY_POINT_GROUP):
        dirs[entry_point.name] = Path(str(files(entry_point.value)))
    return dirs


@dataclass(frozen=True)
class Resolver:
    """The override chain layout: where plugin files are looked up.

    Holds the project (override) root and the installed plugins' package-data
    roots, and offers the lookups that walk them — project override before
    package default.
    """

    project_dir: Path
    package_dirs: dict[str, Path]

    @classmethod
    def discover(cls, project_dir: Path) -> Resolver:
        return cls(project_dir, installed_plugin_dirs())

    def plugin_dirs(self, plugin: str) -> list[Path]:
        override = self.project_dir / ".habit-hooks" / plugin
        package = self.package_dirs.get(plugin)
        return [override] if package is None else [override, package]

    def require_plugin(self, plugin: str) -> None:
        """Fail clearly if a configured plugin is neither overridden nor installed."""
        if self.in_plugin(plugin, "config.toml") is not None:
            return
        raise SystemExit(
            f"habit-sensors: plugin {plugin!r} is not installed — "
            f"install it with `pip install habit-hooks-{plugin}`"
        )

    def in_plugin(self, plugin: str, relative: str) -> Path | None:
        """First existing ``<plugin>/<relative>``, project override before package."""
        for base in self.plugin_dirs(plugin):
            candidate = base / relative
            if candidate.is_file():
                return candidate
        return None

    def part(self, plugins: list[str], relative: str) -> Path | None:
        """First existing ``<plugin>/<relative>`` across plugins, else the core's own.

        The core fallback keeps a default part (``transformers/snooze.toml``)
        resolvable no matter which plugins a project configures, mirroring the
        guide fallback in :meth:`first`.
        """
        for plugin in plugins:
            found = self.in_plugin(plugin, relative)
            if found is not None:
                return found
        candidate = CORE_PACKAGE_DIR / relative
        return candidate if candidate.is_file() else None

    def guide(self, guide: str, plugins: list[str]) -> Path | None:
        return self.first(plugins, [guide])

    def first(self, plugins: list[str], candidates: list[str]) -> Path | None:
        """First existing guide, walking plugins then override-before-package; within
        one directory the candidate names are tried in order. Falls back last to the
        core's built-in baseline guides, so the mapper still coaches (never crashes)
        when no configured plugin supplies the guide."""
        for plugin in plugins:
            for base in self.plugin_dirs(plugin):
                for name in candidates:
                    candidate = base / "guides" / name
                    if candidate.is_file():
                        return candidate
        for name in candidates:
            candidate = CORE_GUIDES / name
            if candidate.is_file():
                return candidate
        return None
