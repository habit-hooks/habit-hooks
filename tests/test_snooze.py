
from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks import sensors
from habit_hooks import snooze_lapse
from habit_hooks.snooze import load_index, transform
from habit_hooks.snooze_lapse import anchor_file, holds
from snooze_project import a_project_with, aliased, snooze

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


def test_an_entry_recording_nothing_drops_every_snoozed_issue(tmp_path: Path) -> None:
    kept = transform([_FINDING], {"src/x.ts": {}, "requests": {}}, tmp_path)
    assert kept == []


def test_a_changed_file_resurfaces_only_its_own_issue(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/y.py").write_text("import requests\n", encoding="utf-8")
    index = {"src/x.ts": {"src/x.ts": "sha256:lapsed"}, "requests": {}}
    kept = transform([_FINDING], index, tmp_path)
    assert [issue["key"] for issue in kept[0]["issues"]] == ["src/x.ts"]


def test_a_snoozed_issue_is_dropped_from_its_finding(tmp_path: Path) -> None:
    kept = transform([_FINDING], {"src/x.ts": {}}, tmp_path)
    assert [issue["key"] for issue in kept[0]["issues"]] == ["requests"]


def test_an_issue_whose_key_is_not_snoozed_is_never_dropped(tmp_path: Path) -> None:
    kept = transform([_FINDING], {}, tmp_path)
    assert [issue["key"] for issue in kept[0]["issues"]] == ["src/x.ts", "requests"]


def test_a_finding_without_issues_passes_through(tmp_path: Path) -> None:
    empty = {"smell": "duplicated-code", "details": {}, "issues": []}
    assert transform([empty], {"src/x.ts": {}}, tmp_path) == [empty]


def test_file_run_bypasses_the_snooze_transformer(tmp_path: Path) -> None:
    config = sensors._configure(sensors.parse_args(["--file", "src/x.ts"]), tmp_path)
    assert "snooze" not in config.transformers


def test_all_run_keeps_the_snooze_transformer(tmp_path: Path) -> None:
    config = sensors._configure(sensors.parse_args(["--all"]), tmp_path)
    assert config.transformers == ["snooze"]


def test_file_run_keeps_a_projects_non_snooze_transformer(tmp_path: Path) -> None:
    config_dir = tmp_path / ".habit-hooks"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text('transformers = ["snooze", "squash"]\n', encoding="utf-8")
    config = sensors._configure(sensors.parse_args(["--file", "src/x.ts"]), tmp_path)
    assert config.transformers == ["squash"]


def test_an_entry_that_records_nothing_holds_without_reading_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    monkeypatch.setattr(
        snooze_lapse,
        "content_hash",
        lambda path: pytest.fail(f"hashed {path} with nothing recorded"),
    )
    assert holds({}, "src/x.ts", tmp_path)


def test_an_approval_covers_only_the_file_it_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_project_with(tmp_path, "src/a.py", "import requests\n")
    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")
    snooze(tmp_path, monkeypatch, aliased("src/b.py"))

    index = load_index(tmp_path)
    assert holds(index["requests"], "src/b.py", tmp_path)
    assert not holds(index["requests"], "src/a.py", tmp_path)


def test_a_file_that_only_now_reports_a_key_is_not_covered_by_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_project_with(tmp_path, "src/a.py", "import requests\n")
    snooze(tmp_path, monkeypatch, aliased("src/a.py"))

    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")
    index = load_index(tmp_path)
    assert holds(index["requests"], "src/a.py", tmp_path)
    assert not holds(index["requests"], "src/b.py", tmp_path)
