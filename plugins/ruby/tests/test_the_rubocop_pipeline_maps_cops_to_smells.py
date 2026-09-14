"""The cop-name-to-smell mapping, asked of the shaping functions directly.

No subprocess here: this is the half that says what RuboCop's output *becomes*.
Whether RuboCop still produces output of that shape is
``test_the_rubocop_sensor_runs_the_real_tool``, and the two are separate so a
mapping bug and a tool-upgrade bug cannot be mistaken for one another.
"""

from __future__ import annotations

import pytest
from rubocop_report import COP_SMELLS, findings, offenses, smell_of


def _offense(cop: str, at: tuple[int, int] = (1, 1), message: str = "nope") -> dict:
    """One RuboCop offence. ``at`` is its (line, column), paired because that is
    how RuboCop reports it and because this repo's own `max-args` gate is 3."""
    line, column = at
    return {
        "cop_name": cop,
        "message": message,
        "location": {"line": line, "column": column},
    }


def _entry(cop: str, file: str = "app/billing.rb", **kwargs) -> dict:
    return {"file": file, "offense": _offense(cop, **kwargs)}


def test_no_offenses_is_an_empty_findings_array() -> None:
    """A clean run prints `[]`, never nothing. That is the sensor contract."""
    assert findings([]) == []


def test_one_offense_becomes_the_whole_canonical_finding() -> None:
    """The finding schema asserted literally, so a field lost in a refactor is a
    failure here rather than a guide that renders blank."""
    entry = _entry("Metrics/ParameterLists", at=(4, 11), message="Too many.")

    assert findings([entry]) == [
        {
            "smell": "too-many-parameters",
            "details": {},
            "issues": [
                {
                    "key": "app/billing.rb",
                    "details": {
                        "file": "app/billing.rb",
                        "line": 4,
                        "column": 11,
                        "message": "Too many.",
                        "source": "rubocop:Metrics/ParameterLists",
                    },
                }
            ],
        }
    ]


@pytest.mark.parametrize("cop", sorted(COP_SMELLS))
def test_every_mapped_cop_reaches_its_smell(cop: str) -> None:
    """Each row of the table proven, so a smell key mistyped in the map is
    caught by name rather than by whichever case happened to use that cop."""
    [finding] = findings([_entry(cop)])

    assert finding["smell"] == COP_SMELLS[cop]
    assert finding["issues"][0]["details"]["source"] == f"rubocop:{cop}"


def test_multiple_expectations_reaches_its_guide_smell() -> None:
    [finding] = findings([_entry("RSpec/MultipleExpectations")])

    assert finding["smell"] == "multiple-expectations"
    assert finding["issues"][0]["details"]["source"] == "rubocop:RSpec/MultipleExpectations"


def test_findings_are_grouped_by_smell_and_sorted() -> None:
    """One finding per smell whatever order the offences arrive in. The output
    is compared byte for byte by the spec cases, so it has to be deterministic."""
    grouped = findings(
        [
            _entry("Lint/UselessAssignment"),
            _entry("Metrics/ParameterLists"),
            _entry("Lint/UselessAssignment", file="app/other.rb"),
        ]
    )

    assert [finding["smell"] for finding in grouped] == [
        "too-many-parameters",
        "unused-variable",
    ]
    assert len(grouped[1]["issues"]) == 2


def test_an_unmapped_cop_is_forwarded_under_its_own_name() -> None:
    """The deliberate exception (CLAUDE.md, "A sensor emits vocabulary smells
    only"): knip's keys are knip's own and get dropped, but a cop that fired is
    one the project's `.rubocop.yml` turned on, so it is the project's
    vocabulary and forwarding it saves running RuboCop separately.
    """
    [finding] = findings([_entry("Style/StringLiterals")])

    assert finding["smell"] == "Style/StringLiterals"
    assert finding["issues"][0]["details"]["source"] == "rubocop:Style/StringLiterals"


def test_a_cop_named_like_an_object_attribute_is_still_forwarded() -> None:
    """`.get` with a default, never a bare lookup or a truthiness test. The cop
    name comes from RuboCop and nothing constrains it to the table (#83)."""
    assert smell_of("Metrics/ClassLength") == "Metrics/ClassLength"
    assert smell_of("") == ""


def test_a_correctable_offence_is_tagged_no_more_than_any_other() -> None:
    """`correctable` is RuboCop's autocorrect bookkeeping, not this plugin's.
    The listing's provenance is which cop fired — `rubocop:<cop>` on every
    issue — and nothing else, so a flag saying an autocorrect exists neither
    changes the source nor invites running one. What to do about an offence is
    the guide's question, and a tag that means "an unsafe autocorrect may
    exist" is not an answer to it.
    """
    entry = _entry("Lint/UselessAssignment")
    entry["offense"]["correctable"] = True

    [finding] = findings([entry])

    assert finding["issues"][0]["details"]["source"] == "rubocop:Lint/UselessAssignment"


def test_a_report_inspecting_nothing_is_no_offenses() -> None:
    """RuboCop still prints its envelope when every file was excluded."""
    assert offenses({"files": []}) == []


def test_the_per_file_nesting_is_flattened_carrying_each_path() -> None:
    """RuboCop nests offences under each file; the finding's issue key is the
    file, so the path has to survive the flattening."""
    parsed = {
        "files": [
            {"path": "app/a.rb", "offenses": [_offense("Metrics/MethodLength")]},
            {"path": "app/b.rb", "offenses": []},
            {"path": "app/c.rb", "offenses": [_offense("Metrics/MethodLength")]},
        ]
    }

    [finding] = findings(offenses(parsed))

    assert [issue["key"] for issue in finding["issues"]] == ["app/a.rb", "app/c.rb"]
