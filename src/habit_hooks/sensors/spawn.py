"""Spawn a part's command as a bounded, isolated subprocess.

Every sensor and transformer is a shell command run against the project's own
tool binaries. Two things keep an unusual-but-real run from turning into a hang
or a lost run: a deadline (a wedged tool must not block the git hook forever) and
an own empty stdin (the child must never inherit the parent's — a ``pre-push``
hook carries refs there). ``run_part`` adds the third at the caller's boundary:
a spawn failure surfaced as the ``SensorError`` every other failure already is.

The deadline is why this is ``Popen`` and not ``subprocess.run``: ``run`` kills
the shell it started and nothing else, and a sensor command is a pipeline
(``ruff ... | jq ...``) whose tools are the shell's children, not ours. Giving
each command its own session is what makes one signal reach all of it — and it
also takes it out of ours, so nothing that used to signal us collectively
reaches it any more. ``LIVE_GROUPS`` is how the run signals them deliberately,
and a CI runner that kills only our process tree now leaves a command running
to its own deadline where a same-group child used to die with the tree.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from ..project_paths import tool_search_path
from .model import Part
from .part_output import part_spawn_failure, part_timeout

# Seconds one invocation may run before it is killed. A wedged tool — waiting on
# input, or churning on a pathological repo — otherwise blocks the hook forever
# with no output; a finite ceiling makes it return.
DEFAULT_SENSOR_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class Spawner:
    """Runs a command against the project's tool bins, bounded and isolated."""

    project_dir: Path
    timeout: float = DEFAULT_SENSOR_TIMEOUT_SECONDS

    def run(self, command: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        """Shell out with the project bins on PATH, an own stdin, and a deadline.

        ``stdin`` is always a string, never ``None``, so the child cannot inherit
        the parent's stdin — a tool that prompts would otherwise block on it.

        Its own session makes the shell *and* everything it starts one process
        group, which is what lets the deadline kill the whole command rather than
        just the shell holding it. A group nothing else can now reach is a group
        the run has to keep track of, so it is registered while it lives.
        """
        with subprocess.Popen(
            ["bash", "-c", command],
            cwd=self.project_dir,
            env=self._path_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # A sensor is a third-party tool this run does not control, but the
            # findings JSON it prints is always ours to expect as UTF-8 — the
            # locale must never be what decides. ``errors="replace"`` rather than
            # the default "strict": one invalid byte in a tool's chatter must not
            # take the whole sensor down with it, and a replacement character
            # sitting in a quoted-back message is a visible sign something was
            # lost, not a silent one.
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        ) as process, LIVE_GROUPS.tracking(process.pid):
            return _bounded_output(process, stdin, self.timeout)

    def _path_env(self) -> dict:
        return {
            **os.environ,
            "PATH": tool_search_path(self.project_dir),
            # Every helper habit-hooks itself ships is a Python script whose
            # print() would otherwise encode in the child's locale — cp1252 on
            # Windows — and a helper's stderr is arbitrary text part_output
            # quotes back verbatim, not JSON that escapes its way to safety
            # like a sensor's findings do. A third-party tool cannot be told
            # this, which is why errors="replace" above remains the fallback
            # for everything else this run spawns.
            "PYTHONIOENCODING": "utf-8",
        }


def _bounded_output(
    process: subprocess.Popen[str], stdin: str, timeout: float
) -> subprocess.CompletedProcess[str]:
    """What it printed, killing the whole command if it ran past its deadline.

    The ``TimeoutExpired`` travels on untouched — it carries the partial output
    ``part_timeout`` quotes back, as the raw bytes it has always been — but the
    group dies first, so nothing the command started is still running once the
    hook has returned. An interrupt on this thread ends it the same way; the
    sensors run on threads that never receive one, and ``LIVE_GROUPS`` is what
    answers for those.
    """
    try:
        stdout, stderr = process.communicate(stdin, timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        kill_group(process.pid)
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def kill_group(pgid: int) -> None:
    """Kill everything one command started, not just the shell that started it.

    Each command's shell is a session leader, so its pid is also its process
    group id and one signal reaches the whole pipeline. A group already empty
    means it all exited between the decision and the signal, which is the
    outcome we wanted. The shell itself is reaped by the ``Popen`` context
    manager; the tools it started are its children, and init reaps those.
    """
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGKILL)


class _LiveGroups:
    """Every command group this process has spawned and not yet finished with.

    A ``KeyboardInterrupt`` is delivered to the main thread only, and sensors
    spawn from worker threads — so the thread that hears the interrupt is never
    the thread holding the process, and the worker's own handler cannot help.
    One registry, because there is one process tree, and the thread that heard
    the interrupt ends the commands on behalf of the threads that did not.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pgids: set[int] = set()
        self._interrupted = False

    @contextlib.contextmanager
    def tracking(self, pgid: int) -> Iterator[None]:
        """Register ``pgid`` for the life of the block, killing it if it is late.

        A command spawned just after the interrupt was answered would otherwise
        run to its own deadline with nobody left waiting for its output — and
        block the thread the interrupted main thread is about to join.
        """
        with self._lock:
            self._pgids.add(pgid)
            interrupted = self._interrupted
        if interrupted:
            kill_group(pgid)
        try:
            yield
        finally:
            with self._lock:
                self._pgids.discard(pgid)

    def interrupt(self) -> None:
        """End every live command, so the threads running them unblock at once.

        One way only: an answered interrupt means this process is on its way
        out, so anything started after it is started into a run nobody reads.
        """
        with self._lock:
            self._interrupted = True
            pgids = list(self._pgids)
        for pgid in pgids:
            kill_group(pgid)


LIVE_GROUPS = _LiveGroups()


def run_part(
    kind: str, part: Part, run: Callable[[], subprocess.CompletedProcess[str]]
) -> subprocess.CompletedProcess[str]:
    """``run()``'s result, its spawn failures raised as the ``SensorError`` they are.

    A wedged tool that never returns must not block the hook: its deadline
    becomes the same notice + failed run any other spawn failure produces. A
    spawn the operating system refuses outright is that failure one step
    earlier, and raises an ``OSError`` nothing between here and ``main`` caught.
    """
    try:
        return run()
    except subprocess.TimeoutExpired as expiry:
        raise part_timeout(kind, part, expiry) from None
    except OSError as refusal:
        raise part_spawn_failure(kind, part, refusal) from None
