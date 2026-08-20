"""The project's own names for things: what it calls a path, and where its tools are.

The one place that decides whether a path belongs to the project and what it is
called there. Both ends of a snooze rest on it: a sensor's paths are anchored on
the way in (``sensors/finding_paths.py``), and the git question behind a lapsing
snooze asks about the very same repo-relative paths (``changed_files.py``).

"Where does this project keep its tools" is the same kind of question and gets
one answer here for the same reason: ``sensors/spawn.py`` runs every command
against it and ``missing_tools.py`` reports a tool missing from it, so a second
answer would have a setup clear a tool the run still cannot find.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePath

from . import host_platform


def project_relative(raw: str, project_dir: Path) -> str | None:
    """``raw`` as a forward-slash path under ``project_dir``, or ``None`` outside it.

    A relative path is read against the project; an absolute one is placed back
    in it. Symlinks are resolved only as a second attempt, so a project reached
    through one still anchors, while a symlinked source directory keeps the path
    the project knows it by.

    The project directory itself is not a path *under* the project: ``""`` and
    ``"."`` name the whole of it, which as a snooze key would stand for every
    file at once and as a pathspec would match them all.
    """
    absolute = os.path.normpath(os.path.join(project_dir, raw))
    return _under(absolute, str(project_dir)) or _under(
        os.path.realpath(absolute), os.path.realpath(project_dir)
    )


def venv_bin_dir(venv_dir: Path) -> Path:
    """Where a venv keeps its executables.

    CPython's venv module puts ``python`` and every installed console script
    under ``bin`` everywhere except Windows, where it uses ``Scripts`` instead
    — the one fact both ``tool_search_path`` below and an installed-run test
    harness need, so both ask here rather than each spelling it separately.
    """
    return venv_dir / ("Scripts" if host_platform.is_windows() else "bin")


def tool_search_path(project_dir: Path) -> str:
    """Where this project's tools are, ahead of everything else on ``PATH``.

    A project's own installs come first so a run measures with the versions it
    pinned rather than whatever is on the machine — and so an editor plugin and
    a hook, run under different shells, still measure alike.
    """
    node = project_dir / "node_modules" / ".bin"
    venv = venv_bin_dir(project_dir / ".venv")
    return os.pathsep.join([str(node), str(venv), os.environ.get("PATH", "")])


def _under(target: str, root: str) -> str | None:
    relative = os.path.relpath(target, root)
    outside = relative == os.pardir or relative.startswith(os.pardir + os.sep)
    return None if outside or relative == os.curdir else PurePath(relative).as_posix()
