"""What a part's finished process actually said, and whether to believe it.

A sensor or transformer is a command that printed something and exited. Reading
that back is its own question, separate from running it: the findings it claims,
whether the exit code says those findings can be trusted, and — when it cannot —
how to describe the failure in the part's own words.

The whole family of bugs this guards against is a broken tool reporting a clean
run: empty stdout parses as "no findings", which is indistinguishable from a
tool that died before printing unless the exit code is consulted too.
"""

from __future__ import annotations

import json
import subprocess

from .model import Part, SensorError

TOOL_EXIT_CODES = (0, 1)

# How much of a failing part's own output is quoted back. habit-hooks writes to a
# coding agent's context, and a tool that dies mid-warning-storm can produce
# megabytes; the first lines carry the diagnosis, the rest only crowds it out.
DIAGNOSIS_LINE_LIMIT = 20


def parse_findings(stdout: str) -> list[dict]:
    text = stdout.strip()
    findings = json.loads(text) if text else []
    if not isinstance(findings, list):
        raise ValueError("output is not a findings array")
    return findings


def part_failure(
    kind: str, part: Part, result: subprocess.CompletedProcess[str]
) -> SensorError:
    """Why it failed, in the part's own words whenever it said anything.

    Naming the command says only *what* broke. A part that diagnosed its own
    failure — the missing base ref `snooze-until-changed` names and the setting
    that fixes it, the npm package a sensor could not `require` — is the one
    thing a pipeline user can act on, and its stderr is otherwise thrown away.
    """
    diagnosis = _first_lines(result.stderr.strip())
    return SensorError(
        f"{kind} {part.name!r} failed: {part.command}"
        + (f"\n{diagnosis}" if diagnosis else "")
    )


def _first_lines(diagnosis: str) -> str:
    """The opening of a part's complaint, saying so when there was more."""
    lines = diagnosis.splitlines()
    if len(lines) <= DIAGNOSIS_LINE_LIMIT:
        return diagnosis
    dropped = len(lines) - DIAGNOSIS_LINE_LIMIT
    return "\n".join([*lines[:DIAGNOSIS_LINE_LIMIT], f"... and {dropped} more lines"])


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
