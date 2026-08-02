"""Unit tests for the snooze transform's rules, with git out of the picture.

The executable spec ([habit-snooze.spec.md]) covers the command; these pin the
two pieces the spec cannot show directly — which file an issue is anchored to,
and what a lapsed file does to the drop decision.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from habit_hooks.snooze import (
    INDEX_PATH,
    SnoozeError,
    anchor_file,
    load_index,
    parse_args,
    run,
    save_index,
    transform,
)

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


def test_config_flag_is_parsed_as_a_path() -> None:
    assert parse_args(["--config", "ci.toml"]).config == Path("ci.toml")


def test_config_defaults_to_none() -> None:
    assert parse_args(["--until-changed"]).config is None


@pytest.mark.parametrize("index_op", ["--snooze", "--prune", "--list"])
def test_until_changed_with_an_index_op_errors_by_name(
    index_op: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """It used to be accepted and silently ignored; now the conflict is named."""
    with pytest.raises(SystemExit):
        parse_args(["--until-changed", index_op])
    err = capsys.readouterr().err
    assert "--until-changed" in err
    assert index_op in err


def _write_index(project_dir: Path, content: str) -> Path:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _feed_stdin(monkeypatch: pytest.MonkeyPatch, findings: object) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(findings)))


def _finding(*keys: str) -> dict:
    return {
        "smell": "loose-equality",
        "details": {},
        "issues": [{"key": key, "details": {"file": key}} for key in keys],
    }


def test_prune_drops_a_key_that_no_longer_appears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_index(tmp_path, json.dumps(["src/x.ts", "src/y.ts"]))
    _feed_stdin(monkeypatch, [_finding("src/x.ts")])
    assert run(parse_args(["--prune"]), tmp_path) == 0
    assert load_index(tmp_path) == ["src/x.ts"]


def test_prune_refuses_to_empty_a_populated_index_on_no_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Empty findings mean "nothing measured", not "everything obsolete" (#94)."""
    _write_index(tmp_path, json.dumps(["src/x.ts", "src/y.ts"]))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert run(parse_args(["--prune"]), tmp_path) != 0
    assert load_index(tmp_path) == ["src/x.ts", "src/y.ts"]
    assert "prune" in capsys.readouterr().err.lower()


def test_prune_still_clears_an_index_it_was_asked_to_when_findings_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real run whose snoozed keys are all fixed but which still found other
    smells prunes them: the refusal is only for the wholly-empty pipe."""
    _write_index(tmp_path, json.dumps(["src/x.ts"]))
    _feed_stdin(monkeypatch, [_finding("src/other.ts")])
    assert run(parse_args(["--prune"]), tmp_path) == 0
    assert load_index(tmp_path) == []


@pytest.mark.parametrize(
    ("content", "why"),
    [
        ("not json", "invalid JSON"),
        ("null", "JSON null"),
        ('"src/a.py"', "a bare string"),
        ('{"src/a.py": "why"}', "an object"),
    ],
)
def test_a_malformed_index_fails_by_name(
    tmp_path: Path, content: str, why: str
) -> None:
    path = _write_index(tmp_path, content)
    with pytest.raises(SnoozeError) as excinfo:
        load_index(tmp_path)
    assert str(path) in str(excinfo.value), why


def test_save_index_writes_atomically_leaving_no_temp_files(tmp_path: Path) -> None:
    save_index(["src/x.ts"], tmp_path)
    index_dir = tmp_path / INDEX_PATH.parent
    assert [p.name for p in index_dir.iterdir()] == ["snooze.json"]
    assert load_index(tmp_path) == ["src/x.ts"]
