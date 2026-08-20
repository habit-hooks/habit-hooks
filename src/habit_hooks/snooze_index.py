"""The checked-in snooze index: load it safely, save it atomically.

Split from ``snooze.py`` so the index file I/O — parsing a JSON file a human
edits, and replacing it without tearing under concurrent hook runs — lives apart
from the transform and its CLI (#94).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

INDEX_PATH = Path(".habit-hooks") / "snooze.json"


class SnoozeError(Exception):
    """A malformed snooze index — a checked-in file a human edits, so it fails by
    name rather than as a traceback or, worse, a silent misread (#94)."""


def load_index(project_dir: Path) -> list[str]:
    path = project_dir / INDEX_PATH
    if not path.exists():
        return []
    return _parse_index(path)


def _parse_index(path: Path) -> list[str]:
    """The index is a JSON list of string keys; anything else fails by name.

    Left untyped, ``null`` iterated as ``None``, a bare ``"src/a.py"`` iterated
    per character, and ``{"key": "reason"}`` survived only to be flattened to a
    bare list on the next ``--snooze`` — each a silent way to mean nothing.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnoozeError(f"{path}: not valid JSON ({exc})") from exc
    if not (isinstance(data, list) and all(isinstance(key, str) for key in data)):
        raise SnoozeError(
            f"{path}: expected a JSON list of string keys, got {_describe(data)}"
        )
    return data


def _describe(data: object) -> str:
    if isinstance(data, list):
        return "a list with a non-string entry"
    return {dict: "an object", str: "a bare string", type(None): "null"}.get(
        type(data), type(data).__name__
    )


def save_index(keys: list[str], project_dir: Path) -> None:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    _replace_atomically(path, json.dumps(sorted(set(keys))) + "\n")


def _replace_atomically(path: Path, content: str) -> None:
    """Write a sibling temp file, then ``os.replace`` it over ``path``.

    Two concurrent hook runs that read-modify-write the index otherwise tear it;
    the rename is atomic on POSIX, so a reader sees the old file or the whole new
    one. The pid keeps the two writers' temp files apart.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
