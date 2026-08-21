"""Run habit-hooks as an *installed* tool, and build the environment it sees.

Getting an install is ``wheelhouse``; this module is what happens next —
running the installed console script against a project, and constructing the
machine such a run lands on. Between them they catch the class of bug where
everything works from a checkout and nothing works once packaged: plugins
located by walking a sibling directory, package data that never made it into
the wheel, a helper invoked as bare ``python``.

The tests that assert what such a run must produce live in
``test_installed_wheel_smoke.py`` (the core finding its plugins) and
``test_installed_plugin_packaging.py`` (each plugin bringing what its sensors
need).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def require_tool(name: str) -> str:
    """Skip a case that wraps a third-party tool this machine has not got.

    A plugin's packaging can only be proved through the tool it wraps, and a
    machine without it can say nothing either way — so the case steps aside
    rather than reporting a packaging failure it did not observe.
    """
    tool = shutil.which(name)
    if tool is None:
        pytest.skip(f"{name} is not on PATH")
    return tool


def run_and_collect_findings(
    habit_sensors: Path, project: Path, env: dict[str, str] | None = None
) -> list[dict]:
    """Run the installed sensors stage and parse its findings.

    Asserts the packaging-failure messages are absent first: those produce an
    empty findings array, which would otherwise read as a clean project.
    """
    result = subprocess.run(
        [str(habit_sensors), "--all"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # sensors.spawn's policy
        env=env,
    )
    assert "is not installed" not in result.stderr, result.stderr
    assert "could not locate" not in result.stderr.lower(), result.stderr
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# Every extension this machine runs a bare command name by, which is how Windows
# decides what is a program at all.
_RUNNABLE_EXTENSIONS = {
    extension.lower() for extension in os.environ.get("PATHEXT", "").split(os.pathsep)
}


def _the_machine_runs(tool: Path) -> bool:
    """Whether this machine would run ``tool`` as a program.

    ``os.access(..., X_OK)`` asks after the execute bit, which Windows has not
    got: there it is true of every file on the search path, DLLs and text files
    alike. What Windows runs is decided by the extension instead, so that is
    the question asked there.
    """
    if os.name == "nt":
        return tool.suffix.lower() in _RUNNABLE_EXTENSIONS
    return os.access(tool, os.X_OK)


def _the_command_it_answers(tool: Path) -> str:
    """The bare command name a lookup would find ``tool`` for.

    A Python interpreter is the file ``python.exe`` on Windows and ``python``
    everywhere else, and ``shutil.which("python")`` finds both — so a set of
    bare names names the file to leave out on one platform only, and a PATH
    built by matching them keeps the very interpreter it was meant to hide.
    """
    return tool.stem.lower() if os.name == "nt" else tool.name


def _link_executables_except(bin_dir: Path, blocked: set[str]) -> None:
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        source = Path(entry)
        if not source.is_dir():
            continue
        for tool in source.iterdir():
            link = bin_dir / tool.name
            if _the_command_it_answers(tool) in blocked or link.exists():
                continue
            if _the_machine_runs(tool):
                link.symlink_to(tool)


def without_python_on_path(tmp_path: Path) -> dict[str, str]:
    """This environment with the usual tools on PATH but no ``python``/``python3``,
    reproducing a clean CI sandbox / stock-macOS environment. Built by symlinking
    every executable on the current PATH except the Python interpreters into a
    single bin dir.

    Only PATH is replaced, exactly as ``sensors/spawn`` replaces it for every
    command habit-hooks runs: an environment cut down to PATH alone varies more
    than the one thing the case is about — on Windows it would leave the child
    without ``PATHEXT``, so the tool lookup inside habit-hooks would answer
    about no machine at all, and without ``SystemRoot``, which its own launcher
    needs.

    ``git`` stands for the tools that must survive: something on this PATH has
    to, or an empty directory would pass for a PATH with no python in it, and
    git is the one tool both this suite and its runners are certain to have.
    """
    bin_dir = tmp_path / "no-python-bin"
    bin_dir.mkdir()
    _link_executables_except(bin_dir, {"python", "python3"})

    assert shutil.which("python", path=str(bin_dir)) is None
    assert shutil.which("python3", path=str(bin_dir)) is None
    assert shutil.which("git", path=str(bin_dir)) is not None
    return {**os.environ, "PATH": str(bin_dir)}
