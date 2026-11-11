from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "generic"
    / "src"
    / "habit_hooks_generic"
    / "jscpd.py"
)
FALLBACK_CONFIG = {"path": ["src"]}


def _write_jscpd_stub(bin_dir: Path, python_body: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "jscpd_stub.py"
    stub.write_text(python_body, encoding="utf-8")
    if os.name == "nt":
        (bin_dir / "jscpd.cmd").write_text(
            f'@echo off\r\n"{sys.executable}" "{stub}" %*\r\n', encoding="utf-8"
        )
        return
    tool = bin_dir / "jscpd"
    tool.write_text(f"#!/usr/bin/env python3\n{python_body}", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)


def _run(tmp_path: Path, python_body: str) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    _write_jscpd_stub(bin_dir, python_body)
    config = tmp_path / "fallback.json"
    config.write_text(json.dumps(FALLBACK_CONFIG), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SENSOR), str(bin_dir / "jscpd"), "--fallback-config", str(config)],
        capture_output=True,
        encoding="utf-8",
        cwd=tmp_path,
    )


def test_an_exit_zero_run_writing_no_report_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, "import sys\nsys.exit(0)\n")

    assert result.returncode == 1
    assert "scanned nothing" in result.stderr


def test_an_exit_zero_run_writing_a_clean_report_passes(tmp_path: Path) -> None:
    body = (
        "import json, sys\n"
        "path = sys.argv[4] + '/jscpd-report.json'\n"
        'with open(path, "w", encoding="utf-8") as report:\n'
        '    json.dump({"duplicates": []}, report)\n'
        "sys.exit(0)\n"
    )

    result = _run(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
