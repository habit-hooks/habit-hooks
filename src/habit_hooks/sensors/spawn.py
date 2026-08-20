"""Spawn a part's argv as a bounded, isolated subprocess.

Every sensor and transformer arrives here as an argument list, already built by
``command_text`` — including the ``bash -c`` around a part that wanted a shell,
which is that module's decision and not this one's. Two things keep an
unusual-but-real run from turning into a hang or a lost run: a deadline (a
wedged tool must not block the git hook forever) and an own empty stdin (the
child must never inherit the parent's — a ``pre-push`` hook carries refs
there). ``run_part`` adds the third at the caller's boundary: a spawn failure
surfaced as the ``SensorError`` every other failure already is.

The deadline is why this is ``Popen`` and not ``subprocess.run``: ``run`` kills
the program it started and nothing else, while a part is often a pipeline
(``ruff ... | jq ...``) whose tools are that program's children, not ours.
Giving each spawn its own session is what makes one signal reach all of it —
and it also takes it out of ours, so nothing that used to signal us
collectively reaches it any more. ``process_groups`` is how the run signals
them deliberately, and a CI runner that kills only our process tree now leaves a
command running to its own deadline where a same-group child used to die with
the tree.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..project_paths import tool_search_path
from .model import Part
from .part_output import command_not_found, part_spawn_failure, part_timeout
from .process_groups import LIVE_GROUPS, kill_group

# Seconds one invocation may run before it is killed. A wedged tool — waiting on
# input, or churning on a pathological repo — otherwise blocks the hook forever
# with no output; a finite ceiling makes it return.
DEFAULT_SENSOR_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class Spawner:
    """Runs an argv against the project's tool bins, bounded and isolated."""

    project_dir: Path
    timeout: float = DEFAULT_SENSOR_TIMEOUT_SECONDS

    def run(self, argv: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
        """Spawn ``argv`` with the project bins on PATH, own stdin, and a deadline.

        ``stdin`` is always a string, never ``None``, so the child cannot inherit
        the parent's stdin — a tool that prompts would otherwise block on it.

        Its own session makes the program *and* everything it starts one process
        group, which is what lets the deadline kill the whole command rather than
        just the program holding it. A group nothing else can now reach is a group
        the run has to keep track of, so it is registered while it lives.

        A program the system cannot find comes back as the answer a shell would
        have given for it, so one recogniser answers for both forms of part.
        Only a missing *program* is answered that way: ``Popen`` raises the very
        same ``FileNotFoundError`` when the directory it was told to run in is
        gone, and that is a broken run rather than a tool to install.
        """
        try:
            return self._spawned(argv, stdin)
        except FileNotFoundError:
            if not self.project_dir.is_dir():
                raise
            return command_not_found(argv)

    def _spawned(self, argv: list[str], stdin: str) -> subprocess.CompletedProcess[str]:
        """What the child printed, its group tracked for as long as it lives."""
        with subprocess.Popen(
            argv,
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
            # Such a helper also imports the modules beside it by name, which
            # needs the script's own directory on sys.path — exactly what
            # PYTHONSAFEPATH (`python -P`) removes. Empty is off; "0" is on.
            "PYTHONSAFEPATH": "",
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
