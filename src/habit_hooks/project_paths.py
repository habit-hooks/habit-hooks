"""Express a path relative to the project directory.

The one place that decides whether a path belongs to the project and what it is
called there. Both ends of a snooze rest on it: a sensor's paths are anchored on
the way in (``sensors/finding_paths.py``), and the git question behind a lapsing
snooze asks about the very same repo-relative paths (``changed_files.py``).
"""

from __future__ import annotations

import os
from pathlib import Path, PurePath


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


def _under(target: str, root: str) -> str | None:
    relative = os.path.relpath(target, root)
    outside = relative == os.pardir or relative.startswith(os.pardir + os.sep)
    return None if outside or relative == os.curdir else PurePath(relative).as_posix()
