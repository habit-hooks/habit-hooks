"""Every released package ships at one version, and the core says so.

``pip install -U habit-hooks`` upgrades a dependency only when the newly
installed core stops being satisfied by the one already there. A plugin floor
left at an older minor is therefore satisfied by an old plugin, and someone
upgrading gets the new core with last release's plugins — which is where nearly
every fix lives, so the upgrade looks like it did nothing.

Raising the floor is one edit in the same commit that bumps the versions, and
forgetting it is silent, so it is gated rather than remembered.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _pyproject(path: Path) -> dict:
    return tomllib.loads((path / "pyproject.toml").read_text(encoding="utf-8"))


def _core() -> dict:
    return _pyproject(REPO)["project"]


def _plugin_requirements(project: dict) -> list[str]:
    """Every requirement naming a plugin, whether required or behind an extra."""
    declared = list(project["dependencies"])
    for extra in project["optional-dependencies"].values():
        declared.extend(extra)
    return [
        requirement
        for requirement in declared
        if requirement.startswith("habit-hooks-")
    ]


def test_every_plugin_is_floored_at_this_release_s_minor() -> None:
    core = _core()
    major, minor, *_ = core["version"].split(".")

    floors = {
        requirement.split("~=")[-1] for requirement in _plugin_requirements(core)
    }

    assert floors == {f"{major}.{minor}"}


def test_every_plugin_ships_at_the_core_s_version() -> None:
    """A floor only reaches a plugin that was released alongside the core."""
    expected = _core()["version"]

    versions = {
        path.parent.name: _pyproject(path.parent)["project"]["version"]
        for path in sorted(REPO.glob("plugins/*/pyproject.toml"))
    }

    assert versions == dict.fromkeys(versions, expected)
