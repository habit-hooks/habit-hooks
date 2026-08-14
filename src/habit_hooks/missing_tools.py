"""Which of the tools a project's plugins declare it cannot reach.

A plugin declares the external tools its sensors reach for
(:mod:`habit_hooks.detectors`); this is the asking. Each kind is asked the way a
run will ask it — a command along ``project_paths.tool_search_path``, the very
PATH ``habit-sensors`` spawns against, and a module of node itself, because a
package read as a library is not answered by a binary of that name. A tool
cleared here that a run cannot find is the support question setting a project up
exists to end.

Separate from :mod:`habit_hooks.initialise`, which decides what setting a
project up comes to: what a project is planned to run and what stands in the way
of it are two questions, and only this one spawns anything.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from attrs import frozen

from .detectors import COMMAND_KIND, NODE_MODULE_KIND, Detector
from .project_paths import tool_search_path

NODE = "node"

# Seconds node gets to say whether it resolves a module. The node asked is the
# project's own ``node_modules/.bin`` — a shim the project wrote — and a wedged
# one must not block the hook this stands in front of, for the reason
# ``sensors.spawn`` gives every command it runs a deadline.
NODE_RESOLVE_TIMEOUT_SECONDS = 30.0


@frozen
class _Tools:
    """What every detector is asked about: where this project looks for a tool,
    the node that answers for its modules, and whether the plugins declared that
    node themselves — asked once, because every detector asks the same."""

    project_dir: Path
    search_path: str
    node: str | None
    node_declared: bool

    @classmethod
    def under(cls, project_dir: Path, declared: list[Detector]) -> _Tools:
        search_path = tool_search_path(project_dir)
        return cls(
            project_dir,
            search_path,
            shutil.which(NODE, path=search_path),
            any(_is_node(detector) for detector in declared),
        )


def _is_node(detector: Detector) -> bool:
    return detector.kind == COMMAND_KIND and detector.name == NODE


def missing_tools(
    declared: list[Detector], project_dir: Path
) -> tuple[Detector, ...]:
    """The declared tools this project cannot reach, in declaration order.

    Declaration order because a plugin declares what everything else needs
    first, so a list read from the top is one that can be worked through from
    the top.
    """
    tools = _Tools.under(project_dir, declared)
    return tuple(detector for detector in declared if _is_missing(detector, tools))


def _is_missing(detector: Detector, tools: _Tools) -> bool:
    """Whether the project can reach this tool, asked the way its kind is found.

    The module kind is named rather than fallen into, so a kind added later is
    looked for on the ``PATH`` — wrong, and visibly so — instead of quietly
    being asked of node.
    """
    if detector.kind == NODE_MODULE_KIND:
        return _module_is_missing(detector.name, tools)
    return shutil.which(detector.name, path=tools.search_path) is None


def _module_is_missing(module: str, tools: _Tools) -> bool:
    """Whether the project cannot reach this module, as far as node can say.

    Nothing can be asked of a machine without node, and where the plugins
    declared ``node`` themselves that one absence is already being reported:
    naming every module behind it hands the reader a list of installs where one
    of them is the whole answer, so they wait for the re-run that can answer.
    A plugin that declares a module and no node has no such absence to point at,
    and a silence there is a setup called clean and a first run that dies on the
    module.
    """
    if tools.node is None:
        return not tools.node_declared
    return not _node_resolves(tools.node, module, tools.project_dir)


def _node_resolves(node: str, module: str, project_dir: Path) -> bool:
    """Whether node can require ``module`` from the project, as a sensor would.

    Asked from the project because that is where node resolves a dependency
    from, and asked as ``require.resolve`` because a package read as a library
    is not answered by a binary of that name. The module is placed in the script
    as JSON, which is a JavaScript string literal for any name a package may have.

    A node that never answers is the answer ``no``: one that cannot be run at
    all resolves nothing, and one still thinking about it past its deadline
    cannot be waited on by a hook.
    """
    script = f"require.resolve({json.dumps(module)})"
    try:
        asked = subprocess.run(
            [node, "-e", script],
            cwd=project_dir,
            capture_output=True,
            text=True,
            input="",
            timeout=NODE_RESOLVE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return asked.returncode == 0
