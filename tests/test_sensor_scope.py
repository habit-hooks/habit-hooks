"""Unit tests for the scope a single sensor sees: how its own ``files`` narrow
the run's scope, and when that leaves it nothing to run over."""

from __future__ import annotations

import shlex
from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def test_sensor_files_narrow_the_expanded_file_list(tmp_path: Path) -> None:
    """A sensor's own ``files`` selects a subset of the run's scope for it alone.

    The scope is still resolved once; this is a central filter over the files that
    scope already picked, never a second scope derivation.
    """
    part = Part(
        name="probe",
        command="${files}",
        directory=tmp_path,
        args=[],
        files=["src/**"],
    )
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/a.py", "tests/b.py"])
    )

    assert execution._expand(part) == ["bash", "-c", "src/a.py"]


def test_no_sensor_files_leaves_the_whole_scope(tmp_path: Path) -> None:
    part = Part(name="probe", command="${files}", directory=tmp_path, args=[])
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/a.py", "tests/b.py"])
    )

    assert execution._expand(part) == ["bash", "-c", "src/a.py tests/b.py"]


def test_an_empty_scope_runs_no_sensor(tmp_path: Path) -> None:
    """A scope that measured nothing must not spawn a sensor — issue #93.

    A tool handed no paths falls back to its own default (``ruff``'s is "scan
    the current directory"), reporting every legacy smell in the whole repo over
    a scope that named none. The runner absorbs it centrally so no sensor, now or
    third-party, has to guard it: an empty scope short-circuits to an empty run.
    """
    marker = tmp_path / "SENSOR_RAN"
    part = Part(
        name="probe",
        command=f"touch {shlex.quote(str(marker))}; printf '[]'",
        directory=tmp_path,
        args=[],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=[]))

    run = execution.run_sensors([part])

    assert run.findings == []
    assert not marker.exists()


def test_a_non_empty_scope_still_runs_its_sensors(tmp_path: Path) -> None:
    """The empty-scope guard must not silence a run that did measure something."""
    part = Part(
        name="probe",
        command='printf \'[{"smell": "oversized-file", "issues": []}]\'',
        directory=tmp_path,
        args=[],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))

    run = execution.run_sensors([part])

    assert run.findings == [{"smell": "oversized-file", "issues": []}]


def test_a_sensor_narrowed_to_no_files_does_not_run(tmp_path: Path) -> None:
    """A sensor's own ``files`` can empty a scope that measured something.

    Its scope is then as empty as #93's, with the same consequence: handed no
    paths, the tool falls back to its own default and reports the whole repo's
    debt. The guard is per sensor because the narrowing is.
    """
    marker = tmp_path / "SENSOR_RAN"
    part = Part(
        name="probe",
        command=f"touch {shlex.quote(str(marker))}; printf '[]' ${{files}}",
        directory=tmp_path,
        args=[],
        files=["*.js"],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["a.py"]))

    run = execution.run_sensors([part])

    assert run.findings == []
    assert not marker.exists()


def test_a_sensor_reading_its_own_paths_is_dropped_too(tmp_path: Path) -> None:
    """Whether the command splices ``${files}`` says nothing about what it scans.

    A sensor that discovers its own paths (``knip``, ``deptry``) would sweep the
    whole project over a subset narrowed to nothing, so the guard is the scope's,
    not a string test on the command.
    """
    marker = tmp_path / "SENSOR_RAN"
    part = Part(
        name="probe",
        command=f"touch {shlex.quote(str(marker))}; printf '[]'",
        directory=tmp_path,
        args=[],
        files=["*.js"],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["a.py"]))

    run = execution.run_sensors([part])

    assert run.findings == []
    assert not marker.exists()


def test_a_sibling_sensor_keeping_files_still_runs(tmp_path: Path) -> None:
    """Dropping one narrowed-out sensor must not silence the rest of the run."""
    narrowed = Part(
        name="narrowed",
        command="printf '[]'",
        directory=tmp_path,
        args=[],
        files=["*.js"],
    )
    kept = Part(
        name="kept",
        command='printf \'[{"smell": "oversized-file", "issues": []}]\'',
        directory=tmp_path,
        args=[],
        files=["*.py"],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["a.py"]))

    run = execution.run_sensors([narrowed, kept])

    assert run.findings == [{"smell": "oversized-file", "issues": []}]
