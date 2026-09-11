"""Which snoozes a recorded content covers, and which it must not (#163).

An affirmation is read back per key *and* anchor, because a key is not always
one file (``snooze_lapse.anchor_file`` says when). Affirming the key instead
would exempt a file nobody judged.

What ``--snooze`` writes is ``test_snooze_records_the_content_it_affirmed.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks import snooze_lapse
from habit_hooks.snooze import load_index
from habit_hooks.snooze_lapse import Lapse, content_hash
from snooze_project import a_project_with, aliased, finding, snooze, write_index


def test_an_index_that_recorded_nothing_reads_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every hook run asks this, so it must not hash a file to learn that an
    index written before #163 has nothing to compare. The anchor is handed in as
    changed, so an empty answer can only come from the empty record."""
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    write_index(tmp_path, ["src/x.ts"])
    monkeypatch.setattr(
        snooze_lapse,
        "content_hash",
        lambda path: pytest.fail(f"hashed {path} with nothing recorded"),
    )
    findings = [finding("src/x.ts", "src/x.ts")]
    asked = Lapse({"src/x.ts"}).affirming(load_index(tmp_path), findings, tmp_path)
    assert asked.affirmed == set()


def test_an_affirmation_covers_only_the_file_it_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run reports one key through two files and only one was affirmed, so
    only that one is spared."""
    a_project_with(tmp_path, "src/a.py", "import requests\n")
    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")
    snooze(tmp_path, monkeypatch, aliased("src/b.py"))

    findings = aliased("src/a.py", "src/b.py")
    lapse = Lapse({"src/a.py"}).affirming(load_index(tmp_path), findings, tmp_path)

    assert lapse.spares("requests", "src/b.py")
    assert not lapse.spares("requests", "src/a.py")


def test_a_file_git_calls_unchanged_is_spared_though_its_record_no_longer_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The git half of the AND, in the direction the digest cannot answer for.

    Someone lands work on the base ref after the affirmation, so the recorded
    content no longer matches — but this branch never touched the file, and
    leaving such a branch alone is what the ratchet was adopted for. Only the
    ``and`` keeps the alert off it; a content-only rule would fire here.
    """
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    a_project_with(tmp_path, "src/x.ts", "export const a = 2;\n")

    index = load_index(tmp_path)
    assert index["src/x.ts"]["src/x.ts"] != content_hash(tmp_path / "src/x.ts")

    findings = [finding("src/x.ts", "src/x.ts")]
    assert Lapse(frozenset()).affirming(index, findings, tmp_path).spares(
        "src/x.ts", "src/x.ts"
    )
    assert not Lapse({"src/x.ts"}).affirming(index, findings, tmp_path).spares(
        "src/x.ts", "src/x.ts"
    )


def test_a_file_that_only_now_reports_a_key_is_not_affirmed_by_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The entry was recorded while one file reported the key, which is the case
    this change is for. A second file picking the smell up later is new debt, and
    surfacing it is what the ratchet is."""
    a_project_with(tmp_path, "src/a.py", "import requests\n")
    snooze(tmp_path, monkeypatch, aliased("src/a.py"))

    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")
    findings = aliased("src/a.py", "src/b.py")
    lapse = Lapse({"src/b.py"}).affirming(load_index(tmp_path), findings, tmp_path)

    assert not lapse.spares("requests", "src/b.py")
