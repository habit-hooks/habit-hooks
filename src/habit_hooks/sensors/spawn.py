"""Spawn a part's argv as a bounded, isolated subprocess.

Every sensor and transformer arrives here as an argument list, already built by
``command_text`` — including the ``bash -c`` around a part that wanted a shell,
which is that module's decision and not this one's. Three things keep an
unusual-but-real run from turning into a hang or a lost run: a deadline
(``deadline.py`` — a wedged tool must not block the git hook forever), an own
empty stdin (the child must never inherit the parent's — a ``pre-push`` hook
carries refs there), and a program named by the file this project actually runs
for it rather than by a name the platform is left to look up its own way
(``project_paths.tool_executable``). What any of them failing then becomes is
``broken_part.py``, which knows the part this argv belongs to where nothing
here does.

The deadline is why this is ``Popen`` and not ``subprocess.run``: ``run`` kills
the program it started and nothing else, while a part is often a pipeline
(``ruff ... | jq ...``) or a helper spawning its own tool, whose processes are
that program's children, not ours. Giving each spawn a process group of its own
is what makes the whole command one thing the deadline can end — and it also
takes it out of ours, so nothing that used to signal us collectively reaches it
any more. ``live_commands`` is how the run ends them deliberately, on either
platform, and a CI runner that kills only our process tree now leaves a command
running to its own deadline where a same-group child used to die with the tree.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..project_paths import tool_executable, tool_search_path
from . import batch_shell
from .deadline import DEFAULT_SENSOR_TIMEOUT_SECONDS, bounded_output
from .live_commands import LIVE_COMMANDS, its_own_process_group
from .part_output import command_not_found, no_project_to_run_in


@dataclass(frozen=True)
class Spawner:
    """Runs an argv against the project's tool bins, bounded and isolated."""

    project_dir: Path
    timeout: float = DEFAULT_SENSOR_TIMEOUT_SECONDS

    def run(self, argv: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
        """Spawn ``argv`` with the project bins on PATH, own stdin, and a deadline.

        ``stdin`` is always a string, never ``None``, so the child cannot inherit
        the parent's stdin — a tool that prompts would otherwise block on it.

        Its own process group holds the program *and* everything it starts, which
        is what lets the deadline end the whole command rather than just the
        program holding it — as far as each platform's own answer reaches
        (``live_commands``). A command nothing else can now reach is one the run
        has to keep track of, so it is registered while it lives.

        A program the system cannot find comes back as the answer a shell would
        have given for it, so one recogniser answers for both forms of part.
        Only a missing *program* is answered that way: ``Popen`` raises the very
        same ``FileNotFoundError`` when the directory it was told to run in is
        gone, and that is a broken run rather than a tool to install. Which of
        the two it was is this layer's to say either way — Windows' own words
        for the refusal name neither the program nor the directory
        (``part_output.no_project_to_run_in``).
        """
        try:
            return self._spawned(self._runnable(argv), stdin)
        except FileNotFoundError:
            if not self.project_dir.is_dir():
                raise no_project_to_run_in(self.project_dir) from None
            return command_not_found(argv)

    def _runnable(self, argv: list[str]) -> list[str]:
        """``argv`` with its program named by the file this project runs for it.

        A bare command name is the only thing in question. Left as a name it is
        looked up by whatever the spawn uses, which on Windows is not the
        lookup the tool was cleared by — so this asks the one that cleared it
        (``project_paths.tool_executable``) and hands the spawn its answer.
        Anything already carrying a directory is a file and not a name: an
        absolute interpreter from ``${python}``, a helper's own path. So is
        every argument after the first, whatever it looks like — only the
        program is being spawned.

        A name reaching no file is handed over as it stands rather than refused
        here. The spawn then fails exactly as it always did, which leaves the
        one guard in :meth:`run` reading the one ``FileNotFoundError`` it was
        written for — and a project directory that is gone still says so,
        instead of being reported as a tool somebody should install.

        Knowing the file is also the only way to know what will read the
        arguments: a ``.bat`` or ``.cmd`` program is run by ``cmd.exe``, whose
        syntax nothing here quotes for (``batch_shell``). Both ways of arriving
        at a program pass through the refusal, since a part may name a batch
        file by its path just as easily as by its name.
        """
        found = (
            None
            if os.path.dirname(argv[0])
            else tool_executable(argv[0], self.project_dir)
        )
        runnable = argv if found is None else [found, *argv[1:]]
        batch_shell.refuse_unreadable_arguments(runnable)
        return runnable

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
            **its_own_process_group(),
        ) as process, LIVE_COMMANDS.tracking(process.pid):
            return bounded_output(process, stdin, self.timeout)

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
