"""What a built wheel says about itself: its distribution, version and needs.

Read off the files the build wrote — the filename for the first two, the
``METADATA`` inside for the third — so nothing about a release is stated twice.
A list of third-party dependencies written here would be a second copy of one
every wheel already carries, free to drift from it silently.

``wheelhouse`` is the installing around this, and the dependency runs one way.
"""

from __future__ import annotations

import re
import zipfile
from email import message_from_bytes
from pathlib import Path

# What marks a requirement that arrives only when the brackets ask for it —
# ``habit-hooks-python<2,>=1.4.dev0; extra == 'python'``.
EXTRA_MARKER = "extra =="


def built(wheels_dir: Path) -> dict[str, str]:
    """Distribution name to version for every wheel in the wheelhouse, read off
    the filenames the build wrote."""
    return dict(_wheel_distribution(wheel) for wheel in sorted(wheels_dir.glob("*.whl")))


def required_from_elsewhere(wheels_dir: Path) -> list[str]:
    """What the built wheels require that this repo does not build itself.

    A requirement behind an ``extra`` is left out: it arrives only when brackets
    ask for it, and no install here asks.
    """
    from_here = built(wheels_dir)
    return [
        requirement
        for wheel in sorted(wheels_dir.glob("*.whl"))
        for requirement in _requires_dist(wheel)
        if EXTRA_MARKER not in requirement
        and _required_distribution(requirement) not in from_here
    ]


def _wheel_distribution(wheel: Path) -> tuple[str, str]:
    name, version, *_ = wheel.name.split("-")
    return _distribution(name), version


def _distribution(name: str) -> str:
    """The one spelling of a distribution name every tool here agrees on."""
    return name.replace("_", "-").lower()


def _requires_dist(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata = next(
            entry for entry in archive.namelist() if entry.endswith(".dist-info/METADATA")
        )
        return message_from_bytes(archive.read(metadata)).get_all("Requires-Dist") or []


def _required_distribution(requirement: str) -> str:
    """The distribution a requirement names, before its extras, specifier or
    marker."""
    return _distribution(re.split(r"[\[<>=!~; ]", requirement, maxsplit=1)[0])
