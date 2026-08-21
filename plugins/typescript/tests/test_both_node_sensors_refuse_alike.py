"""Whatever went wrong, both Node sensors say so in the same words.

eslint and knip each wrap a project tool, and each has to turn a run it cannot
read into a diagnosis. #142 is what happens when they answer that separately:
knip carried its own failure text and its own output cap, eslint carried
neither, and the one that carried neither shipped a notice with nothing in it.
The answer is that both route every unusable run through the one seam
(``sensors/project_tool.cjs``) — so these cases are deliberately paired, and a
new one here should be too.

``test_a_broken_tool_is_never_silent.py`` is the other half: what the seam
answers. This is whether its callers ask.
"""

from __future__ import annotations

from pathlib import Path

from project_tool_probe import a_project_whose_tool, run

SENSORS = Path(__file__).parents[1] / "src" / "habit_hooks_typescript" / "sensors"

FAILS_WITHOUT_A_WORD = "process.exit(2);\n"

# A tool that thinks it succeeded and printed nothing at all. Both sensors ask
# their tool for JSON, and `JSON.parse("")` is a SyntaxError.
SUCCEEDS_WITHOUT_A_WORD = "process.exit(0);\n"


def test_the_eslint_sensor_says_which_tool_failed(tmp_path: Path) -> None:
    project = a_project_whose_tool(tmp_path, "eslint", FAILS_WITHOUT_A_WORD)

    result = run(["node", str(SENSORS / "eslint.cjs"), "--", "src/a.ts"], project)

    assert result.returncode != 0
    assert result.stderr == "eslint: exited 2 without a word of its own\n"


def test_the_knip_sensor_says_which_tool_failed(tmp_path: Path) -> None:
    project = a_project_whose_tool(tmp_path, "knip", FAILS_WITHOUT_A_WORD)

    result = run(["node", str(SENSORS / "knip.cjs")], project)

    assert result.returncode != 0
    assert result.stderr == "knip: exited 2 without a word of its own\n"


def test_a_knip_that_reported_nothing_at_all_is_a_diagnosis_not_a_traceback(
    tmp_path: Path,
) -> None:
    """A clean exit with an empty stdout leaves nothing to parse, and knip
    reached `JSON.parse` without asking — so the sensor died with
    `SyntaxError: Unexpected end of JSON input` and a Node traceback, in the one
    place that exists to hand the runner a sentence instead. eslint has always
    asked before parsing; the answer is now the same for both."""
    project = a_project_whose_tool(tmp_path, "knip", SUCCEEDS_WITHOUT_A_WORD)

    result = run(["node", str(SENSORS / "knip.cjs")], project)

    assert result.returncode != 0
    assert result.stderr == "knip: exited 0 without a word of its own\n"


def test_an_eslint_that_reported_nothing_at_all_is_a_diagnosis_not_a_traceback(
    tmp_path: Path,
) -> None:
    """The pair of the case above, kept beside it: this one has always been
    answered, and it is what knip's answer was matched to."""
    project = a_project_whose_tool(tmp_path, "eslint", SUCCEEDS_WITHOUT_A_WORD)

    result = run(["node", str(SENSORS / "eslint.cjs"), "--", "src/a.ts"], project)

    assert result.returncode != 0
    assert result.stderr == "eslint: exited 0 without a word of its own\n"
