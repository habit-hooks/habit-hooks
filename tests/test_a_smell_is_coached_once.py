"""One smell is coached once, however many sensors reported it (#140).

eslint's ``max-lines`` and the generic ``line-count`` sensor both report
``oversized-file``, so a project running both plugins read the same ~200-word
guide twice about one file. The mapper prints one block per finding, which is
why two sensors seeing one smell had to become one finding before anything is
rendered.

This is the reader's half of that: what reaches stdout, and what the banner
counts. The merge's own rules are ``test_merging_findings_of_one_smell.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from habit_hooks import mapper
from plugin_fixture import write_plugin, write_project_config

OVERSIZED_FILE_GUIDE = "Split the file along its seams."
OVERSIZED_FUNCTION_GUIDE = "Extract the steps this function names."
LISTING = "{% for issue in issues %}{{ issue.details.file }}\n{% endfor %}"


PYTHON_COMPLEXITY_GUIDE = "Split the branches this Python function is holding."
GENERIC_COMPLEXITY_GUIDE = "Split the branches this function is holding."


def _project(tmp_path: Path) -> Path:
    """A polyglot project, as a consumer running two language plugins has.

    ``gen`` declares no language and coaches every smell; ``py`` coaches the one
    smell it has a better answer for — which is how a real plugin set is shaped,
    and what decides whether two findings render alike.
    """
    write_plugin(
        tmp_path,
        "gen",
        {
            "config.toml": "sensors = []",
            "guides/oversized-file.md": f"{OVERSIZED_FILE_GUIDE}\n\n{LISTING}",
            "guides/oversized-function.md": f"{OVERSIZED_FUNCTION_GUIDE}\n\n{LISTING}",
            "guides/high-complexity.md": f"{GENERIC_COMPLEXITY_GUIDE}\n\n{LISTING}",
        },
    )
    write_plugin(
        tmp_path,
        "py",
        {
            "config.toml": 'language = "python"\nsensors = []',
            "guides/high-complexity.md": f"{PYTHON_COMPLEXITY_GUIDE}\n\n{LISTING}",
        },
    )
    write_project_config(tmp_path, 'plugins = ["gen", "py"]')
    return tmp_path


def _finding(smell: str, issues: list[dict], **rest: object) -> dict:
    return {"smell": smell, "details": {}, "issues": issues, **rest}


def _at(file: str, **details: object) -> dict:
    return {"key": file, "details": {"file": file, **details}}


def test_two_sensors_reporting_one_smell_print_its_guide_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The bug as Frank reported it: the whole guide, twice, about one file.

    Counted against the guide's own text rather than the file path, which a
    guide is free to list once per issue.
    """
    from_eslint = _finding(
        "oversized-file",
        [_at("src/big.ts", message="File has too many lines", source="eslint:max-lines")],
    )
    from_line_count = _finding(
        "oversized-file", [_at("src/big.ts", lines=260, source="line-count")]
    )

    mapper.run([from_eslint, from_line_count], _project(tmp_path))

    assert capsys.readouterr().out.count(OVERSIZED_FILE_GUIDE) == 1


def test_one_file_two_sensors_saw_is_one_issue_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both sensors named the same place, so the reader has one thing to do.

    Counted, not merely found: two unmerged findings of one issue each print
    that same banner twice.
    """
    from_eslint = _finding("oversized-file", [_at("src/big.ts", line=None)])
    from_line_count = _finding("oversized-file", [_at("src/big.ts", lines=260)])

    mapper.run([from_eslint, from_line_count], _project(tmp_path))

    out = capsys.readouterr().out
    assert out.count("── oversized-file (1 issue) ──") == 1
    assert "(2 issues)" not in out


def test_every_oversized_function_in_one_file_is_still_its_own_issue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The eslint sensor keys every message by its file, so a line-level smell
    arrives as many issues sharing one key. Collapsing those would tell a reader
    with seven long functions that they have one."""
    issues = [_at("src/big.ts", line=line) for line in (3, 40, 80, 120, 160, 200, 240)]

    mapper.run([_finding("oversized-function", issues)], _project(tmp_path))

    assert "── oversized-function (7 issues) ──" in capsys.readouterr().out


def test_different_smells_keep_their_own_blocks_in_arrival_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Merging is per smell; two smells are still two blocks, still in the order
    the findings arrived."""
    findings = [
        _finding("oversized-function", [_at("src/a.ts", line=3)]),
        _finding("oversized-file", [_at("src/b.ts")]),
    ]

    mapper.run(findings, _project(tmp_path))

    out = capsys.readouterr().out
    assert out.index("oversized-function") < out.index("oversized-file")


def test_one_smell_two_plugins_coach_differently_stays_two_blocks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`high-complexity` has a Python guide and a generic one. Merging on the
    smell alone would coach whichever file arrived second in the other one's
    language — the `.ts` file explained in Python, or the `.py` file quietly
    losing its Python guidance."""
    findings = [
        _finding("high-complexity", [_at("src/a.py", line=12)], language="python"),
        _finding("high-complexity", [_at("src/b.ts", line=40)], language="typescript"),
    ]

    mapper.run(findings, _project(tmp_path))

    out = capsys.readouterr().out
    assert out.count("── high-complexity (1 issue) ──") == 2
    assert PYTHON_COMPLEXITY_GUIDE in out
    assert GENERIC_COMPLEXITY_GUIDE in out


def test_each_file_is_listed_under_the_guide_that_coaches_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The half a block count alone would not catch: the right file under the
    right guide, rather than both files under one of them."""
    findings = [
        _finding("high-complexity", [_at("src/a.py", line=12)], language="python"),
        _finding("high-complexity", [_at("src/b.ts", line=40)], language="typescript"),
    ]

    mapper.run(findings, _project(tmp_path))

    python_block, generic_block = capsys.readouterr().out.split(GENERIC_COMPLEXITY_GUIDE)
    assert "src/a.py" in python_block
    assert "src/b.ts" in generic_block
    assert "src/b.ts" not in python_block
