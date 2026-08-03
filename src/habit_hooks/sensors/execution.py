"""Runs a part's command in a project directory against a scope, then parses the
JSON findings it emits — the bin/PATH + subprocess layer of the ETL."""

from __future__ import annotations

import json
import shlex
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..argv_budget import within_argument_limits
from ..scope import Scope, matching
from .finding_paths import aliasing_notices, anchored
from .model import Part, Run, SensorError
from .part_output import parse_findings, part_failure, sensor_crashed
from .spawn import DEFAULT_SENSOR_TIMEOUT_SECONDS, Spawner, run_part


@dataclass(frozen=True)
class Execution:
    """Where commands run: a project directory and the scope they see.

    Holds the run context and offers the command running — expanding a part's
    placeholders, shelling out with the project bins on PATH, and parsing the
    findings the command prints.
    """

    project_dir: Path
    scope: Scope
    config_path: Path | None = None
    timeout: float = DEFAULT_SENSOR_TIMEOUT_SECONDS

    def run_sensors(self, sensors: list[Part]) -> Run:
        # A sensor whose scope is empty measured nothing, so it does not run: a
        # tool handed no paths falls back to its own default (ruff's is "scan
        # cwd"), reporting the whole repo's debt over a scope that named none
        # (#93). The scope is empty either because the run's was — the scope
        # layer already emits the "measured nothing" notice — or because the
        # sensor's own ``files`` narrowed it away, which is why the question is
        # asked per sensor. Absorbed here, every sensor — including a
        # third-party one that never heard of the convention — is covered
        # without a per-sensor guard.
        scoped = [sensor for sensor in sensors if self._scoped_files(sensor)]
        if not scoped:
            return Run()
        with ThreadPoolExecutor(max_workers=len(scoped)) as pool:
            outputs = list(pool.map(self._safe_sensor, scoped))
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
        payload = json.dumps(findings)
        result = run_part(
            "transformer", transformer, lambda: self._spawner.run(command, payload)
        )
        failure = part_failure("transformer", transformer, result)
        if result.returncode != 0 or not result.stdout.strip():
            raise failure
        try:
            return parse_findings(result.stdout)
        except (ValueError, json.JSONDecodeError):
            raise failure from None

    def run_sensor(self, sensor: Part) -> list[dict]:
        """The sensor's findings, anchored to the project, gathered chunk by chunk.

        Chunked so a work-tree-sized ``${files}`` never overflows one ``bash -c``
        argument. Anchoring the whole concatenation once (``finding_paths.py``)
        keeps a key that aliases across chunks a single key, and — where a
        sensor's output enters the run, for every sensor there is — the snooze
        index portable without any sensor having to know it.
        """
        findings: list[dict] = []
        for command in self._sensor_commands(sensor):
            findings.extend(self._sensor_findings(sensor, command))
        return anchored(findings, self.project_dir, sensor.name)

    def _sensor_findings(self, sensor: Part, command: str) -> list[dict]:
        """One invocation's parsed findings, or ``SensorError`` if untrustworthy."""
        result = run_part("sensor", sensor, lambda: self._spawner.run(command))
        failure = part_failure("sensor", sensor, result)
        if sensor_crashed(result):
            raise failure
        try:
            return parse_findings(result.stdout)
        except (ValueError, json.JSONDecodeError):
            raise failure from None

    def _sensor_commands(self, sensor: Part) -> list[str]:
        """One command per file chunk the sensor's scope splits into.

        A command that splices ``${files}`` is split so a huge list never fails
        the spawn (a raw ``OSError`` ``_safe_sensor`` never caught, escaping an
        ordinary CI-sized run as a traceback); one that reads its own paths
        (``knip``, ``deptry``, ``jscpd``) runs once, not once per chunk.
        """
        files = self._scoped_files(sensor)
        split = "${files}" in sensor.command and files
        chunks = within_argument_limits(files) if split else [files]
        return [self._expand_files(sensor, chunk) for chunk in chunks]

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
        """The command over the whole scope — its transformer form and one chunk."""
        return self._expand_files(part, self._scoped_files(part))

    def _expand_files(self, part: Part, files: list[str]) -> str:
        """The command to run over ``files``, with every substituted value quoted.

        A command is a shell string — sensors pipe through ``jq`` — so every
        value spliced into it has to be quoted or the shell reads it as syntax.
        A path is the dangerous one: it comes from the work tree, so an
        unquoted ``${files}`` lets a filename execute its own contents.
        """
        files_text = " ".join(shlex.quote(f) for f in files)
        args = " ".join(shlex.quote(arg) for arg in part.args)
        return (
            part.command.replace("${python}", shlex.quote(sys.executable))
            .replace("${dir}", shlex.quote(str(part.directory)))
            .replace("${args}", args)
            .replace("${files}", files_text)
            .replace("${config}", self._config_flag())
        )

    def _scoped_files(self, part: Part) -> list[str]:
        """The run's scope, narrowed to this sensor's own ``files`` if it has any.

        The scope is still derived once (``scope.resolve_scope``); a sensor's
        ``files`` only selects a subset of what that scope already picked, never a
        second, competing scope derivation. A sensor stating none sees all of it.
        """
        if part.files is None:
            return self.scope.files
        return matching(self.scope.files, part.files)

    def _config_flag(self) -> str:
        """``--config <path>`` when the run named a config, else nothing.

        A transformer runs as its own process, so the only way it sees the run's
        ``--config`` is to be handed it. The placeholder carries the whole flag,
        not just the path, so a run with no ``--config`` expands to nothing
        rather than a dangling ``--config`` with no argument.
        """
        if self.config_path is None:
            return ""
        return f"--config {shlex.quote(str(self.config_path))}"

    @property
    def _spawner(self) -> Spawner:
        """The subprocess layer, bound to this run's project and deadline."""
        return Spawner(self.project_dir, self.timeout)
