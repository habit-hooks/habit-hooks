"""A part whose recipe needs a shell, on a platform that has not got one.

``command = "..."`` is text for ``bash -c``. Windows has no POSIX shell, and the
``bash`` it does have — ``C:\\Windows\\System32\\bash.exe`` — is the WSL
launcher: it answers with UTF-16 prose where findings JSON belongs, or, with a
distribution installed, about a different filesystem entirely. Neither reads as
a failure, so the part is refused before it spawns — as one part failing, never
as the run dying.

Every case pins the platform through ``host_platform.is_windows()`` and asserts
that platform's answer, so each says the same thing on a Mac and on the Windows
runner. Note that ``bash`` *is* findable on the machine running these: that is
the point of the seam, since a findable ``bash`` is exactly the trap. The one
case that can only be shown by really running a shell recipe is skipped where
there is no shell to run it with — a question about the host, not about what
the code decided.

How a refused part's notice reaches the run is ``test_execution.py``; the other
half of running on Windows — ending a command's whole tree — is
``test_live_commands.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from platform_probe import off_windows, on_windows

from habit_hooks.scope import Scope
from habit_hooks.sensors import posix_shell
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.model import Part, SensorError

_A_SHELL_TO_RUN_IT_WITH = pytest.mark.skipif(
    os.name == "nt",
    reason="showing a shell recipe running takes a machine with a shell on it",
)


def _shell_sensor(tmp_path: Path, command: str) -> Part:
    return Part(name="probe", directory=tmp_path, command=command)


def _argv_sensor(tmp_path: Path) -> Part:
    """A sensor that needs no shell: it prints one finding through an argv."""
    (tmp_path / "probe.py").write_text(
        'print(\'[{"smell": "long-file", "issues": [{"key": "src/a.py"}]}]\')\n',
        encoding="utf-8",
    )
    return Part(
        name="argv-probe", directory=tmp_path, argv=["${python}", "${dir}/probe.py"]
    )


def _execution(tmp_path: Path) -> Execution:
    return Execution(project_dir=tmp_path, scope=Scope(files=["src/a.py"]))


def test_a_sensor_that_wanted_a_shell_is_refused_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The wording is the whole deliverable: whoever reads it cannot fix the
    plugin, so it has to name the part, why it cannot run, and the one line of
    config they can write instead."""
    on_windows(monkeypatch)

    with pytest.raises(SensorError) as refusal:
        posix_shell.refuse_where_there_is_none(
            "sensor", _shell_sensor(tmp_path, "ruff check | jq .")
        )

    assert str(refusal.value) == (
        "sensor 'probe' cannot run on Windows: its recipe is a shell command "
        "line, and there is no POSIX shell here to read it — disable the sensor "
        "with [sensors.probe] disabled = true"
    )


def test_a_transformer_is_refused_with_advice_that_is_true_for_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A transformer has no ``disabled`` key of its own — it runs because the
    root ``transformers`` list names it, so that list is what to edit. Advice
    naming a key that does nothing is worse than no advice."""
    on_windows(monkeypatch)
    transformer = Part(name="snooze", directory=tmp_path, command="jq .")

    with pytest.raises(SensorError) as refusal:
        posix_shell.refuse_where_there_is_none("transformer", transformer)

    assert "drop 'snooze' from the root transformers list" in str(refusal.value)
    assert "[sensors." not in str(refusal.value)


def test_a_part_spelled_as_an_argv_is_never_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The recipe decides, not the platform alone: an argv is spawned as it
    stands, with no shell anywhere in it."""
    on_windows(monkeypatch)
    part = _argv_sensor(tmp_path)

    assert posix_shell.refuse_where_there_is_none("sensor", part) is None


def test_a_shell_recipe_is_not_refused_where_a_shell_reads_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    off_windows(monkeypatch)

    part = _shell_sensor(tmp_path, "ruff check | jq .")

    assert posix_shell.refuse_where_there_is_none("sensor", part) is None


def test_a_shell_sensor_on_windows_fails_the_run_instead_of_spawning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Refused *before* the spawn, which is what the marker file proves: run,
    the recipe would leave one behind. A silent skip would report clean, which
    is the false-clean class #88 exists for, so the run fails and says why."""
    on_windows(monkeypatch)
    marker = tmp_path / "it-ran"
    part = _shell_sensor(tmp_path, f"touch {marker}; printf '[]'")

    run = _execution(tmp_path).run_sensors([part])

    assert not marker.exists()
    assert run.findings == []
    assert run.failed
    assert "no POSIX shell" in "\n".join(run.notices)


def test_a_refused_sensor_costs_the_run_only_its_own_findings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One shell sensor in a plugin must not cost a project every other
    sensor's findings — which is why this is a ``SensorError`` and not the
    ``ConfigError`` that would exit 2 and take the whole run with it."""
    on_windows(monkeypatch)
    parts = [_shell_sensor(tmp_path, "printf '[]'"), _argv_sensor(tmp_path)]

    run = _execution(tmp_path).run_sensors(parts)

    assert run.findings == [{"smell": "long-file", "issues": [{"key": "src/a.py"}]}]
    assert run.failed
    assert len(run.notices) == 1


def test_a_refused_transformer_leaves_the_findings_it_was_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A transformer that cannot run has not dropped anything: its stdout is
    untrustworthy, and reading silence as "no findings" would let one refusal
    discard the whole run and report clean."""
    on_windows(monkeypatch)
    transformer = Part(name="snooze", directory=tmp_path, command="jq .")
    findings = [{"smell": "long-file", "issues": [{"key": "src/a.py"}]}]

    kept, notices = _execution(tmp_path).apply_transformers([transformer], findings)

    assert kept == findings
    assert len(notices) == 1
    assert "no POSIX shell" in notices[0]


@_A_SHELL_TO_RUN_IT_WITH
def test_the_same_sensor_runs_where_there_is_a_shell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The platform is the only difference: the recipe refused above is an
    ordinary sensor everywhere a shell can read it."""
    off_windows(monkeypatch)
    marker = tmp_path / "it-ran"
    part = _shell_sensor(tmp_path, f"touch {marker}; printf '[]'")

    run = _execution(tmp_path).run_sensors([part])

    assert marker.exists()
    assert run.findings == []
    assert not run.failed
