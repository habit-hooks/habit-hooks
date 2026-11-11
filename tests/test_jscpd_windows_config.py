from __future__ import annotations

import json
from pathlib import Path

import pytest

from habit_hooks_generic import jscpd as jscpd_sensor

STUB_BODY = """\
#!/usr/bin/env python3
import json, sys
positional = [a for a in sys.argv[1:] if not a.startswith("--")]
assert positional, "no positional path argument"
assert "\\\\" not in positional[0], positional[0]
report = sys.argv[sys.argv.index("--output") + 1] + "/jscpd-report.json"
clone = {
    "lines": 10,
    "tokens": 50,
    "firstFile": {"name": "a.py", "start": 1, "end": 10},
    "secondFile": {"name": "b.py", "start": 11, "end": 20},
}
with open(report, "w", encoding="utf-8") as f:
    json.dump({"duplicates": [clone]}, f)
sys.exit(0)
"""


def _project(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / ".jscpd.json").write_text(json.dumps({"path": ["src"]}), encoding="utf-8")
    fallback = tmp_path / "fallback.json"
    fallback.write_text(json.dumps({"path": ["src"]}), encoding="utf-8")
    return tmp_path / "jscpd_stub.py", fallback


@pytest.fixture
def windows_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    def run(python_body: str) -> list[dict]:
        stub, fallback = _project(tmp_path)
        stub.write_text(python_body, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | 0o111)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(jscpd_sensor, "is_windows", lambda: True)
        assert jscpd_sensor.main([str(stub), "--fallback-config", str(fallback)]) == 0
        return json.loads(capsys.readouterr().out)

    return run


def test_windows_run_passes_the_project_path_positionally(windows_findings) -> None:
    findings = windows_findings(STUB_BODY)

    assert [finding["smell"] for finding in findings] == ["duplicated-code"]
    assert findings[0]["issues"][0]["key"] == "a.py"