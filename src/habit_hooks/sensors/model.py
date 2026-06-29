"""The recursive ETL node types: a plugin's sensors and transformers, plus the
findings/notices a run accumulates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class SensorError(Exception):
    """A sensor that spawn-failed, exited unexpectedly, or emitted bad JSON."""


@dataclass
class Part:
    name: str
    command: str
    directory: Path
    args: list[str] = field(default_factory=list)


@dataclass
class Plugin:
    name: str
    language: str | None
    sensors: list[Part]
    transformers: list[Part]


@dataclass
class Run:
    findings: list[dict] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.notices)
