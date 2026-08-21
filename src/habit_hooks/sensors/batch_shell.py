"""What ``cmd.exe`` would read in an argument, when the program is a batch file.

``CreateProcess`` never runs a ``.bat`` or ``.cmd`` itself. It hands the whole
command line to ``cmd.exe``, which then reads it as a line of script — so ``&``,
``|``, ``<``, ``>``, ``^``, ``"``, ``%VAR%`` and a newline arrive as that shell's
syntax rather than as text. ``subprocess`` quotes an argv for the Microsoft C
runtime's parser instead, as ``list2cmdline``'s own docstring says, and the two
parsers are not the same one. That gap is CVE-2024-24576; CPython closed its half
in 3.11.9, and this project supports ``>=3.11``, so four releases that never
closed it are still installable — and CI, which takes the newest 3.11.x, is the
one machine that would never show it.

Every path a part is handed comes out of the work tree, which is somebody else's
branch. ``tests/test_execution.py``'s ``test_a_filename_can_never_execute_a_command``
exists because a file added by a pull request from a fork would otherwise run its
author's command on every reviewer's machine, and a Windows run owes the same
guarantee.

**Refused, never escaped.** Escaping means carrying a second quoter for a second
parser — right only on the interpreter versions that are wrong, and one more
thing to be subtly wrong about. Refusing needs no version to be right. No sensor
anyone ships passes an argument carrying any of these characters, so the cost is
nothing, and a refusal is the ordinary named part failure rather than a command
somebody else chose.

**The program's own name decides this, never the platform.** The extension is
what sends a spawn through ``cmd.exe``, and it is the whole of what is knowable
here; nothing off Windows installs a tool as a ``.bat``, so there is no run this
costs. Asking ``host_platform`` as well would leave the guard switched off in
every test that pins a run off Windows — and off in a helper's own copy, which
runs in a child process no test can pin at all.
"""

from __future__ import annotations

from .model import SensorError

BATCH_SUFFIXES = (".bat", ".cmd")

# Everything ``cmd.exe`` reads as other than text: the separators and pipe, both
# redirections, its own escape character, the quote that ends a quoted run, the
# ``%`` that opens a variable, and the newline that ends the line it is reading.
CMD_SYNTAX = frozenset('&|<>^"%\n\r')


class UnreadableArgument(SensorError):
    """An argument the shell behind a batch file would read as its own syntax.

    It names no part, because the spawn knows none: ``broken_part.run_part``
    prefixes the part where it does know, the way ``cli._named`` prefixes a
    binary onto a ``ConfigError``, so one wording serves the part's spawn and a
    bare one.
    """


def refuse_unreadable_arguments(argv: list[str]) -> None:
    """Stop ``argv`` before it spawns when its program's shell would read it."""
    unreadable = cmd_syntax(argv[0], argv[1:])
    if unreadable is None:
        return
    raise UnreadableArgument(
        f"cannot pass {unreadable!r} to {argv[0]!r}: a batch file is run by "
        "cmd.exe, which would read that as its own syntax rather than as text "
        "— rename the file, or keep it out of the scope with [files]"
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
