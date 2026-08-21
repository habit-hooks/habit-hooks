"""Pin the platform a test asks about, and watch what a kill did instead of doing it.

Every module whose expected answer could differ between a Mac and Windows —
an argv budget, a venv layout, whether a shell recipe may run at all, how a
command is ended — puts that question to the same seam, so the pinning lives
here once rather than as a hand-rolled ``monkeypatch.setattr`` at each site.

Pinning is what makes a platform test worth having: a case that reads its
expected answer off the host machine is green on a Mac, red on the Windows
runner, and evidence of nothing on either. ``host_platform.is_windows`` is
replaced rather than ``sys.platform``, because that function is the one seam
every platform decision in this tool asks through.

``A_SHELL_TO_RUN_IT_WITH`` is the other half of pinning: some POSIX behaviour
(a shell must never let a filename execute its own contents; a pipeline dies
whole, not just its shell) can only be shown by really running a shell recipe,
and ``off_windows`` alone is not enough for that — it makes the code stop
refusing the part, but does not conjure a shell onto a machine that has none.
Skipping there is a question about the host, not about what the code decided,
so it stays a ``skipif`` rather than another platform branch to get wrong.

Resolving a command's name to a file is the same kind of question. Which
filenames a machine runs for a bare ``jscpd`` — ``jscpd.CMD`` on Windows, and
``jscpd`` alone off it — is that machine's own rule, put to ``shutil.which``
rather than decided anywhere in this tool, so there is no seam ``on_windows``
could flip. The two hosts answer for themselves, and each half of the story
runs on the one that can tell it.

Whether a process can be *signalled* is that kind of question too. POSIX ends
one with a signal, so the parent reads ``status: null, signal: "SIGKILL"``;
Windows has no signals at all, and Node's ``process.kill`` there calls
``TerminateProcess``, leaving an ordinary ``status: 1`` and no signal — which is
the very shape a successful findings run has. Nothing in this tool decides
that, so there is no seam to flip: each host answers for itself, and each half
of the story runs on the one that can tell it.

``A_MACHINE_THAT_CAN_MAKE_A_SYMLINK`` is the same kind of question one step
further out: not what platform this is, but what this account is *allowed* to
do on it. Windows grants symlink creation to an administrator and to Developer
Mode and to nobody else, so the two Windows machines disagree with each other —
which is why it is settled by trying it once here rather than by reading
``os.name``, and why a machine that can do it runs the case wherever it is.

The recorders below stand in for the two ways a command is ended. Neither can be
let run: ``os.killpg`` would signal a real process group — pid 4321 is somebody
— and ``taskkill`` does not exist off Windows at all.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from habit_hooks import host_platform
from habit_hooks.sensors import live_commands

A_SHELL_TO_RUN_IT_WITH = pytest.mark.skipif(
    os.name == "nt",
    reason="showing a shell recipe run takes a machine with a shell on it",
)

A_MACHINE_THAT_SPELLS_A_COMMAND_ITSELF = pytest.mark.skipif(
    os.name != "nt",
    reason="only Windows adds an extension of its own to a bare command name",
)

A_MACHINE_THAT_DOES_NOT = pytest.mark.skipif(
    os.name == "nt",
    reason="everywhere else a command is the filename it is, and a shebang runs",
)


def _symlinks_are_permitted_here() -> bool:
    """Whether this machine will let a test create a symlink at all.

    Tried rather than inferred. Windows needs ``SeCreateSymbolicLinkPrivilege``
    to make one — held by an administrator, and by any account with Developer
    Mode switched on, but by nobody else — so ``os.name`` answers the wrong
    question twice over: it would skip a privileged Windows machine that can
    run the case perfectly well, and it says nothing about a POSIX filesystem
    that refuses one.
    """
    with tempfile.TemporaryDirectory() as scratch:
        try:
            Path(scratch, "probe").symlink_to(scratch)
        except (OSError, NotImplementedError):
            return False
        return True


A_MACHINE_WITH_SIGNALS = pytest.mark.skipif(
    os.name == "nt",
    reason="a killed process only carries a signal where the platform has them",
)

A_MACHINE_WITHOUT_SIGNALS = pytest.mark.skipif(
    os.name != "nt",
    reason="only Windows ends a process with TerminateProcess, leaving an exit code",
)

A_MACHINE_THAT_CAN_MAKE_A_SYMLINK = pytest.mark.skipif(
    not _symlinks_are_permitted_here(),
    reason=(
        "creating a symlink needs SeCreateSymbolicLinkPrivilege on Windows, so "
        "a symlinked node_modules — pnpm's ordinary layout, and the shape issue "
        "#142 came from — is unmeasured on a machine without it (see #137 for "
        "why a platform gap is skipped out loud rather than passed over)"
    ),
)


def on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host_platform, "is_windows", lambda: True)


def off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host_platform, "is_windows", lambda: False)


def recorded_spawns(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], dict]]:
    """Every command ``live_commands`` would spawn, with the options it passed."""
    spawns: list[tuple[list[str], dict]] = []

    def record(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        spawns.append((argv, options))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(live_commands.subprocess, "run", record)
    return spawns


def recorded_signals(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Every process group ``live_commands`` would signal, and with what.

    ``raising=False``: Windows' own ``os`` has no ``killpg`` to replace, and
    ``monkeypatch.setattr`` refuses to patch an attribute that does not exist.
    The POSIX branch is only ever reached with ``host_platform.is_windows()``
    pinned false, so this stand-in is what makes that branch — not the real
    host platform — testable everywhere.
    """
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        live_commands.os,
        "killpg",
        lambda pgid, number: signals.append((pgid, number)),
        raising=False,
    )
    return signals
