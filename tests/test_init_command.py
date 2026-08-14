"""Unit tests for ``habit-hooks init``: the config it writes, under the name it
answers to.

Two things it must get right before it says anything at all: a project with no
config gets one naming the plugins it needs, and a project that has one is left
exactly as it was — re-running init is how someone asks why a run reports
nothing, so it must not be the thing that changed the answer.

The offer to install what is missing is ``test_init_installs.py``; what init
decides is ``test_initialise.py``; how it words it is ``test_init_report.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from habit_hooks import hooks
from habit_hooks.init_command import run
from plugin_fixture import write_project_config


def _config(project_dir: Path) -> Path:
    return project_dir / ".habit-hooks" / "config.toml"


def test_a_fresh_project_gets_a_config_naming_the_plugins_it_needs(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (init_project / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(init_project)

    assert run([]) == 0
    assert _config(init_project).read_text() == 'plugins = ["python", "generic"]\n'


def test_a_configured_project_is_left_exactly_as_it_was(
    init_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The doctor case: init is what someone runs to find out why a run reports
    nothing, and overwriting their settings would answer a different question."""
    write_project_config(init_project, '# mine\nplugins = ["generic"]\n')
    monkeypatch.chdir(init_project)

    assert run([]) == 0
    assert _config(init_project).read_text() == '# mine\nplugins = ["generic"]\n'


def test_the_pipeline_runs_init_rather_than_piping_it_into_the_mapper(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Forwarded to ``habit-sensors``, everything init prints would land on the
    pipe where ``habit-mapper`` expects findings JSON — which is how ``--help``
    once came back as a ``JSONDecodeError`` (#114)."""
    monkeypatch.chdir(init_project)

    assert hooks.main(["init"]) == 0
    assert "Wrote .habit-hooks/config.toml" in capsys.readouterr().out


def test_the_pipeline_s_help_names_the_command_that_sets_a_project_up(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Somebody typing `--help` in their first ten minutes is exactly who `init`
    is for, and the scan flags beside it are no use to a project with nothing
    configured yet. Asked at a stated width, because argparse re-wraps the
    epilog to the terminal it is printed on."""
    monkeypatch.setenv("COLUMNS", "100")

    assert hooks.main(["--help"]) == 0
    assert "habit-hooks init" in capsys.readouterr().out


def test_a_rejected_config_fails_the_tool_under_the_pipeline_s_name(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Init loads the config it reports on, so it inherits the loader's refusals
    — which name no binary, and would otherwise reach the reader as a traceback.
    """
    write_project_config(init_project, "plugns = []\n")
    monkeypatch.chdir(init_project)

    assert hooks.main(["init"]) == 2
    assert capsys.readouterr().err.startswith("habit-hooks: unknown config key")


def test_init_takes_no_arguments_and_says_so(
    init_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A scope flag here is somebody expecting init to run a scan; ignoring it
    would report on a setup they did not ask about."""
    monkeypatch.chdir(init_project)

    with pytest.raises(SystemExit) as failure:
        hooks.main(["init", "--all"])

    assert failure.value.code == 2
    assert "usage: habit-hooks init" in capsys.readouterr().err
