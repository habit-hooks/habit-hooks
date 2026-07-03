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
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    return uv


def _php() -> str:
    php = shutil.which("php")
    if php is None:
        pytest.skip("php is not on PATH")
    return php


def _build_wheels(out_dir: Path, packages: tuple[str, ...]) -> None:
    for package in packages:
        subprocess.run(
            [_uv(), "build", "--wheel", "--package", package, "--out-dir", str(out_dir)],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


def _install_into_venv(venv: Path, wheels_dir: Path) -> Path:
    subprocess.run([_uv(), "venv", str(venv)], check=True, capture_output=True, text=True)
    python = venv / "bin" / "python"
    wheels = [str(p) for p in sorted(wheels_dir.glob("*.whl"))]
    subprocess.run(
        [_uv(), "pip", "install", "--python", str(python), *wheels],
        check=True,
        capture_output=True,
        text=True,
    )
    return venv / "bin" / "habit-sensors"


@pytest.fixture(scope="module")
def installed_habit_sensors(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("wheel-smoke")
    wheels_dir = root / "wheels"
    wheels_dir.mkdir()
    _build_wheels(wheels_dir, ("habit-hooks", "habit-hooks-generic", "habit-hooks-php"))
    return _install_into_venv(root / "venv", wheels_dir)


@pytest.fixture(scope="module")
def default_install(tmp_path_factory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("default-install")
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    _build_wheels(wheelhouse, ("habit-hooks", "habit-hooks-generic"))
    venv = root / "venv"
    subprocess.run([_uv(), "venv", str(venv)], check=True, capture_output=True, text=True)
    python = venv / "bin" / "python"
    subprocess.run(
        [
            _uv(),
            "pip",
            "install",
            "--python",
            str(python),
            "--find-links",
            str(wheelhouse),
            "habit-hooks",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return python, venv / "bin" / "habit-sensors"


def _oversized_fixture(project: Path) -> None:
    config = project / ".habit-hooks"
    config.mkdir()
    (config / "config.toml").write_text(
        'plugins = ["generic"]\n'
        'files = ["**/*.py"]\n\n'
        "[sensors.jscpd]\n"
        "disabled = true\n"
    )
    (project / "big.py").write_text("".join(f"x{n} = 0\n" for n in range(1, 206)))


def test_installed_generic_plugin_emits_a_real_finding(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _oversized_fixture(project)

    result = subprocess.run(
        [str(installed_habit_sensors), "--all"],
        cwd=project,
        capture_output=True,
        text=True,
    )

    assert "is not installed" not in result.stderr, result.stderr
    assert "could not locate" not in result.stderr.lower(), result.stderr
    assert result.returncode == 0, result.stderr

    findings = json.loads(result.stdout)
    assert findings == [
        {
            "smell": "oversized-file",
            "details": {"maxAllowed": 200},
            "issues": [
                {
                    "key": "big.py",
                    "details": {"file": "big.py", "lines": 205, "source": "line-count"},
                }
            ],
        }
    ]


def test_installing_core_by_name_pulls_generic_and_finds_a_smell(
    default_install: tuple[Path, Path], tmp_path: Path
) -> None:
    python, habit_sensors = default_install

    pip_list = subprocess.run(
        [_uv(), "pip", "list", "--python", str(python)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "habit-hooks-generic" in pip_list.stdout, pip_list.stdout

    project = tmp_path / "default-proj"
    project.mkdir()
    _oversized_fixture(project)

    result = subprocess.run(
        [str(habit_sensors), "--all"],
        cwd=project,
        capture_output=True,
        text=True,
    )

    assert "is not installed" not in result.stderr, result.stderr
    assert "could not locate" not in result.stderr.lower(), result.stderr
    assert result.returncode == 0, result.stderr

    findings = json.loads(result.stdout)
    assert findings == [
        {
            "smell": "oversized-file",
            "details": {"maxAllowed": 200},
            "issues": [
                {
                    "key": "big.py",
                    "details": {"file": "big.py", "lines": 205, "source": "line-count"},
                }
            ],
        }
    ]


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


def _php_fixture(project: Path) -> None:
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


def test_installed_php_plugin_locates_its_bundled_phar(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    _php()
    project = tmp_path / "php-proj"
    project.mkdir()
    _php_fixture(project)

    result = subprocess.run(
        [str(installed_habit_sensors), "--all"],
        cwd=project,
        capture_output=True,
        text=True,
    )

    assert "is not installed" not in result.stderr, result.stderr
    assert "could not locate" not in result.stderr.lower(), result.stderr
    assert result.returncode == 0, result.stderr

    findings = json.loads(result.stdout)
    by_smell = {finding["smell"]: finding for finding in findings}
    assert by_smell.keys() == {"too-many-parameters", "unused-variable"}
    for finding in findings:
        assert finding["language"] == "php"
        issue = finding["issues"][0]
        assert Path(issue["key"]).name == "billing.php"
        assert issue["details"]["source"].startswith("phpmd:")
