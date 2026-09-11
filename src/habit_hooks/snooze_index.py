"""The checked-in snooze index: load it safely, save it atomically.

Split from ``snooze.py`` so the index file I/O — parsing a JSON file a human
edits, and replacing it without tearing under concurrent hook runs — lives apart
from the transform and its CLI (#94).

An entry is a key and the anchors it was granted against, each recorded with the
content that file held at the time (#163). An entry that records nothing stays a
bare key, so an index written before that keeps loading and a project migrates
one ``--snooze`` at a time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from attrs import frozen

INDEX_PATH = Path(".habit-hooks") / "snooze.json"

ENTRY_FIELDS = frozenset({"key", "anchors"})

# The anchor files an entry was granted against, each mapped to the content it
# held then. Empty for an entry written before #163, and for one whose anchor is
# no file to read.
Anchors = dict[str, str]

# What `load_index` hands the rest of the tool: every snoozed key, with what it
# was granted against.
Index = dict[str, Anchors]


@frozen
class Entry:
    """One line of the index as written: a key, and what that line recorded.

    Distinct from `Index` because a list of these can hold the same key twice
    and a mapping cannot. Collapsing them is the step where a recording is
    lost, so a duplicate has to be visible before it happens.
    """

    key: str
    anchors: Anchors


class SnoozeError(Exception):
    """A malformed snooze index — a checked-in file a human edits, so it fails by
    name rather than as a traceback or, worse, a silent misread (#94)."""


def load_index(project_dir: Path) -> Index:
    path = project_dir / INDEX_PATH
    if not path.exists():
        return {}
    return _parse_index(path)


def _parse_index(path: Path) -> Index:
    """The index is a JSON list of entries; anything else fails by name.

    Left untyped, ``null`` iterated as ``None``, a bare ``"src/a.py"`` iterated
    per character, and ``{"key": "reason"}`` survived only to be flattened to a
    bare list on the next ``--snooze`` — each a silent way to mean nothing.
    """
    data = _parse_json(path)
    if not isinstance(data, list):
        raise SnoozeError(
            f"{path}: expected a JSON list of snoozed entries, got {_describe(data)}"
        )
    entries = [_entry(path, item) for item in data]
    _reject_a_conflicting_duplicate(path, entries)
    return {entry.key: entry.anchors for entry in entries}


def _parse_json(path: Path) -> object:
    """The file as JSON, refusing a name written twice inside one object.

    ``json`` keeps the last of two members sharing a name, so an anchor pasted
    twice with two different digests would load as one of them and say nothing.
    That is the refusal below, one level further in.
    """

    def one_name_each(pairs: list[tuple[str, object]]) -> dict:
        names = [name for name, _ in pairs]
        repeated = next((name for name in names if names.count(name) > 1), None)
        if repeated is not None:
            raise SnoozeError(
                f'{path}: expected each name once, got "{repeated}" more than once'
            )
        return dict(pairs)

    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text, object_pairs_hook=one_name_each)
    except json.JSONDecodeError as exc:
        raise SnoozeError(f"{path}: not valid JSON ({exc})") from exc


def _entry(path: Path, item: object) -> Entry:
    """One entry: a bare key, or that key with the anchors it was granted against.

    A key beside a field the index has no meaning for is refused rather than
    read and dropped on the next write — the flattening above, in the shape it
    takes now that an entry can be an object.
    """
    if isinstance(item, str):
        return Entry(item, {})
    if _is_entry(item):
        return Entry(item["key"], item.get("anchors", {}))
    raise SnoozeError(
        f"{path}: expected each entry to be a snoozed key, or an object with "
        f'"key" and an optional "anchors", got {_describe(item)}'
    )


def _reject_a_conflicting_duplicate(path: Path, entries: list[Entry]) -> None:
    """Two entries for one key are refused unless they say the same thing.

    Loading into a mapping keeps the last, so a bare duplicate beside a recorded
    one drops the recording and reverts that entry to the behaviour it had before
    it recorded anything — silently, with the order in the file deciding. Two
    entries that agree cannot lose anything, so a plain ``["a", "a"]`` was always
    legal and still is.
    """
    seen: Index = {}
    for entry in entries:
        if seen.setdefault(entry.key, entry.anchors) != entry.anchors:
            raise SnoozeError(
                f'{path}: expected each key once, got "{entry.key}" twice '
                "recording different anchors"
            )


def _is_entry(item: object) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("key"), str)
        and _is_anchors(item.get("anchors", {}))
        and not set(item) - ENTRY_FIELDS
    )


def _is_anchors(anchors: object) -> bool:
    return isinstance(anchors, dict) and all(
        isinstance(anchor, str) and isinstance(content, str)
        for anchor, content in anchors.items()
    )


def _describe(data: object) -> str:
    return {
        dict: "an object",
        list: "a list",
        str: "a bare string",
        bool: "a boolean",
        int: "a number",
        float: "a number",
        type(None): "null",
    }.get(type(data), type(data).__name__)


def save_index(entries: Index, project_dir: Path) -> None:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    written = [_written(key, entries[key]) for key in sorted(entries)]
    _replace_atomically(path, json.dumps(written) + "\n")


def _written(key: str, anchors: Anchors) -> str | dict:
    """An entry recording nothing is written as the bare key it was before #163,
    so an index no ``--snooze`` has renewed keeps the shape its project knows.
    Anchors are sorted along with the keys, so a file written on one line still
    reviews as a stable diff."""
    if not anchors:
        return key
    return {"key": key, "anchors": dict(sorted(anchors.items()))}


def _replace_atomically(path: Path, content: str) -> None:
    """Write a sibling temp file, then ``os.replace`` it over ``path``.

    Two concurrent hook runs that read-modify-write the index otherwise tear it;
    the rename is atomic on POSIX, so a reader sees the old file or the whole new
    one. The pid keeps the two writers' temp files apart.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
