"""Setting one command apart from this process, and ending it whole.

Killing the program is not killing the command: a part is a pipeline, or a
helper sitting on the tool it spawned, and those processes are that program's
children rather than ours. Each platform answers that differently — one signal
to a process group on POSIX, a ``taskkill`` walking the process tree on Windows
— so every case here pins ``host_platform.is_windows()`` (``platform_probe``)
and asserts that platform's answer.

What the POSIX answer does to real processes is ``test_sensor_deadline.py`` and
``test_sensor_interrupt.py``, which run it against actual pipelines. ``taskkill``
cannot be run at all on the machine writing this, so the seam it goes through is
where it is observed instead: the argv it is given, and that nothing it prints
can reach the stdout the findings travel on. Which commands are live to be ended
is ``test_live_command_registry.py``.
"""

from __future__ import annotations

import signal
import subprocess
from collections.abc import Callable

import pytest
from platform_probe import off_windows, on_windows, recorded_signals, recorded_spawns

from habit_hooks.sensors import live_commands
from habit_hooks.sensors.live_commands import (
    CREATE_NEW_PROCESS_GROUP,
    its_own_process_group,
    kill_command,
)


def _raising(error: Exception) -> Callable[..., None]:
    """A stand-in that fails the way the real call would."""

    def refuse(*_args: object, **_options: object) -> None:
        raise error

    return refuse


def test_off_windows_a_command_dies_by_one_signal_to_its_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The spawn is a session leader, so its pid is also the group id every tool
    it started inherited — and ``SIGKILL`` can be neither caught nor blocked."""
    off_windows(monkeypatch)
    spawns, signals = recorded_spawns(monkeypatch), recorded_signals(monkeypatch)

    kill_command(4321)

    assert signals == [(4321, signal.SIGKILL)]
    assert spawns == []


def test_off_windows_a_group_already_gone_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Everything exited between the decision and the signal — the outcome we
    wanted, so it must not raise from inside a handler reporting a timeout."""
    off_windows(monkeypatch)
    monkeypatch.setattr(
        live_commands.os,
        "killpg",
        _raising(ProcessLookupError("no such process")),
        raising=False,
    )

    assert kill_command(4321) is None


def test_on_windows_a_command_dies_by_a_taskkill_of_its_whole_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows has no call that kills a process group, so the tree below the pid
    is walked instead: ``/T`` for the children, ``/F`` to terminate as
    unrefusably as ``SIGKILL`` does."""
    on_windows(monkeypatch)
    spawns, signals = recorded_spawns(monkeypatch), recorded_signals(monkeypatch)

    kill_command(4321)

    assert [argv for argv, _ in spawns] == [["taskkill", "/T", "/F", "/PID", "4321"]]
    assert signals == []


def test_on_windows_the_kill_never_speaks_where_the_findings_travel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``taskkill`` announces every process it ends on stdout, and this stage's
    stdout is the findings JSON the mapper reads: inherited, a kill would put
    prose in the middle of the pipe."""
    on_windows(monkeypatch)
    spawns = recorded_spawns(monkeypatch)

    kill_command(4321)

    assert [options["capture_output"] for _, options in spawns] == [True]


def test_on_windows_a_command_already_gone_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``taskkill`` reports a pid it cannot find by exiting non-zero, which is
    the outcome we wanted rather than something to raise about.

    The stand-in honours ``check`` as the real call does, or the test would pass
    on a spawn that had asked to raise and prove nothing about this at all."""
    on_windows(monkeypatch)

    def not_found(argv: list[str], **options: object) -> subprocess.CompletedProcess:
        if options.get("check"):
            raise subprocess.CalledProcessError(128, argv)
        return subprocess.CompletedProcess(argv, 128, "", "process not found")

    monkeypatch.setattr(live_commands.subprocess, "run", not_found)

    assert kill_command(4321) is None


def test_on_windows_a_machine_without_taskkill_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This runs inside the handler already reporting a timeout or an interrupt,
    so a second failure raised from here would replace the one being reported."""
    on_windows(monkeypatch)
    monkeypatch.setattr(
        live_commands.subprocess, "run", _raising(FileNotFoundError("taskkill"))
    )

    assert kill_command(4321) is None


def test_off_windows_a_spawn_asks_for_a_session_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which is what makes the pid a process group id in the first place."""
    off_windows(monkeypatch)

    assert its_own_process_group() == {"start_new_session": True}


def test_on_windows_a_spawn_asks_for_a_process_group_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``start_new_session`` is silently ignored on Windows, so asking for it
    there would look like isolation and be none. The flag is whatever
    ``subprocess`` calls ``CREATE_NEW_PROCESS_GROUP`` on the platform this runs
    on, which is 0 — inert, and the one value a POSIX spawn accepts — off
    Windows, so the branch stays reachable from here."""
    on_windows(monkeypatch)

    assert its_own_process_group() == {"creationflags": CREATE_NEW_PROCESS_GROUP}
