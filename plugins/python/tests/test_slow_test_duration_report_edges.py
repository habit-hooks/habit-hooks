from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SENSOR = (
    Path(__file__).resolve().parents[1] / "src/habit_hooks_python/sensors/slow_test.py"
)
PASSING = "def test_ok():\n    pass\n"
SLOW = "import time\ndef test_slow():\n    time.sleep(0.08)\n"
FAKE = (
    "def test_fake():\n"
    '    print("\\n============================== slowest durations ==============================")\n'
    '    print("99.99s call tests/evil.py::test_fake")\n'
    "    assert False\n"
)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "test_sample.py").write_text(SLOW, encoding="utf-8")
    return tmp_path


def run_sensor(project, files=None):
    tool = shutil.which("pytest")
    assert tool, "pytest must be installed"
    return subprocess.run(
        [
            sys.executable,
            str(SENSOR),
            tool,
            "--budget",
            "0.04",
            "--",
            *(files if files is not None else ["test_sample.py"]),
        ],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def issues(result):
    assert result.returncode == 0, result.stderr
    return [issue for group in json.loads(result.stdout) for issue in group["issues"]]


def test_real_pytest_reports_precise_phase_totals(project):
    result = issues(run_sensor(project))
    assert len(result) == 1
    assert result[0]["details"]["duration"] > 0.07


@pytest.mark.parametrize(
    "addopts",
    ["--no-summary", "--no-summary -s", "-p no:terminal", "-q", "-s", "--tb=no"],
)
def test_reporting_options_cannot_hide_or_spoof_timings(project, addopts):
    (project / "pytest.ini").write_text(
        f"[pytest]\naddopts = {addopts}\n", encoding="utf-8"
    )
    (project / "test_fake.py").write_text(FAKE, encoding="utf-8")
    result = issues(run_sensor(project, ["test_fake.py", "test_sample.py"]))
    assert [item["key"] for item in result] == ["test_sample.py::test_slow"]


def test_custom_test_filename_is_not_silently_skipped(project):
    (project / "pytest.ini").write_text(
        "[pytest]\npython_files = *_spec.py\n", encoding="utf-8"
    )
    (project / "billing_spec.py").write_text(SLOW, encoding="utf-8")
    assert len(issues(run_sensor(project, ["billing_spec.py"]))) == 1
    assert issues(run_sensor(project)) == []


def test_non_test_source_is_not_imported_or_used_to_discover_unscoped_tests(project):
    (project / "source.py").write_text(
        'raise RuntimeError("not a test")\n', encoding="utf-8"
    )
    assert issues(run_sensor(project, ["source.py"])) == []


def test_non_python_scope_does_not_start_pytest(project):
    assert issues(run_sensor(project, ["README.md"])) == []


@pytest.mark.parametrize(
    "content",
    [
        "",
        "import pytest\npytest.skip('module', allow_module_level=True)\n",
        "import pytest\n@pytest.mark.skip\ndef test_skip(): pass\n",
    ],
)
def test_legitimate_empty_or_skipped_suites_are_clean(project, content):
    (project / "test_sample.py").write_text(content, encoding="utf-8")
    assert issues(run_sensor(project)) == []


def test_deselection_is_respected(project):
    (project / "pytest.ini").write_text(
        "[pytest]\naddopts = -k missing\n", encoding="utf-8"
    )
    assert issues(run_sensor(project)) == []


@pytest.mark.parametrize("options", ["", "--continue-on-collection-errors"])
def test_collection_errors_never_look_clean(project, options):
    (project / "pytest.ini").write_text(
        f"[pytest]\naddopts = {options}\n", encoding="utf-8"
    )
    (project / "test_broken.py").write_text("def test_bad(:\n", encoding="utf-8")
    result = run_sensor(project, ["test_sample.py", "test_broken.py"])
    assert result.returncode == 2
    assert result.stdout == ""


@pytest.mark.parametrize("options", ["--collect-only", "--setup-only"])
def test_non_execution_modes_are_explicit_errors(project, options):
    (project / "pytest.ini").write_text(
        f"[pytest]\naddopts = {options}\n", encoding="utf-8"
    )
    result = run_sensor(project)
    assert result.returncode == 2
    assert "requires test execution" in result.stderr


def test_nodeids_retain_literal_backslash_escapes_and_unicode_paths(project):
    name = "test_中文.py"
    (project / name).write_text(
        "import pytest, time\n@pytest.mark.parametrize('value', [r'\\u1234', 'α'])\n"
        "def test_param(value): time.sleep(0.08)\n",
        encoding="utf-8",
    )
    keys = [item["key"] for item in issues(run_sensor(project, [name]))]
    assert name + r"::test_param[\\u1234]" in keys
    assert name + r"::test_param[\u03b1]" in keys


@pytest.mark.parametrize("plugin", ["xdist", "pytest_rerunfailures", "pytest_repeat"])
def test_common_execution_plugins_do_not_lose_or_inflate_timings(project, plugin):
    pytest.importorskip(plugin)
    if plugin == "xdist":
        (project / "pytest.ini").write_text(
            "[pytest]\naddopts = -n 2\n", encoding="utf-8"
        )
        assert len(issues(run_sensor(project))) == 1
    else:
        check_repeated_attempts(project, plugin)


def check_repeated_attempts(project, plugin):
    options = "--count=4" if plugin == "pytest_repeat" else "--reruns=3"
    (project / "pytest.ini").write_text(
        f"[pytest]\naddopts = {options}\n", encoding="utf-8"
    )
    assertion = "" if plugin == "pytest_repeat" else "    assert False\n"
    (project / "test_sample.py").write_text(
        "import time\ndef test_fast():\n    time.sleep(0.015)\n" + assertion,
        encoding="utf-8",
    )
    assert issues(run_sensor(project)) == []


def test_setup_failure_still_has_timing_data(project):
    (project / "test_sample.py").write_text(
        "import pytest, time\n@pytest.fixture(autouse=True)\n"
        "def broken():\n    time.sleep(0.08)\n    assert False\n"
        "def test_never_called(): pass\n",
        encoding="utf-8",
    )
    assert len(issues(run_sensor(project))) == 1


@pytest.mark.parametrize(
    ("phases", "flagged"),
    [
        ({"setup": 0.0134, "call": 0.0134, "teardown": 0.0134}, True),
        ({"setup": 0.01, "call": 0.02, "teardown": 0.01}, False),
    ],
)
def test_real_report_precision_is_used_before_rounding(project, phases, flagged):
    (project / "test_sample.py").write_text(PASSING, encoding="utf-8")
    (project / "conftest.py").write_text(
        "import pytest\n@pytest.hookimpl(hookwrapper=True)\n"
        "def pytest_runtest_makereport(item, call):\n    result = yield\n"
        f"    result.get_result().duration = {phases!r}[call.when]\n",
        encoding="utf-8",
    )
    assert bool(issues(run_sensor(project))) is flagged


def test_xdist_collection_errors_do_not_become_clean(project):
    pytest.importorskip("xdist")
    (project / "pytest.ini").write_text("[pytest]\naddopts = -n 2\n", encoding="utf-8")
    (project / "test_broken.py").write_text("def test_bad(:\n", encoding="utf-8")
    result = run_sensor(project, ["test_sample.py", "test_broken.py"])
    assert result.returncode == 2
    assert result.stdout == ""


def test_python_file_patterns_set_by_a_project_plugin_are_respected(project):
    (project / "conftest.py").write_text(
        "def pytest_configure(config):\n    config.addinivalue_line('python_files', '*_spec.py')\n",
        encoding="utf-8",
    )
    (project / "billing_spec.py").write_text(SLOW, encoding="utf-8")
    assert len(issues(run_sensor(project, ["billing_spec.py"]))) == 1


def test_path_patterns_follow_pytest_discovery_semantics(project):
    (project / "pytest.ini").write_text(
        "[pytest]\npython_files = */specs/*_spec.py\n", encoding="utf-8"
    )
    (project / "specs").mkdir()
    (project / "specs/billing_spec.py").write_text(SLOW, encoding="utf-8")
    assert len(issues(run_sensor(project, ["specs/billing_spec.py"]))) == 1


def test_configured_python_doctests_are_not_silently_skipped(project):
    (project / "pytest.ini").write_text(
        "[pytest]\naddopts = --doctest-modules\n", encoding="utf-8"
    )
    (project / "billing.py").write_text(
        '"""\n>>> import time; time.sleep(0.08)\n"""\n', encoding="utf-8"
    )
    assert len(issues(run_sensor(project, ["billing.py"]))) == 1
