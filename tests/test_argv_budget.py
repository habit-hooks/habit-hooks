
from __future__ import annotations

import pytest
from platform_probe import off_windows, on_windows

from habit_hooks.argv_budget import (
    POSIX_ARGUMENT_BUDGET,
    WINDOWS_ARGUMENT_BUDGET,
    argument_budget,
    argument_cost,
    within_argument_limits,
)

BORDERLINE_ARGUMENTS = ["a" * 15_000, "b" * 6_000]


def test_the_budget_is_the_posix_number_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    off_windows(monkeypatch)

    assert argument_budget() == POSIX_ARGUMENT_BUDGET


def test_the_budget_switches_to_windows_s_when_the_platform_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    on_windows(monkeypatch)

    assert argument_budget() == WINDOWS_ARGUMENT_BUDGET


def test_paths_under_the_posix_budget_share_one_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    off_windows(monkeypatch)

    assert len(list(within_argument_limits(BORDERLINE_ARGUMENTS))) == 1


def test_the_same_paths_split_once_windows_s_narrower_budget_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    on_windows(monkeypatch)

    assert len(list(within_argument_limits(BORDERLINE_ARGUMENTS))) == 2


def test_a_batch_never_costs_more_than_the_budget() -> None:
    batches = list(within_argument_limits(["aaaa", "bbbbb"], budget=10))

    assert batches == [["aaaa"], ["bbbbb"]]
    assert all(argument_cost(batch) <= 10 for batch in batches)
