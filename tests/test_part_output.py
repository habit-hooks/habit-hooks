"""What a broken sensor's output becomes: the notice the run reports.

Running a part is ``test_sensor_subprocess.py``; this is the reading back — the
``part_output`` question of how a failure is described once the command has
exited. A command nobody installed is the one failure the tool has no words of
its own for, because it never ran, so habit-hooks supplies them (#114).
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def _sensor_notice(tmp_path: Path, command: str) -> str:
    """The one notice a sensor running ``command`` leaves on its failed run."""
    part = Part(name="probe", command=command, directory=tmp_path)
    execution = Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))

    run = execution.run_sensors([part])

    assert run.findings == []
    assert run.failed
    assert len(run.notices) == 1
    return run.notices[0]


def test_a_sensor_whose_tool_is_not_installed_names_the_tool(tmp_path: Path) -> None:
    """The commonest failure on a machine that has just met habit-hooks answered
    as whatever the shell or the sensor's own helper happened to print — for
    jscpd, twenty lines of Python internals whose punchline named the binary only
    as a filename that could not be found (#114). It is still the same notice +
    failed run any broken sensor produces; the notice now says what to install,
    and what to do instead of installing it."""
    notice = _sensor_notice(tmp_path, "no-such-tool-here --json ${files}")

    assert notice == (
        "habit-sensors: sensor 'probe' needs the 'no-such-tool-here' command, "
        "which is not installed — install it, or disable the sensor with "
        "[sensors.probe] disabled = true"
    )


def test_a_tool_missing_from_inside_a_pipeline_is_named_too(tmp_path: Path) -> None:
    """The shipped ``ruff`` and ``eslint`` sensors both pipe their tool through
    ``jq`` under ``set -o pipefail``, so the missing half is never the last thing
    the shell mentions — the whole command's output is searched for it."""
    pipeline = "set -o pipefail\nno-such-tool-here | jq ."

    assert "needs the 'no-such-tool-here' command" in _sensor_notice(tmp_path, pipeline)


def test_a_sensor_that_broke_some_other_way_still_quotes_itself_back(
    tmp_path: Path,
) -> None:
    """Only a command that was never found is answered in our own words. Every
    other failure is the tool diagnosing itself, and that is the one thing a
    reader can act on, so it is still carried into the notice verbatim."""
    notice = _sensor_notice(tmp_path, "echo 'cannot reach registry' >&2; exit 1")

    assert notice.startswith("habit-sensors: sensor 'probe' failed:")
    assert "cannot reach registry" in notice
