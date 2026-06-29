"""Resolves a plugin and its parts across the override chain, applying the config's
per-sensor args and disable overrides — the loading half of the ETL."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

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
        for plugin in plugins:
            path = self.resolver.in_plugin(plugin, f"{kind}/{name}.toml")
            if path is not None:
                spec = _read_toml(path)
                args = self._sensor_args(name, spec) if kind == "sensors" else []
                return Part(name, spec["command"], path.parent, args)
        raise SystemExit(f"habit-sensors: no {kind[:-1]} {name!r} in {plugins}")

    def _sensor_args(self, name: str, spec: dict) -> list[str]:
        override = self.config.sensors.get(name)
        if override is not None and override.args is not None:
            return override.args
        return spec.get("args", [])

    def _disabled(self, sensor: str) -> bool:
        override = self.config.sensors.get(sensor)
        return bool(override and override.disabled)
