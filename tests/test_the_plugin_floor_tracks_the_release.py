"""Every released package ships at one version, and the core says so.

``pip install -U habit-hooks`` upgrades a dependency only when the newly
installed core stops being satisfied by the one already there. A plugin floor
left at an older minor is therefore satisfied by an old plugin, and someone
upgrading gets the new core with last release's plugins — which is where nearly
every fix lives, so the upgrade looks like it did nothing.

Raising the floor is one edit in the same commit that bumps the versions, and
forgetting it is silent, so it is gated rather than remembered.

The floor also has to admit the release *making* it, which is a second silent
failure and not the same one: ``~=1.4`` reads as "1.4 or later", but it means
``>=1.4``, and by PEP 440 ordering ``1.4.0rc1`` sorts below ``1.4`` — so a
release candidate declares floors its own plugins cannot satisfy and cannot be
installed at all. Both halves are asked with ``packaging``, so the question is
the one pip will ask rather than a reading of the string.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

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


def _floor_for(version: str) -> SpecifierSet:
    """The specifier every plugin is floored at, spelled from this release.

    ``.dev0`` is the lowest version the minor has, so every pre-release of it is
    admitted while the previous minor still is not — and the same spelling
    serves the release candidate and the final release, so there is nothing to
    rewrite between them.
    """
    major, minor, *_ = version.split(".")
    return SpecifierSet(f">={major}.{minor}.dev0,<{int(major) + 1}")


def test_every_plugin_is_floored_at_this_release_s_minor() -> None:
    core = _core()

    floors = {
        Requirement(requirement).specifier
        for requirement in _plugin_requirements(core)
    }

    assert floors == {_floor_for(core["version"])}


def test_this_release_satisfies_the_floors_it_declares() -> None:
    """The plugins this release ships install against the core that names them.

    Asked with the core's own version because the plugins carry it too, which is
    the test below.
    """
    released = Version(_core()["version"])

    refused = [
        requirement
        for requirement in _plugin_requirements(_core())
        if released not in Requirement(requirement).specifier
    ]

    assert refused == [], f"{released} does not satisfy {refused}"


def test_every_plugin_ships_at_the_core_s_version() -> None:
    """A floor only reaches a plugin that was released alongside the core."""
    expected = _core()["version"]

    versions = {
        path.parent.name: _pyproject(path.parent)["project"]["version"]
        for path in sorted(REPO.glob("plugins/*/pyproject.toml"))
    }

    assert versions == dict.fromkeys(versions, expected)
