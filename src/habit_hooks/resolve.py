"""Resolve a guide file across the override chain.

Each plugin is tried project-override (``.habit-hooks/<plugin>/``) before package
default (``<package>/plugins/<plugin>/``); plugins are walked in the configured
order, so an earlier plugin's guide wins over a later one's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def package_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "plugins").is_dir():
            return parent
    raise SystemExit("could not locate the package plugins directory")


@dataclass(frozen=True)
class Resolver:
    """The override chain layout: where plugin files are looked up.

    Holds the project (override) and package (default) roots and offers the
    lookups that walk them — project override before package default.
    """

    project_dir: Path
    package_dir: Path

    def plugin_dirs(self, plugin: str) -> list[Path]:
        return [
            self.project_dir / ".habit-hooks" / plugin,
            self.package_dir / "plugins" / plugin,
        ]

    def in_plugin(self, plugin: str, relative: str) -> Path | None:
        """First existing ``<plugin>/<relative>``, project override before package."""
        for base in self.plugin_dirs(plugin):
            candidate = base / relative
            if candidate.is_file():
                return candidate
        return None

    def guide(self, guide: str, plugins: list[str]) -> Path | None:
        return self.first(plugins, [guide])

    def first(self, plugins: list[str], candidates: list[str]) -> Path | None:
        """First existing guide, walking plugins then override-before-package; within
        one directory the candidate names are tried in order."""
        for plugin in plugins:
            for base in self.plugin_dirs(plugin):
                for name in candidates:
                    candidate = base / "guides" / name
                    if candidate.is_file():
                        return candidate
        return None
