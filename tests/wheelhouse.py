"""The wheels this repo releases, and installing out of them.

Two different questions get asked of a build, and they are kept apart on
purpose. ``install_wheels`` asks whether a wheel *carried* what a run needs —
package data, entry points, a helper beside its spec — and installs the built
files by path, where no resolver has a say in what lands. ``install_by_name``
asks the other one: whether the packages' *declared* dependencies pull each
other the way a real ``pip install habit-hooks`` would.

The second is where a floor a release candidate's own plugins cannot satisfy
surfaces — ``~=1.4`` refuses ``1.4.0rc1``, which is why the floors are spelled
``>=1.4.dev0,<2`` (``tests/test_the_plugin_floor_tracks_the_release.py``). A
pre-release flag is never the fix: nothing passed here can make a resolver
consider a version its specifier excludes outright.

Either way, what landed is asserted rather than assumed: a resolver that can
reach an index can be served last release's code, which would run, pass, and
say nothing whatever about this build.

What a wheel says about itself is ``wheel_metadata``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from habit_hooks.project_paths import venv_executable
from wheel_metadata import built, required_from_elsewhere

REPO_ROOT = Path(__file__).resolve().parents[1]


def require_uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    return uv


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
    """Install every built wheel; returns the installed habit-sensors.

    By path and ``--no-deps``, so the code that runs is the file that was just
    built and nothing can be substituted for it.
    """
    python = _fresh_venv(venv)
    wheels = [str(wheel) for wheel in sorted(wheels_dir.glob("*.whl"))]
    _uv_run("pip", "install", "--python", str(python), "--no-deps", *wheels)
    _install_what_this_repo_does_not_build(python, wheels_dir)
    _assert_the_built_wheels_are_installed(python, wheels_dir)
    return venv_executable(venv, "habit-sensors")


def install_by_name(venv: Path, wheels_dir: Path, name: str) -> Path:
    """Install one package *by name*, so what it *declares* is what pulls the
    rest in — the question installing by path cannot ask.

    The wheelhouse is the only index it may use. A resolver that can reach a
    real one answers a bare name with the newest *published* release, which for
    a pre-release build is the release before this one: a correct resolve that
    measures nothing about these wheels, and how ``1.3.1`` came to answer for
    ``1.4.0rc1``. Cut off from it, the floors this core declares have only the
    wheels just built to satisfy them, which is the whole question.
    """
    python = _fresh_venv(venv)
    _install_what_this_repo_does_not_build(python, wheels_dir)
    _uv_run(
        "pip", "install", "--python", str(python),
        "--no-index", "--find-links", str(wheels_dir), name,
    )
    _assert_the_built_wheels_are_installed(python, wheels_dir)
    return python


def installed_packages(python: Path) -> dict[str, str]:
    """Distribution name to version, for everything in that environment."""
    listed = _uv_run("pip", "list", "--python", str(python), "--format", "json").stdout
    return {package["name"]: package["version"] for package in json.loads(listed)}


def _uv_run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run uv, quoting it back rather than swallowing it when it fails.

    A resolver refuses an install with a paragraph naming the requirement
    nothing could satisfy — the one thing a reader can act on, and the answer to
    the release-time question this module exists to ask. ``check=True`` over a
    captured pipe turns that paragraph into an exit status.
    """
    result = subprocess.run(
        [require_uv(), *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # sensors.spawn's policy
    )
    if result.returncode != 0:
        pytest.fail(f"uv {' '.join(args)} failed:\n{result.stderr}")
    return result


def _fresh_venv(venv: Path) -> Path:
    _uv_run("venv", str(venv))
    return venv_executable(venv, "python")


def _install_what_this_repo_does_not_build(python: Path, wheels_dir: Path) -> None:
    """Bring in the third-party packages the built wheels need.

    Neither install here can leave this to a resolver reading the wheelhouse —
    one asks nothing of a resolver at all, the other is denied an index — yet
    the dependencies still have to arrive.
    """
    required = required_from_elsewhere(wheels_dir)
    if required:
        _uv_run("pip", "install", "--python", str(python), *required)


def _assert_the_built_wheels_are_installed(python: Path, wheels_dir: Path) -> None:
    """Every wheel this repo built is there, at the version it was built at.

    An install that resolves by name reaches an index as readily as the
    wheelhouse, and a published release of the same package satisfies a resolver
    just as well — so a green run could be measuring last release's code. What
    was built has to be what answered, and that is stated here.
    """
    from_here = built(wheels_dir)
    installed = installed_packages(python)
    answering = {name: installed.get(name) for name in from_here}
    assert answering == from_here, f"installed {answering}, built {from_here}"
