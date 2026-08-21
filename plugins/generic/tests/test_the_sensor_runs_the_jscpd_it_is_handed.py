"""The jscpd this run resolved is the one the sensor spawns.

``sensors/jscpd.toml`` names its tool with ``${detector:jscpd}``, so the run
resolves it to a file and hands that file over as the helper's first argument.
Spawning it — rather than the bare name it was resolved from — is the whole of
what the sensor owes: a name is looked up again by whatever spawns it, and
Windows' own lookup adds ``.exe`` and nothing else, where npm installs jscpd as
a ``jscpd.CMD`` shim.

A jscpd nobody installed is no longer answered here. The part carries no file
for it, so nothing is ever spawned and the run answers as it does for any
missing command — the notice, the failed run, and that sensor's dropped findings
(``sensors/broken_part.py``).
"""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from tool_lookup import where_the_bare_name_reaches_nothing

from jscpd_sensor import SENSOR, write_clones, write_json


def test_the_jscpd_it_is_handed_runs_where_the_name_reaches_nothing(
    tmp_path: Path, jscpd: str
) -> None:
    write_clones(tmp_path / "src", ["alpha", "beta"])
    config = write_json(
        tmp_path / "cfg.json",
        {"path": ["src"], "threshold": 100, "minLines": 5, "minTokens": 50},
    )

    result = subprocess.run(
        [sys.executable, str(SENSOR), jscpd, "--fallback-config", str(config)],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=where_the_bare_name_reaches_nothing("jscpd"),
    )

    assert result.returncode == 0, result.stderr
    assert [finding["smell"] for finding in json.loads(result.stdout)] == [
        "duplicated-code"
    ]
