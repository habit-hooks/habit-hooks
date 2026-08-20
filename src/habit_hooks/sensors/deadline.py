"""How long a command may run, and what is left of it when it may not run on.

The waiting half of a spawn: ``spawn.py`` starts the process, this waits on it
under a ceiling, and ``live_commands.py`` is what ends one. A wedged tool —
waiting on input, or churning on a pathological repo — otherwise blocks the git
hook forever with no output, so a finite ceiling is what makes it return.

Killing it is not the end of the story. Whatever it managed to print first is
the only clue to what it was stuck on, and that does not come back from the
timeout itself: on Windows each pipe is drained by a thread sitting in a single
read that ends when the pipe closes and not before, so ``TimeoutExpired`` there
carries nothing at all and the notice lost the one line worth reading. The kill
closes that pipe, so asking a second time — the idiom ``subprocess``'s own
documentation gives for this — is what collects it, on either platform.
"""

from __future__ import annotations

import subprocess

from .live_commands import kill_command

# Seconds one invocation may run before it is killed.
DEFAULT_SENSOR_TIMEOUT_SECONDS = 300.0

# Seconds a killed command gets to be read to its end. It is already dead, so
# this is only the pipe draining — unless something the kill could not reach is
# still holding the far end open, which is why the wait is bounded at all
# rather than being the endless one a plain ``communicate()`` would be.
LAST_WORDS_TIMEOUT_SECONDS = 5.0


def bounded_output(
    process: subprocess.Popen[str], stdin: str, timeout: float
) -> subprocess.CompletedProcess[str]:
    """What it printed, killing the whole command if it ran past its deadline.

    The ``TimeoutExpired`` travels on, carrying what the command had said by
    the time it died (:func:`_with_last_words`) — but the command dies first,
    so nothing it started is still running once the hook has returned. An
    interrupt on this thread ends it the same way; the sensors run on threads
    that never receive one, and ``LIVE_COMMANDS`` is what answers for those.
    """
    try:
        stdout, stderr = process.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired as expiry:
        kill_command(process.pid)
        raise _with_last_words(process, expiry) from None
    except KeyboardInterrupt:
        kill_command(process.pid)
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def _with_last_words(
    process: subprocess.Popen[str], expiry: subprocess.TimeoutExpired
) -> subprocess.TimeoutExpired:
    """The same timeout, carrying everything the killed command had said.

    Read after the kill rather than out of ``expiry``, because a deadline that
    passes while a pipe is still being drained is not a platform-independent
    amount of output: POSIX hands over the partial reads, Windows hands over
    nothing. Reading the closed pipe is one answer for both, and it is the
    fuller one — anything printed between the deadline and the kill is in it
    too.

    A read that fails in its turn — a pipe something the kill could not reach
    is still holding open, or anything else a second read can raise — leaves
    the original expiry standing. This runs inside the handler reporting the
    timeout, so a failure raised from here would replace the failure being
    reported with itself, and the notice is never worse for having asked.
    """
    try:
        stdout, stderr = process.communicate(timeout=LAST_WORDS_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return expiry
    return subprocess.TimeoutExpired(process.args, expiry.timeout, stdout, stderr)
