"""What ``--prune`` keeps and reaps once an entry records something (#163).

``--prune`` reaps what the latest run no longer reports. An entry now carries
recordings, and reaping the key they belong to must not reach into them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.snooze import load_index, parse_args, run
from snooze_project import a_project_with, feed_stdin, finding, snooze


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
