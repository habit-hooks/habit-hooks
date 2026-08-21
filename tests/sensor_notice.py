"""The notice a broken sensor leaves on its failed run.

Shared by the two suites that read one back: which failure it describes
(``test_part_output.py``) and how much of the tool's own words come with it
(``test_how_much_a_failure_says.py``) — the same line ``part_output.py`` and
``diagnosis.py`` are themselves split along.
"""

from __future__ import annotations

from pathlib import Path

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part


def sensor_notice(tmp_path: Path, command: str) -> str:
    """The one notice a sensor running ``command`` leaves on its failed run."""
    return only_notice(Part(name="probe", command=command, directory=tmp_path), tmp_path)


def script_notice(tmp_path: Path, script: str) -> str:
    """The one notice a sensor running python ``script`` leaves on its failed run.

    No shell is needed for what these tests prove — how a broken part's own
    output is quoted back — so this spells an ``argv`` part, unlike the real
    shell's own ``command not found`` diagnosis ``sensor_notice`` above needs.
    """
    (tmp_path / "probe.py").write_text(script, encoding="utf-8")
    part = Part(name="probe", directory=tmp_path, argv=["${python}", "${dir}/probe.py"])
    return only_notice(part, tmp_path)


def only_notice(part: Part, project_dir: Path) -> str:
    """The one notice ``part`` leaves on the failed run it produces."""
    execution = Execution(project_dir=project_dir, scope=Scope(files=["src/a.py"]))

    run = execution.run_sensors([part])

    assert run.findings == []
    assert run.failed
    assert len(run.notices) == 1
    return run.notices[0]
