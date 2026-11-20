from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from git_repo import repository, stop_the_upward_walk_at
from habit_hooks import mapper, rendering, sensors
from habit_hooks.config import load_config
from habit_hooks.resolve import Resolver
from habit_hooks.scope import Scope
from habit_hooks.sensors.execution import Execution
from habit_hooks.sensors.loader import PluginLoader
from plugin_fixture import write_project_config
from slow_test import report_entries, run_pytest
from slow_test import findings as report_for

SLOW_TEST = """\
import time


def test_this_is_slow():
    time.sleep(0.2)


def test_this_is_fast():
    assert 1 + 1 == 2
"""

PROJECT_CONFIG = (
    'plugins = ["python", "generic"]\n'
    + "".join(
        f"[sensors.{name}]\ndisabled = true\n"
        for name in ("ruff", "deptry", "comment", "line-count", "jscpd")
    )
    + '[sensors.slow-test]\nargs = ["--budget", "0.1"]\n'
)


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    stop_the_upward_walk_at(tmp_path, monkeypatch)
    return tmp_path


@pytest.fixture
def pytest_tool() -> str:
    found = shutil.which("pytest")
    if found is None:
        pytest.fail("pytest is not on PATH — run 'uv sync'")
    return found


@pytest.fixture
def app(isolated_root: Path, monkeypatch: pytest.MonkeyPatch, pytest_tool: str) -> Path:
    project = isolated_root / "app"
    repository(project)
    (project / "tests").mkdir()
    (project / "tests" / "test_billing.py").write_text(SLOW_TEST, encoding="utf-8")
    write_project_config(project, PROJECT_CONFIG)
    monkeypatch.chdir(project)
    return project


def slow_test_sensor(project: Path):
    loader = PluginLoader(Resolver.discover(project), load_config(project))
    parts = [
        part
        for part in loader.load_plugin("python").sensors
        if part.name == "slow-test"
    ]
    assert len(parts) == 1, parts
    return parts[0]


def scan_tests(project: Path):
    return Execution(
        project_dir=project, scope=Scope(files=["tests/test_billing.py"])
    ).run_sensors([slow_test_sensor(project)])


def test_a_newly_added_test_over_the_budget_is_a_slow_test_finding(app: Path) -> None:
    run = scan_tests(app)
    assert run.notices == []
    assert [finding["smell"] for finding in run.findings] == ["slow-test"]
    finding = run.findings[0]
    assert finding["details"] == {"maxAllowed": 0.1}
    assert [issue["key"] for issue in finding["issues"]] == [
        "tests/test_billing.py::test_this_is_slow"
    ]
    assert finding["issues"][0]["details"]["duration"] > 0.1


def test_a_budget_the_slow_test_fits_under_is_a_clean_run(app: Path) -> None:
    write_project_config(
        app,
        PROJECT_CONFIG.replace(
            'args = ["--budget", "0.1"]', 'args = ["--budget", "2"]'
        ),
    )
    run = scan_tests(app)
    assert run.notices == []
    assert run.findings == []


def test_a_slow_test_finding_is_coached_not_uncoached(
    app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert sensors.main(["--all"]) == 0
    report = json.loads(capsys.readouterr().out)
    finding = report[0]
    guide = rendering.resolve_guide(finding, load_config(app), Resolver.discover(app))
    assert [item["smell"] for item in report] == ["slow-test"]
    assert finding["language"] == "python"
    assert guide.name == "slow-test.md"
    assert mapper.run(report, app) == 0


def test_the_slow_test_guide_coaches_fast_deterministic_tests(
    isolated_root: Path,
) -> None:
    write_project_config(isolated_root, 'plugins = ["python", "generic"]')
    rendered = rendering.render_finding(
        report_for([("tests/test_billing.py::test_this_is_slow", 1.23)], 1.0)[0],
        load_config(isolated_root),
        Resolver.discover(isolated_root),
    )
    assert "Cut per-test work" in rendered.text
    assert "Reuse fixtures" in rendered.text
    assert "deterministic" in rendered.text.lower()
    assert "tests/test_billing.py::test_this_is_slow" in rendered.text
    assert "Tests over 1.0 seconds" in rendered.text


def test_real_pytest_durations_are_parseable(tmp_path: Path, pytest_tool: str) -> None:
    tests = tmp_path / "plain" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_billing.py").write_text(SLOW_TEST, encoding="utf-8")
    report = tmp_path / "timings.json"
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(tmp_path / "plain")
        result = run_pytest(pytest_tool, ["tests/test_billing.py"], report)
    assert result.returncode == 0, result.stderr
    entries = dict(report_entries(report))
    assert entries["tests/test_billing.py::test_this_is_slow"] > 0.1
    keys = [
        issue["key"] for issue in report_for(list(entries.items()), 0.1)[0]["issues"]
    ]
    assert keys == ["tests/test_billing.py::test_this_is_slow"]
