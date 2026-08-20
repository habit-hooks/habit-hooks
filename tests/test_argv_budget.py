"""Unit tests for the argument budget split between platforms.

``test_sensor_argv.py`` proves a sensor's own chunking end to end against
this platform's budget; this covers the platform switch underneath it
directly, so the Windows branch runs from here too, not only from a real
Windows machine. ``git_history.changed_paths`` never names a budget of its
own — it lives or dies by ``within_argument_limits``' default doing the same
platform check as everyone else, which is what the transition tests below
are for.
"""

from __future__ import annotations

import pytest

from habit_hooks import host_platform
from habit_hooks.argv_budget import (
    POSIX_ARGUMENT_BUDGET,
    WINDOWS_ARGUMENT_BUDGET,
    argument_budget,
    within_argument_limits,
)

# Two paths that together clear Windows' budget but stay well under POSIX's.
BORDERLINE_ARGUMENTS = ["a" * 15_000, "b" * 6_000]


def test_the_budget_is_the_posix_number_on_this_machine() -> None:
    assert argument_budget() == POSIX_ARGUMENT_BUDGET


def test_the_budget_switches_to_windows_s_when_the_platform_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_platform, "is_windows", lambda: True)

    assert argument_budget() == WINDOWS_ARGUMENT_BUDGET


def test_paths_under_the_posix_budget_share_one_spawn() -> None:
    assert len(list(within_argument_limits(BORDERLINE_ARGUMENTS))) == 1


def test_the_same_paths_split_once_windows_s_narrower_budget_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_platform, "is_windows", lambda: True)

    assert len(list(within_argument_limits(BORDERLINE_ARGUMENTS))) == 2
