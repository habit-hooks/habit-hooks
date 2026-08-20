"""Unit tests for the one place that asks what platform this run is on."""

from __future__ import annotations

import pytest

from habit_hooks import host_platform


def test_win32_is_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host_platform.sys, "platform", "win32")

    assert host_platform.is_windows() is True


def test_a_posix_platform_is_not_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host_platform.sys, "platform", "darwin")

    assert host_platform.is_windows() is False
