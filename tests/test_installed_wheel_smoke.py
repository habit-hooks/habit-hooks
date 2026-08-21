"""Whether an installed core can still find and run its plugins.

This is the test that would have caught the original "installed runs cannot
locate plugins" bug: it runs the real ``habit-sensors`` console script out of a
throwaway venv — no source tree, no editable install, no ``plugins/`` sibling
directory on disk — against a fixture with a known smell. A genuine finding must
come out, never the plugin-not-found error.

What each *plugin* had to bring with it is ``test_installed_plugin_packaging``.
Building and installing is ``wheelhouse``, the install itself ``conftest``, the
environment a run lands in ``installed_env``, and the projects
``installed_projects``; this module is only what an installed run must produce.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from habit_hooks.project_paths import venv_executable
from installed_env import run_and_collect_findings, without_python_on_path
from installed_projects import MAX_ALLOWED_LINES, OVERSIZED_LINES, oversized_project
from wheelhouse import build_wheels, install_by_name, installed_packages

# A plugin no wheel in this repo provides, so "you configured a plugin that is
# not there" keeps meaning that however many plugins we ship.
UNSHIPPED_PLUGIN = "ruby"


@pytest.fixture(scope="module")
def default_install(tmp_path_factory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("default-install")
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    build_wheels(wheelhouse, ("habit-hooks", "habit-hooks-generic"))
    venv = root / "venv"
    python = install_by_name(venv, wheelhouse, "habit-hooks")
    return python, venv_executable(venv, "habit-sensors")


def _assert_only_the_oversized_file(findings: list[dict]) -> None:
    assert findings == [
        {
            "smell": "oversized-file",
            "details": {"maxAllowed": MAX_ALLOWED_LINES},
            "issues": [
                {
                    "key": "big.py",
                    "details": {
                        "file": "big.py",
                        "lines": OVERSIZED_LINES,
                        "source": "line-count",
                    },
                }
            ],
        }
    ]


def test_installed_generic_plugin_emits_a_real_finding(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    project = oversized_project(tmp_path, "proj")

    _assert_only_the_oversized_file(
        run_and_collect_findings(installed_habit_sensors, project)
    )


def test_bundled_python_sensor_runs_without_python_on_path(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    """The bundled line-count sensor invokes a Python helper script. With a bare
    ``python`` in the command this fails on any environment that ships only
    ``python3`` (or none). The ``${python}`` placeholder must run it via the
    interpreter behind ``habit-sensors`` regardless of PATH."""
    project = oversized_project(tmp_path, "no-python-proj")

    findings = run_and_collect_findings(
        installed_habit_sensors,
        project,
        env=without_python_on_path(tmp_path),
    )

    _assert_only_the_oversized_file(findings)


def test_installing_core_by_name_pulls_generic_and_finds_a_smell(
    default_install: tuple[Path, Path], tmp_path: Path
) -> None:
    python, habit_sensors = default_install
    packages = installed_packages(python)
    assert "habit-hooks-generic" in packages, packages

    project = oversized_project(tmp_path, "default-proj")

    _assert_only_the_oversized_file(
        run_and_collect_findings(habit_sensors, project)
    )


def test_configured_but_uninstalled_plugin_names_its_install_command(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    project = tmp_path / "missing"
    project.mkdir()
    config = project / ".habit-hooks"
    config.mkdir()
    (config / "config.toml").write_text(f'plugins = ["{UNSHIPPED_PLUGIN}"]\n', encoding="utf-8")

    result = subprocess.run(
        [str(installed_habit_sensors), "--all"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode != 0
    assert f"plugin '{UNSHIPPED_PLUGIN}' is not installed" in result.stderr
    assert f"pip install habit-hooks-{UNSHIPPED_PLUGIN}" in result.stderr
