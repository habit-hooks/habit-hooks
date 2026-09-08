"""Shared unused-member coaching across producer-specific issue shapes."""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks import mapper
from plugin_fixture import write_project_config


def _finding(language: str, details: dict) -> dict:
    return {
        "smell": "unused-class-member",
        "language": language,
        "details": {},
        "issues": [{"key": "producer-key", "details": details}],
    }


@pytest.mark.parametrize(
    "case",
    [
        (
            "java",
            {"file": "src/main/java/Foo.java", "line": 17, "message": "opaque PMD text"},
            "src/main/java/Foo.java:17  opaque PMD text",
        ),
        (
            "typescript",
            {"file": "src/helper.ts", "line": 8, "name": "unusedMethod"},
            "src/helper.ts:8  unusedMethod",
        ),
        (
            "java",
            {
                "file": "src/main/java/Foo.java",
                "line": 24,
                "name": "structuredName",
                "message": "fallback text",
            },
            "src/main/java/Foo.java:24  structuredName",
        ),
    ],
)
def test_the_shared_guide_prefers_a_defined_name(
    case: tuple[str, dict, str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    language, issue_details, display = case
    write_project_config(
        tmp_path, 'plugins = ["java", "typescript", "generic"]'
    )

    code = mapper.run([_finding(language, issue_details)], tmp_path)

    out = capsys.readouterr().out
    assert display in out
    assert "General guidance" not in out
    assert code == 1


def test_generic_alone_can_coach_an_unused_member_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_project_config(tmp_path, 'plugins = ["generic"]')
    details = {
        "file": "src/Foo.java",
        "line": 5,
        "message": "PMD supplied this text",
    }

    mapper.run([_finding("java", details)], tmp_path)

    out = capsys.readouterr().out
    assert "src/Foo.java:5  PMD supplied this text" in out
    assert "General guidance" not in out


def test_omitting_generic_leaves_java_unused_members_uncoached(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_project_config(tmp_path, 'plugins = ["java"]')
    details = {
        "file": "src/Foo.java",
        "line": 5,
        "message": "PMD supplied this text",
    }

    mapper.run([_finding("java", details)], tmp_path)

    out = capsys.readouterr().out
    assert "General guidance" in out
    assert "PMD supplied this text" not in out
