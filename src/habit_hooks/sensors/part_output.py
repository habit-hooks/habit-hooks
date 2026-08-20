"""What a part's finished process actually said, and whether to believe it.

A sensor or transformer is a command that printed something and exited. Reading
that back is its own question, separate from running it: the findings it claims,
whether the exit code says those findings can be trusted, and — when it cannot —
how to describe the failure in the part's own words, or in ours when it has none
because the tool it wanted is not installed or the checkout it wanted is gone.
How much of those words to carry back is ``diagnosis.py``.

The whole family of bugs this guards against is a broken tool reporting a clean
run: empty stdout parses as "no findings", which is indistinguishable from a
tool that died before printing unless the exit code is consulted too.
"""

from __future__ import annotations

import errno
import json
import re
import subprocess
from pathlib import Path

from .diagnosis import as_text, keep_both_ends
from .model import Part, SensorError

TOOL_EXIT_CODES = (0, 1)

# The shell's own answer to a command it cannot find, wherever in the command it
# was: ``bash: line 2: ruff: command not found``. A part is somebody else's
# program, so this phrase is the one thing that can be recognised across all of
# them without knowing what any of them was supposed to run.
COMMAND_NOT_FOUND = re.compile(r"(?:^|: )([^:\s]+): command not found$", re.MULTILINE)

# What a shell exits with for a program it could not find.
COMMAND_NOT_FOUND_EXIT = 127


def parse_findings(stdout: str) -> list[dict]:
    text = stdout.strip()
    findings = json.loads(text) if text else []
    if not isinstance(findings, list):
        raise ValueError("output is not a findings array")
    return findings


def command_not_found(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """The answer a shell would have given for a program it cannot find.

    A ``command`` part is read by ``bash``, which diagnoses this itself —
    ``bash: line 1: ruff: command not found``, exit 127 — and that phrase is
    what :data:`COMMAND_NOT_FOUND` recognises. An ``argv`` part has no shell to
    speak for it: the spawn simply fails. Saying it here in the shell's own
    words and exit code leaves one recogniser for both forms, so the message a
    first-time user gets cannot depend on how their sensor was spelled — and
    the commonest first-contact failure (#114) stays diagnosed on exactly the
    platform that has no shell to fall back on.
    """
    return subprocess.CompletedProcess(
        argv, COMMAND_NOT_FOUND_EXIT, "", f"{argv[0]}: command not found\n"
    )


def no_project_to_run_in(project_dir: Path) -> FileNotFoundError:
    """The refusal for a spawn whose working directory is not there any more.

    Both platforms refuse this as a ``FileNotFoundError``, and only one of them
    says what it could not find: POSIX carries the directory in the error, while
    Windows answers ``[WinError 2] The system cannot find the file specified``
    about a spawn that named both a program and a directory — words that send
    the reader off to install a tool that was never the problem. So the answer
    is ours on either platform, for the same reason ``command_not_found`` above
    is: what a reader can act on is the one thing this run knows and the system
    does not say.

    It stays a ``FileNotFoundError``, because ``spawn.run_part`` turns every
    ``OSError`` into the notice + failed run that a broken part deserves — a
    checkout deleted mid-run must not surface as a traceback.
    """
    return FileNotFoundError(
        errno.ENOENT, f"the project directory is gone: {project_dir}"
    )


def part_failure(
    kind: str, part: Part, result: subprocess.CompletedProcess[str]
) -> SensorError:
    """Why it failed, in the part's own words whenever it said anything.

    Naming the command says only *what* broke. A part that diagnosed its own
    failure — the missing base ref `snooze-until-changed` names and the setting
    that fixes it, the npm package a sensor could not `require` — is the one
    thing a pipeline user can act on, and its stderr is otherwise thrown away.

    A command nobody installed is the exception: there the tool never ran, so
    there are no words of its own to carry, only the shell's.
    """
    missing = COMMAND_NOT_FOUND.search(result.stderr)
    if missing is not None:
        return _missing_tool(kind, part, missing[1])
    diagnosis = keep_both_ends(result.stderr.strip())
    return SensorError(
        f"{kind} {part.name!r} failed: {part.command_line}"
        + (f"\n{diagnosis}" if diagnosis else "")
    )


def _missing_tool(kind: str, part: Part, command: str) -> SensorError:
    """It never ran because its tool is absent — name the tool, not the search.

    A tool nobody installed is the commonest way a sensor fails on a machine that
    has just met habit-hooks, and the answer used to be whatever the shell or the
    sensor's own helper happened to print: for jscpd, twenty lines of Python
    internals whose punchline named the binary only as a filename that could not
    be found (#114). Naming the command and the part that wanted it is the whole
    diagnosis, so the rest of the output is dropped rather than quoted back.
    """
    return SensorError(
        f"{kind} {part.name!r} needs the {command!r} command, which is not "
        f"installed — install it, or {switch_off(kind, part.name)}"
    )


def switch_off(kind: str, name: str) -> str:
    """How to stop running the part, spelled in config the reader can edit.

    Only a sensor has a `disabled` switch of its own; a transformer runs because
    the root `transformers` list names it, so that list is what to edit. Shared
    with ``posix_shell``, whose refusal ends the same way: a part that cannot
    run here, and the one key its reader can do something about.
    """
    if kind == "sensor":
        return f"disable the sensor with [sensors.{name}] disabled = true"
    return f"drop {name!r} from the root transformers list"


def part_timeout(
    kind: str, part: Part, expiry: subprocess.TimeoutExpired
) -> SensorError:
    """It ran past its deadline — the same failure every other spawn failure is.

    A tool that never returns would otherwise block the git hook with no output.
    Surfacing the timeout as a ``SensorError`` makes it a notice and a failed
    run like any crash, and whatever the tool managed to print before it was
    killed is quoted back, as the only clue to what it was stuck on.
    """
    diagnosis = keep_both_ends(as_text(expiry.stderr).strip())
    return SensorError(
        f"{kind} {part.name!r} timed out after {expiry.timeout:g}s: {part.command_line}"
        + (f"\n{diagnosis}" if diagnosis else "")
    )


def part_spawn_failure(kind: str, part: Part, refusal: OSError) -> SensorError:
    """The operating system refused to start it, so it never got to speak.

    An argument list past a cap the argv budget guessed wrong, a working
    directory that is gone, no shell to read a recipe: a failure before the
    command existed, leaving nothing to quote back but the refusal itself —
    the system's own words, or ours where it had none.
    It travels the same notice + failed run channel a crash does, because a
    layer that runs other people's programs must never fail as a traceback.
    """
    return SensorError(
        f"{kind} {part.name!r} could not run: {part.command_line}\n{refusal}"
    )


def sensor_crashed(result: subprocess.CompletedProcess[str]) -> bool:
    """Whether the sensor's exit says its output cannot be trusted.

    Exit 1 is how a linter says "I found things", so it is accepted — but not
    when nothing was printed. A non-zero exit with empty stdout is a tool that
    died before it could print, which ``parse_findings`` would otherwise read as
    an empty findings array and the run would report clean. Exit 0 stays trusted
    either way: it is the sensor explicitly claiming it finished, and a silent
    sensor can only add nothing, never discard what the others found.
    """
    if result.returncode not in TOOL_EXIT_CODES:
        return True
    return result.returncode != 0 and not result.stdout.strip()
