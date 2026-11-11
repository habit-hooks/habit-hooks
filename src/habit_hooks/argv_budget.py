
from __future__ import annotations

from collections.abc import Iterator

from . import host_platform

POSIX_ARGUMENT_BUDGET = 100_000

WINDOWS_ARGUMENT_BUDGET = 20_000


def argument_budget() -> int:
    return WINDOWS_ARGUMENT_BUDGET if host_platform.is_windows() else POSIX_ARGUMENT_BUDGET


def argument_cost(arguments: list[str]) -> int:
    return sum(len(argument) + 1 for argument in arguments)


def within_argument_limits(
    arguments: list[str], budget: int | None = None
) -> Iterator[list[str]]:
    if budget is None:
        budget = argument_budget()
    batch: list[str] = []
    length = 0
    for argument in arguments:
        if batch and length + len(argument) + 1 > budget:
            yield batch
            batch, length = [], 0
        batch.append(argument)
        length += len(argument) + 1
    if batch:
        yield batch
