"""Resolve a guide file across the override chain.

Each plugin is tried project-override (``.habit-hooks/<plugin>/``) before package
default (``<package>/plugins/<plugin>/``); plugins are walked in the configured
order, so an earlier plugin's guide wins over a later one's.
"""

from __future__ import annotations

from pathlib import Path


def plugin_dirs(plugin: str, project_dir: Path, package_dir: Path) -> list[Path]:
    return [
        project_dir / ".habit-hooks" / plugin,
        package_dir / "plugins" / plugin,
    ]


def resolve_guide(
    guide: str, plugins: list[str], project_dir: Path, package_dir: Path
) -> Path | None:
    return resolve_first(plugins, project_dir, package_dir, [guide])


def resolve_first(
    plugins: list[str], project_dir: Path, package_dir: Path, candidates: list[str]
) -> Path | None:
    """First existing guide, walking plugins then override-before-package; within
    one directory the candidate names are tried in order."""
    for plugin in plugins:
        for base in plugin_dirs(plugin, project_dir, package_dir):
            for name in candidates:
                candidate = base / "guides" / name
                if candidate.is_file():
                    return candidate
    return None
