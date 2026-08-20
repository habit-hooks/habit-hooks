"""CLI plumbing shared by every console script (#103).

Two contracts live here so the four entry points state them the same way:

* ``--version`` prints ``habit-hooks vX.Y.Z`` from the installed distribution —
  the tool ships through four channels (PyPI, Homebrew, uvx, an npm shim) and a
  bug report has to be able to say which version it is against.
* ``ToolError`` reserves exit **2** for a failure of the tool itself — a bad
  config, an unresolvable ref, a missing plugin — so a CI wrapper can tell it
  apart from the **1** an enforced finding exits with. It subclasses
  ``SystemExit`` so an uncaught one still fails loudly rather than reading as a
  clean run; ``run_console`` maps it to 2 at every entry point.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Callable
from importlib.metadata import version

EXIT_TOOL_ERROR = 2


class ToolError(SystemExit):
    """A failure of the tool itself, as opposed to a finding: exit 2, not 1."""


class ConfigError(ToolError):
    """A rejected config, raised where the running binary is not known.

    The config loader serves all three console scripts — and any third-party
    caller besides — so it must not name one of them. ``run_console`` adds the
    name as it prints the failure; being a ``ToolError`` it still exits 2, named
    or not.
    """


def ensure_utf8_streams() -> None:
    """Make stdin, stdout and stderr UTF-8, whatever codepage the console is in.

    habit-mapper prints guide text with box-drawing characters
    (``── smell (n issues) ──``); on a non-UTF-8 console (cp1252 is Windows'
    default) writing one raises ``UnicodeEncodeError`` — the write-side twin of
    the read-side decode bug #133 was filed for, and the reason a console that
    got past the decode could still die on the very first line it prints.
    ``habit-mapper``/``habit-snooze`` read the findings pipe off ``sys.stdin``,
    which decodes in the same locale unless reconfigured the same way — the
    identical bug on the one stream #133's fix skipped. ``reconfigure`` exists
    on every stream CPython hands a console script by default; called more
    than once, as it is by both ``run_console`` and ``habit_hooks.hooks.main``,
    it is a no-op the second time. Stdin alone is wrapped in
    ``contextlib.suppress``: a real console always gives one that supports it,
    but a test's own stand-in (pytest's captured stdin, a bare ``io.StringIO``)
    need not, and neither is this project's to fix.
    """
    with contextlib.suppress(AttributeError):
        sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def version_line() -> str:
    return f"habit-hooks v{version('habit-hooks')}"


def add_version_flag(parser: argparse.ArgumentParser) -> None:
    """Give ``parser`` the ``--version`` flag every console script shares."""
    parser.add_argument("--version", action="version", version=version_line())


def _named(error: ToolError, program: str) -> str:
    """The line to print for ``error``, prefixed with ``program`` if it needs it.

    A ``ConfigError`` comes out of the loader all three console scripts share,
    which cannot know which binary the user ran; every other ``ToolError`` is
    raised where the name is known and already carries it.
    """
    return f"{program}: {error}" if isinstance(error, ConfigError) else str(error)


def run_console(
    program: str,
    body: Callable[[list[str]], int],
    argv: list[str] | None,
) -> int:
    """A console script's entry point: run ``body`` over ``argv`` (defaulting to
    ``sys.argv``) and map a ``ToolError`` to exit 2. An argparse usage error (its
    own ``SystemExit(2)``) and ``--version``'s ``SystemExit(0)`` are not
    ``ToolError`` and pass through unchanged, so a bad flag stays 2 and a version
    query stays 0.

    ``program`` is the binary this entry point *is*. It is the only place that
    knows, which is why an unnamed failure is named here rather than threaded
    through everything a console script calls.
    """
    ensure_utf8_streams()
    try:
        return body(argv if argv is not None else sys.argv[1:])
    except ToolError as error:
        sys.stderr.write(f"{_named(error, program)}\n")
        return EXIT_TOOL_ERROR
