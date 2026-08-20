"""Unit tests for the tools ``habit-hooks init`` reports this machine has not got.

A plugin declares what its sensors reach for; init has to ask about each one the
way the run itself will — on the project's own ``PATH`` for a command, and of
node for a module — because a tool cleared here that a run cannot find is the
support question this whole command exists to end.

What init plans for the project is ``test_initialise.py``; what a detector may
say at all is ``test_detector_schema.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from executable_stub import write_recording_tool, write_stub, write_wedged_tool
from platform_probe import off_windows

from habit_hooks import missing_tools
from habit_hooks.initialise import plan
from plugin_fixture import write_plugin

JQ = '{ name = "jq", kind = "command", install = "brew install jq" }'
NODE = '{ name = "node", kind = "command", install = "brew install node" }'
TS_MORPH = (
    '{ name = "ts-morph", kind = "node-module", install = "npm i -D ts-morph" }'
)

NODE_LOG = "node.log"


def _needing(project_dir: Path, *entries: str) -> Path:
    """A project init reads as Python, whose plugin declares exactly ``entries``."""
    (project_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    declared = f"detectors = [{', '.join(entries)}]"
    write_plugin(project_dir, "python", {"config.toml": declared})
    return project_dir


def _missing(project_dir: Path) -> list[str]:
    return [detector.name for detector in plan(project_dir).missing_tools]


def test_a_plugin_that_declares_no_tools_leaves_nothing_in_the_way(
    toolless_project: Path,
) -> None:
    """A plugin needing nothing installed reports nothing missing, on a machine
    that has nothing installed."""
    _needing(toolless_project)

    assert plan(toolless_project).missing_tools == ()


def test_a_command_in_the_project_s_python_bin_is_not_missing(
    toolless_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run spawns against ``<project>/.venv/bin``, so a tool installed there is
    one it can reach — asking a narrower question would send someone off to
    install what they already have.

    ``.venv/bin`` is the POSIX half of that path (``project_paths.venv_bin_dir``
    answers ``.venv/Scripts`` on Windows), so this pins off Windows rather than
    stubbing a directory the search path would not be looking in.
    """
    off_windows(monkeypatch)
    _needing(toolless_project, JQ)
    write_stub(toolless_project / ".venv" / "bin", "jq")

    assert _missing(toolless_project) == []


def test_a_command_in_the_project_s_node_bin_is_not_missing(
    toolless_project: Path,
) -> None:
    """The other half of the path a run spawns against."""
    _needing(toolless_project, JQ)
    write_stub(toolless_project / "node_modules" / ".bin", "jq")

    assert _missing(toolless_project) == []


def test_a_command_nowhere_on_the_path_is_missing_with_the_way_to_get_it(
    toolless_project: Path,
) -> None:
    """Naming the tool without the command that installs it leaves the reader to
    go and find it, which is the whole of what init is for."""
    _needing(toolless_project, JQ)

    (jq,) = plan(toolless_project).missing_tools

    assert jq.name == "jq"
    assert jq.install == "brew install jq"


def test_every_missing_command_is_named_in_the_order_its_plugin_declared_them(
    toolless_project: Path,
) -> None:
    """A plugin declares what everything else needs first, and a list read from
    the top is a list that can be worked through from the top."""
    _needing(toolless_project, NODE, JQ)

    assert _missing(toolless_project) == ["node", "jq"]


def test_a_module_node_resolves_from_the_project_is_not_missing(
    toolless_project: Path,
) -> None:
    """A package read as a library is not answered by a binary of that name, so
    node is asked rather than the ``PATH``."""
    _needing(toolless_project, NODE, TS_MORPH)
    write_stub(toolless_project / "node_modules" / ".bin", "node")

    assert _missing(toolless_project) == []


def test_a_module_node_cannot_resolve_is_missing(toolless_project: Path) -> None:
    _needing(toolless_project, NODE, TS_MORPH)
    write_stub(toolless_project / "node_modules" / ".bin", "node", exit_code=1)

    assert _missing(toolless_project) == ["ts-morph"]


def test_a_missing_node_answers_for_its_modules_rather_than_them(
    toolless_project: Path,
) -> None:
    """Nothing can be asked of node when there is no node. Reporting every module
    missing on top of it hands the reader a list of installs where one of them is
    the answer: install node, run it again, and be told the truth."""
    _needing(toolless_project, NODE, TS_MORPH)

    assert _missing(toolless_project) == ["node"]


def test_a_module_whose_plugin_never_declared_node_is_missing_on_its_own(
    toolless_project: Path,
) -> None:
    """Node's absence answers for its modules only where that absence is itself
    being reported. A plugin that declares a module and no node has nothing to
    point the reader at, so a silence here is a setup called clean and a first
    run that dies on the module."""
    _needing(toolless_project, TS_MORPH)

    assert _missing(toolless_project) == ["ts-morph"]


def test_a_node_that_never_answers_is_not_waited_on(
    toolless_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The node asked is the project's own ``node_modules/.bin`` — a shim the
    project wrote — and a wedged one must not block the hook this stands in
    front of. An unanswered module is a missing one."""
    _needing(toolless_project, NODE, TS_MORPH)
    write_wedged_tool(toolless_project / "node_modules" / ".bin", "node")
    monkeypatch.setattr(missing_tools, "NODE_RESOLVE_TIMEOUT_SECONDS", 0.1)

    assert _missing(toolless_project) == ["ts-morph"]


def test_node_is_asked_to_resolve_the_module_from_the_project_itself(
    toolless_project: Path,
) -> None:
    """``require.resolve`` from the project is where a sensor's own ``require``
    would look, so a module resolvable only from somewhere else stays missing."""
    _needing(toolless_project, NODE, TS_MORPH)
    bin_dir = toolless_project / "node_modules" / ".bin"
    write_recording_tool(bin_dir, "node", NODE_LOG)

    plan(toolless_project)

    asked, asked_in = (bin_dir / NODE_LOG).read_text(encoding="utf-8").splitlines()
    assert 'require.resolve("ts-morph")' in asked
    assert Path(asked_in).resolve() == toolless_project.resolve()
