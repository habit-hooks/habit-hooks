"""Which commands are live, and what an interrupt does to them.

A ``KeyboardInterrupt`` is delivered to the main thread only, and sensors spawn
from worker threads — so the thread that hears the interrupt is never the thread
holding the process. The registry is how the one ends the commands on behalf of
the others, and these cases ask it which pids it ends and when.

*How* one is ended is ``test_live_commands.py``, one platform at a time; here it
is stood in for, because which command the registry reaches for is the same
question on either. The one exception is the case below that keeps the whole
path honest on Windows, where an interrupt has to reach a real ``taskkill``.
"""

from __future__ import annotations

import pytest
from platform_probe import on_windows, recorded_spawns

from habit_hooks.sensors import live_commands


def _kills(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The pids the registry ends, standing in for ending them."""
    kills: list[int] = []
    monkeypatch.setattr(live_commands, "kill_command", kills.append)
    return kills


def test_nothing_live_is_nothing_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    kills = _kills(monkeypatch)

    live_commands._LiveCommands().interrupt()

    assert kills == []


def test_an_interrupt_ends_every_live_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every sensor is a worker blocked on its own command's deadline: up to
    five minutes of frozen terminal, during exactly the hang that made somebody
    press the key. Ending the commands unblocks all of them at once."""
    kills = _kills(monkeypatch)
    live = live_commands._LiveCommands()

    with live.tracking(11), live.tracking(22):
        live.interrupt()

    assert set(kills) == {11, 22}


def test_a_finished_command_is_no_longer_live(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry forgets a command as its block ends, so a later interrupt
    cannot kill a pid the operating system has since handed to somebody else."""
    kills = _kills(monkeypatch)
    live = live_commands._LiveCommands()

    with live.tracking(11):
        pass
    live.interrupt()

    assert kills == []


def test_a_command_started_after_the_interrupt_is_ended_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It would otherwise run to its own deadline with nobody left waiting for
    its output, blocking the thread the interrupted main thread is joining."""
    kills = _kills(monkeypatch)
    live = live_commands._LiveCommands()
    live.interrupt()

    with live.tracking(33):
        assert kills == [33]


def test_on_windows_an_interrupt_reaches_the_kill_that_platform_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole path, unstubbed, on the platform whose kill is a command rather
    than a call: an interrupt has to end a live command there too, and it is the
    thread that heard it doing so."""
    on_windows(monkeypatch)
    spawns = recorded_spawns(monkeypatch)
    live = live_commands._LiveCommands()

    with live.tracking(11), live.tracking(22):
        live.interrupt()

    assert {argv[-1] for argv, _ in spawns} == {"11", "22"}
