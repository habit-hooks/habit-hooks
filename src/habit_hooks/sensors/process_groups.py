"""The command groups this run has started, and how to end them.

Every part is spawned into a session of its own (``spawn.py``), so one command
— a pipeline's tools included — is one process group a single signal reaches.
That also takes the group out of ours: nothing that used to signal us
collectively reaches it any more, so ending one is something the run now has to
do deliberately, and a registry of what is live is what it does it with.

Keeping that registry here rather than in ``spawn.py`` is the split between
starting a command and ending one: ``execution`` ends them without spawning
anything, on the thread that heard the interrupt.
"""

from __future__ import annotations

import contextlib
import os
import signal
import threading
from collections.abc import Iterator


def kill_group(pgid: int) -> None:
    """Kill everything one command started, not just the program it started with.

    Each spawn is a session leader, so its pid is also its process group id and
    one signal reaches the whole pipeline. A group already empty means it all
    exited between the decision and the signal, which is the outcome we wanted.
    The leader itself is reaped by the ``Popen`` context manager; the tools it
    started are its children, and init reaps those.
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
