"""What ``--prune`` keeps and reaps once an entry records something (#163).

``--prune`` reaps what the latest run no longer reports. An entry now carries
recordings, so it has two ways to go stale: the key itself, which #94 already
covered, and one anchor of a key that is still live. Neither may take the other
with it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.snooze import load_index, parse_args, run
from habit_hooks.snooze_lapse import content_hash
from snooze_project import a_project_with, aliased, feed_stdin, finding, snooze


def test_prune_keeps_what_a_key_it_keeps_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rebuilding a bare list of keys would strip every affirmation on the next
    prune."""
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    recorded = load_index(tmp_path)["src/x.ts"]

    feed_stdin(monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert run(parse_args(["--prune"]), tmp_path) == 0
    assert load_index(tmp_path) == {"src/x.ts": recorded}


def test_prune_drops_an_anchor_the_run_no_longer_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An anchor goes stale inside a live entry: one file is deleted while the
    key is still reported through another, so pruning by key alone would leave
    the dead one recorded forever."""
    a_project_with(tmp_path, "src/a.py", "import requests\n")
    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")
    snooze(tmp_path, monkeypatch, aliased("src/a.py", "src/b.py"))

    feed_stdin(monkeypatch, aliased("src/b.py"))
    assert run(parse_args(["--prune"]), tmp_path) == 0
    assert load_index(tmp_path) == {
        "requests": {"src/b.py": content_hash(tmp_path / "src/b.py")}
    }
