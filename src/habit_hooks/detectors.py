"""What a plugin's ``detectors`` may say, and the refusal of anything else.

A plugin declares the external tools its sensors reach for: each detector names
a tool, the way to look for it, and the command that installs it, so a project
can be told what it is missing and offered the command that fixes it. The core
knows the ways of looking; which tools to look for is the plugin's to say.

This is one config key's schema, so it belongs with
:mod:`habit_hooks.config_schema` in every way but size — the detector vocabulary
is its own, and it is the part of a config that keeps growing. It moved out
*whole*, rather than being split from the refusals that describe it, so "what
may a detector say?" still has one answer in one file. The generic key refusals
stay behind and are imported from here; only the ``Detector`` type travels the
other way, as the name ``Config`` annotates its detectors with.
"""

from __future__ import annotations

import ntpath

from attrs import field, fields, frozen

from .cli import ConfigError
from .config_schema import named_keys, reject_unknown

# How a detector is looked for: `command` is an executable on PATH,
# `node-module` a package `node` resolves from the project (a package read as a
# library rather than spawned is not answered by a binary of that name). Named
# so whatever does the looking spells a kind the same way this file accepts it.
COMMAND_KIND = "command"
NODE_MODULE_KIND = "node-module"
DETECTOR_KINDS = frozenset({COMMAND_KIND, NODE_MODULE_KIND})


@frozen
class Detector:
    """An external tool a plugin needs, and the command that installs it."""

    name: str
    kind: str
    install: str
    # Directories under the project this tool is looked for in ahead of the
    # default search path — bundler's ``bin``, which a plugin names for the
    # tools it keeps there. A tuple so a detector read from TOML (a list) and
    # one built in Python compare equal.
    search_paths: tuple[str, ...] = field(converter=tuple, default=())


DETECTOR_FIELDS = frozenset(field.name for field in fields(Detector))
# The fields an entry must carry. ``search_paths`` is not among them: it names
# the one thing a detector may leave unsaid — no directory beyond the default
# search path — so requiring it would refuse every existing declaration.
REQUIRED_FIELDS = frozenset({"name", "kind", "install"})


def _reject_unknown_kind(value: object, where: str) -> None:
    if value in DETECTOR_KINDS:
        return
    known = ", ".join(repr(kind) for kind in sorted(DETECTOR_KINDS))
    raise ConfigError(
        f"unknown detector 'kind' {value!r} in {where}; known values: {known}"
    )


def _says_something(value: object) -> bool:
    """Whether a field carries a usable answer rather than the look of one."""
    return isinstance(value, str) and bool(value.strip())


def _label(entry: dict) -> str:
    """How a refusal names a detector: by its ``name``, or whole when it has none.

    A plugin declares several, so a refusal naming none of them would send the
    reader through all of them to find the one it meant.
    """
    name = entry.get("name")
    return f"detector {name!r}" if _says_something(name) else f"detector {entry!r}"


def _reject_unusable_field(entry: dict, key: str, where: str) -> None:
    """A field present but saying nothing is the absence it looks like."""
    if _says_something(entry[key]):
        return
    raise ConfigError(
        f"{_label(entry)} needs a non-empty string {key!r} in {where}; "
        f"got {entry[key]!r}"
    )


def _reject_unusable_search_paths(entry: dict, where: str) -> None:
    """A search path names a directory under the project, so it is a non-empty
    string that stays there or nothing: an absolute path is a directory the
    project does not keep, a path separator splices directories into the
    lookup, and an empty one is the absence it looks like."""
    paths = entry.get("search_paths", [])
    unusable = not isinstance(paths, list) or not all(
        _names_a_directory(path) for path in paths
    )
    if unusable:
        raise ConfigError(
            f"{_label(entry)} needs 'search_paths' as a list of non-empty "
            f"directories under the project in {where}; got {paths!r}"
        )


def _names_a_directory(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not _splices_extra_directories(value)
        and not _escapes_the_project(value)
    )


def _splices_extra_directories(path: str) -> bool:
    """Whether the entry smuggles more than one directory into the search path.

    The entries are joined into one lookup path with exactly these characters
    — ``:`` on POSIX, ``;`` on Windows — so an entry carrying either splices
    every directory after it into each lookup for the tool, and
    ``bin:../tools`` would search ``../tools`` as the project's own. Both are
    refused on every host because a plugin config travels between platforms.
    """
    return ":" in path or ";" in path


def _escapes_the_project(path: str) -> bool:
    r"""Whether the path names anything but a directory under the project.

    Both platforms' forms, not the host's, because a config travels: a Windows
    drive or rooted path reads as relative to ``os.path.isabs`` on a Mac and is
    a directory this project still does not keep. Drive-relative (``C:tools``)
    is refused with them — it names the current directory of another drive —
    and so is a ``..`` component, which climbs out the same way.

    The leading separator is read off the components rather than asked of
    ``isabs``, which cannot answer for both platforms at once: ``ntpath.isabs``
    stopped counting a single leading (back)slash as rooted in CPython 3.13,
    and ``\tools`` is still ``C:\tools`` to ``project_dir /`` on Windows
    (#166). Once ``splitdrive`` has returned empty, an empty first component
    is what the older ``ntpath.isabs`` meant, and it subsumes
    ``posixpath.isabs``.
    """
    if ntpath.splitdrive(path)[0]:
        return True
    components = path.replace("\\", "/").split("/")
    return components[0] == "" or ".." in components


def _reject_invalid_detector(entry: object, where: str) -> None:
    """Fail clearly on one entry that cannot become a :class:`Detector`.

    ``name``, ``kind`` and ``install`` are required, and required to answer:
    one missing — or emptily naming — its ``install`` names a tool and then
    leaves the reader to find it, and one missing its ``kind`` cannot be looked
    for at all. ``search_paths`` is the one field a detector may leave out; what
    it says when it does say it is refused below. An unknown ``kind`` is refused
    for the same reason: nothing knows how to look for it, so it could only ever
    be reported missing.
    """
    if not isinstance(entry, dict):
        raise ConfigError(
            f"detector {entry!r} is not a table in {where}; "
            "expected { name = ..., kind = ..., install = ... }"
        )
    missing = sorted(key for key in REQUIRED_FIELDS if key not in entry)
    if missing:
        raise ConfigError(
            f"{_label(entry)} is missing {named_keys(missing)} in {where}"
        )
    reject_unknown(DETECTOR_FIELDS, entry, f"a detector in {where}")
    _reject_unknown_kind(entry["kind"], where)
    _reject_unusable_field(entry, "name", where)
    _reject_unusable_field(entry, "install", where)
    _reject_unusable_search_paths(entry, where)


def reject_invalid_detectors(value: object, where: str) -> None:
    """Fail clearly on anything a plugin's ``detectors`` key cannot mean.

    The key's own shape is refused here rather than in the loader, where
    ``detectors = 42`` met a ``for`` and escaped as a ``TypeError`` at exit 1 —
    the code reserved for an enforced finding (#114).
    """
    if not isinstance(value, list):
        raise ConfigError(
            f"'detectors' must be a list of tables in {where}; got {value!r}"
        )
    for entry in value:
        _reject_invalid_detector(entry, where)
