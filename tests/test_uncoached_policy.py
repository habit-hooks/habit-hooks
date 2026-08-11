"""The root ``uncoached`` key decides what a smell the catalogue never named does.

Before #111 an uncatalogued smell fell through to ``enforced``, so a name nobody
had written a guide for could fail a build and then decline to explain why. The
catalogue is the record of what this product has decided is worth failing a
build over, so a name absent from it now coaches without blocking — and a
project that disagrees says so once, at the root, rather than per smell.

The three values are exercised through ``mapper.run`` because the answer is
two-part: what reaches stdout and what the exit code says. A catalogued smell is
the discriminator in each case — the policy must never move one of those.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks import mapper
from habit_hooks.catalogue import INCOMPLETE_RUN
from plugin_fixture import write_plugin, write_project_config

UNCOACHED_SMELL = "mystery-rule"
CATALOGUED_SMELL = "oversized-file"


def _finding(smell: str) -> dict:
    return {
        "smell": smell,
        "details": {},
        "issues": [{"key": "src/a.py", "details": {"file": "src/a.py"}}],
    }


def _project(tmp_path: Path, config: str) -> Path:
    """A project running one fixture plugin, which ships no guide of its own.

    Both smells therefore resolve to the core's ``uncoached.md``, leaving
    severity as the only thing under test.
    """
    write_plugin(tmp_path, "fixt", {"config.toml": "sensors = []"})
    write_project_config(tmp_path, f'plugins = ["fixt"]\n{config}')
    return tmp_path


def _run(tmp_path: Path, config: str, smell: str = UNCOACHED_SMELL) -> int:
    return mapper.run([_finding(smell)], _project(tmp_path, config))


def test_by_default_an_uncoached_smell_coaches_but_stays_green(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run(tmp_path, "")

    assert code == 0
    assert UNCOACHED_SMELL in capsys.readouterr().out


def test_suggest_is_the_default_spelled_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run(tmp_path, 'uncoached = "suggest"')

    assert code == 0
    assert UNCOACHED_SMELL in capsys.readouterr().out


def test_enforce_restores_the_blocking_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run(tmp_path, 'uncoached = "enforce"')

    assert code == 1
    assert UNCOACHED_SMELL in capsys.readouterr().out


def test_ignore_drops_the_finding_entirely(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dropped through the same seam as ``[smells.<name>] disabled``: the finding
    never renders, so the run reports clean rather than coaching in silence."""
    code = _run(tmp_path, 'uncoached = "ignore"')

    out = capsys.readouterr().out
    assert code == 0
    assert UNCOACHED_SMELL not in out


_CATALOGUED_CASES = [
    (policy, smell)
    for policy in ("suggest", "ignore", "enforce")
    for smell in (CATALOGUED_SMELL, INCOMPLETE_RUN)
]


@pytest.mark.parametrize("case", _CATALOGUED_CASES, ids=str)
def test_a_catalogued_smell_is_out_of_the_policys_reach(
    case: tuple[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both stay `enforced` at every value: the key answers for the smells nobody
    decided about, never for the ones we did. `incomplete-run` is the one that
    must not move — `ignore` turning a broken run into a clean one would undo #88
    through a key that speaks about code smells."""
    policy, smell = case

    code = _run(tmp_path, f'uncoached = "{policy}"', smell)

    assert code == 1
    assert smell in capsys.readouterr().out


def _declaring(policy: str, severity: str) -> str:
    return f'uncoached = "{policy}"\n[smells.{UNCOACHED_SMELL}]\nseverity = "{severity}"'


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (_declaring("suggest", "enforced"), 1),
        (_declaring("enforce", "suggested"), 0),
        (_declaring("ignore", "enforced"), 1),
    ],
)
def test_a_declared_severity_wins_over_the_policy(
    config: str, expected: int, tmp_path: Path
) -> None:
    """One uncoached smell can be promoted (or held back) without moving the
    rest — including out of ``ignore``, where declaring a severity is the
    project saying it has decided about this smell after all."""
    assert _run(tmp_path, config) == expected
