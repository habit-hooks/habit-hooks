"""Split a list of arguments into command lines the operating system will spawn.

Two subprocess layers hand a work-tree-sized list of paths to a child — git
(``git_history``) as pathspecs, the sensors (``sensors/execution``) as a tool's
file arguments. Both can overflow what a single spawn accepts, and both degrade
badly when they do: git reads the failed spawn as "nothing changed", a sensor
lets the raw ``OSError`` escape as a traceback. One budget answers for both so
the limit cannot be right in one place and wrong in the other — and the budget
is one more thing that answers differently depending on
``host_platform.is_windows()``, the same way the venv's executable directory
does.

The caller hands in the text the spawn will carry, not the text it started from:
a sensor quotes its paths first (``it's.py`` costs 12 bytes on a command line,
not 7) and pays for the command wrapped around them out of the same budget.
"""

from __future__ import annotations

from collections.abc import Iterator

from . import host_platform

# Bytes of argument text per spawned command line, elsewhere than Windows.
# Well under the smallest ARG_MAX we run on (macOS, 1MB) and the smallest
# single-element cap (Linux MAX_ARG_STRLEN, 128KB) — the sensors splice a
# whole batch into one ``bash -c`` argument, so that per-element cap is the
# binding one there.
POSIX_ARGUMENT_BUDGET = 100_000

# Windows has neither limit; ``CreateProcess`` instead caps the *entire*
# command line at 32,767 characters, shared by every caller: the interpreter
# or shell wrapped around the paths, the paths themselves, and (for a sensor)
# the quoting each one costs. 20,000 leaves close to 13,000 characters of
# headroom for the rest of that command line — real margin under the cap
# without shrinking the batches so far that a work-tree-sized scope needs an
# unreasonable number of spawns.
WINDOWS_ARGUMENT_BUDGET = 20_000


def argument_budget() -> int:
    """The argument budget for this platform, asked fresh every call.

    A function rather than a constant so a test can flip
    ``host_platform.is_windows()`` and see the other platform's number — a
    module-level constant would freeze whichever platform was true at import.
    """
    return WINDOWS_ARGUMENT_BUDGET if host_platform.is_windows() else POSIX_ARGUMENT_BUDGET


def argument_cost(arguments: list[str]) -> int:
    """What ``arguments`` spend of a budget, counted as the batching counts.

    The fixed part of a spawn — the shell or interpreter wrapped around a batch,
    the flags before it — comes out of the same budget the batch is measured
    against, so it has to be measured the same way or the two do not add up.
    """
    return sum(len(argument) + 1 for argument in arguments)


def within_argument_limits(
    arguments: list[str], budget: int | None = None
) -> Iterator[list[str]]:
    """Batches of ``arguments`` each small enough for one ``subprocess`` spawn.

    Arguments are measured exactly as given, so a caller that quotes them quotes
    before batching; one with a fixed cost around the batch — a sensor's command
    template — passes what is left of the budget after paying it. ``budget``
    left unset asks :func:`argument_budget` for this platform's own.

    A single argument longer than the budget still ships alone: splitting inside
    one path would corrupt it, and the caller's per-batch spawn is where the
    operating system, not this budget, has the final say.
    """
    if budget is None:
        budget = argument_budget()
    batch: list[str] = []
    length = 0
    for argument in arguments:
        if batch and length + len(argument) > budget:
            yield batch
            batch, length = [], 0
        batch.append(argument)
        length += len(argument) + 1
    if batch:
        yield batch
