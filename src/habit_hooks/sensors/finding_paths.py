"""Anchor a sensor's reported paths to the project, and spot keys that alias.

A sensor reports paths the way its tool does — ``ruff``, ``eslint`` and
``ts-morph`` absolute, others relative to their own scan root — so the runner
re-expresses every ``details.file`` relative to the project as the findings enter
the run. Doing it here, once, is the whole point: a snooze index full of one
machine's absolute paths matches nothing on a teammate's checkout or in CI, and a
sensor that never heard of the convention still obeys it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from ..project_paths import project_relative
from .model import SensorError


def anchored(findings: list[dict], project_dir: Path, sensor: str) -> list[dict]:
    """``findings`` with every reported path re-expressed relative to the project.

    An issue's ``key`` is anchored the same way and by the same rule, whatever
    spelling the sensor used for it — ``./src/a.py`` and an absolute
    ``/…/src/a.py`` both come back as ``src/a.py``. A key that is not a path —
    ``deptry`` keys by module, ``knip`` by export name — has nothing to resolve
    and comes back byte for byte as the sensor wrote it, so the carve-out costs
    no special case.
    """
    return [_anchored_finding(finding, project_dir, sensor) for finding in findings]


def aliasing_notices(findings: list[dict], sensor: str) -> list[str]:
    """One notice per path key that stands for more than one file (issue #79).

    A key that is one of its files but not the others is a path standing in for
    files it does not name: snoozing it exempts every one of them, with nothing
    saying so. A key that is no file at all is the sensor grouping its issues on
    purpose, which the contract invites it to do.
    """
    files_by_key: defaultdict[str, set[str]] = defaultdict(set)
    for issue in _issues(findings):
        file = _reported_file(issue, sensor)
        if file is not None and "key" in issue:
            files_by_key[issue["key"]].add(file)
    return [
        _alias_notice(sensor, key, files)
        for key, files in sorted(files_by_key.items())
        if len(files) > 1 and key in files
    ]


def _alias_notice(sensor: str, key: str, files: set[str]) -> str:
    return (
        f"sensor {sensor!r} keys {len(files)} files as {key!r} "
        f"({', '.join(sorted(files))}) — snoozing it would exempt them all"
    )


def _anchored_finding(finding: dict, project_dir: Path, sensor: str) -> dict:
    issues = finding.get("issues")
    if not issues:
        return finding
    if not isinstance(issues, list):
        raise _malformed(sensor, "a finding whose 'issues' is not a list")
    return {
        **finding,
        "issues": [_anchored_issue(issue, project_dir, sensor) for issue in issues],
    }


def _anchored_issue(issue: dict, project_dir: Path, sensor: str) -> dict:
    if not isinstance(issue, dict):
        raise _malformed(sensor, "an issue that is not an object")
    reported = _reported_file(issue, sensor)
    if reported is None:
        return issue
    file = project_relative(reported, project_dir)
    if file is None:
        raise SensorError(
            f"sensor {sensor!r} reported a path outside the project: {reported!r}"
        )
    anchored_issue = {**issue, "details": {**issue["details"], "file": file}}
    key = issue.get("key")
    if isinstance(key, str):
        anchored_issue["key"] = project_relative(key, project_dir) or key
    return anchored_issue


def _malformed(sensor: str, described: str) -> SensorError:
    """Output the contract's shape does not fit — loud, named, never a traceback.

    A sensor is somebody else's program. One with a typo in its output has to
    fail like any other broken sensor, not take the whole runner down with it.
    """
    return SensorError(f"sensor {sensor!r} emitted {described}")


def _issues(findings: list[dict]) -> Iterator[dict]:
    return (issue for finding in findings for issue in finding.get("issues", []))


def _reported_file(issue: dict, sensor: str) -> str | None:
    details = issue.get("details", {})
    if not isinstance(details, dict):
        raise _malformed(sensor, "an issue whose 'details' is not an object")
    file = details.get("file")
    return file if isinstance(file, str) and file else None
