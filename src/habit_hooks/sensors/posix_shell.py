"""Whether a part's ``command`` recipe can be read here at all.

A ``command`` part is text for ``bash -c`` (``command_text``), which every POSIX
platform has and Windows has not. What Windows has instead, at
``C:\\Windows\\System32\\bash.exe``, is the WSL launcher, and neither of its
answers is a run: with no distribution installed it puts UTF-16 prose on the
stdout where findings JSON belongs — seen on the CI runner, where nothing in
that output said what had gone wrong — and with one installed it is worse, since
the tool then measures another filesystem and reports about files that are not
the ones being scanned. So the platform decides this, never a search for a
``bash`` binary: a findable ``bash`` is exactly the trap.

Refusing it is one part failing, not the run dying — a ``SensorError``, so the
notice, the failed run and that part's dropped findings are the ones every
broken part already earns. A plugin that ships one shell sensor must not cost a
project the findings of all its others, and a run that silently skipped the part
instead would report clean, which is the whole class #88 exists for.

The person who reads it cannot fix that plugin, so it names the action they do
have: switch the part off, spelled in the config key that part answers to.
"""

from __future__ import annotations

from .. import host_platform
from .model import Part, SensorError
from .part_output import switch_off


def refuse_where_there_is_none(kind: str, part: Part) -> None:
    """Stop ``part`` before it spawns when no shell here can read its recipe."""
    if part.command is None or not host_platform.is_windows():
        return
    raise SensorError(
        f"{kind} {part.name!r} cannot run on Windows: its recipe is a shell "
        f"command line, and there is no POSIX shell here to read it — "
        f"{switch_off(kind, part.name)}"
    )
