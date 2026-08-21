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
from habit_hooks.sensors.model import Part


def write_project_config(project_dir: Path, body: str) -> None:
    path = project_dir / ".habit-hooks" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def write_plugin(project_dir: Path, name: str, files: dict[str, str]) -> None:
    """Write a fixture plugin's package data under ``.habit-hooks/<name>/``.

    ``files`` maps a path relative to the plugin directory to its contents, e.g.
    ``{"config.toml": ..., "sensors/s.toml": ..., "guides/x.py": ...}``.
    """
    base = project_dir / ".habit-hooks" / name
    for relative, contents in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def loader_for(project_dir: Path) -> PluginLoader:
    config = load_config(project_dir)
    return PluginLoader(Resolver.discover(project_dir), config)


def one_transformer(project_dir: Path, recipe: str, plugin_toml: str = "") -> Part:
    """The single transformer of a fixture plugin, as a run's loader builds it.

    Resolved against the run's plugins rather than any one of them, which is how
    a root transformer is reached (``sensors.run_sensors``).
    """
    write_project_config(project_dir, 'plugins = ["fixt"]')
    write_plugin(
        project_dir,
        "fixt",
        {"config.toml": f"sensors = []\n{plugin_toml}", "transformers/t.toml": recipe},
    )
    return loader_for(project_dir).resolve_part(["fixt"], "transformers", "t")


def one_sensor(project_dir: Path, sensor_toml: str, plugin_toml: str = "") -> Part:
    """The single sensor of a fixture plugin, as a run's loader builds it.

    The project config names the fixture plugin, so what the run knows about
    that plugin — the detectors it declares among them — comes from what the
    case wrote rather than from whichever plugins the dev environment installed.
    ``plugin_toml`` is whatever else that plugin's ``config.toml`` has to say;
    a case about the sensor alone needs none of it.
    """
    write_project_config(project_dir, 'plugins = ["fixt"]')
    write_plugin(
        project_dir,
        "fixt",
        {
            "config.toml": f'sensors = ["s"]\n{plugin_toml}',
            "sensors/s.toml": sensor_toml,
        },
    )
    return loader_for(project_dir).load_plugin("fixt").sensors[0]
