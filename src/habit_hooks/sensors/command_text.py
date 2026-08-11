"""The text a part actually runs: its placeholders filled in, every value quoted.

A part's ``command`` is a shell string — a sensor pipes its tool through ``jq`` —
so anything spliced into it has to be quoted or the shell reads it as syntax. A
path is the dangerous one: it comes from the work tree, so an unquoted
``${files}`` lets a filename execute its own contents.

Building the text is its own question, separate from spawning it (``spawn.py``)
and from reading back what it printed (``part_output.py``): it is also what the
argv budget is spent on, and the budget can only count bytes that already exist.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from ..cli import ConfigError
from .model import Part


def quoted(paths: list[str]) -> list[str]:
    """``paths``, each spelled as the shell will read it.

    Quoting before the chunking rather than after is what lets the argv budget
    count the bytes the spawn actually carries: ``it's.py`` costs 12 on a command
    line, not 7, and a chunk measured raw arrives half as long again.
    """
    return [shlex.quote(path) for path in paths]


def expanded(part: Part, quoted_files: list[str], config_path: Path | None) -> str:
    """``part``'s command over ``quoted_files``, with every other value quoted."""
    _refuse_unusable_arguments(part)
    return (
        part.command.replace("${python}", shlex.quote(sys.executable))
        .replace("${dir}", shlex.quote(str(part.directory)))
        .replace("${args}", " ".join(shlex.quote(argument) for argument in part.args))
        .replace("${files}", " ".join(quoted_files))
        .replace("${config}", _config_flag(config_path))
    )


def _refuse_unusable_arguments(part: Part) -> None:
    """Stop the run when ``part`` has args its command has nowhere to put.

    This is the only place that knows both the args and whether the command can
    take them, and args a command cannot expand are args the tool never sees —
    the same silent nothing #102 refuses a config key nothing consumes for, and
    exactly how ``[sensors.<name>] args`` stayed dead for seven of eight shipped
    sensors while the docs promised it worked.

    Whose mistake it is does not change the answer: a plugin shipping an
    unusable ``args`` default in its own ``sensors/<name>.toml`` is refused the
    same way a project setting one is. There is no warning channel here that
    would not also fail the run (every sensor notice does, at exit 1, with that
    sensor's findings dropped), so "warn" would cost the consumer more than a
    named refusal and tell them less — and a project blocked by someone else's
    packaging can clear it with ``[sensors.<name>] args = []``, since an override
    replaces wholesale and an empty list is a value.
    """
    if not part.args or "${args}" in part.command:
        return
    raise ConfigError(
        f"sensor {part.name!r} cannot take arguments — its command has no "
        f"'${{args}}' to expand {part.args} into; remove the 'args', clear a "
        f"plugin's own default with [sensors.{part.name}] args = [], or override "
        "the sensor with a command that spells '${args}'"
    )


def _config_flag(config_path: Path | None) -> str:
    """``--config <path>`` when the run named a config, else nothing.

    A transformer runs as its own process, so the only way it sees the run's
    ``--config`` is to be handed it. The placeholder carries the whole flag,
    not just the path, so a run with no ``--config`` expands to nothing
    rather than a dangling ``--config`` with no argument.
    """
    if config_path is None:
        return ""
    return f"--config {shlex.quote(str(config_path))}"
