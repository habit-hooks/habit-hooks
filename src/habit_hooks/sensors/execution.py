"""Runs a part's command in a project directory against a scope, then parses the
JSON findings it emits — the bin/PATH + subprocess layer of the ETL."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..scope import Scope
from .finding_paths import aliasing_notices, anchored
from .model import Part, Run, SensorError

ACCEPTED_EXIT_CODES = (0, 1)


def _parse_findings(stdout: str) -> list[dict]:
    text = stdout.strip()
    findings = json.loads(text) if text else []
    if not isinstance(findings, list):
        raise ValueError("output is not a findings array")
    return findings


def _part_failure(
    kind: str, part: Part, result: subprocess.CompletedProcess[str]
) -> SensorError:
    """Why it failed, in the part's own words whenever it said anything.

    Naming the command says only *what* broke. A part that diagnosed its own
    failure — the missing base ref `snooze-until-changed` names and the setting
    that fixes it, the npm package a sensor could not `require` — is the one
    thing a pipeline user can act on, and its stderr is otherwise thrown away.
    """
    diagnosis = result.stderr.strip()
    return SensorError(
        f"{kind} {part.name!r} failed: {part.command}"
        + (f"\n{diagnosis}" if diagnosis else "")
    )


def _sensor_crashed(result: subprocess.CompletedProcess[str]) -> bool:
    """Whether the sensor's exit says its output cannot be trusted.

    Exit 1 is how a linter says "I found things", so it is accepted — but only
    alongside the findings that justify it. A non-zero exit with nothing on
    stdout is a tool that died before it could print, which `_parse_findings`
    would otherwise read as an empty findings array and the run would report
    clean. Exit 0 stays trusted either way: it is the sensor explicitly claiming
    it finished, and a silent sensor can only add nothing, never discard what
    the others found.
    """
    if result.returncode not in ACCEPTED_EXIT_CODES:
        return True
    return result.returncode != 0 and not result.stdout.strip()


@dataclass(frozen=True)
class Execution:
    """Where commands run: a project directory and the scope they see.

    Holds the run context and offers the command running — expanding a part's
    placeholders, shelling out with the project bins on PATH, and parsing the
    findings the command prints.
    """

    project_dir: Path
    scope: Scope

    def run_sensors(self, sensors: list[Part]) -> Run:
        if not sensors:
            return Run()
        with ThreadPoolExecutor(max_workers=len(sensors)) as pool:
            outputs = list(pool.map(self._safe_sensor, sensors))
        run = Run()
        for findings, notices in outputs:
            run.findings.extend(findings)
            run.notices.extend(notices)
        return run

    def apply_transformers(
        self, transformers: list[Part], findings: list[dict]
    ) -> tuple[list[dict], list[str]]:
        """Pipe the findings through each transformer, surviving a broken one.

        A failed transformer keeps the findings it was given: its stdout cannot
        be trusted, and treating silence as "no findings" would let one crash
        discard the whole run and report clean.
        """
        notices = []
        for transformer in transformers:
            try:
                findings = self._transform(transformer, findings)
            except SensorError as error:
                notices.append(f"habit-sensors: {error}")
        return findings, notices

    def _transform(self, transformer: Part, findings: list[dict]) -> list[dict]:
        """One transformer's output, or ``SensorError`` if it cannot be trusted.

        Stricter than a sensor: a transformer has no convention for exiting
        non-zero, and must print its array explicitly. An empty stdout is a
        crash, whereas a literal ``[]`` is a legitimate "everything dropped".
        """
        command = self._expand(transformer)
        result = self._run(command, json.dumps(findings))
        failure = _part_failure("transformer", transformer, result)
        if result.returncode != 0 or not result.stdout.strip():
            raise failure
        try:
            return _parse_findings(result.stdout)
        except (ValueError, json.JSONDecodeError):
            raise failure from None

    def run_sensor(self, sensor: Part) -> list[dict]:
        """The sensor's findings, with every path anchored to the project.

        Anchoring here — where a sensor's output enters the run, for every sensor
        there is — is what keeps a snooze index portable without any sensor
        having to know that (``finding_paths.py``).
        """
        command = self._expand(sensor)
        result = self._run(command)
        failure = _part_failure("sensor", sensor, result)
        if _sensor_crashed(result):
            raise failure
        try:
            findings = _parse_findings(result.stdout)
        except (ValueError, json.JSONDecodeError):
            raise failure from None
        return anchored(findings, self.project_dir, sensor.name)

    def _safe_sensor(self, sensor: Part) -> tuple[list[dict], list[str]]:
        """Its findings and whatever the run must be told about them.

        An unanchorable path is a broken sensor: no findings, one notice. Aliased
        keys leave the findings standing — they are sound, it is snoozing them
        that would not be — and still fail the run, because a warning nobody has
        to act on is how #79 stayed invisible in the first place.
        """
        try:
            findings = self.run_sensor(sensor)
        except SensorError as error:
            return [], [f"habit-sensors: {error}"]
        return findings, [
            f"habit-sensors: {notice}"
            for notice in aliasing_notices(findings, sensor.name)
        ]

    def _expand(self, part: Part) -> str:
        files = " ".join(self.scope.files)
        args = " ".join(shlex.quote(arg) for arg in part.args)
        return (
            part.command.replace("${python}", shlex.quote(sys.executable))
            .replace("${dir}", str(part.directory))
            .replace("${args}", args)
            .replace("${files}", files)
        )

    def _run(
        self, command: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", command],
            cwd=self.project_dir,
            env=self._path_env(),
            input=stdin,
            capture_output=True,
            text=True,
        )

    def _path_env(self) -> dict:
        env = dict(os.environ)
        bins = [
            self.project_dir / "node_modules" / ".bin",
            self.project_dir / ".venv" / "bin",
        ]
        prefix = os.pathsep.join(str(b) for b in bins)
        env["PATH"] = prefix + os.pathsep + env.get("PATH", "")
        return env
