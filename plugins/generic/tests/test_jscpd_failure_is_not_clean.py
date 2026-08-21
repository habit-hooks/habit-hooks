"""jscpd's two signals are ambiguous alone, so the wrapper reads both.

jscpd writes a report only when it has duplicates to put in one, and exits
non-zero both when duplication crosses the threshold and when it breaks. So
neither "no report" nor "non-zero" means failure by itself — only the two
together do. Getting that wrong in either direction is a bug we have shipped
before: fail on a missing report and every clean run breaks; trust the report's
absence and a dead detector reports clean.

These are unit tests rather than executable-spec cases: each drives the wrapper
into one of jscpd's own answers, which is a way this sensor can be wrong rather
than something a user reads the docs to learn.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from jscpd_sensor import run_sensor, write_clones, write_json


# The sensor takes its tool as its first argument whether or not it gets far
# enough to spawn one, and the case below never does. Naming something no machine
# runs keeps that case honest about needing no jscpd installed.
A_TOOL_THIS_CASE_NEVER_SPAWNS = "jscpd-nothing-here-runs"


def _run_sensor(
    project: Path, jscpd: str, config: Path
) -> subprocess.CompletedProcess[str]:
    """The project configures nothing, so the named config is what runs."""
    return run_sensor(project, jscpd, ["--fallback-config", str(config)])


def _config(project: Path, scan: list[str], threshold: int = 100) -> Path:
    return write_json(
        project / "cfg.json",
        {"path": scan, "threshold": threshold, "minLines": 5, "minTokens": 50},
    )


def _sources(project: Path, names: list[str]) -> None:
    write_clones(project / "src", names)


def test_a_jscpd_that_cannot_scan_fails_instead_of_reporting_clean(
    tmp_path: Path, jscpd: str
) -> None:
    config = _config(tmp_path, ["no-such-directory"])

    result = _run_sensor(tmp_path, jscpd, config)

    assert result.returncode == 1, result.stdout
    assert result.stdout.strip() == ""
    assert "no such file or directory" in result.stderr.lower()


def test_finding_no_clones_is_clean_even_though_jscpd_writes_no_report(
    tmp_path: Path, jscpd: str
) -> None:
    """The ordinary clean case, and the one a report-only rule would break.

    jscpd writes a report only when it has duplicates to put in one, so a scan
    that finds nothing leaves no file behind — indistinguishable, by that signal
    alone, from a scan that never happened. Its exit code is what separates them.
    """
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.ts").write_text("export const p = 1;\n", encoding="utf-8")
    (source / "b.ts").write_text("export const q = 2;\n", encoding="utf-8")
    config = _config(tmp_path, ["src"])

    result = _run_sensor(tmp_path, jscpd, config)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_clones_are_reported(tmp_path: Path, jscpd: str) -> None:
    _sources(tmp_path, ["alpha", "beta"])
    config = _config(tmp_path, ["src"])

    result = _run_sensor(tmp_path, jscpd, config)

    assert result.returncode == 0, result.stderr
    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["duplicated-code"]


def test_a_fallback_config_that_is_not_there_fails_the_run(tmp_path: Path) -> None:
    """The project configures nothing and neither, somehow, do we.

    Nothing to fall back to is a broken install, not an empty project — and it
    is reached before jscpd is ever spawned, so nothing downstream would notice
    a `[]` printed here. It is also why this case asks for no jscpd of its own:
    a machine without one still has to answer it.
    """
    _sources(tmp_path, ["alpha", "beta"])

    result = _run_sensor(
        tmp_path, A_TOOL_THIS_CASE_NEVER_SPAWNS, tmp_path / "absent.json"
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_crossing_the_threshold_is_a_result_not_a_failure(
    tmp_path: Path, jscpd: str
) -> None:
    """jscpd exits non-zero here, but it wrote a report — so it is read."""
    _sources(tmp_path, ["alpha", "beta"])
    config = _config(tmp_path, ["src"], threshold=0)

    result = _run_sensor(tmp_path, jscpd, config)

    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["duplicated-code"]
