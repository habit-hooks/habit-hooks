"""A project's ruleset has to be recognised in every spelling PMD accepts.

The bundled ruleset is only the answer to "this project has none", so a project
that names its own must get theirs *instead* of ours. That only happens if the
sensor takes their `-R` out of the args: PMD accepts the option more than once
and unions what it is given, so a spelling the sensor fails to recognise does
not fall back to ours — it hands PMD both, and the run reports the smells that
project's ruleset was written to exclude. Silently, at exit 0.

picocli takes five spellings, and `-R=x` / `-Rx` were the two that got through.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from habit_hooks_java.sensors.pmd_sensor import ruleset_of

BUNDLED = "pmd-ruleset.xml"
THEIRS = "mine.xml"


@pytest.mark.parametrize(
    "args",
    [
        ["--rulesets", THEIRS],
        ["--rulesets=" + THEIRS],
        ["-R", THEIRS],
        ["-R=" + THEIRS],
        ["-R" + THEIRS],
    ],
    ids=["--rulesets X", "--rulesets=X", "-R X", "-R=X", "-RX"],
)
def test_a_ruleset_named_in_args_is_the_one_pmd_gets(args: list[str]) -> None:
    ruleset, remaining = ruleset_of(args, Path("/nowhere"))

    assert ruleset == Path(THEIRS)
    assert remaining == []


def test_the_flags_around_a_ruleset_still_reach_pmd() -> None:
    ruleset, remaining = ruleset_of(
        ["--aux-classpath", "lib.jar", "-R=" + THEIRS, "--no-progress"],
        Path("/nowhere"),
    )

    assert ruleset == Path(THEIRS)
    assert remaining == ["--aux-classpath", "lib.jar", "--no-progress"]


def test_a_project_naming_none_gets_the_bundled_ruleset(tmp_path: Path) -> None:
    ruleset, remaining = ruleset_of(["--no-progress"], tmp_path)

    assert ruleset.name == BUNDLED
    assert remaining == ["--no-progress"]


def test_a_conventional_ruleset_beats_the_bundled_one(tmp_path: Path) -> None:
    theirs = tmp_path / "pmd" / "ruleset.xml"
    theirs.parent.mkdir()
    theirs.write_text("<ruleset/>")

    assert ruleset_of([], tmp_path) == (theirs, [])


def test_a_ruleset_option_with_nothing_after_it_is_left_for_pmd_to_refuse(
    tmp_path: Path,
) -> None:
    """A bare `-R` names nothing, so it is not a ruleset this sensor can honour.
    Passing it through is what makes PMD say so; swallowing it would run the
    bundled ruleset under a project's config that was meant to replace it."""
    ruleset, remaining = ruleset_of(["-R"], tmp_path)

    assert ruleset.name == BUNDLED
    assert remaining == ["-R"]
