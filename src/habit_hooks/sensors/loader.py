"""Resolves a plugin and its parts across the override chain, applying the config's
per-sensor args and disable overrides — the loading half of the ETL."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..cli import ConfigError, ToolError
from ..config import Config
from ..config_schema import read_toml
from ..resolve import Resolver
from .model import Part, Plugin
from .named_tools import DeclaredTools, files_for


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
        part = Part(name, path.parent, command, argv)
        if kind == "sensors":
            part = replace(
                part,
                args=self._sensor_setting(name, spec, "args") or [],
                files=self._sensor_setting(name, spec, "files"),
            )
        return self._with_its_tools(kind, part)

    def _with_its_tools(self, kind: str, part: Part) -> Part:
        """``part`` knowing the file this project runs for each tool it names.

        The tools are the whole run's — every active plugin's declarations
        (``Config.plugin_detectors``) — rather than the declaring plugin's own,
        for two reasons. It is the same list a setup clears a project's tools
        against, so a tool a project was told it has is one its sensors can be
        handed. And a root transformer belongs to no plugin at all: it is
        resolved against the run's plugins as a whole (``sensors.run_sensors``),
        so it has none of its own to ask.

        The cost is that a plugin naming a tool it forgot to declare still runs
        wherever another enabled plugin declares it, and breaks only for the
        consumer who enables that one plugin —
        ``test_a_plugin_declares_the_tools_it_names`` is the gate for that.

        Asked as the config loads, so a recipe naming a tool no plugin declares
        is refused before anything is spawned.
        """
        tools = DeclaredTools(self.config.plugin_detectors, self.resolver.project_dir)
        return replace(part, detectors=files_for(part, kind[:-1], tools))

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
    notices. What an ``argv`` is made of is the fourth.
    """
    command, argv = spec.get("command"), spec.get("argv")
    if argv == []:
        raise ConfigError(
            f"{kind[:-1]} {name!r} spells an empty 'argv' — the first element "
            "of an argv is the program to run, so a list with nothing in it "
            "names no command at all; give it the program and its arguments, "
            "or spell a 'command' string instead"
        )
    _refuse_an_argv_that_is_not_arguments(kind, name, argv)
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


def _refuse_an_argv_that_is_not_arguments(
    kind: str, name: str, argv: object
) -> None:
    """Stop a part whose ``argv`` is not a list of things a spawn could carry.

    Every element is an argument handed to a program as it stands, so the whole
    has to be a list and every one of its elements a string. Neither mistake
    used to be answered here: a number among them was a ``TypeError`` traceback
    at exit 1 — the code reserved for an enforced finding, so a run reads a
    mistyped spec as a smell in the code — and a bare string was not answered at
    all. That one is the mistake that hides, because a string is iterable and
    nothing stumbles over it: ``argv = "ruff"`` spawns four arguments of one
    character each, and the run reports needing the ``'r'`` command. Both are the
    first-contact class #114 refuses to answer with anything but a sentence.
    """
    if argv is None:
        return
    if not isinstance(argv, list):
        raise ConfigError(
            f"{kind[:-1]} {name!r} spells {argv!r} as its 'argv' — an argv is a "
            "list, the program first and one element per argument after it; put "
            "it in brackets, or spell a 'command' string instead"
        )
    unspellable = [element for element in argv if not isinstance(element, str)]
    if not unspellable:
        return
    raise ConfigError(
        f"{kind[:-1]} {name!r} spells {unspellable[0]!r} in its 'argv' — every "
        "element is an argument handed to a program as it stands, so each has "
        "to be a string; quote it, or spell a 'command' string instead"
    )
