"""Spawn the third-party tool a sensor wraps, by the file rather than the name.

A local copy of what ``habit_hooks/sensors/spawn.py`` and its ``batch_shell`` do
for a part's own argv, and it is a copy on purpose: this plugin declares no
dependency on ``habit-hooks``, so a helper cannot import the core, and four
small copies beat a dependency that does not exist. The core's modules carry the
full reasoning; the two rules are Windows' own.

**A bare name is looked up first.** Windows' spawn appends ``.exe`` to a name and
nothing else, so the ``jscpd.CMD`` npm installs and the ``pmd.bat`` PMD ships are
found by a lookup and then unreachable by a spawn handed the name — the tool the
setup cleared, reported missing by the run. This is not a second answer to that
question: habit-hooks hands a helper a ``PATH`` of the project's own bins
(``sensors/spawn._path_env``), so ``shutil.which`` here asks exactly what cleared
the tool, along exactly the same path.

**A batch file's arguments are then ``cmd.exe``'s syntax.** ``CreateProcess``
runs a ``.bat`` or ``.cmd`` through that shell, which reads ``&``, ``|``, ``<``,
``>``, ``^``, ``"``, ``%VAR%`` and a newline as its own (CVE-2024-24576; CPython
closed its half in 3.11.9, and ``>=3.11`` is supported). A sensor's arguments are
paths out of the work tree, so one is refused rather than escaped: no tool anyone
wraps needs those characters, and refusing needs no interpreter version to be
right.
"""

from __future__ import annotations

import shutil
import subprocess

BATCH_SUFFIXES = (".bat", ".cmd")

# Everything ``cmd.exe`` reads as other than text: the separators and pipe, both
# redirections, its own escape character, the quote that ends a quoted run, the
# ``%`` that opens a variable, and the newline that ends the line it is reading.
CMD_SYNTAX = frozenset('&|<>^"%\n\r')

# Found, and refused rather than run — the code a shell keeps for a command it
# located and would not execute, and outside every wrapped tool's success set.
REFUSED_EXIT = 126


def run_tool(command: list[str]) -> subprocess.CompletedProcess[str]:
    """What ``command`` said, spawned as the file this project runs for its name.

    A name reaching no file is spawned as it stands, so the caller's own
    ``FileNotFoundError`` remains the single answer for a tool nobody installed.
    """
    program = shutil.which(command[0]) or command[0]
    unreadable = cmd_syntax(program, command[1:])
    if unreadable is not None:
        return subprocess.CompletedProcess(
            command,
            REFUSED_EXIT,
            "",
            f"{program}: cannot pass {unreadable!r} to a batch file — cmd.exe "
            "would read it as its own syntax rather than as text\n",
        )
    return subprocess.run(
        [program, *command[1:]],
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # sensors.spawn's policy
    )


def cmd_syntax(program: str, arguments: list[str]) -> str | None:
    """The first of ``arguments`` ``cmd.exe`` would read as syntax, if it reads any.

    ``None`` where ``program`` is not a batch file: nothing then stands between
    the spawn and the program, and an ``&`` in a filename is a filename.
    """
    if not program.lower().endswith(BATCH_SUFFIXES):
        return None
    return next(
        (argument for argument in arguments if CMD_SYNTAX & set(argument)), None
    )
