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
from habit_hooks.cli import ConfigError, ToolError, run_console

_VERSION_LINE = f"habit-hooks v{version('habit-hooks')}"
_REJECTION = "unknown config key 'severty' in [smells.duplicated-code]"


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


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_the_pipeline_entry_point_prints_its_own_usage(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Forwarded to ``habit-sensors``, the usage text lands on the pipe where
    ``habit-mapper`` expects findings JSON — so asking for help answered with a
    ``JSONDecodeError`` and the usage was never seen by anybody. It is answered
    here, before either stage is spawned, under the pipeline's own name."""
    assert hooks.main([flag]) == 0
    usage = capsys.readouterr().out
    assert usage.startswith("usage: habit-hooks ")
    for scope_flag in ("--all", "--file", "--branch", "--last", "--since"):
        assert scope_flag in usage


def test_the_sensors_stage_keeps_its_own_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The pipeline's help is the same parser under a different name, so this
    pins that naming it ``habit-hooks`` never renames the stage's own help."""
    with pytest.raises(SystemExit) as exit_:
        sensors.parse_args(["--help"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out.startswith("usage: habit-sensors ")


def test_a_tool_failure_exits_two_not_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unresolvable base ref is the tool's own failure, not a finding: exit 2,
    distinct from the 1 an enforced finding uses (see ``test_mapper`` for the 1).
    """
    repository_with_committed_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert sensors.main(["--branch", "nope"]) == 2


def test_a_malformed_config_fails_the_tool_not_the_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A config that is not TOML at all exited 1 — the code reserved for an
    enforced finding — so CI reading the exit code concluded the code had a
    smell. The tool never ran: that is a 2, on one named line (#114)."""
    config = tmp_path / ".habit-hooks" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('files = ["src/**"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert sensors.main(["--all"]) == 2
    assert capsys.readouterr().err == (
        f"habit-sensors: {config}: invalid TOML: Unclosed array"
        " (at end of document)\n"
    )


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


@pytest.mark.parametrize("program", ["habit-sensors", "habit-mapper", "habit-snooze"])
def test_a_rejected_config_names_the_binary_that_printed_it(
    program: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """One loader serves all three binaries and cannot know which one ran, so a
    hardcoded prefix sent a ``habit-mapper --config`` user hunting through
    habit-sensors for their typo. The entry point names it instead."""

    def reject(_: list[str]) -> int:
        raise ConfigError(_REJECTION)

    assert run_console(program, reject, []) == 2
    assert capsys.readouterr().err == f"{program}: {_REJECTION}\n"


def test_a_failure_that_already_names_itself_is_not_named_twice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Only a rejected config is raised where the binary is unknown; every other
    ``ToolError`` is raised somewhere that knows and says so already."""

    def fail(_: list[str]) -> int:
        raise ToolError("habit-sensors: not a git repository")

    assert run_console("habit-sensors", fail, []) == 2
    assert capsys.readouterr().err == "habit-sensors: not a git repository\n"
