"""The CLI contract restored in #103.

Every console script answers ``--version`` with the installed distribution's
version, and the exit code tells the tool's *own* failure (2 — a bad config, an
unresolvable ref, a missing plugin) from an enforced finding (1). A CI wrapper
that could not tell the two apart is the whole reason this matters.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

import pytest

from git_repo import repository_with_committed_file
from habit_hooks import hooks, mapper, sensors, snooze

_VERSION_LINE = f"habit-hooks v{version('habit-hooks')}"


@pytest.mark.parametrize("main", [sensors.main, mapper.main, snooze.main])
def test_an_argparse_script_prints_the_distribution_version(
    main: Callable[[list[str]], int], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_:
        main(["--version"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out.strip() == _VERSION_LINE


def test_the_pipeline_entry_point_also_reports_the_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``habit-hooks`` forwards its args to two subprocesses, so it must answer
    ``--version`` itself rather than pipe the string through as findings JSON."""
    assert hooks.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == _VERSION_LINE


def test_a_tool_failure_exits_two_not_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unresolvable base ref is the tool's own failure, not a finding: exit 2,
    distinct from the 1 an enforced finding uses (see ``test_mapper`` for the 1).
    """
    repository_with_committed_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert sensors.main(["--branch", "nope"]) == 2


@pytest.mark.parametrize("value", ["0", "-1"])
def test_last_rejects_a_non_positive_count_by_name(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--last 0`` scoped nothing and ``--last -1`` resolved to ``HEAD~-1`` and
    degraded to the empty tree — both silently scanned everything. A non-positive
    count now fails by name with the usage-error exit 2, before any scope path."""
    with pytest.raises(SystemExit) as failure:
        sensors.parse_args(["--last", value])
    assert failure.value.code == 2
    assert "--last" in capsys.readouterr().err
