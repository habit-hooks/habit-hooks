"""What ``--snooze`` writes into an entry, and what keeps it there (#163).

An entry records the content of each file it was granted against, and this is
what that recording promises: it replaces rather than accumulates, it does not
mistake a line ending for an edit, it survives a run that measured nothing about
it, and it stays out of ``--list``. What ``--prune`` then keeps and reaps is
``test_prune_keeps_what_the_run_still_reports.py``; which snoozes the record
covers is ``test_an_affirmation_covers_only_its_own_file.py``; and the lapse
itself is in ``docs/habit-snooze.spec.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.snooze import load_index, parse_args, run
from habit_hooks.snooze_lapse import anchor_file, content_hash, renewed
from snooze_project import a_project_with, aliased, finding, snooze


def test_snooze_records_the_anchor_files_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert load_index(tmp_path) == {
        "src/x.ts": {"src/x.ts": content_hash(tmp_path / "src/x.ts")}
    }


def test_an_edit_changes_the_recorded_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of recording it: a later edit is a different answer."""
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    before = load_index(tmp_path)["src/x.ts"]

    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\nexport const b = 2;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert load_index(tmp_path)["src/x.ts"] != before


def test_snoozing_again_replaces_the_entry_rather_than_adding_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Appending would leave the stale content beside the fresh one, and every
    later run would have two answers to choose between."""
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    a_project_with(tmp_path, "src/x.ts", "export const a = 2;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert list(load_index(tmp_path)) == ["src/x.ts"]


def test_an_anchor_that_is_no_file_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sensor may key by module or export name, so the anchor is often not a
    path at all. There is nothing to record, and the entry keeps the behaviour
    it had before #163 rather than failing the run."""
    snooze(tmp_path, monkeypatch, [finding("SomeExportedName")])
    assert load_index(tmp_path) == {"SomeExportedName": {}}


@pytest.mark.parametrize("file", [None, 5, ""], ids=["null", "a number", "empty"])
def test_a_details_file_that_is_no_path_falls_back_to_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, file: object
) -> None:
    """`sensors.finding_paths` reads a `file` that is not a non-empty string as
    absent and lets the issue through rather than failing its sensor, so one
    reaches here. Recording opens the anchor as a path, so reading it any other
    way turns a tolerated finding into a traceback."""
    issue = {"key": "k", "details": {"file": file}}
    assert anchor_file(issue) == "k"

    snooze(tmp_path, monkeypatch, [{"smell": "s", "details": {}, "issues": [issue]}])
    assert load_index(tmp_path) == {"k": {}}


def test_an_unreadable_anchor_keeps_what_was_recorded_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file briefly unreadable is not an answer. Replacing an affirmation with
    nothing would lapse it on the next run for a reason nobody chose."""
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    recorded = load_index(tmp_path)["src/x.ts"]

    (tmp_path / "src/x.ts").unlink()
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert load_index(tmp_path)["src/x.ts"] == recorded


def test_the_recorded_content_ignores_a_crlf_line_ending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``snooze.json`` is checked in and shared, and git already reports nothing
    for a CRLF-only difference under ``core.autocrlf``. Hashing raw bytes would
    lapse a Windows developer's affirmation the moment Linux CI read it."""
    crlf = a_project_with(tmp_path / "crlf", "x.ts", "const a = 1;\r\nconst b = 2;\r\n")
    lf = a_project_with(tmp_path / "lf", "x.ts", "const a = 1;\nconst b = 2;\n")

    snooze(crlf, monkeypatch, [finding("x.ts", "x.ts")])
    snooze(lf, monkeypatch, [finding("x.ts", "x.ts")])

    assert load_index(crlf) == load_index(lf)


def test_a_lone_carriage_return_is_content_and_not_a_line_ending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule forgives a line ending, not any byte resembling one. Measured: a
    file rewritten with a lone ``\\r`` is reported as changed with ``core.autocrlf``
    set and without it, so forgiving that too would forgive an edit every checkout
    agrees is an edit — unlike ``\\r\\n``, where the two settings disagree."""
    cr = a_project_with(tmp_path / "cr", "x.ts", "const a = 1;\rconst b = 2;\r")
    lf = a_project_with(tmp_path / "lf", "x.ts", "const a = 1;\nconst b = 2;\n")

    snooze(cr, monkeypatch, [finding("x.ts", "x.ts")])
    snooze(lf, monkeypatch, [finding("x.ts", "x.ts")])

    assert load_index(cr) != load_index(lf)


def test_a_key_reported_under_several_files_records_each_of_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key is not always one file (``snooze_lapse.anchor_file`` says when). One
    content could only describe one of them, and which one would come down to the
    order the sensor listed them in."""
    a_project_with(tmp_path, "src/a.py", "import requests\n")
    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")

    snooze(tmp_path, monkeypatch, aliased("src/a.py", "src/b.py"))

    assert load_index(tmp_path) == {
        "requests": {
            "src/a.py": content_hash(tmp_path / "src/a.py"),
            "src/b.py": content_hash(tmp_path / "src/b.py"),
        }
    }


def test_an_anchor_the_run_does_not_report_keeps_what_it_recorded(
    tmp_path: Path,
) -> None:
    """A run narrowed to one file measures nothing about the others an entry
    covers, and a snooze must not lapse because of a question nobody asked.
    ``--prune`` is where an anchor that is really gone is dropped."""
    a_project_with(tmp_path, "src/a.py", "import requests\n")
    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")
    both = renewed({}, aliased("src/a.py", "src/b.py"), tmp_path)

    assert renewed(both, aliased("src/a.py"), tmp_path) == both


def test_list_prints_bare_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--list`` shows what is snoozed, not the bookkeeping that decides for how
    long."""
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert run(parse_args(["--list"]), tmp_path) == 0
    assert capsys.readouterr().out == "src/x.ts\n"
