"""Pin the platform a test asks about, and watch what a kill did instead of doing it.

Three modules put platform questions to the same seam — ``test_posix_shell.py``
(whether a shell recipe may run at all), ``test_live_commands.py`` (how one
command is ended) and ``test_live_command_registry.py`` (what an interrupt does
to the live ones) — so the pinning lives here once.

Pinning is what makes a platform test worth having: a case that reads its
expected answer off the host machine is green on a Mac, red on the Windows
runner, and evidence of nothing on either. ``host_platform.is_windows`` is
replaced rather than ``sys.platform``, because that function is the one seam
every platform decision in this tool asks through.

The recorders below stand in for the two ways a command is ended. Neither can be
let run: ``os.killpg`` would signal a real process group — pid 4321 is somebody
— and ``taskkill`` does not exist off Windows at all.
"""

from __future__ import annotations

import subprocess

import pytest

from habit_hooks import host_platform
from habit_hooks.sensors import live_commands


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
    """Every process group ``live_commands`` would signal, and with what."""
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        live_commands.os,
        "killpg",
        lambda pgid, number: signals.append((pgid, number)),
    )
    return signals
