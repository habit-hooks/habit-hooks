"""An entry the index cannot mean is refused, never quietly flattened (#163).

An entry that may be an object as well as a bare key is one more way for
something to survive a load only to be dropped on the next write. An index read
as something it does not say is a false clean — the #78/#84 class — so
``_parse_index`` refuses every shape it cannot mean by name, and says what is
allowed instead. The document-level refusals are in ``test_snooze_index.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from habit_hooks.snooze import INDEX_PATH, SnoozeError, load_index


def _write_index(project_dir: Path, content: str) -> Path:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("entry", "why"),
    [
        ({"key": "src/a.py", "reason": "we discussed it"}, "an unknown field"),
        ({"anchors": {"src/a.py": "sha256:abc"}}, "no key at all"),
        ({"key": "src/a.py", "anchors": "sha256:abc"}, "anchors that are not a table"),
        ({"key": "src/a.py", "anchors": {"src/a.py": 5}}, "a content that is no digest"),
        (["src/a.py"], "a nested list"),
        (7, "a number"),
    ],
)
def test_an_entry_the_index_cannot_mean_fails_by_name(
    tmp_path: Path, entry: object, why: str
) -> None:
    """An entry carrying something the index has no meaning for is refused, not
    loaded and dropped on the next write. That silent flattening is what the
    index is parsed strictly to prevent (#94), and an entry that may be an object
    rather than a key is one more way for it to happen."""
    _write_index(tmp_path, json.dumps([entry]))
    with pytest.raises(SnoozeError) as excinfo:
        load_index(tmp_path)
    assert "expected each entry" in str(excinfo.value), why


@pytest.mark.parametrize(
    ("entries", "why"),
    [
        (
            ["src/a.py", {"key": "src/a.py", "anchors": {"src/a.py": "sha256:abc"}}],
            "a bare key before a recorded one",
        ),
        (
            [{"key": "src/a.py", "anchors": {"src/a.py": "sha256:abc"}}, "src/a.py"],
            "a recorded key after a bare one",
        ),
        (
            [
                {"key": "a", "anchors": {"src/a.py": "sha256:abc"}},
                {"key": "a", "anchors": {"src/a.py": "sha256:def"}},
            ],
            "two records disagreeing about one anchor",
        ),
    ],
)
def test_a_key_written_twice_with_different_anchors_fails_by_name(
    tmp_path: Path, entries: list, why: str
) -> None:
    """Loading into a mapping keeps the last, so the order in the file would
    silently decide which recording survives."""
    _write_index(tmp_path, json.dumps(entries))
    with pytest.raises(SnoozeError) as excinfo:
        load_index(tmp_path)
    assert "twice" in str(excinfo.value), why


@pytest.mark.parametrize(
    ("entries", "loaded"),
    [
        (["a", "a"], {"a": {}}),
        (
            [
                {"key": "a", "anchors": {"src/a.py": "sha256:abc"}},
                {"key": "a", "anchors": {"src/a.py": "sha256:abc"}},
            ],
            {"a": {"src/a.py": "sha256:abc"}},
        ),
    ],
    ids=["two bare keys, which 1.5.0 already accepted", "two records that agree"],
)
def test_a_key_written_twice_saying_the_same_thing_loads(
    tmp_path: Path, entries: list, loaded: dict
) -> None:
    """Collapsing them loses nothing, and refusing would break an index that
    every earlier version read without complaint."""
    _write_index(tmp_path, json.dumps(entries))
    assert load_index(tmp_path) == loaded


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ('[{"key": "a", "key": "b"}]', "a field written twice"),
        ('[{"key": "a", "anchors": {"x": "sha256:1", "x": "sha256:2"}}]', "an anchor twice"),
    ],
)
def test_a_name_written_twice_inside_one_object_fails_by_name(
    tmp_path: Path, text: str, why: str
) -> None:
    """`json` keeps the last of two members sharing a name, so this would load as
    one of them with nothing said — the same silent loss, one level further in."""
    _write_index(tmp_path, text)
    with pytest.raises(SnoozeError) as excinfo:
        load_index(tmp_path)
    assert "once" in str(excinfo.value), why


def test_a_refusal_names_the_shape_an_entry_may_take(tmp_path: Path) -> None:
    """A refusal has to say what is allowed, not only that this was not: a
    message naming no shape leaves the reader to guess the format."""
    _write_index(tmp_path, json.dumps([{"key": "src/a.py", "reason": "no"}]))
    message = str(pytest.raises(SnoozeError, load_index, tmp_path).value)
    assert "snoozed key" in message
    assert '"anchors"' in message
    assert "an object" in message
