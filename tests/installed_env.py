"""Exercise habit-hooks as an *installed* tool rather than from the source tree.

Builds this repo's wheels, installs them into a throwaway venv, and constructs
the environment an installed run sees. That is the only way to catch the class
of bug where everything works from a checkout and nothing works once packaged:
plugins located by walking a sibling directory, package data that never made it
into the wheel, a helper invoked as bare ``python``.

The tests that assert what such a run must produce live in
``test_installed_wheel_smoke.py`` (the core finding its plugins) and
``test_installed_plugin_packaging.py`` (each plugin bringing what its sensors
need); this module only gets them an install.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def require_uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    return uv


def require_tool(name: str) -> str:
    """Skip a case that wraps a third-party tool this machine has not got.

    A plugin's packaging can only be proved through the tool it wraps, and a
    machine without it can say nothing either way — so the case steps aside
    rather than reporting a packaging failure it did not observe.
    """
    tool = shutil.which(name)
    if tool is None:
        pytest.skip(f"{name} is not on PATH")
    return tool


def _uv_run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [require_uv(), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # sensors.spawn's policy
    )


def build_wheels(out_dir: Path, packages: tuple[str, ...]) -> None:
    for package in packages:
        subprocess.run(
            [require_uv(), "build", "--wheel", "--package", package, "--out-dir", str(out_dir)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",  # sensors.spawn's policy
        )


def install_wheels(venv: Path, wheels_dir: Path) -> Path:
    """Install every built wheel explicitly; returns the installed habit-sensors."""
    _uv_run("venv", str(venv))
    wheels = [str(path) for path in sorted(wheels_dir.glob("*.whl"))]
    _uv_run("pip", "install", "--python", str(venv / "bin" / "python"), *wheels)
    return venv / "bin" / "habit-sensors"


def install_by_name(venv: Path, wheels_dir: Path, name: str) -> Path:
    """Install one package *by name* off a local wheelhouse, so its declared
    dependencies resolve the way a real ``pip install habit-hooks`` would."""
    _uv_run("venv", str(venv))
    _uv_run(
        "pip", "install", "--python", str(venv / "bin" / "python"),
        "--find-links", str(wheels_dir), name,
    )
    return venv / "bin" / "python"


def installed_packages(python: Path) -> str:
    return _uv_run("pip", "list", "--python", str(python)).stdout


def run_and_collect_findings(
    habit_sensors: Path, project: Path, env: dict[str, str] | None = None
) -> list[dict]:
    """Run the installed sensors stage and parse its findings.

    Asserts the packaging-failure messages are absent first: those produce an
    empty findings array, which would otherwise read as a clean project.
    """
    result = subprocess.run(
        [str(habit_sensors), "--all"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # sensors.spawn's policy
        env=env,
    )
    assert "is not installed" not in result.stderr, result.stderr
    assert "could not locate" not in result.stderr.lower(), result.stderr
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _link_executables_except(bin_dir: Path, blocked: set[str]) -> None:
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        source = Path(entry)
        if not source.is_dir():
            continue
        for tool in source.iterdir():
            link = bin_dir / tool.name
            if tool.name in blocked or link.exists() or not os.access(tool, os.X_OK):
                continue
            link.symlink_to(tool)


def path_without_python(tmp_path: Path) -> str:
    """A PATH with the usual tools (``bash`` etc.) but no ``python``/``python3``,
    reproducing a clean CI sandbox / stock-macOS environment. Built by symlinking
    every executable on the current PATH except the Python interpreters into a
    single bin dir."""
    bin_dir = tmp_path / "no-python-bin"
    bin_dir.mkdir()
    _link_executables_except(bin_dir, {"python", "python3"})

    assert shutil.which("python", path=str(bin_dir)) is None
    assert shutil.which("python3", path=str(bin_dir)) is None
    assert shutil.which("bash", path=str(bin_dir)) is not None
    return str(bin_dir)
