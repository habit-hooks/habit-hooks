"""The bundled `.jscpd.json` answers "this project has none", never overrides.

The sensor used to pass `--config <ours>` on every run, so a team's own
`threshold`, `minLines`, `minTokens` and `ignore` were silently replaced by
ours (#125). Which places count as "a config of its own" is not ours to invent
either: it is the set jscpd itself reads — `.jscpd.json` in the directory it
runs in, then a `jscpd` key in `package.json` — so a project is never told its
config was honoured where jscpd would never have looked.

Each case puts a clone under `src` and another under `lib`, and lets the two
configs disagree about which one is scanned: the bundled config (written
outside the project, where the real one lives) names `src`, the project's own
names `lib`. Whose directory comes back names whose config won.
"""

from __future__ import annotations

import json
from pathlib import Path

from jscpd_sensor import requires_jscpd, run_sensor, write_clones, write_json


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    write_clones(project / "src", ["alpha", "beta"])
    write_clones(project / "lib", ["gamma", "delta"])
    return project


def _bundled_config(tmp_path: Path) -> Path:
    """Ours, outside the project — its relative `src` must still find theirs."""
    return write_json(
        tmp_path / "plugin" / ".jscpd.json",
        {"path": ["src"], "minLines": 5, "minTokens": 50},
    )


def _scanned(result) -> set[str]:
    findings = json.loads(result.stdout)
    return {
        Path(issue["key"]).parent.name
        for finding in findings
        for issue in finding["issues"]
    }


def test_the_projects_own_jscpd_json_replaces_ours(tmp_path: Path) -> None:
    requires_jscpd()
    project = _project(tmp_path)
    write_json(project / ".jscpd.json", {"path": ["lib"], "minLines": 5})

    result = run_sensor(project, ["--fallback-config", str(_bundled_config(tmp_path))])

    assert result.returncode == 0, result.stderr
    assert _scanned(result) == {"lib"}


def test_a_jscpd_key_in_package_json_replaces_ours(tmp_path: Path) -> None:
    """jscpd's other config home, so it has to be ours too."""
    requires_jscpd()
    project = _project(tmp_path)
    write_json(project / "package.json", {"jscpd": {"path": ["lib"], "minLines": 5}})

    result = run_sensor(project, ["--fallback-config", str(_bundled_config(tmp_path))])

    assert result.returncode == 0, result.stderr
    assert _scanned(result) == {"lib"}


def test_a_package_json_without_a_jscpd_key_is_not_a_config(tmp_path: Path) -> None:
    """Nearly every JS project has one; almost none of them configure jscpd."""
    requires_jscpd()
    project = _project(tmp_path)
    write_json(project / "package.json", {"name": "example", "private": True})

    result = run_sensor(project, ["--fallback-config", str(_bundled_config(tmp_path))])

    assert result.returncode == 0, result.stderr
    assert _scanned(result) == {"src"}


def test_a_package_json_jscpd_cannot_parse_falls_back_to_ours(tmp_path: Path) -> None:
    """jscpd warns and carries on rather than dying, and so must the sensor."""
    requires_jscpd()
    project = _project(tmp_path)
    (project / "package.json").write_text("{ not json")

    result = run_sensor(project, ["--fallback-config", str(_bundled_config(tmp_path))])

    assert result.returncode == 0, result.stderr
    assert _scanned(result) == {"src"}
