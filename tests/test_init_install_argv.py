"""Unit tests for how ``habit-hooks init`` runs the installs it offers.

Not through a shell: ``shell=True`` on Windows reads a command through
``cmd.exe``, which does not understand the single quotes ``plugin_install.py``
spells around a plugin name (``uv tool install 'habit-hooks[python]'``) — so
the very install this offers to run could not work there. Split out of
``test_init_installs.py`` once it grew this second concern, separate from
whether and in what order a command runs at all.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest
from habit_hooks import init_command
from habit_hooks.init_command import run
from init_install_fixture import FIRST, PYTHON, answering, needing, ran


def test_a_quoted_argument_reaches_the_command_as_one_piece(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``plugin_install.py`` quotes an argument exactly the way ``uv tool
    install 'habit-hooks[python]'`` shows one — for a POSIX-style reader.
    Windows' ``cmd.exe`` does not read a single quote as quoting at all; it
    passes the literal characters through, so an install run that way could
    never work there. Read back as an argv instead, the quoting is undone the
    same way on every platform, with no shell in between to disagree about
    what a quote means.
    """
    quoted = shlex.quote("habit-hooks[python]")
    needing(
        init_project,
        f'{{ name = "wobble-quoted", kind = "command", '
        f'install = "{PYTHON} mark.py {quoted}" }}',
    )
    monkeypatch.chdir(init_project)
    answering("y\n", monkeypatch)

    assert run([]) == 0
    assert ran(init_project) == ["habit-hooks[python]"]


def _recorded_commands(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple, dict]]:
    """Every ``subprocess.run`` call ``init_command`` makes, wrapping the real
    one rather than replacing it: this module's own import is the one every
    caller shares, ``git_history`` included, and a stand-in that stopped
    answering for git would break the plan a test still needs built."""
    real_run = subprocess.run
    calls: list[tuple[tuple, dict]] = []

    def _recording(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        calls.append((args, kwargs))
        return real_run(*args, **kwargs)

    monkeypatch.setattr(init_command.subprocess, "run", _recording)
    return calls


def test_the_command_is_spawned_as_an_argv_never_read_by_a_shell(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mechanism behind the case above: ``shell=True`` on Windows reads a
    command through ``cmd.exe``, so passing a raw string through one at all is
    the bug, whatever it contains. This is what proves the fix rather than a
    lucky quoting outcome — spawned as a list, with no ``shell=True`` in the
    call, on every platform, not only where a real POSIX shell happens to
    agree with ``plugin_install.py``'s own quoting.
    """
    calls = _recorded_commands(monkeypatch)
    needing(init_project, FIRST)
    monkeypatch.chdir(init_project)
    answering("y\n", monkeypatch)

    run([])

    (spawned, options) = next(call for call in calls if "mark.py" in call[0][0])
    assert isinstance(spawned[0], list)
    assert options.get("shell") is not True
