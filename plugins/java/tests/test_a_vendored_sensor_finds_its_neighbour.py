"""The route that copies the plugin's files into a project must still import.

Vendoring under ``.habit-hooks/<plugin>/`` is the extras-free install the README
advertises: the copied files win the override chain, ``${dir}`` in the sensor
command expands to wherever they landed, and the plugin package is typically not
installed at all — that is the point of vendoring. The sensor imports
``pmd_ruleset`` from beside itself, which has to resolve because a loose
script's own directory is ``sys.path[0]``, never because ``habit_hooks_java``
happens to be importable.

``-S`` is what tells those two apart: it denies the child the site-packages this
checkout has the plugin installed into, so an import reaching for the package
fails here exactly as it would for a project that vendored instead of
installing. Without it the copy would pass on the installed package's modules
and prove nothing about the files it just copied.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

SENSORS = Path(__file__).resolve().parents[1] / "src" / "habit_hooks_java" / "sensors"

FIVE_PARAMETER_METHOD = """class Billing {
    double charge(double a, double b, double c, double d, double e) {
        return a + b + c + d + e;
    }
}
"""


def _vendored_sensor(project: Path) -> Path:
    """The plugin's sensor files copied where a project vendoring them puts them."""
    sensors = project / ".habit-hooks" / "java" / "sensors"
    shutil.copytree(SENSORS, sensors, ignore=shutil.ignore_patterns("__pycache__"))
    return sensors / "pmd_sensor.py"


def test_a_vendored_sensor_reports_a_smell_with_no_package_around_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "Billing.java").write_text(FIVE_PARAMETER_METHOD, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-S", str(_vendored_sensor(tmp_path)), "--", "Billing.java"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stderr
    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["too-many-parameters"]
