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
import sys
from collections.abc import Callable
from importlib.metadata import version

EXIT_TOOL_ERROR = 2


class ToolError(SystemExit):
    """A failure of the tool itself, as opposed to a finding: exit 2, not 1."""


def version_line() -> str:
    return f"habit-hooks v{version('habit-hooks')}"


def add_version_flag(parser: argparse.ArgumentParser) -> None:
    """Give ``parser`` the ``--version`` flag every console script shares."""
    parser.add_argument("--version", action="version", version=version_line())


def run_console(
    parse: Callable[[list[str]], argparse.Namespace],
    body: Callable[[argparse.Namespace], int],
    argv: list[str] | None,
) -> int:
    """A console script's entry point: parse ``argv`` (defaulting to
    ``sys.argv``), run ``body`` over the parsed args, and map a ``ToolError`` to
    exit 2. An argparse usage error (its own ``SystemExit(2)``) and
    ``--version``'s ``SystemExit(0)`` are not ``ToolError`` and pass through
    unchanged, so a bad flag stays 2 and a version query stays 0.
    """
    try:
        return body(parse(argv if argv is not None else sys.argv[1:]))
    except ToolError as error:
        sys.stderr.write(f"{error}\n")
        return EXIT_TOOL_ERROR
