"""The argv a part actually runs: placeholders filled in, and a shell only when
the part asked for one.

A part spells one of two recipes, and this is where the difference is spent:

* ``argv = [...]`` is spawned exactly as written. No shell reads it, so nothing
  is quoted — quoting exists so a shell cannot mistake a filename for syntax,
  and with no shell in the way a quote character would simply become part of
  the filename. It is also the only form that runs where there is no POSIX
  shell: on Windows ``bash`` is usually the WSL launcher, which answers from
  another filesystem entirely.
* ``command = "..."`` is text for ``bash -c``, and buys syntax a list cannot
  carry — the ``ruff`` and ``eslint`` sensors pipe their tool through ``jq`` —
  at the price of a shell to read it, which is why a platform without one
  refuses the part rather than spawning it (``posix_shell``).
  Everything spliced into that text is quoted first, a path most of all: it
  comes from the work tree, so an unquoted ``${files}`` lets a filename execute
  its own contents.

**A placeholder is either a string or a list, and the argv form tells them
apart.** ``${python}``, ``${dir}`` and ``${detector:<name>}`` — the file this
project runs for one of its plugins' declared tools (``named_tools``) — are
strings: they are substituted inside an element, so ``"${dir}/line-count.py"``
stays one argument, and a tool's own path stays the one value it is. ``${files}``,
``${args}`` and ``${config}`` are lists: an element that is exactly one of them
becomes zero or more arguments in its place. An element that merely contains
one — ``"--paths=${files}"`` — is refused rather than joined, because joining a
file list into a single argument is the bug the argv form exists to make
impossible. The ``command`` form needs no such distinction: a shell splits the
text on its own spaces.

Building the argv is its own question, separate from spawning it (``spawn.py``)
and from reading back what it printed (``part_output.py``): it is also what the
argv budget is spent on, and the budget can only count text that already exists.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from ..cli import ConfigError
from .model import Part
from .named_tools import spelled_for_a_shell, spelled_plainly

LIST_PLACEHOLDERS = ("${files}", "${args}", "${config}")


def spelled_files(part: Part, files: list[str]) -> list[str]:
    """``files`` as ``part``'s spawn will carry them — and so as it must budget.

    Quoting before the chunking rather than after is what lets the argv budget
    count the bytes the spawn actually carries: spliced into a command's text
    ``it's.py`` costs 12, not 7, and a chunk measured raw arrives half as long
    again. An argv carries each path as an argument of its own, which nothing
    reads as syntax, so there it costs exactly what it is.
    """
    if part.argv is not None:
        return list(files)
    return [shlex.quote(path) for path in files]


def spells(part: Part, placeholder: str) -> bool:
    """Whether ``part``'s recipe has anywhere to put ``placeholder``.

    An argv spells a list placeholder as a whole element of its own — anything
    else is refused below — so membership answers it; a command spells it
    somewhere inside its text.
    """
    if part.argv is not None:
        return placeholder in part.argv
    return placeholder in (part.command or "")


def expanded(part: Part, files: list[str], config_path: Path | None) -> list[str]:
    """The argv that runs ``part`` over ``files``, its own shell included.

    ``files`` arrive spelled for this part's form (:func:`spelled_files`), as
    the chunking that measured them had to spell them first.
    """
    _refuse_unusable_arguments(part)
    if part.argv is not None:
        return _argv_form(part, files, config_path)
    return ["bash", "-c", _shell_form(part, files, config_path)]


def _argv_form(part: Part, files: list[str], config_path: Path | None) -> list[str]:
    """Every element of ``part.argv``, substituted or expanded where it stands."""
    lists = {
        "${files}": files,
        "${args}": part.args,
        "${config}": _config_arguments(config_path),
    }
    return [
        argument
        for element in part.argv or []
        for argument in _element_arguments(part, element, lists)
    ]


def _element_arguments(
    part: Part, element: str, lists: dict[str, list[str]]
) -> list[str]:
    """What one argv element becomes: a list placeholder's arguments, or itself."""
    if element in lists:
        return lists[element]
    _refuse_embedded_list_placeholder(part, element)
    return [
        spelled_plainly(part, element)
        .replace("${python}", sys.executable)
        .replace("${dir}", str(part.directory))
    ]


def _shell_form(part: Part, files: list[str], config_path: Path | None) -> str:
    """``part.command`` with every value quoted for the shell about to read it."""
    return (
        spelled_for_a_shell(part, part.command or "")
        .replace("${python}", shlex.quote(sys.executable))
        .replace("${dir}", shlex.quote(str(part.directory)))
        .replace("${args}", shlex.join(part.args))
        .replace("${files}", " ".join(files))
        .replace("${config}", shlex.join(_config_arguments(config_path)))
    )


def _refuse_embedded_list_placeholder(part: Part, element: str) -> None:
    """Stop the run when an argv element buries a placeholder that is a list.

    ``"--paths=${files}"`` has no honest expansion. The files are separate
    arguments, and the one thing that could be done with them here — joining
    them into a single argument — is the mistake the argv form exists to make
    impossible, so it is refused where the author can still see why rather than
    handed to the tool as one very long filename.
    """
    embedded = next((name for name in LIST_PLACEHOLDERS if name in element), None)
    if embedded is None:
        return
    raise ConfigError(
        f"{part.name!r} cannot expand {embedded} inside {element!r} — it stands "
        f"for a whole list of arguments, so it has to be an argv element of its "
        f"own; split it into two elements, or use a 'command' string, where a "
        "shell does the splitting"
    )


def _refuse_unusable_arguments(part: Part) -> None:
    """Stop the run when ``part`` has args its recipe has nowhere to put.

    This is the only place that knows both the args and whether the recipe can
    take them, and args a recipe cannot expand are args the tool never sees —
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
    if not part.args or spells(part, "${args}"):
        return
    raise ConfigError(
        f"sensor {part.name!r} cannot take arguments — its command has no "
        f"'${{args}}' to expand {part.args} into; remove the 'args', clear a "
        f"plugin's own default with [sensors.{part.name}] args = [], or override "
        "the sensor with a command that spells '${args}'"
    )


def _config_arguments(config_path: Path | None) -> list[str]:
    """``--config <path>`` when the run named a config, else nothing.

    A transformer runs as its own process, so the only way it sees the run's
    ``--config`` is to be handed it. The placeholder carries the whole flag,
    not just the path, so a run with no ``--config`` expands to nothing
    rather than a dangling ``--config`` with no argument.
    """
    if config_path is None:
        return []
    return ["--config", str(config_path)]
