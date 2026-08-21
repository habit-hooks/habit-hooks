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
import subprocess
from pathlib import Path

import pytest
from node_tool_stub import install

SENSOR = (
    Path(__file__).parents[1]
    / "src"
    / "habit_hooks_typescript"
    / "sensors"
    / "knip.cjs"
)


def _findings(tmp_path: Path, report: dict) -> list[dict]:
    install(tmp_path, "knip", json.dumps(report))
    result = subprocess.run(
        ["node", str(SENSOR)],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
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


def test_a_column_is_reported_under_the_name_the_contract_gives_it(
    tmp_path: Path,
) -> None:
    """knip spells it `col`; every other sensor and the contract spell it `column`.

    `docs/sensor-interface.spec.md` names `line` / `column` as an issue's
    location, and forwarding knip's own spelling left that location invisible to
    everything downstream that asks for it by name — a guide rendering a
    position, and the mapper deciding whether two issues name one place.
    Translating the tool's vocabulary is this sensor's job, and a field name is
    vocabulary like any other.
    """
    findings = _findings(
        tmp_path,
        {
            "files": [],
            "issues": [
                {
                    "file": "src/a.ts",
                    "exports": [{"name": "unused", "line": 3, "col": 14}],
                }
            ],
        },
    )

    (issue,) = findings[0]["issues"]
    assert issue["details"]["line"] == 3
    assert issue["details"]["column"] == 14
    assert "col" not in issue["details"]
