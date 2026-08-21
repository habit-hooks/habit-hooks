"""The tools a part's recipe names, and the file this project runs for each.

A sensor spawns tools its plugin did not ship, and the plugin declares every one
of them as a detector (:mod:`habit_hooks.detectors`). ``${detector:<name>}`` is
how a recipe asks for one, and it stands for the file the setup cleared that
tool by (``project_paths.tool_executable``) — the very same lookup, so a tool a
project was told it has is a file its sensors can be handed. Handing over the
file is the whole point: a bare name is looked up again by whatever spawns it,
and on Windows that lookup adds ``.exe`` and nothing else, where npm installs
every Node tool as a ``.cmd`` shim.

Only the tools a recipe actually names are resolved for it. A part answers for
what it reaches for and never for its plugin's other tools, or a project missing
a tool no sensor of that plugin names would fail the sensors that never wanted
it.

Two names can never stand for a file, and both are settled when the config loads
rather than at a spawn, because both are a packaging mistake in a plugin that no
run could recover from: a name no active plugin declares has no install command
to offer, and a ``node-module`` is a package node resolves from the project,
never a program on a search path. Each is a ``ConfigError`` (exit 2), unnamed so
``cli.run_console`` puts the running binary on the front of it. Whoever reads one
is a consumer whose whole run has just stopped — one plugin's parts are loaded
alongside every other plugin's — and the recipe is not theirs to fix, so each
refusal ends with the one thing they can do about it: switch that part off.

A tool that is declared, a command, and simply **not installed** is neither of
those: it is the ordinary missing tool every first run meets. So it resolves to
``None`` here and stays the notice + failed run ``part_output`` already answers
a missing command with (``broken_part.run_part``).
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from pathlib import Path

from attrs import frozen

from ..cli import ConfigError
from ..detectors import COMMAND_KIND, NODE_MODULE_KIND, Detector
from ..project_paths import tool_executable
from .model import Part
from .part_output import switch_off

# A name of no characters is matched too, so ``${detector:}`` is a typo somebody
# is told about rather than the one spelling that would reach a tool verbatim.
DETECTOR = re.compile(r"\$\{detector:([^{}]*)\}")


@frozen
class DeclaredTools:
    """What every name a recipe carries is put to: the tools this run's plugins
    declare, and the project they are looked for in.

    One value because both are the run's rather than any one part's, and every
    name asks the same two things of them — the shape ``missing_tools._Tools``
    has, for the same reason.
    """

    declared: list[Detector]
    project_dir: Path

    def file_for(self, name: str) -> str | None:
        """The file this project runs for the command ``name``, or ``None``."""
        return tool_executable(name, self.project_dir)

    def kinds_of(self, name: str) -> list[str]:
        """Every way this run's plugins declare that ``name`` is looked for."""
        return sorted(
            {detector.kind for detector in self.declared if detector.name == name}
        )

    def spelled_out(self) -> str:
        """What this run does declare, each with the way it is looked for."""
        named = ", ".join(
            f"{detector.name} ({detector.kind})" for detector in self.declared
        )
        return named or "none"


def files_for(part: Part, kind: str, tools: DeclaredTools) -> dict[str, str | None]:
    """The file this project runs for each tool ``part`` names, ``None`` if absent.

    A name that can never stand for a file at all stops the run here, naming the
    part, why, and the config line that stops running it.
    """
    named = _names_in(part)
    for name in named:
        unusable = _why_no_file_for(name, tools)
        if unusable is not None:
            raise ConfigError(
                f"{kind} {part.name!r} names ${{detector:{name}}}, {unusable} — "
                f"{switch_off(kind, part.name)}"
            )
    return {name: tools.file_for(name) for name in named}


def spelled_plainly(part: Part, text: str) -> str:
    """``text`` with every tool it names replaced by the file that runs it."""
    return _filled_in(part, text, str)


def spelled_for_a_shell(part: Part, text: str) -> str:
    """The same, quoted for the shell that is about to read ``text``."""
    return _filled_in(part, text, shlex.quote)


def _filled_in(part: Part, text: str, spell: Callable[[str], str]) -> str:
    """``text`` with each tool this project can run spelled as its form carries it.

    A tool it cannot run is left standing. The argv is still built, but it is
    never spawned: the part fails first as the missing command it is
    (``Part.missing_detector``, ``broken_part.run_part``), so there is nothing
    here for a bare name to be any use to.
    """
    for name, file in part.detectors.items():
        if file is not None:
            text = text.replace(f"${{detector:{name}}}", spell(file))
    return text


def _names_in(part: Part) -> list[str]:
    """Every tool ``part``'s recipe names, in the order it first names them."""
    recipe = (part.command or "") if part.argv is None else " ".join(part.argv)
    return list(dict.fromkeys(DETECTOR.findall(recipe)))


def _why_no_file_for(name: str, tools: DeclaredTools) -> str | None:
    """Why ``name`` can never stand for a file to spawn, or ``None`` when it can."""
    kinds = tools.kinds_of(name)
    if COMMAND_KIND in kinds:
        return None
    if not kinds:
        return _nobody_declared(tools)
    return _the_wrong_kind(name, kinds)


def _nobody_declared(tools: DeclaredTools) -> str:
    """Named by a recipe that no plugin in this run backed with a declaration."""
    return (
        "which no active plugin declares: a plugin names the tools its sensors "
        "reach for in its config.toml 'detectors', and this run declares "
        f"{tools.spelled_out()}"
    )


def _the_wrong_kind(name: str, kinds: list[str]) -> str:
    """Named, but looked for in a way that answers about no file at all."""
    spelled = ", ".join(repr(kind) for kind in kinds)
    return (
        f"but {name!r} is declared {spelled}, not {COMMAND_KIND!r}: only a "
        f"command names a file this run can spawn{_and_what_a_module_is(kinds)}"
    )


def _and_what_a_module_is(kinds: list[str]) -> str:
    """Why a module is not a command, said only where a module is what was named.

    The kind is asked for by name rather than fallen into, as
    ``missing_tools._is_missing`` asks it: a kind added later then earns the
    plain refusal, instead of an explanation about node that has nothing to do
    with it.
    """
    if NODE_MODULE_KIND not in kinds:
        return ""
    return ", and a module is read by node from the project, never spawned by name"
