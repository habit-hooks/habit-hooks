"""What running one part comes to when it cannot run, or breaks while running.

A part is somebody else's program, and this is the boundary that knows whose:
the spawn beneath it is handed an argv and nothing more, while a notice has to
name the part and tell whoever reads it what to do instead. So every way of
breaking is named for its part here, and comes to the one thing the run already
survives — a ``SensorError``, or an answer that reads back as one: the notice,
the failed run and that part's dropped findings every broken part earns. One
broken part must never cost the run the others' findings, and running other
people's programs must never end in a traceback.

Three are settled before anything is spawned. A recipe this platform has no
shell for is refused as the one part failing that it is (``posix_shell``), and
it is asked here because this is the boundary that knows both the part and
whether it is a sensor or a transformer — which is what decides how to say
"switch it off". A tool the project cannot run is the part naming one of its
plugin's declared tools (``named_tools``) that this project has no file for, so
there is nothing to spawn: it answers in the shell's own words for a command
nobody installed, because that is what it is, and the one recogniser that
already names a missing command names this one too. An argument the shell
behind a batch file would read as its own syntax is refused deeper down, where
the program has become a file and can be recognised as one (``batch_shell``);
that refusal knows everything about itself except which part earned it, so this
is where the part's name goes on the front of it.

Two more end a spawn that had started. A wedged tool that never returns must
not block the hook: its deadline becomes the same notice + failed run any other
spawn failure produces. A spawn the operating system refuses outright is that
failure one step earlier, and raises an ``OSError`` nothing between here and
``main`` caught.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from . import batch_shell, posix_shell
from .model import Part, SensorError
from .part_output import command_not_found, part_spawn_failure, part_timeout


def run_part(
    kind: str, part: Part, run: Callable[[], subprocess.CompletedProcess[str]]
) -> subprocess.CompletedProcess[str]:
    """``run()``'s result, or the failure this part earned in place of one."""
    posix_shell.refuse_where_there_is_none(kind, part)
    if part.missing_detector is not None:
        return command_not_found([part.missing_detector])
    try:
        return run()
    except batch_shell.UnreadableArgument as refusal:
        raise SensorError(f"{kind} {part.name!r} {refusal}") from None
    except subprocess.TimeoutExpired as expiry:
        raise part_timeout(kind, part, expiry) from None
    except OSError as refusal:
        raise part_spawn_failure(kind, part, refusal) from None
