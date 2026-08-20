"""Resolves a plugin and its parts across the override chain, applying the config's
per-sensor args and disable overrides — the loading half of the ETL."""

from __future__ import annotations

from dataclasses import dataclass

from ..cli import ConfigError, ToolError
from ..config import Config
from ..config_schema import read_toml
from ..resolve import Resolver
from .model import Part, Plugin


@dataclass(frozen=True)
class PluginLoader:
    """How plugins and parts are built: the override-chain resolver plus the config.

    Holds the resolver and config and offers the lookups that turn plugin names
    into ``Plugin`` and ``Part`` objects, honouring per-sensor overrides.
    """

    resolver: Resolver
    config: Config

    def load_plugin(self, name: str) -> Plugin:
        self.resolver.require_plugin(name)
        path = self.resolver.in_plugin(name, "config.toml")
        spec = read_toml(path) if path else {}
        sensors = [
            self.resolve_part([name], "sensors", sensor)
            for sensor in spec.get("sensors", [])
            if not self._disabled(sensor)
        ]
        transformers = [
            self.resolve_part([name], "transformers", transformer)
            for transformer in spec.get("transformers", [])
        ]
        return Plugin(name, spec.get("language"), sensors, transformers)

    def resolve_part(self, plugins: list[str], kind: str, name: str) -> Part:
        path = self.resolver.part(plugins, f"{kind}/{name}.toml")
        if path is None:
            raise ToolError(
                f"habit-sensors: no {kind[:-1]} {name!r} in {plugins} or the core"
            )
        spec = read_toml(path)
        command, argv = _recipe(kind, name, spec)
        if kind != "sensors":
            return Part(name, path.parent, command, argv)
        return Part(
            name,
            path.parent,
            command,
            argv,
            self._sensor_setting(name, spec, "args") or [],
            self._sensor_setting(name, spec, "files"),
        )

    def _sensor_setting(self, name: str, spec: dict, key: str) -> list[str] | None:
        """The project's ``[sensors.<name>]`` override for ``key``, else the spec's.

        One override rule for every per-sensor setting: a project value replaces
        the sensor spec's default wholesale, and absent either it is unset.
        """
        override = self.config.sensors.get(name)
        value = getattr(override, key) if override is not None else None
        return value if value is not None else spec.get(key)

    def _disabled(self, sensor: str) -> bool:
        override = self.config.sensors.get(sensor)
        return bool(override and override.disabled)


def _recipe(kind: str, name: str, spec: dict) -> tuple[str | None, list[str] | None]:
    """What the part runs: exactly one of ``command`` and ``argv``.

    The two are not interchangeable and cannot be combined. An ``argv`` is
    spawned as it stands, a ``command`` is text ``bash`` reads, and a spec
    saying both leaves which one runs to whichever the code happened to look at
    first — while one saying neither is a part that states what it is and never
    what it does. Both earn the treatment #102 gives a config key nothing
    consumes: a refusal that names the part, rather than a default nobody chose
    or the ``KeyError`` traceback a missing ``command`` used to be (#114).

    An ``argv`` with nothing in it is the third of that family and answers in
    the same register. It reads as a recipe right up to the spawn, where the
    first element it does not have is the program — an ``IndexError`` traceback
    out of the layer whose whole job is that other people's programs fail as
    notices.
    """
    command, argv = spec.get("command"), spec.get("argv")
    if argv == []:
        raise ConfigError(
            f"{kind[:-1]} {name!r} spells an empty 'argv' — the first element "
            "of an argv is the program to run, so a list with nothing in it "
            "names no command at all; give it the program and its arguments, "
            "or spell a 'command' string instead"
        )
    if (command is None) != (argv is None):
        return command, argv
    spelled = (
        "spells both 'command' and 'argv'"
        if command is not None
        else "spells neither 'command' nor 'argv'"
    )
    raise ConfigError(
        f"{kind[:-1]} {name!r} {spelled} — a part runs one or the other: 'argv' "
        "is a list of arguments spawned as it stands, which is the only form "
        "there is where no POSIX shell exists; 'command' is a shell string, for "
        "the syntax a list cannot carry, such as a pipe into jq"
    )
