from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from habit_hooks_generic import jscpd as jscpd_sensor

FALLBACK_CONFIG = {"minLines": 5, "minTokens": 50}

CLONE = {
    "lines": 10,
    "tokens": 50,
    "firstFile": {"name": "a.py", "start": 1, "end": 10},
    "secondFile": {"name": "b.py", "start": 11, "end": 20},
}

PLUGIN_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "generic"
    / "src"
    / "habit_hooks_generic"
    / "config.toml"
)


def whole_project_stub(assertions: str) -> str:
    return (
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "arguments = sys.argv[1:]\n"
        "positional = []\n"
        "skip = False\n"
        "for argument in arguments:\n"
        "    if skip:\n"
        "        skip = False\n"
        "        continue\n"
        "    if argument.startswith('--'):\n"
        "        skip = True\n"
        "        continue\n"
        "    positional.append(argument)\n"
        + assertions
        + "output = arguments[arguments.index('--output') + 1]\n"
        f"clone = {json.dumps(CLONE)}\n"
        "with open(output + '/jscpd-report.json', 'w', encoding='utf-8') as report:\n"
        "    json.dump({'duplicates': [clone]}, report)\n"
    )


@pytest.fixture
def run_sensor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    def run(python_body: str, project_config: bool = False) -> list[dict]:
        if project_config:
            (tmp_path / ".jscpd.json").write_text(
                json.dumps({"path": ["src"]}), encoding="utf-8"
            )
        fallback = tmp_path / "fallback.json"
        fallback.write_text(json.dumps(FALLBACK_CONFIG), encoding="utf-8")
        stub = tmp_path / "jscpd_stub.py"
        stub.write_text(python_body, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | 0o111)
        monkeypatch.chdir(tmp_path)
        argv = [str(stub), "--fallback-config", str(fallback)]
        assert jscpd_sensor.main(argv) == 0
        return json.loads(capsys.readouterr().out)

    return run


def test_the_run_scans_the_project_in_one_positional(run_sensor) -> None:
    body = whole_project_stub(
        "import os\n"
        "assert len(positional) == 1, arguments\n"
        "assert os.path.isabs(positional[0]) and '\\\\' not in positional[0], arguments\n"
    )

    findings = run_sensor(body, project_config=True)

    assert findings == [jscpd_sensor.clone_finding(CLONE)]


def test_a_project_config_runs_without_the_fallback_config(run_sensor) -> None:
    body = whole_project_stub("assert '--config' not in arguments, arguments\n")

    findings = run_sensor(body, project_config=True)

    assert findings == [jscpd_sensor.clone_finding(CLONE)]


def test_without_a_project_config_the_fallback_config_is_passed(run_sensor) -> None:
    body = whole_project_stub("assert '--config' in arguments, arguments\n")

    findings = run_sensor(body)

    assert findings == [jscpd_sensor.clone_finding(CLONE)]


def test_the_plugin_recipe_never_hands_jscpd_the_scoped_files() -> None:
    config = tomllib.loads(PLUGIN_CONFIG.read_text(encoding="utf-8"))

    entry = next(sensor for sensor in config["sensors"] if sensor["name"] == "jscpd")

    assert "${files}" not in entry["args"]
    assert "${files:comma}" not in entry["args"]


def test_the_shipped_fallback_keeps_its_settings_and_has_no_path() -> None:
    shipped = Path(jscpd_sensor.__file__).parent / ".jscpd.json"

    config = json.loads(shipped.read_text(encoding="utf-8"))

    assert config["ignore"] == ["tests/fixtures/**", "dist/**", "node_modules/**"]
    assert config["threshold"] == 0
    assert config["minLines"] == 5
    assert config["minTokens"] == 50
    assert "path" not in config
