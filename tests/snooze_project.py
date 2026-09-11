"""A project with files, an index and findings on stdin, for the #163 tests.

The #163 test files build the same situation — a file on disk, a finding
anchored to it, and ``--snooze`` fed through the real CLI — so the fixtures live
here once rather than as copies drifting apart.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from habit_hooks.snooze import INDEX_PATH, parse_args, run


def feed_stdin(monkeypatch: pytest.MonkeyPatch, findings: object) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(findings)))


def finding(key: str, file: str | None = None) -> dict:
    """One issue, anchored to ``file`` — or to its key, as a sensor may leave it."""
    details = {"file": file} if file is not None else {}
    return {
        "smell": "oversized-file",
        "details": {"maxAllowed": 200},
        "issues": [{"key": key, "details": details}],
    }


def aliased(*files: str) -> list[dict]:
    """One key over several files — see ``snooze_lapse.anchor_file`` for when a
    sensor reports that."""
    return [
        {
            "smell": "unused-dependency",
            "details": {},
            "issues": [{"key": "requests", "details": {"file": f}} for f in files],
        }
    ]


def a_project_with(project_dir: Path, name: str, text: str) -> Path:
    path = project_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return project_dir


def write_index(project_dir: Path, entries: object) -> None:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries), encoding="utf-8")


def snooze(project_dir: Path, monkeypatch: pytest.MonkeyPatch, findings: list) -> None:
    feed_stdin(monkeypatch, findings)
    assert run(parse_args(["--snooze"]), project_dir) == 0, f"--snooze failed in {project_dir}"
