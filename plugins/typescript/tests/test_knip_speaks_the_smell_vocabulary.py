"""The knip sensor emits catalogue smells only, never knip's own issue keys.

A key the plugin cannot translate used to be forwarded under knip's own name,
where it had no guide and no catalogue severity — so `binaries` turned an
untouched repository red with boilerplate that named neither the tool nor the
rule (#111). Translating the tool's vocabulary is the sensor's job: the four
dead-code keys knip's `--production` pass already coached gained a smell, and
anything still untranslated is dropped here.

knip itself is stubbed. These cases are about the mapping, and a stub report
states the exact issue shape knip 5 emits (including the `enumMembers` object
map) without a fixture tree that coaxes the real tool into producing it — the
real tool is exercised by `plugins/typescript/docs/typescript-plugin.spec.md`.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

SENSOR = (
    Path(__file__).parents[1]
    / "src"
    / "habit_hooks_typescript"
    / "sensors"
    / "knip.js"
)


def _stub_knip(tmp_path: Path, report: dict) -> dict[str, str]:
    """A `knip` on PATH that prints `report`, whatever it is asked."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    stub = bin_dir / "knip"
    stub.write_text('#!/bin/sh\ncat "$(dirname "$0")/report.json"\n', encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def _findings(tmp_path: Path, report: dict) -> list[dict]:
    result = subprocess.run(
        ["node", str(SENSOR)],
        cwd=tmp_path,
        env=_stub_knip(tmp_path, report),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _report(**keys: object) -> dict:
    """One knip issue row on `src/helper.ts` carrying `keys`."""
    return {"files": [], "issues": [{"file": "src/helper.ts", "owners": [], **keys}]}


def _occurrence(name: str) -> list[dict]:
    return [{"name": name, "line": 3, "col": 1}]


# The keys knip reports that this plugin has no smell for. `unlisted` and
# `unresolved` name real defects and get smells of their own in #124; until then
# they are dropped with the rest.
UNTRANSLATED_KEYS = ["binaries", "duplicates", "catalog", "unlisted", "unresolved"]

TRANSLATED_KEYS = [
    ("exports", "unused-export"),
    ("types", "unused-export"),
    ("nsExports", "unused-export"),
    ("nsTypes", "unused-export"),
    ("dependencies", "unused-dependency"),
]


@pytest.mark.parametrize("knip_key", UNTRANSLATED_KEYS)
def test_a_key_outside_the_vocabulary_never_reaches_the_pipe(
    knip_key: str, tmp_path: Path
) -> None:
    findings = _findings(tmp_path, _report(**{knip_key: _occurrence("thing")}))

    assert findings == []


@pytest.mark.parametrize(("knip_key", "smell"), TRANSLATED_KEYS)
def test_a_translated_key_arrives_as_its_smell(
    knip_key: str, smell: str, tmp_path: Path
) -> None:
    findings = _findings(tmp_path, _report(**{knip_key: _occurrence("neverUsed")}))

    assert [f["smell"] for f in findings] == [smell]
    assert findings[0]["issues"][0]["details"]["source"] == f"knip:{knip_key}"


def test_an_unused_enum_member_arrives_as_unused_class_member(tmp_path: Path) -> None:
    """knip reports enum members as an object map keyed by the parent symbol."""
    report = _report(enumMembers={"Colour": _occurrence("Green")})

    findings = _findings(tmp_path, report)

    assert [f["smell"] for f in findings] == ["unused-class-member"]
    assert findings[0]["issues"][0]["key"] == "Green"


def test_dropping_an_untranslated_key_leaves_its_neighbours_alone(
    tmp_path: Path,
) -> None:
    """The drop is per key, not per report: a run that also names a translated
    key still reports it."""
    report = _report(binaries=_occurrence("habit-hooks"))
    report["files"] = ["src/orphan.ts"]

    findings = _findings(tmp_path, report)

    assert [f["smell"] for f in findings] == ["unused-file"]
    assert findings[0]["issues"][0]["key"] == "src/orphan.ts"
