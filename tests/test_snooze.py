"""Unit tests for the snooze transform's rules and its argument contract.

The executable spec ([habit-snooze.spec.md]) covers the command; these pin the
two pieces the spec cannot show directly — which file an issue is anchored to,
and what a lapsed file does to the drop decision. The index file itself, and the
commands that maintain it, live in ``test_snooze_index.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks import sensors
from habit_hooks.snooze import anchor_file, parse_args, transform

_FINDING = {
    "smell": "oversized-file",
    "details": {"maxAllowed": 200},
    "issues": [
        {"key": "src/x.ts", "details": {"file": "src/x.ts"}},
        {"key": "requests", "details": {"file": "src/y.py"}},
    ],
}


def test_anchor_prefers_the_details_file() -> None:
    issue = {"key": "requests", "details": {"file": "src/y.py"}}
    assert anchor_file(issue) == "src/y.py"


def test_anchor_falls_back_to_the_key_without_a_file() -> None:
    assert anchor_file({"key": "src/x.ts", "details": {"line": 3}}) == "src/x.ts"


def test_anchor_falls_back_to_the_key_without_details() -> None:
    assert anchor_file({"key": "src/x.ts"}) == "src/x.ts"


def test_no_lapsed_file_drops_every_snoozed_issue() -> None:
    kept = transform([_FINDING], {"src/x.ts", "requests"})
    assert kept == []


def test_a_lapsed_file_resurfaces_only_its_own_issue() -> None:
    kept = transform([_FINDING], {"src/x.ts", "requests"}, {"src/y.py"})
    assert [issue["key"] for issue in kept[0]["issues"]] == ["requests"]


def test_a_lapsed_file_leaves_unsnoozed_issues_alone() -> None:
    kept = transform([_FINDING], set(), {"src/y.py"})
    assert [issue["key"] for issue in kept[0]["issues"]] == ["src/x.ts", "requests"]


def test_a_finding_without_issues_passes_through() -> None:
    empty = {"smell": "duplicated-code", "details": {}, "issues": []}
    assert transform([empty], {"src/x.ts"}, {"src/x.ts"}) == [empty]


def test_file_run_bypasses_the_snooze_transformer(tmp_path: Path) -> None:
    """`--file` asks for one file's full picture, so its snooze exemption — a
    statement about the backlog, not that file — is stripped from the run (#55)."""
    config = sensors._configure(sensors.parse_args(["--file", "src/x.ts"]), tmp_path)
    assert "snooze" not in config.transformers


def test_all_run_keeps_the_snooze_transformer(tmp_path: Path) -> None:
    """The bypass is `--file` only: `--all` still filters through the index."""
    config = sensors._configure(sensors.parse_args(["--all"]), tmp_path)
    assert config.transformers == ["snooze"]


def test_file_run_keeps_a_projects_non_snooze_transformer(tmp_path: Path) -> None:
    """Only snoozing is bypassed — a project's unrelated transformer still runs,
    so `--file` does not silently drop a step it never asked about (#55)."""
    config_dir = tmp_path / ".habit-hooks"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text('transformers = ["snooze", "squash"]\n', encoding="utf-8")
    config = sensors._configure(sensors.parse_args(["--file", "src/x.ts"]), tmp_path)
    assert config.transformers == ["squash"]


def test_config_flag_is_parsed_as_a_path() -> None:
    assert parse_args(["--config", "ci.toml"]).config == Path("ci.toml")


def test_config_defaults_to_none() -> None:
    assert parse_args(["--until-changed"]).config is None


@pytest.mark.parametrize("transform_flag", ["--until-changed", "--config=ci.toml"])
@pytest.mark.parametrize("index_op", ["--snooze", "--prune", "--list"])
def test_a_transform_flag_with_an_index_op_errors_by_name(
    transform_flag: str, index_op: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both flags shape the transform and have no bearing on an index operation.
    Each used to be accepted there and then silently ignored — `--prune --config
    ci.toml` looked like it honoured a config it never read."""
    with pytest.raises(SystemExit):
        parse_args([transform_flag, index_op])
    err = capsys.readouterr().err
    assert transform_flag.removesuffix("=ci.toml") in err
    assert index_op in err
