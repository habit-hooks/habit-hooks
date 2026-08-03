"""What an interrupt does to a run already in flight.

``Ctrl-C`` is delivered to the main thread alone, but sensors spawn from worker
threads and their tools live in their own process groups — so ending them is
nobody's job unless somebody arranges it (issue #96)."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

WEDGED_RUN = """
import os, sys
from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part

marker = os.environ["HABIT_HOOKS_PROBE_MARKER"]
sleeper = f"{sys.executable} -c 'import time; time.sleep(60)' {marker}"
part = Part(name="probe", command=f"{sleeper} | {sleeper}", directory=Path("."))
Execution(
    project_dir=Path("."), scope=Scope(files=["src/a.py"]), timeout=60.0
).run_sensors([part])
"""


def _pids(marker: str) -> list[str]:
    """The processes whose command line carries ``marker`` — the sensor's tools.

    The marker travels to the run in the environment, not in its arguments, so
    what this finds is only ever the pipeline, never the tool that spawned it.
    """
    found = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True)
    return found.stdout.split()


def _within(seconds: float, condition: Callable[[], bool]) -> bool:
    """Whether ``condition`` comes true inside ``seconds``, polled not slept."""
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


@contextlib.contextmanager
def _wedged_run(marker: str, tmp_path: Path) -> Iterator[subprocess.Popen[bytes]]:
    """A habit-hooks run wedged on a marked pipeline, in a process group of its own.

    Its own group is what a terminal gives a foreground job, so signalling that
    group signals the tool exactly as ``Ctrl-C`` does — and reaches nothing the
    run has since put in a session of its own.
    """
    tool = subprocess.Popen(
        [sys.executable, "-c", WEDGED_RUN],
        cwd=tmp_path,
        env={**os.environ, "HABIT_HOOKS_PROBE_MARKER": marker},
        start_new_session=True,
    )
    try:
        assert _within(30, lambda: bool(_pids(marker))), "the sensor never started"
        yield tool
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(tool.pid, signal.SIGKILL)
        subprocess.run(["pkill", "-f", marker])
        tool.wait()


def test_an_interrupted_run_does_not_wait_out_its_sensor_deadlines(
    tmp_path: Path,
) -> None:
    """``Ctrl-C`` must end the run now, not one sensor deadline from now.

    The interrupt reaches the main thread, which is blocked collecting sensors
    that run in worker threads — where a ``KeyboardInterrupt`` is never
    delivered. The pool's shutdown then waits for every one of them, each stuck
    on its own deadline: up to five minutes of frozen terminal, during exactly
    the hang that made the user press the key. Giving the tools their own
    session took away the terminal's own answer to this, so the run has to have
    one: kill the groups from the thread that heard the interrupt.
    """
    marker = f"habit_hooks_probe_{uuid.uuid4().hex}"

    with _wedged_run(marker, tmp_path) as tool:
        os.killpg(tool.pid, signal.SIGINT)

        assert _within(20, lambda: tool.poll() is not None), "still running"
        assert _within(5, lambda: not _pids(marker)), "left its pipeline behind"
