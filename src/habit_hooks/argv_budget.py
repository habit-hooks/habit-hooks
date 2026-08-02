"""Split a list of arguments into command lines the operating system will spawn.

Two subprocess layers hand a work-tree-sized list of paths to a child — git
(``git_history``) as pathspecs, the sensors (``sensors/execution``) as a tool's
file arguments. Both can overflow what a single spawn accepts, and both degrade
badly when they do: git reads the failed spawn as "nothing changed", a sensor
lets the raw ``OSError`` escape as a traceback. One budget answers for both so
the limit cannot be right in one place and wrong in the other.
"""

from __future__ import annotations

from collections.abc import Iterator

# Bytes of argument text per spawned command line. Well under the smallest
# ARG_MAX we run on (macOS, 1MB) and the smallest single-element cap (Linux
# MAX_ARG_STRLEN, 128KB), leaving room for the command and environment a spawn
# carries around the arguments.
ARGUMENT_BUDGET = 100_000


def within_argument_limits(arguments: list[str]) -> Iterator[list[str]]:
    """Batches of ``arguments`` each small enough for one ``subprocess`` spawn.

    A single argument longer than the budget still ships alone: splitting inside
    one path would corrupt it, and the caller's per-batch spawn is where the
    operating system, not this budget, has the final say.
    """
    batch: list[str] = []
    length = 0
    for argument in arguments:
        if batch and length + len(argument) > ARGUMENT_BUDGET:
            yield batch
            batch, length = [], 0
        batch.append(argument)
        length += len(argument) + 1
    if batch:
        yield batch
