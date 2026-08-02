"""Unit tests for the sensor command runner's placeholder expansion."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def _execution(tmp_path: Path) -> Execution:
    return Execution(project_dir=tmp_path, scope=Scope(files=[]))


def test_expand_replaces_python_with_the_running_interpreter(tmp_path: Path) -> None:
    part = Part(
        name="line-count",
        command="${python} ${dir}/line-count.py",
        directory=tmp_path,
        args=[],
    )

    expanded = _execution(tmp_path)._expand(part)

    assert expanded == f"{shlex.quote(sys.executable)} {tmp_path}/line-count.py"


def test_a_filename_can_never_execute_a_command(tmp_path: Path) -> None:
    """A scoped path is data. Bash must not evaluate anything inside it.

    habit-hooks runs from a git hook and in CI, so a file added by a pull
    request from a fork would otherwise run its author's command on every
    reviewer's machine.
    """
    marker = tmp_path / "PWNED"
    part = Part(
        name="probe",
        command="echo ${files} >/dev/null; printf '[]'",
        directory=tmp_path,
        args=[],
    )
    execution = Execution(
        project_dir=tmp_path,
        scope=Scope(files=[f"src/a$(touch {marker}).py"]),
    )

    execution.run_sensor(part)

    assert not marker.exists()


def test_a_filename_containing_a_space_stays_one_argument(tmp_path: Path) -> None:
    part = Part(name="probe", command="${files}", directory=tmp_path, args=[])
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/my file.py", "src/plain.py"])
    )

    expanded = execution._expand(part)

    assert expanded == "'src/my file.py' src/plain.py"


def test_expand_carries_the_named_config_to_a_transformer(tmp_path: Path) -> None:
    """A transformer is a separate process, so ``${config}`` is how the run's
    ``--config`` reaches it — one config answer for sensors and transformers."""
    part = Part(name="snooze", command="run ${config}", directory=tmp_path, args=[])
    execution = Execution(
        project_dir=tmp_path,
        scope=Scope(files=[]),
        config_path=tmp_path / "other.toml",
    )

    expanded = execution._expand(part)

    assert shlex.split(expanded) == ["run", "--config", str(tmp_path / "other.toml")]


def test_expand_drops_config_when_the_run_named_none(tmp_path: Path) -> None:
    """No ``--config`` must expand to nothing, not a bare ``--config`` flag."""
    part = Part(name="snooze", command="run ${config}", directory=tmp_path, args=[])

    expanded = _execution(tmp_path)._expand(part)

    assert shlex.split(expanded) == ["run"]


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

    assert execution._expand(part) == "src/a.py"


def test_no_sensor_files_leaves_the_whole_scope(tmp_path: Path) -> None:
    part = Part(name="probe", command="${files}", directory=tmp_path, args=[])
    execution = Execution(
        project_dir=tmp_path, scope=Scope(files=["src/a.py", "tests/b.py"])
    )

    assert execution._expand(part) == "src/a.py tests/b.py"


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


def test_a_plugin_directory_containing_a_space_still_runs(tmp_path: Path) -> None:
    directory = tmp_path / "my plugin"
    directory.mkdir()
    (directory / "findings.json").write_text(
        '[{"smell": "oversized-file", "issues": [{"key": "src/a.py"}]}]'
    )
    part = Part(
        name="probe", command="cat ${dir}/findings.json", directory=directory, args=[]
    )

    findings = Execution(project_dir=tmp_path, scope=Scope(files=[])).run_sensor(part)

    assert findings == [{"smell": "oversized-file", "issues": [{"key": "src/a.py"}]}]
