"""What a broken sensor's output becomes: the notice the run reports.

Running a part is ``test_sensor_deadline.py`` and ``test_sensor_environment.py``;
this is the reading back — which failure is being described, once the command
has exited. How much of the tool's own words come with it is
``test_how_much_a_failure_says.py``. A command nobody installed is the one failure the tool has no words of
its own for, because it never ran, so habit-hooks supplies them (#114).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from platform_probe import A_SHELL_TO_RUN_IT_WITH, off_windows

from sensor_notice import only_notice, script_notice, sensor_notice

from habit_hooks.sensors.model import Part


@A_SHELL_TO_RUN_IT_WITH
def test_a_sensor_whose_tool_is_not_installed_names_the_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commonest failure on a machine that has just met habit-hooks answered
    as whatever the shell or the sensor's own helper happened to print — for
    jscpd, twenty lines of Python internals whose punchline named the binary only
    as a filename that could not be found (#114). It is still the same notice +
    failed run any broken sensor produces; the notice now says what to install,
    and what to do instead of installing it.

    ``COMMAND_NOT_FOUND`` recognises the real shell's own words for this, so
    proving it needs a real shell to say them — pinned off Windows, skipped
    where there is none. The argv form's equivalent is
    ``test_an_argv_sensor_names_its_missing_tool_in_the_very_same_words`` below.
    """
    off_windows(monkeypatch)
    notice = sensor_notice(tmp_path, "no-such-tool-here --json ${files}")

    assert notice == (
        "habit-sensors: sensor 'probe' needs the 'no-such-tool-here' command, "
        "which is not installed — install it, or disable the sensor with "
        "[sensors.probe] disabled = true"
    )


@A_SHELL_TO_RUN_IT_WITH
def test_a_tool_missing_from_inside_a_pipeline_is_named_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shipped ``ruff`` and ``eslint`` sensors both pipe their tool through
    ``jq`` under ``set -o pipefail``, so the missing half is never the last
    thing the shell mentions — the whole command's output is searched for it.
    The pipe is the point, so, like its sibling above, this pins off Windows.
    """
    off_windows(monkeypatch)
    pipeline = "set -o pipefail\nno-such-tool-here | jq ."

    assert "needs the 'no-such-tool-here' command" in sensor_notice(tmp_path, pipeline)


def test_a_sensor_that_broke_some_other_way_still_quotes_itself_back(
    tmp_path: Path,
) -> None:
    """Only a command that was never found is answered in our own words. Every
    other failure is the tool diagnosing itself, and that is the one thing a
    reader can act on, so it is still carried into the notice verbatim."""
    notice = script_notice(
        tmp_path,
        "import sys\n"
        "print('cannot reach registry', file=sys.stderr)\n"
        "sys.exit(1)\n",
    )

    assert notice.startswith("habit-sensors: sensor 'probe' failed:")
    assert "cannot reach registry" in notice


def test_an_argv_sensor_names_its_missing_tool_in_the_very_same_words(
    tmp_path: Path,
) -> None:
    """An argv part has no shell to say ``command not found`` for it — the
    spawn just fails — and a generic "could not run" would leave the commonest
    first-contact failure (#114) undiagnosed on exactly the platform that has
    no shell to fall back on. So the answer is the shell's own, word for word:
    which form a sensor is spelled in must not change what a newcomer reads."""
    part = Part(
        name="probe", directory=tmp_path, argv=["no-such-tool-here", "--json"]
    )

    assert only_notice(part, tmp_path) == (
        "habit-sensors: sensor 'probe' needs the 'no-such-tool-here' command, "
        "which is not installed — install it, or disable the sensor with "
        "[sensors.probe] disabled = true"
    )


def test_a_spawn_refused_for_another_reason_is_not_called_a_missing_tool(
    tmp_path: Path,
) -> None:
    """``Popen`` raises the same ``FileNotFoundError`` for a missing program and
    for a project directory that is gone, and only the spawning layer can tell
    them apart. Reading the second as the first would name a tool that is
    installed and send the reader off to install it again."""
    part = Part(name="probe", directory=tmp_path, argv=["printf", "[]"])

    notice = only_notice(part, tmp_path / "deleted")

    assert "needs the" not in notice
    assert notice.startswith("habit-sensors: sensor 'probe' could not run: printf '[]'")

