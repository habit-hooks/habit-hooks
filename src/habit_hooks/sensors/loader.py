"""Resolves a plugin and its parts across the override chain, applying the config's
per-sensor args and disable overrides — the loading half of the ETL."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..cli import ToolError
from ..config import Config
from ..resolve import Resolver
from .model import Part, Plugin


def _read_toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


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
        spec = _read_toml(path) if path else {}
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
        spec = _read_toml(path)
        if kind != "sensors":
            return Part(name, spec["command"], path.parent)
        return Part(
            name,
            spec["command"],
            path.parent,
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
