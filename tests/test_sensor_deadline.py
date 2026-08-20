"""A sensor that never returns must not hang the hook forever, and killing it
must not leave the tool it wrapped running behind it.

This is the deadline half of running a sensor's command: the timeout itself,
what a killed sensor's notice says, and that the whole process group — not
just the shell — dies with it (issue #96). The other half — an own stdin, and
reaching the project's own tools — is ``test_sensor_environment.py``. How a
command's argv is bounded is ``test_sensor_argv.py``; how a finished failure is
described is ``test_part_output.py``.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def _timed_out_notice(tmp_path: Path, command: str) -> str:
    """The notices a sensor wedged by ``command`` leaves on its failed run."""
    part = Part(name="probe", command=command, directory=tmp_path)
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/a.py"]), timeout=0.3
    )

    run = execution.run_sensors([part])

    assert run.failed
    return "\n".join(run.notices)


def test_a_wedged_sensor_times_out_into_a_failed_run(tmp_path: Path) -> None:
    """A tool that never returns must not hang the hook forever.

    A sensor waiting on input or churning on a pathological repo blocks the git
    hook with no output. The deadline turns that into the same notice + failed
    run any other spawn failure produces, so the run reports and moves on.
    """
    part = Part(name="probe", command="sleep 5; printf '[]'", directory=tmp_path)
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/a.py"]), timeout=0.2
    )

    run = execution.run_sensors([part])

    assert run.findings == []
    assert run.failed
    assert any("timed out" in notice for notice in run.notices)


def test_a_wedged_sensor_quotes_back_the_little_it_managed_to_say(
    tmp_path: Path,
) -> None:
    """What it printed before the kill is the only clue, so it must read as text.

    ``TimeoutExpired`` carries raw bytes whatever the spawn was told, so the
    diagnosis reached the notice as a ``b'...'`` repr — the tool's own words
    wrapped in Python syntax, in the one place a user has nothing else to go on.
    """
    notice = _timed_out_notice(tmp_path, "echo 'cannot reach registry' >&2; sleep 5")

    assert "cannot reach registry" in notice
    assert "b'" not in notice


def test_a_wedged_sensor_that_said_a_lot_is_still_a_notice(tmp_path: Path) -> None:
    """A timeout after a warning storm must not crash the run reporting it.

    Past ``DIAGNOSIS_LINE_LIMIT`` the diagnosis is truncated by joining lines,
    and joining raw bytes raises ``TypeError`` — uncaught anywhere above, so a
    chatty wedged tool took the whole run down with a traceback instead of
    leaving the notice + failed run every other spawn failure produces.
    """
    storm = 'for i in $(seq 1 25); do echo "warning $i" >&2; done; sleep 5'

    notice = _timed_out_notice(tmp_path, storm)
    lines = notice.splitlines()

    assert "warning 1" in lines
    assert "warning 10" in lines
    assert "warning 11" not in lines
    assert "warning 15" not in lines
    assert "warning 16" in lines
    assert "warning 25" in lines
    assert "... 5 lines omitted ..." in notice


def test_a_wedged_sensor_printing_undecodable_bytes_is_still_a_notice(
    tmp_path: Path,
) -> None:
    """Output that is not text at all must not crash the crash handler.

    A tool killed mid-character, or one printing binary, leaves bytes no codec
    accepts. Decoding them strictly would raise from inside the very path that
    exists to report a failure, losing the timeout it was called to describe.
    """
    notice = _timed_out_notice(tmp_path, r"printf 'sad \377\376 end' >&2; sleep 5")

    assert "timed out" in notice
    assert "sad" in notice
    assert "end" in notice
    assert "b'" not in notice


def _surviving_pids(marker: str) -> list[str]:
    """The processes still running a command tagged ``marker``, given time to die.

    A signalled process does not vanish the instant the signal is sent, so this
    polls rather than sleeping a guessed amount: it answers at once when the
    group is already gone, and only waits out the deadline when something lived.
    """
    deadline = time.monotonic() + 5
    while True:
        found = subprocess.run(
            ["pgrep", "-f", marker],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        pids = found.stdout.split()
        if not pids or time.monotonic() > deadline:
            return pids
        time.sleep(0.05)


def test_a_timed_out_sensor_takes_its_whole_pipeline_with_it(tmp_path: Path) -> None:
    """Killing the shell is not killing the command.

    A sensor is a pipeline — the shipped ``ruff`` and ``eslint`` sensors both
    pipe their tool through ``jq`` — and those tools are children of the ``bash``
    we spawned, not of us. Killing ``bash`` alone left them running as orphans
    past the hook that started them, so the wedged tool the deadline exists to
    stop went on churning, invisibly, with nothing left to report it to.
    """
    marker = f"habit_hooks_probe_{uuid.uuid4().hex}"
    sleeper = f"{shlex.quote(sys.executable)} -c 'import time; time.sleep(30)' {marker}"
    part = Part(name="probe", command=f"{sleeper} | {sleeper}", directory=tmp_path)
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/a.py"]), timeout=1.0
    )

    run = execution.run_sensors([part])

    assert run.failed
    assert _surviving_pids(marker) == []
