"""The commands this run has started, how each is set apart, and how one is ended.

Every part is spawned into a process group of its own
(:func:`its_own_process_group`, which ``spawn.py`` hands to ``Popen``), so one
command — a pipeline's tools, a helper's tool — is one thing this run can end.
Setting it apart also takes it out of ours: nothing that used to signal us
collectively reaches it any more, so ending one is something the run has to do
deliberately, and a registry of what is live is what it does it with.

Keeping that registry here rather than in ``spawn.py`` is the split between
starting a command and ending one: ``execution`` ends them without spawning
anything of its own, on the thread that heard the interrupt.

**The two platforms do not guarantee the same amount of this.** On POSIX
``start_new_session`` makes the spawn a session and process-group leader; every
descendant inherits that group id and keeps it after the leader dies, so
``killpg`` reaches even a tool whose own parent has already exited, and
``SIGKILL`` can be neither caught nor blocked. On Windows a process group is
only ever a target for console control events — there is no call that kills one
— so ``CREATE_NEW_PROCESS_GROUP`` buys the isolation from the console's Ctrl-C
and nothing at all towards the deadline. Ending a command there is
``taskkill /T /F``, which walks *live* parent links down from the pid it is
given: ``/F`` terminates as unrefusably as ``SIGKILL``, but a grandchild whose
own parent exited first is no longer reachable from that walk and lives on.
What keeps that gap narrow is that Windows runs argv parts only
(:mod:`.posix_shell`), so a command there is a tool, or a helper sitting on the
tool it spawned — and a helper waiting on its tool is still alive when the kill
arrives.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import threading
from collections.abc import Iterator

from .. import host_platform

# ``subprocess`` defines its Windows creation flags on Windows alone, so this
# asks it rather than spelling the number. Off Windows the answer is 0 — the one
# value a POSIX ``Popen`` accepts — which leaves the Windows branch spawnable,
# and therefore testable, from a machine that is not Windows.
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def its_own_process_group() -> dict:
    """The spawn arguments that put a command in a process group of its own.

    Asked per spawn rather than frozen into a module constant, so a test can
    flip ``host_platform.is_windows()`` and see the other platform's answer.
    Neither argument can simply be passed always: ``start_new_session`` is
    silently ignored on Windows, and a non-zero ``creationflags`` is refused
    everywhere else.
    """
    if host_platform.is_windows():
        return {"creationflags": CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def kill_command(pid: int) -> None:
    """Kill everything one command started, not just the program it started with.

    On POSIX the spawn is a session leader, so the pid it was given is also the
    process group id every tool it started inherited, and one signal reaches the
    whole pipeline. A group already empty means it all exited between the
    decision and the signal, which is the outcome we wanted. The leader itself
    is reaped by the ``Popen`` context manager; the tools it started are its
    children, and init reaps those.
    """
    if host_platform.is_windows():
        _taskkill_tree(pid)
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)


def _taskkill_tree(pid: int) -> None:
    """Windows' answer, which is a command to run rather than a call to make.

    Its output is captured and dropped: ``taskkill`` announces every process it
    ends on stdout, and this stage's stdout is the findings JSON the mapper
    reads. Its exit code is ignored for the same reason ``ProcessLookupError``
    is suppressed above — a pid already gone is the outcome we wanted — and so
    is a machine with no ``taskkill`` on it at all, because this runs inside the
    handler already reporting a timeout or an interrupt, and a second failure
    raised from here would replace the one being reported with itself.
    """
    with contextlib.suppress(OSError):
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )


class _LiveCommands:
    """Every command this process has spawned and not yet finished with.

    A ``KeyboardInterrupt`` is delivered to the main thread only, and sensors
    spawn from worker threads — so the thread that hears the interrupt is never
    the thread holding the process, and the worker's own handler cannot help.
    One registry, because there is one process tree, and the thread that heard
    the interrupt ends the commands on behalf of the threads that did not.

    What is tracked is the pid of the program each command was started with. On
    POSIX that number is also the process group id, because the spawn is a
    session leader; on Windows it is a pid and nothing more, which is all
    ``taskkill`` needs to walk the tree below it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pids: set[int] = set()
        self._interrupted = False

    @contextlib.contextmanager
    def tracking(self, pid: int) -> Iterator[None]:
        """Register ``pid`` for the life of the block, killing it if it is late.

        A command spawned just after the interrupt was answered would otherwise
        run to its own deadline with nobody left waiting for its output — and
        block the thread the interrupted main thread is about to join.
        """
        with self._lock:
            self._pids.add(pid)
            interrupted = self._interrupted
        if interrupted:
            kill_command(pid)
        try:
            yield
        finally:
            with self._lock:
                self._pids.discard(pid)

    def interrupt(self) -> None:
        """End every live command, so the threads running them unblock at once.

        One way only: an answered interrupt means this process is on its way
        out, so anything started after it is started into a run nobody reads.
        """
        with self._lock:
            self._interrupted = True
            pids = list(self._pids)
        for pid in pids:
            kill_command(pid)


LIVE_COMMANDS = _LiveCommands()
