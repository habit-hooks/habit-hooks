"""Unused-member behavior from built wheels without the source tree."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from habit_hooks.project_paths import venv_executable
from installed_env import require_tool, run_and_collect_findings
from installed_projects import JAVA_UNUSED_MEMBER_SOURCE, java_unused_member_project


def _assert_installed_guide(
    mapper: Path, project: Path, case: tuple[str, str, dict, str]
) -> None:
    language, plugins, details, display = case
    (project / ".habit-hooks").mkdir(parents=True)
    (project / ".habit-hooks" / "config.toml").write_text(
        f"plugins = {plugins}\n", encoding="utf-8"
    )
    finding = {
        "smell": "unused-class-member",
        "language": language,
        "details": {},
        "issues": [{"key": "producer-key", "details": details}],
    }
    result = subprocess.run(
        [str(mapper)],
        cwd=project,
        input=json.dumps([finding]),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 1, result.stderr
    assert display in result.stdout
    assert "General guidance" not in result.stdout


def _installed_guide_ownership(python: Path, cwd: Path) -> dict[str, bool]:
    result = subprocess.run(
        [
            str(python),
            "-c",
            "from importlib.resources import files; import json; "
            "print(json.dumps({p: files(p).joinpath('guides', "
            "'unused-class-member.md').is_file() for p in "
            "('habit_hooks_java', 'habit_hooks_typescript', "
            "'habit_hooks_generic')}))",
        ],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(result.stdout)


def test_installed_java_fallback_reports_both_unused_private_member_rules(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    require_tool("pmd")
    project = java_unused_member_project(tmp_path)

    findings = run_and_collect_findings(installed_habit_sensors, project)

    assert [finding["smell"] for finding in findings] == ["unused-class-member"]
    issues = findings[0]["issues"]
    assert [issue["key"] for issue in issues] == [
        JAVA_UNUSED_MEMBER_SOURCE,
        JAVA_UNUSED_MEMBER_SOURCE,
    ]
    assert [issue["details"]["line"] for issue in issues] == [2, 3]
    assert [issue["details"]["source"] for issue in issues] == [
        "pmd:UnusedPrivateField",
        "pmd:UnusedPrivateMethod",
    ]
    assert all("name" not in issue["details"] for issue in issues)


def test_installed_generic_wheel_alone_owns_shared_unused_member_coaching(
    installed_habit_sensors: Path, tmp_path: Path
) -> None:
    venv = installed_habit_sensors.parent.parent
    mapper = venv_executable(venv, "habit-mapper")
    cases = [
        (
            "java",
            '["java", "generic"]',
            {"file": "src/Foo.java", "line": 7, "message": "opaque PMD text"},
            "src/Foo.java:7  opaque PMD text",
        ),
        (
            "typescript",
            '["typescript", "generic"]',
            {"file": "src/helper.ts", "line": 8, "name": "unusedMethod"},
            "src/helper.ts:8  unusedMethod",
        ),
    ]
    for case in cases:
        _assert_installed_guide(mapper, tmp_path / case[0], case)
    python = venv_executable(venv, "python")
    assert _installed_guide_ownership(python, tmp_path) == {
        "habit_hooks_java": False,
        "habit_hooks_typescript": False,
        "habit_hooks_generic": True,
    }
