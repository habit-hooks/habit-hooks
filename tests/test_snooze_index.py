"""Unit tests for the checked-in index and the commands that maintain it.

Split from ``test_snooze.py`` along the same seam as the source (``snooze.py``
holds the transform and its CLI, ``snooze_index.py`` the file I/O): what the
index file accepts, what ``--prune`` may do to it, and what a broken one — a
file a human edits — does to the run.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from habit_hooks.cli import EXIT_TOOL_ERROR
from habit_hooks.snooze import (
    INDEX_PATH,
    SnoozeError,
    load_index,
    main,
    parse_args,
    run,
    save_index,
)


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
    """Empty findings mean "nothing measured", not "everything obsolete" (#94).

    The refusal is a judgement about the run, so it keeps the enforced-finding
    exit 1 — apart from the tool's own failures, which exit 2.
    """
    _write_index(tmp_path, json.dumps(["src/x.ts", "src/y.ts"]))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert run(parse_args(["--prune"]), tmp_path) == 1
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


@pytest.mark.parametrize("index_op", ["--list", "--snooze", "--prune"])
def test_a_corrupt_index_fails_as_a_tool_error(
    index_op: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checked-in index a human broke is a failure of the tool itself, not a
    finding about the code: exit 2, like an unresolvable base ref (#103)."""
    _write_index(tmp_path, "not json")
    _feed_stdin(monkeypatch, [])
    monkeypatch.chdir(tmp_path)
    assert main([index_op]) == EXIT_TOOL_ERROR


def test_save_index_writes_atomically_leaving_no_temp_files(tmp_path: Path) -> None:
    save_index(["src/x.ts"], tmp_path)
    index_dir = tmp_path / INDEX_PATH.parent
    assert [p.name for p in index_dir.iterdir()] == ["snooze.json"]
    assert load_index(tmp_path) == ["src/x.ts"]
