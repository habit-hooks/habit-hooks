"""The knip sensor names the config it ships only once the project has none.

Installing habit-hooks must never override a developer's existing preferences,
so the shipped ``knip.json`` is the answer to "this project has no knip config"
and never an override. That makes the question the sensor has to ask knip's own:
knip 5 looks for eight file names plus a ``knip`` key in ``package.json``, all in
the project directory, and never walks up (``util/fs.js`` ``findFile``). The same
answer has to reach the gate on the second ``--production`` pass, which reads the
trailing ``!`` markers — read them off a config that is not the one running and
the pass stays off in exactly the case it exists for (#120).

knip is stubbed by a script that records the argv it was spawned with: what is
under test is which config the sensor names and how many passes it runs, not
what knip makes of either. The real tool is exercised by
``plugins/typescript/docs/typescript-plugin.spec.md``.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSOR = PACKAGE / "sensors" / "knip.cjs"
SHIPPED_CONFIG = PACKAGE / "knip.json"

EMPTY_REPORT = {"files": [], "issues": []}

# Every place knip 5 looks for a config, as `constants.js` KNIP_CONFIG_LOCATIONS
# spells them, plus the manifest key it merges in regardless.
KNIP_CONFIG_LOCATIONS = [
    "knip.json",
    "knip.jsonc",
    ".knip.json",
    ".knip.jsonc",
    "knip.ts",
    "knip.js",
    "knip.config.ts",
    "knip.config.js",
]

# A config that gates the production pass on: `!` on both `entry` and `project`.
MARKED = '{"entry": ["src/cli.ts!"], "project": ["src/**/*.ts!"]}'
UNMARKED = '{"entry": ["src/cli.ts"], "project": ["src/**/*.ts"]}'

RECORDING_STUB = """#!/bin/sh
printf '%s\\t' "$@" >> "$(dirname "$0")/argv.log"
printf '\\n' >> "$(dirname "$0")/argv.log"
cat "$(dirname "$0")/report.json"
"""


def _project_with_a_stubbed_knip(tmp_path: Path) -> Path:
    """A project whose `knip` on PATH records its argv and prints an empty run."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "report.json").write_text(json.dumps(EMPTY_REPORT), encoding="utf-8")
    stub = bin_dir / "knip"
    stub.write_text(RECORDING_STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    project = tmp_path / "demo"
    project.mkdir()
    (project / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    return project


def _passes(project: Path) -> list[list[str]]:
    """The argv of every knip the sensor spawned, in order."""
    bin_dir = project.parent / "bin"
    subprocess.run(
        ["node", str(SENSOR)],
        cwd=project,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        check=True,
    )
    log = (bin_dir / "argv.log").read_text(encoding="utf-8")
    return [line.rstrip("\t").split("\t") for line in log.splitlines()]


def test_the_shipped_config_is_named_when_the_project_wrote_none(
    tmp_path: Path,
) -> None:
    project = _project_with_a_stubbed_knip(tmp_path)

    first, *_ = _passes(project)

    assert "--config" in first, first
    assert first[first.index("--config") + 1] == str(SHIPPED_CONFIG)


@pytest.mark.parametrize("location", KNIP_CONFIG_LOCATIONS)
def test_a_config_the_project_wrote_is_left_for_knip_to_find(
    location: str, tmp_path: Path
) -> None:
    """Naming ours would override it; naming theirs would still be us choosing."""
    project = _project_with_a_stubbed_knip(tmp_path)
    (project / location).write_text(UNMARKED, encoding="utf-8")

    first, *_ = _passes(project)

    assert "--config" not in first, first


def test_a_knip_key_in_the_manifest_is_a_config_the_project_wrote(
    tmp_path: Path,
) -> None:
    """knip merges `package.json#knip` whether or not a config file is found, so
    a project that has only that has still stated its preferences."""
    project = _project_with_a_stubbed_knip(tmp_path)
    (project / "package.json").write_text(
        json.dumps({"name": "demo", "knip": json.loads(UNMARKED)}), encoding="utf-8"
    )

    first, *_ = _passes(project)

    assert "--config" not in first, first


def test_the_gate_reads_the_shipped_markers_when_ours_is_in_force(
    tmp_path: Path,
) -> None:
    """The shipped config carries `!` on both keys, so the pass it gates runs —
    and runs against the same config, or the two passes disagree about the tree."""
    project = _project_with_a_stubbed_knip(tmp_path)

    passes = _passes(project)

    assert len(passes) == 2, passes
    assert "--production" in passes[1]
    assert passes[1][passes[1].index("--config") + 1] == str(SHIPPED_CONFIG)


def test_a_project_config_without_markers_runs_no_production_pass(
    tmp_path: Path,
) -> None:
    """`--production` analyses nothing without `!` on both keys, so the gate must
    read the project's markers — not the ones the shipped config happens to have."""
    project = _project_with_a_stubbed_knip(tmp_path)
    (project / "knip.json").write_text(UNMARKED, encoding="utf-8")

    assert len(_passes(project)) == 1


def test_a_project_config_with_markers_still_gates_the_production_pass(
    tmp_path: Path,
) -> None:
    """The project's own config decides the gate in both directions."""
    project = _project_with_a_stubbed_knip(tmp_path)
    (project / "knip.json").write_text(MARKED, encoding="utf-8")

    passes = _passes(project)

    assert len(passes) == 2, passes
    assert "--config" not in passes[1], passes[1]
