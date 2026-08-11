"""The knip sensor names the config it ships only once the project has none.

Installing habit-hooks must never override a developer's existing preferences,
so the shipped ``knip.json`` is the answer to "this project has no knip config"
and never an override. That makes the question the sensor has to ask knip's own:
knip 5 looks for eight file names plus a ``knip`` key in ``package.json``, all in
the project directory, and never walks up (``util/fs.js`` ``findFile``). The same
answer has to reach the gate on the second ``--production`` pass, which reads the
trailing ``!`` markers — read them off a config that is not the one running and
the pass stays off in exactly the case it exists for (#120).

knip is stubbed by a script that records the argv it was spawned with
(``knip_project.py``): what is under test is which config the sensor names and
how many passes it runs, not what knip makes of either. The real tool is
exercised by ``plugins/typescript/docs/typescript-plugin.spec.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from knip_project import SHIPPED_CONFIG, passes, project

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


def test_the_shipped_config_is_named_when_the_project_wrote_none(
    tmp_path: Path,
) -> None:
    consumer = project(tmp_path)

    first, *_ = passes(consumer)

    assert "--config" in first, first
    assert first[first.index("--config") + 1] == str(SHIPPED_CONFIG)


@pytest.mark.parametrize("location", KNIP_CONFIG_LOCATIONS)
def test_a_config_the_project_wrote_is_left_for_knip_to_find(
    location: str, tmp_path: Path
) -> None:
    """Naming ours would override it; naming theirs would still be us choosing."""
    consumer = project(tmp_path)
    (consumer / location).write_text(UNMARKED, encoding="utf-8")

    first, *_ = passes(consumer)

    assert "--config" not in first, first


def test_a_knip_key_in_the_manifest_is_a_config_the_project_wrote(
    tmp_path: Path,
) -> None:
    """knip merges `package.json#knip` whether or not a config file is found, so
    a project that has only that has still stated its preferences."""
    consumer = project(tmp_path)
    (consumer / "package.json").write_text(
        json.dumps({"name": "demo", "knip": json.loads(UNMARKED)}), encoding="utf-8"
    )

    first, *_ = passes(consumer)

    assert "--config" not in first, first


def test_the_gate_reads_the_shipped_markers_when_ours_is_in_force(
    tmp_path: Path,
) -> None:
    """The shipped config carries `!` on both keys, so the pass it gates runs —
    and runs against the same config, or the two passes disagree about the tree."""
    consumer = project(tmp_path)

    spawned = passes(consumer)

    assert len(spawned) == 2, spawned
    assert "--production" in spawned[1]
    assert spawned[1][spawned[1].index("--config") + 1] == str(SHIPPED_CONFIG)


def test_a_project_config_without_markers_runs_no_production_pass(
    tmp_path: Path,
) -> None:
    """`--production` analyses nothing without `!` on both keys, so the gate must
    read the project's markers — not the ones the shipped config happens to have."""
    consumer = project(tmp_path)
    (consumer / "knip.json").write_text(UNMARKED, encoding="utf-8")

    assert len(passes(consumer)) == 1


def test_a_project_config_with_markers_still_gates_the_production_pass(
    tmp_path: Path,
) -> None:
    """The project's own config decides the gate in both directions."""
    consumer = project(tmp_path)
    (consumer / "knip.json").write_text(MARKED, encoding="utf-8")

    spawned = passes(consumer)

    assert len(spawned) == 2, spawned
    assert "--config" not in spawned[1], spawned[1]


def test_the_sensor_s_args_reach_knip(tmp_path: Path) -> None:
    """`[sensors.knip] args` is the project telling knip something, so knip has to
    hear it — this sensor spawns the tool itself, and args it does not forward are
    args the tool never sees."""
    consumer = project(tmp_path)

    first, *_ = passes(consumer, ("--exclude", "files"))

    assert first[first.index("--exclude") + 1] == "files", first


def test_a_config_named_through_the_args_is_the_one_in_force(tmp_path: Path) -> None:
    """A project that keeps its config off knip's search list names it through the
    args, which is as much a config of its own as writing `knip.json`. Ours must
    not be named alongside it — knip takes the last `--config` it is given, so a
    second one is us deciding which of the two wins."""
    consumer = project(tmp_path)
    (consumer / "custom.json").write_text(MARKED, encoding="utf-8")

    first, *_ = passes(consumer, ("--config", "custom.json"))

    assert str(SHIPPED_CONFIG) not in first, first
    assert first[first.index("--config") + 1] == "custom.json", first


def test_a_config_flag_with_nothing_after_it_is_knip_s_error_to_report(
    tmp_path: Path,
) -> None:
    """`args = ["--config"]` names no file, so it names no config — it is a
    mistake, and knip's own parser is what says so. Reading the flag as an answer
    yields a boolean, and resolving that would take the sensor down with a
    TypeError before knip ever got to explain itself."""
    consumer = project(tmp_path)

    first, *_ = passes(consumer, ("--config",))

    assert first[first.index("--config") + 1] == str(SHIPPED_CONFIG), first
    assert first[-1] == "--config", first


def test_the_gate_reads_the_config_the_args_named(tmp_path: Path) -> None:
    """The production pass is gated on the markers of the config actually running.
    This config carries none, so the pass stays off — where the shipped config it
    replaced carries them and would have run it."""
    consumer = project(tmp_path)
    (consumer / "custom.json").write_text(UNMARKED, encoding="utf-8")

    assert len(passes(consumer, ("--config", "custom.json"))) == 1
