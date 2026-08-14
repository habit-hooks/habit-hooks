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

from attrs import fields, frozen

from .cli import ConfigError
from .config_schema import named_keys, reject_unknown

# How a detector is looked for: `command` is an executable on PATH,
# `node-module` a package `node` resolves from the project (a package read as a
# library rather than spawned is not answered by a binary of that name).
DETECTOR_KINDS = frozenset({"command", "node-module"})


@frozen
class Detector:
    """An external tool a plugin needs, and the command that installs it."""

    name: str
    kind: str
    install: str


DETECTOR_FIELDS = frozenset(field.name for field in fields(Detector))


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


def _reject_invalid_detector(entry: object, where: str) -> None:
    """Fail clearly on one entry that cannot become a :class:`Detector`.

    Every field is required, and required to answer: one missing — or emptily
    naming — its ``install`` names a tool and then leaves the reader to find it,
    and one missing its ``kind`` cannot be looked for at all. An unknown ``kind``
    is refused for the same reason: nothing knows how to look for it, so it could
    only ever be reported missing.
    """
    if not isinstance(entry, dict):
        raise ConfigError(
            f"detector {entry!r} is not a table in {where}; "
            "expected { name = ..., kind = ..., install = ... }"
        )
    missing = sorted(key for key in DETECTOR_FIELDS if key not in entry)
    if missing:
        raise ConfigError(f"{_label(entry)} is missing {named_keys(missing)} in {where}")
    reject_unknown(DETECTOR_FIELDS, entry, f"a detector in {where}")
    _reject_unknown_kind(entry["kind"], where)
    _reject_unusable_field(entry, "name", where)
    _reject_unusable_field(entry, "install", where)


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
