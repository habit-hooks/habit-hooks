
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
    assert hooks.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == _VERSION_LINE


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_the_pipeline_entry_point_prints_its_own_usage(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert hooks.main([flag]) == 0
    usage = capsys.readouterr().out
    assert usage.startswith("usage: habit-hooks ")
    for scope_flag in ("--all", "--file", "--branch", "--last", "--since"):
        assert scope_flag in usage


def test_the_sensors_stage_keeps_its_own_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_:
        sensors.parse_args(["--help"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out.startswith("usage: habit-sensors ")


def test_a_tool_failure_exits_two_not_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_with_committed_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert sensors.main(["--branch", "nope"]) == 2


def test_a_malformed_config_fails_the_tool_not_the_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
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
    with pytest.raises(SystemExit) as failure:
        sensors.parse_args(["--last", value])
    assert failure.value.code == 2
    assert "--last" in capsys.readouterr().err


@pytest.mark.parametrize("program", ["habit-sensors", "habit-mapper", "habit-snooze"])
def test_a_rejected_config_names_the_binary_that_printed_it(
    program: str, capsys: pytest.CaptureFixture[str]
) -> None:

    def reject(_: list[str]) -> int:
        raise ConfigError(_REJECTION)

    assert run_console(program, reject, []) == 2
    assert capsys.readouterr().err == f"{program}: {_REJECTION}\n"


def test_a_failure_that_already_names_itself_is_not_named_twice(
    capsys: pytest.CaptureFixture[str],
) -> None:

    def fail(_: list[str]) -> int:
        raise ToolError("habit-sensors: not a git repository")

    assert run_console("habit-sensors", fail, []) == 2
    assert capsys.readouterr().err == "habit-sensors: not a git repository\n"


def test_repeated_file_flags_are_preserved() -> None:
    parsed = sensors.parse_args(["--file", "a.md", "--file", "b.md"])

    assert parsed.file == ["a.md", "b.md"]
