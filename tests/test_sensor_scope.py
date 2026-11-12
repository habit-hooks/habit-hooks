
from __future__ import annotations

import shlex
from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def test_sensor_files_narrow_the_expanded_file_list(tmp_path: Path) -> None:
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


def test_an_empty_scope_runs_no_scoped_sensor(tmp_path: Path) -> None:
    marker = tmp_path / "SENSOR_RAN"
    part = Part(
        name="probe",
        command=f"touch {shlex.quote(str(marker))}; printf '[]' ${{files}}",
        directory=tmp_path,
        args=[],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=[]))

    run = execution.run_sensors([part])

    assert run.findings == []
    assert not marker.exists()


def test_an_empty_scope_still_runs_a_whole_project_sensor(tmp_path: Path) -> None:
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
    assert marker.exists()


def test_a_non_empty_scope_still_runs_its_sensors(tmp_path: Path) -> None:
    part = Part(
        name="probe",
        directory=tmp_path,
        argv=[
            "${python}",
            "-c",
            'print(\'[{"smell": "oversized-file", "issues": []}]\')',
        ],
        args=[],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))

    run = execution.run_sensors([part])

    assert run.findings == [{"smell": "oversized-file", "issues": []}]


def test_a_sensor_narrowed_to_no_files_does_not_run(tmp_path: Path) -> None:
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
    narrowed = Part(
        name="narrowed",
        directory=tmp_path,
        argv=["${python}", "-c", "print('[]')"],
        args=[],
        files=["*.js"],
    )
    kept = Part(
        name="kept",
        directory=tmp_path,
        argv=[
            "${python}",
            "-c",
            'print(\'[{"smell": "oversized-file", "issues": []}]\')',
        ],
        args=[],
        files=["*.py"],
    )
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["a.py"]))

    run = execution.run_sensors([narrowed, kept])

    assert run.findings == [{"smell": "oversized-file", "issues": []}]
