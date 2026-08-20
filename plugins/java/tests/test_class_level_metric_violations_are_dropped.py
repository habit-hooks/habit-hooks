"""NcssCount and CyclomaticComplexity report classes as well as methods and
constructors, off one rule each. The catalogue has a smell only for an
over-complex or oversized *method* — `high-complexity`'s guide says "extract
one function per branch" — so a class-level violation of either rule must be
dropped, not forwarded as if it named a function.

The bundled ruleset only sets `methodReportLevel`, leaving
`CyclomaticComplexity`'s `classReportLevel` at PMD's default of 80: a class of
many simple methods trips it, and before this fix `smell_of` filtered
class-level violations for `NcssCount` only, so the class-level
`CyclomaticComplexity` slipped through as `high-complexity` with no
over-complex function anywhere in the file.
"""

from __future__ import annotations

from pmd_sensor import findings, smell_of


def _entry(rule: str, description: str, beginline: int = 1) -> dict:
    return {
        "file": "Fat.java",
        "violation": {
            "rule": rule,
            "description": description,
            "beginline": beginline,
        },
    }


def test_a_class_level_cyclomatic_complexity_violation_is_dropped() -> None:
    entry = _entry(
        "CyclomaticComplexity",
        "The class 'Fat' has a total cyclomatic complexity of 100 (highest 5).",
    )

    assert smell_of(entry) is None


def test_a_method_level_cyclomatic_complexity_violation_is_high_complexity() -> None:
    entry = _entry(
        "CyclomaticComplexity", "The method 'f(int)' has a cyclomatic complexity of 12."
    )

    assert smell_of(entry) == "high-complexity"


def test_a_constructor_level_cyclomatic_complexity_violation_is_high_complexity() -> (
    None
):
    entry = _entry(
        "CyclomaticComplexity",
        "The constructor 'Both(int)' has a cyclomatic complexity of 12.",
    )

    assert smell_of(entry) == "high-complexity"


def test_a_class_level_ncss_count_violation_is_still_dropped() -> None:
    """The behaviour the original filter already had, kept while the filter
    generalises from one rule to two."""
    entry = _entry("NcssCount", "The class 'Fat' has an NCSS line count of 200.")

    assert smell_of(entry) is None


def test_a_method_level_ncss_count_violation_is_still_oversized_function() -> None:
    entry = _entry("NcssCount", "The method 'f()' has an NCSS line count of 40.")

    assert smell_of(entry) == "oversized-function"


def test_an_enum_level_ncss_count_violation_is_dropped() -> None:
    """PMD also words this one as 'The enum', 'The interface' and 'The
    record' — none of them a method or a constructor."""
    entry = _entry("NcssCount", "The enum 'Kind' has an NCSS line count of 90.")

    assert smell_of(entry) is None


def test_excessive_parameter_list_still_maps_to_too_many_parameters() -> None:
    entry = _entry(
        "ExcessiveParameterList", "Avoid long parameter lists.", beginline=4
    )

    assert smell_of(entry) == "too-many-parameters"


def test_unnecessary_import_still_maps_to_unused_import() -> None:
    entry = _entry("UnnecessaryImport", "Unused import 'java.io.File'.")

    assert smell_of(entry) == "unused-import"


def test_unused_local_variable_still_maps_to_unused_variable() -> None:
    entry = _entry(
        "UnusedLocalVariable", "Avoid unused local variables such as 'dead'."
    )

    assert smell_of(entry) == "unused-variable"


def test_empty_catch_block_still_maps_to_swallowed_exception() -> None:
    entry = _entry("EmptyCatchBlock", "Avoid empty catch blocks.")

    assert smell_of(entry) == "swallowed-exception"


def test_a_class_level_violation_never_reaches_findings() -> None:
    """The whole shape a real PMD run would produce: a class-level
    complexity violation sitting beside a real method-level one — only the
    method-level violation survives into the findings the mapper sees."""
    entries = [
        _entry(
            "CyclomaticComplexity",
            "The class 'Fat' has a total cyclomatic complexity of 100 (highest 5).",
        ),
        _entry(
            "CyclomaticComplexity",
            "The method 'f(int)' has a cyclomatic complexity of 12.",
            beginline=3,
        ),
    ]

    result = findings(entries)

    assert len(result) == 1
    assert result[0]["smell"] == "high-complexity"
    assert len(result[0]["issues"]) == 1
