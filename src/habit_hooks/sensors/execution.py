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
from .model import Part, Run, SensorError

ACCEPTED_EXIT_CODES = (0, 1)


def _parse_findings(stdout: str) -> list[dict]:
    text = stdout.strip()
    findings = json.loads(text) if text else []
    if not isinstance(findings, list):
        raise ValueError("output is not a findings array")
    return findings


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
        for findings, notice in outputs:
            run.findings.extend(findings)
            if notice:
                run.notices.append(notice)
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
        failure = SensorError(
            f"transformer {transformer.name!r} failed: {transformer.command}"
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise failure
        try:
            return _parse_findings(result.stdout)
        except (ValueError, json.JSONDecodeError):
            raise failure from None

    def run_sensor(self, sensor: Part) -> list[dict]:
        command = self._expand(sensor)
        result = self._run(command)
        if result.returncode not in ACCEPTED_EXIT_CODES:
            raise SensorError(f"sensor {sensor.name!r} failed: {sensor.command}")
        try:
            return _parse_findings(result.stdout)
        except (ValueError, json.JSONDecodeError):
            raise SensorError(
                f"sensor {sensor.name!r} failed: {sensor.command}"
            ) from None

    def _safe_sensor(self, sensor: Part) -> tuple[list[dict], str | None]:
        try:
            return self.run_sensor(sensor), None
        except SensorError as error:
            return [], f"habit-sensors: {error}"

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
