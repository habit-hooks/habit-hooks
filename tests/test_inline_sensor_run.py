
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_fixture import loader_for, write_plugin, write_project_config

from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution

MADE_UP = {"violations": [
    {"where": "src/a.py", "rule": "MAGIC-1", "note": "too magic"},
    {"where": "src/b.py", "rule": "MAGIC-1", "note": "also magic"},
]}
GROUPING = (
    '.violations | group_by(.rule) | map({smell: "made-up-smell", details: {}, '
    'issues: map({key: .where, details: {file: .where, message: .note}})})'
)
FINDING = {
    "smell": "made-up-smell",
    "details": {},
    "issues": [
        {"key": "src/a.py", "details": {"file": "src/a.py", "message": "too magic"}},
        {"key": "src/b.py", "details": {"file": "src/b.py", "message": "also magic"}},
    ],
}


def inline_run(project: Path, entry: str, files: dict[str, str]):
    write_project_config(project, 'plugins = ["fixt"]')
    write_plugin(project, "fixt", {"config.toml": f"sensors = [{entry}]", **files})
    sensor = loader_for(project).load_plugin("fixt").sensors[0]
    return Execution(
        project_dir=project, scope=Scope(files=["src/a.py"])
    ).run_sensors([sensor])


def an_entry(body: str, extra: str = "") -> tuple[str, dict[str, str]]:
    return (
        f'{{ tool = "${{python}}", name = "lint", args = ["${{dir}}/tool.py"]'
        f"{extra} }}",
        {"tool.py": body},
    )


def test_a_transform_maps_a_made_up_shape_into_grouped_findings(tmp_path: Path) -> None:
    entry, files = an_entry(
        f"print({json.dumps(MADE_UP)!r})\n", ', transform = "map.jq"'
    )

    run = inline_run(tmp_path, entry, {**files, "map.jq": GROUPING})

    assert run.findings == [FINDING]
    assert run.notices == []


def test_without_a_transform_stdout_is_already_the_findings(tmp_path: Path) -> None:
    extra = {**FINDING, "extra": "kept"}
    entry, files = an_entry(f"print({json.dumps([extra])!r})\n")

    run = inline_run(tmp_path, entry, files)

    assert run.findings == [extra]


def test_an_empty_scope_never_spawns_the_tool(tmp_path: Path) -> None:
    files = {"tool.py": 'import pathlib; pathlib.Path("SPAWNED").write_text("x"); print("[]")\n'}
    entry = '{ tool = "${python}", name = "lint", args = ["${dir}/tool.py", "${files}"] }'

    write_project_config(tmp_path, 'plugins = ["fixt"]')
    write_plugin(tmp_path, "fixt", {"config.toml": f"sensors = [{entry}]", **files})
    sensor = loader_for(tmp_path).load_plugin("fixt").sensors[0]

    run = Execution(project_dir=tmp_path, scope=Scope(files=[])).run_sensors([sensor])

    assert run.findings == []
    assert not (tmp_path / "SPAWNED").exists()


def test_a_linter_exit_is_success_when_the_codes_say_so(tmp_path: Path) -> None:
    entry, files = an_entry(
        'import sys; print("[]"); sys.exit(1)\n', ', success_exit_codes = [0, 1]'
    )

    run = inline_run(tmp_path, entry, files)

    assert run.findings == []
    assert run.notices == []


def test_an_exit_1_with_no_output_is_a_failed_run_not_findings(tmp_path: Path) -> None:
    entry, files = an_entry("import sys; sys.exit(1)\n", ', success_exit_codes = [0, 1]')

    run = inline_run(tmp_path, entry, files)

    assert run.findings == []
    assert "is not JSON" in run.notices[0]


def test_an_exit_code_outside_the_success_codes_fails_the_run(tmp_path: Path) -> None:
    entry, files = an_entry(
        'import sys; sys.stderr.write("boom: bad config\\n"); sys.exit(3)\n',
        ', success_exit_codes = [0, 1]',
    )

    run = inline_run(tmp_path, entry, files)

    assert run.findings == []
    assert "sensor 'lint' failed" in run.notices[0]
    assert "boom: bad config" in run.notices[0]


def test_the_tools_stdout_is_the_diagnosis_when_stderr_was_empty(
    tmp_path: Path,
) -> None:
    entry, files = an_entry('import sys; print("Error: no such rule"); sys.exit(2)\n')

    run = inline_run(tmp_path, entry, files)

    assert "Error: no such rule" in run.notices[0]


def test_output_that_is_not_json_fails_the_run(tmp_path: Path) -> None:
    entry, files = an_entry('print("not json at all")\n')

    run = inline_run(tmp_path, entry, files)

    assert "is not JSON" in run.notices[0]


@pytest.mark.parametrize(
    "findings",
    [
        [{"smell": 1, "details": {}, "issues": []}],
        [{"smell": "s", "details": [], "issues": []}],
        [{"smell": "s", "details": {}, "issues": {}}],
        [{"smell": "s", "details": {}, "issues": [{"key": 2, "details": {}}]}],
        [{"smell": "s", "details": {}, "issues": [{"key": "k", "details": None}]}],
    ],
)
def test_a_finding_outside_the_contract_fails_the_run(
    tmp_path: Path, findings: list
) -> None:
    entry, files = an_entry(f"print({json.dumps(findings)!r})\n")

    run = inline_run(tmp_path, entry, files)

    assert "contract" in run.notices[0]


def test_a_transform_that_does_not_answer_an_array_fails_the_run(
    tmp_path: Path,
) -> None:
    entry, files = an_entry(
        f"print({json.dumps(MADE_UP)!r})\n", ', transform = "map.jq"'
    )

    run = inline_run(
        tmp_path, entry, {**files, "map.jq": "{count: (.violations | length)}"}
    )

    assert "findings array" in run.notices[0]


def test_a_transform_that_answers_nothing_fails_the_run(tmp_path: Path) -> None:
    entry, files = an_entry(
        f"print({json.dumps(MADE_UP)!r})\n", ', transform = "map.jq"'
    )

    run = inline_run(tmp_path, entry, {**files, "map.jq": "empty"})

    assert "map.jq" in run.notices[0]
