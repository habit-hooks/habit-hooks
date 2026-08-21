"""Ask one git question inside a project, and hand back what git said.

This is the spawning policy every question in ``git_history`` shares — the
project as the working directory, output captured and decoded as UTF-8, an empty
stdin — held apart from the questions themselves. How a thing is asked is a
smaller and stabler concern than what is asked and what its answer means, and
this is the half with one reason to change; it is the same line, in the same
direction, as ``part_output`` → ``diagnosis`` and ``mapper`` → ``rendering``.
The dependency runs one way: ``git_history`` imports from here, never back.

All three answers degrade rather than raise. There is nothing a message could
usefully say about a machine with no git on it, so ``git`` answers ``None`` when
the program could not be run at all, ``git_output`` answers empty text on any
failure whatever, and ``git_succeeded`` answers ``False``. What to make of any
of those silences is the asking module's decision, not this one's — an empty
answer is never allowed to quietly mean "nothing there".
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """``git <args>`` in the project, or ``None`` when git could not be run at all.

    Every call is handed an empty stdin: ``hash-object --stdin`` needs one, and
    no other question asked here reads input, so none of them can sit waiting for
    one that never comes.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=project_dir,
            capture_output=True,
            encoding="utf-8",
            errors="replace",  # sensors.spawn's policy
            input="",
        )
    except OSError:
        return None


def git_output(project_dir: Path, *args: str) -> str:
    """``git <args>`` output, or empty on any failure — the safe degrade."""
    result = git(project_dir, *args)
    if result is None or result.returncode != 0:
        return ""
    return result.stdout.strip()


def git_succeeded(project_dir: Path, *args: str) -> bool:
    """Whether ``git <args>`` answered yes, for the questions git answers by exit
    code alone (``--is-inside-work-tree``, ``check-ignore --quiet``).

    A git that could not be run and a git that said no are one answer here: both
    are the absence of a yes, and neither is a mistake the caller can report.
    """
    result = git(project_dir, *args)
    return result is not None and result.returncode == 0
