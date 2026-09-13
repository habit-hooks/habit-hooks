"""Shared unused-member coaching follows the line-level issue contract."""

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
            {
                "file": "src/main/java/Foo.java",
                "line": 17,
                "content": "private int staleField;",
            },
            "src/main/java/Foo.java:17  private int staleField;",
        ),
        (
            "typescript",
            {"file": "src/helper.ts", "line": 8, "content": "unusedMethod"},
            "src/helper.ts:8  unusedMethod",
        ),
    ],
)
def test_the_shared_guide_renders_line_level_content(
    case: tuple[str, dict, str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    language, details, display = case
    write_project_config(tmp_path, 'plugins = ["generic"]')

    code = mapper.run([_finding(language, details)], tmp_path)

    out = capsys.readouterr().out
    assert display in out
    assert "General guidance" not in out
    assert code == 1
