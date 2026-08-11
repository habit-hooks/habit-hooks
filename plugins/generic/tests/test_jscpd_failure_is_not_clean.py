"""jscpd's two signals are ambiguous alone, so the wrapper reads both.

jscpd writes a report only when it has duplicates to put in one, and exits
non-zero both when duplication crosses the threshold and when it breaks. So
neither "no report" nor "non-zero" means failure by itself — only the two
together do. Getting that wrong in either direction is a bug we have shipped
before: fail on a missing report and every clean run breaks; trust the report's
absence and a dead detector reports clean.

These are unit tests rather than executable-spec cases because a spec case runs
in a temp project where jscpd is not on PATH — there, the wrapper never gets far
enough to make this decision.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
SENSOR = _REPO_ROOT / "plugins/generic/src/habit_hooks_generic/sensors/jscpd.py"
JSCPD_BIN = _REPO_ROOT / "node_modules" / ".bin"

CLONED_BLOCK = (
    "export function {name}(x: number, y: number) {{\n"
    "  const sum = x + y;\n"
    "  const product = x * y;\n"
    "  const diff = x - y;\n"
    "  const quotient = x / y;\n"
    "  const scaled = sum * product;\n"
    "  const shifted = diff - quotient;\n"
    "  const blended = scaled + shifted;\n"
    "  return {{ sum, product, diff, quotient, scaled, shifted, blended }};\n"
    "}}\n"
)


def _requires_jscpd() -> None:
    if not (JSCPD_BIN / "jscpd").exists():
        pytest.skip("jscpd is not installed at the repo root (pnpm install)")


def _run_sensor(
    project: Path, config: Path, path: str | None = None
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PATH"] = (
        path if path is not None else f"{JSCPD_BIN}{os.pathsep}{environment['PATH']}"
    )
    return subprocess.run(
        [sys.executable, str(SENSOR), "--config", str(config)],
        cwd=project,
        capture_output=True,
        text=True,
        env=environment,
    )


def _config(project: Path, scan: list[str], threshold: int = 100) -> Path:
    config = project / "cfg.json"
    config.write_text(
        json.dumps(
            {"path": scan, "threshold": threshold, "minLines": 5, "minTokens": 50}
        )
    )
    return config


def _sources(project: Path, names: list[str]) -> None:
    source = project / "src"
    source.mkdir()
    for name in names:
        (source / f"{name}.ts").write_text(CLONED_BLOCK.format(name=name))


def test_a_jscpd_that_cannot_scan_fails_instead_of_reporting_clean(
    tmp_path: Path,
) -> None:
    _requires_jscpd()
    config = _config(tmp_path, ["no-such-directory"])

    result = _run_sensor(tmp_path, config)

    assert result.returncode == 1, result.stdout
    assert result.stdout.strip() == ""
    assert "no such file or directory" in result.stderr.lower()


def test_a_jscpd_nobody_installed_answers_the_way_a_shell_does(
    tmp_path: Path,
) -> None:
    """An absent tool raised a ``FileNotFoundError`` out of ``subprocess.run``,
    and twenty lines of Python internals became the sensor's diagnosis (#114).

    This wrapper stands in for the shell when it looks for jscpd, so it answers
    the way a shell does — ``jscpd: command not found`` — which is the phrase the
    run recognises to name the missing tool instead of quoting a traceback back.
    """
    config = _config(tmp_path, ["src"])

    result = _run_sensor(tmp_path, config, path="/nonexistent")

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == "jscpd: command not found"


def test_finding_no_clones_is_clean_even_though_jscpd_writes_no_report(
    tmp_path: Path,
) -> None:
    """The ordinary clean case, and the one a report-only rule would break.

    jscpd writes a report only when it has duplicates to put in one, so a scan
    that finds nothing leaves no file behind — indistinguishable, by that signal
    alone, from a scan that never happened. Its exit code is what separates them.
    """
    _requires_jscpd()
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.ts").write_text("export const p = 1;\n")
    (source / "b.ts").write_text("export const q = 2;\n")
    config = _config(tmp_path, ["src"])

    result = _run_sensor(tmp_path, config)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_clones_are_reported(tmp_path: Path) -> None:
    _requires_jscpd()
    _sources(tmp_path, ["alpha", "beta"])
    config = _config(tmp_path, ["src"])

    result = _run_sensor(tmp_path, config)

    assert result.returncode == 0, result.stderr
    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["duplicated-code"]


def test_crossing_the_threshold_is_a_result_not_a_failure(tmp_path: Path) -> None:
    """jscpd exits non-zero here, but it wrote a report — so it is read."""
    _requires_jscpd()
    _sources(tmp_path, ["alpha", "beta"])
    config = _config(tmp_path, ["src"], threshold=0)

    result = _run_sensor(tmp_path, config)

    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["duplicated-code"]
