"""What a config is, what it may say, and the refusal of anything else.

The shape of every section is the attrs types below, and the keys a user may set
are their declared fields minus the loader-populated internals — so one
definition answers both "what does this section hold?" and "what may the TOML
name?". Finding, merging and resolving a config is :mod:`habit_hooks.config`.

Unknown keys are rejected at every level — project *and* plugin config — with a
``ConfigError`` (exit 2): a key nothing consumes is a typo or a
documented-but-dead key, and silently ignoring it is why both keep shipping
(#102). The same rule covers a *value* nothing consumes: a misspelled
``uncoached`` would otherwise quietly pick a policy (#111).

A file that is not TOML at all is the same kind of refusal, which is why reading
one lives here too: unprotected, ``tomllib``'s own exception escaped as a
traceback at exit **1** — the code reserved for an enforced finding — so CI read
a missing ``]`` as a smell in the code rather than a typo in a config (#114).

The rejection names no binary, because all three console scripts load a config
through here and one hardcoded name sends the other two's users to the wrong
tool; ``cli.run_console`` names it when it prints it.

One key has a vocabulary of its own and holds it in
:mod:`habit_hooks.detectors`: what a plugin's ``detectors`` may say, refusals
included, moved out whole under this file's own 200-line gate.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import define, field, fields

from .catalogue import UNCOACHED_POLICIES, UNCOACHED_SUGGEST
from .cli import ConfigError

if TYPE_CHECKING:  # `detectors` imports the key refusals below, so this way only.
    from .detectors import Detector


@define
class SmellOverride:
    severity: str | None = None
    guide: str | None = None
    disabled: bool | None = None


@define
class ScopeDefaults:
    changedOnly: bool = False
    autoBranchOffMain: bool = False
    branchBase: str = "main"
    mainBranch: str = "main"


@define
class SensorOverride:
    disabled: bool | None = None
    files: list[str] | None = None
    args: list[str] | None = None


@define
class Config:
    plugins: list[str] = field(factory=lambda: ["generic"])
    # Snooze is on by default so a checked-in index takes effect without wiring;
    # naming `transformers` replaces the list wholesale, which is how a project
    # drops it or orders it against its own steps.
    transformers: list[str] = field(factory=lambda: ["snooze"])
    files: list[str] | None = None
    # What happens to a smell the catalogue does not name: it coaches without
    # failing the run unless this says otherwise (see ``rendering.severity_of``).
    uncoached: str = UNCOACHED_SUGGEST
    scope: ScopeDefaults = field(factory=ScopeDefaults)
    sensors: dict[str, SensorOverride] = field(factory=dict)
    runners: dict[str, str] = field(factory=dict)
    smells: dict[str, SmellOverride] = field(factory=dict)
    # Each active plugin's declared language (generic declares none). The mapper
    # reads it to prefer, for a finding of a given language, a plugin that speaks
    # it over the languageless fallback. Populated by the loader, never from TOML.
    plugin_languages: dict[str, str] = field(factory=dict, metadata={"internal": True})
    # Every active plugin's declared detectors. A plugin-only key: a project
    # names the plugins it runs, and what each of those needs installed is the
    # plugin's to declare. Populated by the loader, never from TOML.
    plugin_detectors: list[Detector] = field(factory=list, metadata={"internal": True})


# The keys a plugin ``config.toml`` may set: ``sensors``/``transformers``/
# ``language`` read in ``sensors/loader.py``; ``files``/``runners``/``language``/
# ``detectors`` read by the config loader. Unlike the project config these are
# not one attrs type, so the allowed set is named here.
PLUGIN_CONFIG_KEYS = frozenset(
    {"sensors", "transformers", "language", "files", "runners", "detectors"}
)


def read_toml(path: Path) -> dict:
    """``path`` parsed, or a ``ConfigError`` naming the file and what is wrong.

    Every TOML this tool reads goes through here — the project config, a
    plugin's, a sensor or transformer spec — so a hand-edit slip in any of them
    answers with one line rather than a stack trace. ``tomllib``'s own text is
    the diagnosis: it already carries the line and column to go and look at.
    """
    with path.open("rb") as file:
        try:
            return tomllib.load(file)
        except tomllib.TOMLDecodeError as invalid:
            raise ConfigError(f"{path}: invalid TOML: {invalid}") from None


def settable(cls: type) -> set[str]:
    """The keys a user may set on ``cls``: its attrs fields, minus internals."""
    return {f.name for f in fields(cls) if f.metadata.get("internal") is not True}


def named_keys(keys: list[str]) -> str:
    """``keys`` quoted behind the right one of "key"/"keys", for a refusal."""
    label = "key" if len(keys) == 1 else "keys"
    return f"{label} {', '.join(repr(key) for key in keys)}"


def reject_unknown(allowed: frozenset[str] | set[str], data: dict, where: str) -> None:
    """Fail clearly on any key in ``data`` that ``where`` does not consume."""
    unknown = sorted(key for key in data if key not in allowed)
    if not unknown:
        return
    raise ConfigError(
        f"unknown config {named_keys(unknown)} in {where}; "
        f"known keys: {', '.join(sorted(allowed))}"
    )


def reject_unknown_uncoached_value(value: object) -> None:
    """Fail clearly on an ``uncoached`` value that is not one of the policies."""
    if value in UNCOACHED_POLICIES:
        return
    known = ", ".join(repr(policy) for policy in sorted(UNCOACHED_POLICIES))
    raise ConfigError(
        f"unknown 'uncoached' value {value!r} in the project config; "
        f"known values: {known}"
    )
