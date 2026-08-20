"""The recursive ETL node types: a plugin's sensors and transformers, plus the
findings/notices a run accumulates."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path


class SensorError(Exception):
    """A sensor that spawn-failed, exited unexpectedly, or emitted bad JSON."""


@dataclass
class Part:
    """One sensor or transformer: what it runs, where from, and over what.

    A part spells its recipe exactly one of two ways, and ``loader`` refuses
    any other count. ``argv`` is an argument list spawned as it stands — the
    only form that runs where there is no POSIX shell. ``command`` is text a
    shell reads, which buys syntax a list cannot carry (a pipe into ``jq``) at
    the price of needing ``bash`` to read it. ``command_text`` is where the
    difference is spent.
    """

    name: str
    directory: Path
    command: str | None = None
    argv: list[str] | None = None
    args: list[str] = field(default_factory=list)
    # A sensor's own discovery globs: when set, the run's scope is narrowed to
    # this subset for this sensor alone. ``None`` means "the whole scope".
    files: list[str] | None = None

    @property
    def command_line(self) -> str:
        """The part's recipe as a message about it should quote it back.

        A failure names what was being run, and both forms have to answer for
        themselves. ``shlex.join`` spells an argv the way a reader could paste
        it into a terminal — for reading, never for running: the spawn carries
        the list, and nothing re-parses this text.
        """
        if self.command is not None:
            return self.command
        return shlex.join(self.argv or [])


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
    active_languages: set[str] = field(default_factory=set)

    @property
    def failed(self) -> bool:
        return bool(self.notices)
