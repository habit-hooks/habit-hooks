"""habit-hooks does not bill a project for its own footprint.

Setting the typescript plugin up means installing the tools it spawns, jscpd
for the generic plugin, and the two packages its shipped eslint config resolves
— the ``--save-dev`` packages the README asks for. The project's own source
imports none of them, because habit-hooks is what uses them, so knip called
every one an unused dependency and told the project to delete the tools it had
just been told to install (#143). The shipped ``knip.json`` overlooks them in
``ignoreDependencies``. ``knip`` is the exception: it is asked for like the
rest, and knip leaves itself out of its own answer, so the list does not name
it.

That list is read out of the config here rather than restated, and whether it
is the *right* list — complete, and free of anything that is not our footprint
— is ``tests/test_the_shipped_knip_config_ignores_what_we_asked_for.py``, which
derives it from every plugin's declarations. This suite asks the next question:
that knip really honours it, and what must survive it. A dependency the
*project* stopped using is still its own dead weight, so the fix cannot be a
blanket "never report an unused dependency". And a project that wrote a knip
config of its own gets the answer its config gives — ours is the fallback for a
project that wrote none, never an override (CLAUDE.md, "A wrapped tool's own
config wins").

The real knip runs here. What the shipped config makes knip do is knip's
answer, and a stub can only repeat whatever we told it — so the suites that
stub it ask a different question (which config the sensor named, how a key
maps), and this one asks the tool.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
PACKAGE = PLUGIN / "src" / "habit_hooks_typescript"
SENSOR = PACKAGE / "sensors" / "knip.cjs"
SHIPPED_CONFIG = PACKAGE / "knip.json"

# Read from the config under test, never restated: a second hand-written copy
# would let the two drift apart, and each would then pass while disagreeing.
TOOLS_HABIT_HOOKS_REQUIRES = tuple(
    json.loads(SHIPPED_CONFIG.read_text(encoding="utf-8"))["ignoreDependencies"]
)

# One the project chose for itself and no longer imports — its own dead weight,
# and the finding this smell exists for.
THE_PROJECTS_OWN_DEAD_WEIGHT = "left-pad"

# knip itself, and the compiler it reads .ts with, both of which knip leaves out
# of its own answer.
KNIPS_OWN = ("knip", "typescript")

ENTRY = 'import { usedInProduction } from "./helper";\nexport const app = usedInProduction();\n'
HELPER = (
    "export function usedInProduction(): number {\n  return 1;\n}\n\n"
    "export function usedOnlyByTests(): number {\n  return 2;\n}\n"
)
TEST = 'import { usedOnlyByTests } from "../src/helper";\n\nusedOnlyByTests();\n'

# A config of the project's own, saying what the shipped one says about the
# tree and nothing at all about dependencies.
THEIR_OWN_CONFIG = json.dumps(
    {"entry": ["src/index.ts!"], "project": ["src/**/*.ts!"]}
)


def _project(tmp_path: Path) -> Path:
    """A project set up the way the README's step 4 leaves one.

    Its own source imports none of the tools, which is the whole point: they
    are habit-hooks' dependencies living in the project's manifest.
    """
    project = tmp_path / "demo"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir(parents=True)
    declared = [*TOOLS_HABIT_HOOKS_REQUIRES, *KNIPS_OWN, THE_PROJECTS_OWN_DEAD_WEIGHT]
    (project / "package.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "version": "0.0.0",
                "devDependencies": {name: "*" for name in sorted(declared)},
            }
        ),
        encoding="utf-8",
    )
    (project / "src" / "index.ts").write_text(ENTRY, encoding="utf-8")
    (project / "src" / "helper.ts").write_text(HELPER, encoding="utf-8")
    (project / "tests" / "helper.test.ts").write_text(TEST, encoding="utf-8")
    (project / "node_modules").symlink_to(PLUGIN / "node_modules")
    return project


def _findings(project: Path) -> list[dict]:
    result = subprocess.run(
        ["node", str(SENSOR)],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _keys_of(findings: list[dict], smell: str) -> set[str]:
    return {
        issue["key"]
        for finding in findings
        if finding["smell"] == smell
        for issue in finding["issues"]
    }


def test_the_tools_habit_hooks_asked_for_are_never_the_projects_dead_weight(
    tmp_path: Path,
) -> None:
    reported = _keys_of(_findings(_project(tmp_path)), "unused-dependency")

    assert reported.isdisjoint(TOOLS_HABIT_HOOKS_REQUIRES), reported


def test_a_dependency_the_project_itself_stopped_using_is_still_reported(
    tmp_path: Path,
) -> None:
    """Overlooking our own footprint must not become overlooking theirs."""
    reported = _keys_of(_findings(_project(tmp_path)), "unused-dependency")

    assert reported == {THE_PROJECTS_OWN_DEAD_WEIGHT}


def test_a_project_that_wrote_its_own_config_gets_its_own_answer(
    tmp_path: Path,
) -> None:
    """Their config decides, ours is not in force, and what it overlooks is not
    overlooked for them. Reporting our tools here is the correct answer to the
    config they wrote — the fix is a fallback config, never a filter over knip's
    findings, which would speak over every project's config alike."""
    project = _project(tmp_path)
    (project / "knip.json").write_text(THEIR_OWN_CONFIG, encoding="utf-8")

    reported = _keys_of(_findings(project), "unused-dependency")

    assert reported.issuperset(TOOLS_HABIT_HOOKS_REQUIRES), reported


def test_the_gated_production_pass_still_runs_under_the_shipped_config(
    tmp_path: Path,
) -> None:
    """`--production` is gated on a trailing `!` marking both `entry` and
    `project`, read straight out of the config in force. A new key alongside
    them must leave that reading alone, or the second pass silently stops."""
    findings = _findings(_project(tmp_path))

    assert _keys_of(findings, "test-only-dead-code") == {"usedOnlyByTests"}
