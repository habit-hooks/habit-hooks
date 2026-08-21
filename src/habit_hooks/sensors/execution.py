"""Runs a part's command in a project directory against a scope, then parses the
JSON findings it emits — the bin/PATH + subprocess layer of the ETL."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..argv_budget import argument_budget, argument_cost, within_argument_limits
from ..scope import Scope, matching
from .broken_part import run_part
from .command_text import expanded, spelled_files, spells
from .deadline import DEFAULT_SENSOR_TIMEOUT_SECONDS
from .finding_paths import aliasing_notices, anchored
from .live_commands import LIVE_COMMANDS
from .model import Part, Run, SensorError
from .part_output import parse_findings, part_failure, sensor_crashed
from .spawn import Spawner


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
        run = Run()
        for findings, notices in self._sensor_outputs(scoped):
            run.findings.extend(findings)
            run.notices.extend(notices)
        return run

    def _sensor_outputs(self, scoped: list[Part]) -> list[tuple[list[dict], list[str]]]:
        """Every sensor's output, in parallel, ending them all on an interrupt.

        A ``KeyboardInterrupt`` is delivered to the main thread — this one —
        while the sensors are spawned from worker threads, which never receive
        it. Leaving it there, the pool's shutdown would then wait for every
        worker, each blocked until its own command's deadline: up to five
        minutes of frozen terminal, during exactly the hang that made somebody
        press the key. Ending the commands here unblocks the workers at once,
        and it has to happen inside the ``with`` — its exit is the wait.
        """
        with ThreadPoolExecutor(max_workers=len(scoped)) as pool:
            try:
                return list(pool.map(self._safe_sensor, scoped))
            except KeyboardInterrupt:
                LIVE_COMMANDS.interrupt()
                raise

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
        argv = self._expand(transformer)
        payload = json.dumps(findings)
        tools = transformer.tools_that_read_its_arguments
        result = run_part(
            "transformer", transformer, lambda: self._spawner.run(argv, payload, tools=tools)
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

        Chunked so a work-tree-sized ``${files}`` never overflows one spawn.
        Anchoring the whole concatenation once (``finding_paths.py``) keeps a
        key that aliases across chunks a single key, and — where a sensor's
        output enters the run, for every sensor there is — the snooze index
        portable without any sensor having to know it.
        """
        findings: list[dict] = []
        for argv in self._sensor_commands(sensor):
            findings.extend(self._sensor_findings(sensor, argv))
        return anchored(findings, self.project_dir, sensor.name)

    def _sensor_findings(self, sensor: Part, argv: list[str]) -> list[dict]:
        """One invocation's parsed findings, or ``SensorError`` if untrustworthy."""
        tools = sensor.tools_that_read_its_arguments
        result = run_part("sensor", sensor, lambda: self._spawner.run(argv, tools=tools))
        failure = part_failure("sensor", sensor, result)
        if sensor_crashed(result):
            raise failure
        try:
            return parse_findings(result.stdout)
        except (ValueError, json.JSONDecodeError):
            raise failure from None

    def _sensor_commands(self, sensor: Part) -> list[list[str]]:
        """One invocation's argv per file chunk the sensor's scope splits into.

        A recipe that splices ``${files}`` is split so a huge list never fails
        the spawn (a raw ``OSError`` ``_safe_sensor`` never caught, escaping an
        ordinary CI-sized run as a traceback); one that reads its own paths
        (``knip``, ``deptry``, ``jscpd``) runs once, not once per chunk.

        Each form spends the budget on what it actually carries. A ``command``
        part's paths are quoted into one ``bash -c`` argument; an ``argv``
        part's are arguments of their own, quoted not at all. Either way the
        rest of the argv is paid for first, so the batch is measured against
        what is left rather than against the whole.
        """
        files = self._spelled_files(sensor)
        split = spells(sensor, "${files}") and files
        budget = argument_budget() - argument_cost(self._expand_files(sensor, []))
        chunks = within_argument_limits(files, budget) if split else [files]
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

    def _expand(self, part: Part) -> list[str]:
        """The argv over the whole scope — its transformer form and one chunk."""
        return self._expand_files(part, self._spelled_files(part))

    def _spelled_files(self, part: Part) -> list[str]:
        return spelled_files(part, self._scoped_files(part))

    def _expand_files(self, part: Part, files: list[str]) -> list[str]:
        return expanded(part, files, self.config_path)

    def _scoped_files(self, part: Part) -> list[str]:
        """The run's scope, narrowed to this sensor's own ``files`` if it has any.

        The scope is still derived once (``scope.resolve_scope``); a sensor's
        ``files`` only selects a subset of what that scope already picked, never a
        second, competing scope derivation. A sensor stating none sees all of it.
        """
        if part.files is None:
            return self.scope.files
        return matching(self.scope.files, part.files)

    @property
    def _spawner(self) -> Spawner:
        """The subprocess layer, bound to this run's project and deadline."""
        return Spawner(self.project_dir, self.timeout)
