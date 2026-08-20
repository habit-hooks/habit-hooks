"""What a command killed at its deadline is still able to say for itself.

A wedged tool that said *why* before it was killed is the one thing a reader
can act on, and the timeout notice is where it has to land. Getting it there is
not the same question on both platforms, and neither can be pinned by a seam:
``TimeoutExpired`` hands over the partial reads on POSIX and nothing whatever
on Windows, where each pipe is drained by a thread sitting in a single read
that ends when the pipe closes and not before. So the output is read after the
kill instead, from the pipe the kill closed — and the shapes both platforms
arrive in are scripted here rather than pinned, because they are answers
``subprocess`` gives rather than decisions this tool makes.

A real wedged sensor, killed for real, is ``test_sensor_deadline.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from habit_hooks.sensors import deadline
from habit_hooks.sensors.deadline import bounded_output
from habit_hooks.sensors.model import Part
from habit_hooks.sensors.part_output import part_timeout

ARGV = ["probe"]
PID = 4321
A_WINDOWS_EXPIRY = subprocess.TimeoutExpired(ARGV, 0.3)
A_POSIX_EXPIRY = subprocess.TimeoutExpired(ARGV, 0.3, stderr=b"cannot reach registry\n")


class _Command:
    """A process answering ``communicate`` with one scripted turn per call.

    Each turn is either what that call returns or what it raises, which is how
    ``subprocess`` behaves either side of a kill: the deadline call raises, and
    a later one returns whatever the closed pipe finally gave up.
    """

    args = ARGV
    pid = PID
    returncode = -9

    def __init__(self, *turns: object) -> None:
        self._turns = list(turns)

    def communicate(self, stdin: str = "", timeout: float = 0.0) -> object:
        turn = self._turns.pop(0)
        if isinstance(turn, BaseException):
            raise turn
        return turn


@pytest.fixture
def killed(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The commands the deadline ended, without ending anything: pid 4321 is
    somebody, and which kill a platform gets is ``test_live_commands.py``."""
    ended: list[int] = []
    monkeypatch.setattr(deadline, "kill_command", ended.append)
    return ended


def test_a_command_that_answered_in_time_is_not_killed_or_asked_again(
    killed: list[int],
) -> None:
    """The scripted turn runs out if anything asks twice, so a second read
    cannot creep into the path every sensor in every run takes."""
    result = bounded_output(_Command(("[]", "")), "", 0.3)

    assert result.stdout == "[]"
    assert killed == []


def test_a_timeout_that_carried_nothing_still_quotes_the_tool_back(
    killed: list[int],
) -> None:
    """The Windows shape, and the bug: the notice said only that the sensor had
    timed out, dropping the line the tool had already printed saying why."""
    command = _Command(A_WINDOWS_EXPIRY, ("", "cannot reach registry\n"))

    with pytest.raises(subprocess.TimeoutExpired) as timeout:
        bounded_output(command, "", 0.3)

    assert killed == [PID]
    assert timeout.value.stderr == "cannot reach registry\n"
    assert timeout.value.timeout == 0.3


def test_the_deadline_reported_is_the_one_that_passed(killed: list[int]) -> None:
    """Not the short grace the closed pipe is read within, which is neither the
    sensor's ceiling nor anything a reader could set."""
    command = _Command(A_WINDOWS_EXPIRY, ("", ""))

    with pytest.raises(subprocess.TimeoutExpired) as timeout:
        bounded_output(command, "", 0.3)

    assert timeout.value.timeout == 0.3


def test_a_pipe_that_will_not_close_leaves_the_first_answer_standing(
    killed: list[int], tmp_path: Path
) -> None:
    """Something the kill could not reach can hold the far end of the pipe open
    — a grandchild whose own parent died first, which Windows' kill walks past.
    Waiting on that forever is the hang the deadline exists to stop, so the read
    is bounded too, and what the timeout already carried is what gets reported.
    """
    command = _Command(A_POSIX_EXPIRY, subprocess.TimeoutExpired(ARGV, 5.0))
    part = Part(name="probe", directory=tmp_path, argv=ARGV)

    with pytest.raises(subprocess.TimeoutExpired) as timeout:
        bounded_output(command, "", 0.3)

    assert timeout.value is A_POSIX_EXPIRY
    assert "cannot reach registry" in str(part_timeout("sensor", part, timeout.value))
