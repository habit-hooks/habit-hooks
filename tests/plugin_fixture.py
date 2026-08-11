"""Build a fixture plugin under a project's ``.habit-hooks/<plugin>/`` override
directory, so a test exercises the real resolver, config loader, and plugin
loader without building and installing a wheel.

The override chain treats ``.habit-hooks/<plugin>/`` as the plugin's package
data, so a plugin that lives only there is fully resolvable (``Resolver``); this
is the same mechanism the executable specs use for their fixture plugins.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.config import load_config
from habit_hooks.resolve import Resolver
from habit_hooks.sensors.loader import PluginLoader


def write_project_config(project_dir: Path, body: str) -> None:
    path = project_dir / ".habit-hooks" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def write_plugin(project_dir: Path, name: str, files: dict[str, str]) -> None:
    """Write a fixture plugin's package data under ``.habit-hooks/<name>/``.

    ``files`` maps a path relative to the plugin directory to its contents, e.g.
    ``{"config.toml": ..., "sensors/s.toml": ..., "guides/x.py": ...}``.
    """
    base = project_dir / ".habit-hooks" / name
    for relative, contents in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)


def loader_for(project_dir: Path) -> PluginLoader:
    config = load_config(project_dir)
    return PluginLoader(Resolver.discover(project_dir), config)
