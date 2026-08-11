"""Refuse a config this tool cannot honour, naming what it could not honour.

Unknown keys are rejected at every level — project *and* plugin config — with a
``ConfigError`` (exit 2): a key nothing consumes is a typo or a
documented-but-dead key, and silently ignoring it is why both keep shipping
(#102). The allowed keys are the type's declared attrs fields (minus
loader-populated internals). The same rule covers a *value* nothing consumes:
a misspelled ``uncoached`` would otherwise quietly pick a policy (#111).

A file that is not TOML at all is the same kind of refusal, which is why reading
one lives here too: unprotected, ``tomllib``'s own exception escaped as a
traceback at exit **1** — the code reserved for an enforced finding — so CI read
a missing ``]`` as a smell in the code rather than a typo in a config (#114).

The rejection names no binary, because all three console scripts load a config
through this guard and one hardcoded name sends the other two's users to the
wrong tool; ``cli.run_console`` names it when it prints it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from attrs import fields

from .catalogue import UNCOACHED_POLICIES
from .cli import ConfigError

# The keys a plugin ``config.toml`` may set: ``sensors``/``transformers``/
# ``language`` read in ``sensors/loader.py``; ``files``/``runners``/``language``
# read by the config loader. Unlike the project config these are not one attrs
# type, so the allowed set is named here.
PLUGIN_CONFIG_KEYS = frozenset({"sensors", "transformers", "language", "files", "runners"})


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


def reject_unknown(allowed: frozenset[str] | set[str], data: dict, where: str) -> None:
    """Fail clearly on any key in ``data`` that ``where`` does not consume."""
    unknown = sorted(key for key in data if key not in allowed)
    if not unknown:
        return
    label = "key" if len(unknown) == 1 else "keys"
    names = ", ".join(repr(key) for key in unknown)
    raise ConfigError(
        f"unknown config {label} {names} in {where}; "
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
