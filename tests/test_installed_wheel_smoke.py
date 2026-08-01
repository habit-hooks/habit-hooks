"""End-to-end smoke test against installed wheels.

This is the test that would have caught the original "installed runs cannot
locate plugins" bug: it builds the core + plugin wheels, installs them into a
throwaway venv (no source tree, no editable install, no ``plugins/`` sibling
directory on disk), and runs the real ``habit-sensors`` console script on a
fixture with a known smell. A genuine finding must come out — never the
plugin-not-found error.

The php case additionally proves the plugin's bundled ``phpmd.phar`` ships as
package data: the sensor must locate it next to itself inside the installed
wheel, with no source tree on disk.

Building and installing is ``installed_env``; this module is only what an
installed run must produce.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from installed_env import (
    build_wheels,
    install_by_name,
    install_wheels,
    installed_packages,
    path_without_python,
    require_php,
    run_and_collect_findings,
)

OVERSIZED_LINES = 205
MAX_ALLOWED_LINES = 200


@pytest.fixture(scope="module")
def installed_habit_sensors(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("wheel-smoke")
    wheels_dir = root / "wheels"
    wheels_dir.mkdir()
    build_wheels(wheels_dir, ("habit-hooks", "habit-hooks-generic", "habit-hooks-php"))
    return install_wheels(root / "venv", wheels_dir)


@pytest.fixture(scope="module")
def default_install(tmp_path_factory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("default-install")
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    build_wheels(wheelhouse, ("habit-hooks", "habit-hooks-generic"))
    venv = root / "venv"
    python = install_by_name(venv, wheelhouse, "habit-hooks")
    return python, venv / "bin" / "habit-sensors"


def _oversized_project(tmp_path: Path, name: str) -> Path:
    """A project whose only smell is one file over the line-count threshold."""
    project = tmp_path / name
    project.mkdir()
    config = project / ".habit-hooks"
    config.mkdir()
    (config / "config.toml").write_text(
        'plugins = ["generic"]\n'
        'files = ["**/*.py"]\n\n'
        "[sensors.jscpd]\n"
        "disabled = true\n"
    )
    lines = "".join(f"x{n} = 0\n" for n in range(1, OVERSIZED_LINES + 1))
    (project / "big.py").write_text(lines)
    return project


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
    project = _oversized_project(tmp_path, "proj")

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
    project = _oversized_project(tmp_path, "no-python-proj")

    findings = run_and_collect_findings(
        installed_habit_sensors,
        project,
        env={"PATH": path_without_python(tmp_path)},
    )

    _assert_only_the_oversized_file(findings)


def test_installing_core_by_name_pulls_generic_and_finds_a_smell(
    default_install: tuple[Path, Path], tmp_path: Path
) -> None:
    python, habit_sensors = default_install
    packages = installed_packages(python)
    assert "habit-hooks-generic" in packages, packages

    project = _oversized_project(tmp_path, "default-proj")

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
    (config / "config.toml").write_text('plugins = ["python"]\n')

    result = subprocess.run(
        [str(installed_habit_sensors), "--all"],
        cwd=project,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "plugin 'python' is not installed" in result.stderr
    assert "pip install habit-hooks-python" in result.stderr


def _php_project(tmp_path: Path) -> Path:
    project = tmp_path / "php-proj"
    project.mkdir()
    config = project / ".habit-hooks"
    config.mkdir()
    (config / "config.toml").write_text('plugins = ["php"]\n')
    (project / "billing.php").write_text(
        "<?php\n"
        "function charge($a, $b, $c, $d, $e, $f, $g, $h, $i, $j, $k) {\n"
        "    $unused = 1;\n"
        "    return $a + $b + $c + $d + $e + $f + $g + $h + $i + $j + $k;\n"
        "}\n"
    )
    return project


def test_installed_php_plugin_locates_its_bundled_phar(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    require_php()
    project = _php_project(tmp_path)

    findings = run_and_collect_findings(installed_habit_sensors, project)

    by_smell = {finding["smell"]: finding for finding in findings}
    assert by_smell.keys() == {"too-many-parameters", "unused-variable"}
    for finding in findings:
        assert finding["language"] == "php"
        issue = finding["issues"][0]
        assert Path(issue["key"]).name == "billing.php"
        assert issue["details"]["source"].startswith("phpmd:")
