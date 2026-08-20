"""A project on a machine that has no tools installed on it at all.

Every question about finding a tool carries the same trap: a machine that
happens to have the real ``jscpd`` on it answers the case instead of the case
answering itself, and it passes for a reason it never asserted. So the search
path is emptied down to one directory holding nothing, and each case installs
exactly what it is about — into the project's own bins, or onto the machine,
which is the difference several of them turn on.

What an installed tool looks like is ``executable_stub``'s: its shape is the
real host's question, not the platform seam's.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def project_with_no_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project directory whose machine carries nothing habit-hooks could run."""
    machine_bin(tmp_path).mkdir()
    monkeypatch.setenv("PATH", str(machine_bin(tmp_path)))
    project = tmp_path / "project"
    project.mkdir()
    return project


def machine_bin(tmp_path: Path) -> Path:
    """The one directory that machine's ``PATH`` holds."""
    return tmp_path / "machine-bin"
