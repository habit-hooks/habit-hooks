"""The PMD this run resolved is the one the sensor spawns.

``sensors/pmd.toml`` names its tool with ``${detector:pmd}``, so the run
resolves it to a file and hands that file over as the helper's first argument.
Spawning it — rather than the bare name it was resolved from — is the whole of
what the sensor owes: a name is looked up again by whatever spawns it, and
Windows' own lookup adds ``.exe`` and nothing else, where PMD installs as a
``pmd.bat``.

A PMD nobody installed is no longer answered here. The part carries no file for
it, so nothing is ever spawned and the run answers as it does for any missing
command — the notice, the failed run, and that sensor's dropped findings
(``sensors/broken_part.py``).
"""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from tool_lookup import where_the_bare_name_reaches_nothing

SENSOR = (
    Path(__file__).resolve().parents[1] / "src/habit_hooks_java/sensors/pmd_sensor.py"
)

FIVE_PARAMETER_METHOD = """class Billing {
    double charge(double a, double b, double c, double d, double e) {
        return a + b + c + d + e;
    }
}
"""


def test_the_pmd_it_is_handed_runs_where_the_name_reaches_nothing(
    tmp_path: Path, pmd: str
) -> None:
    (tmp_path / "Billing.java").write_text(FIVE_PARAMETER_METHOD, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SENSOR), pmd, "--", "Billing.java"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=where_the_bare_name_reaches_nothing("pmd"),
    )

    assert result.returncode == 0, result.stderr
    assert [finding["smell"] for finding in json.loads(result.stdout)] == [
        "too-many-parameters"
    ]
