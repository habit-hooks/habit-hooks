"""``[sensors.pmd] args`` must reach PMD itself, not become a file to scan.

Before this fix ``main()`` turned every argv token that was not the ruleset
into a ``-d <path>`` PMD file argument, so a genuine PMD flag such as
``--minimum-priority`` broke the run outright (picocli: "Expected parameter
for option '--dir' but found '--minimum-priority'"). The sensor's command now
spells ``${args} -- ${files}``, and the wrapper splits ``sys.argv[1:]`` on the
*last* ``--``: everything before it goes to PMD verbatim, everything after
becomes a file. A ``--rulesets``/``-R`` on the PMD-flag half is still pulled
out for `-R`, exactly as it was before this split existed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SENSOR = (
    Path(__file__).resolve().parents[1] / "src/habit_hooks_java/sensors/pmd_sensor.py"
)

FIVE_PARAMETER_METHOD_WITH_UNUSED_IMPORT = """import java.io.File;
class Billing {
    double charge(double a, double b, double c, double d, double e) {
        return a + b + c + d + e;
    }
}
"""

TWO_PARAMETER_METHOD = """class Project {
    void save(String a, String b) {
    }
}
"""

TWO_IS_TOO_MANY_RULESET = """<?xml version="1.0"?>
<ruleset name="custom" xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">
 <description>two parameters is already too many</description>
 <rule ref="category/java/design.xml/ExcessiveParameterList">
  <properties><property name="minimum" value="2"/></properties>
 </rule>
</ruleset>
"""


def _run(cwd: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SENSOR), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_a_pmd_flag_in_args_reaches_pmd(tmp_path: Path) -> None:
    """ExcessiveParameterList reports at priority 3 and UnnecessaryImport at
    priority 4 (verified against PMD 7.26.0), so ``--minimum-priority 3``
    keeps the first and drops the second — proof the flag reached PMD's own
    filtering rather than becoming a bogus ``-d`` file argument. A threshold
    that dropped every rule would pass as trivially as one that reached
    nothing at all, so the assertion has to be a smell that survives, not an
    empty result."""
    (tmp_path / "Billing.java").write_text(FIVE_PARAMETER_METHOD_WITH_UNUSED_IMPORT)

    without_the_flag = _run(tmp_path, ["--", "Billing.java"])
    with_the_flag = _run(tmp_path, ["--minimum-priority", "3", "--", "Billing.java"])

    assert without_the_flag.returncode == 0, without_the_flag.stderr
    without_smells = {finding["smell"] for finding in json.loads(without_the_flag.stdout)}
    assert without_smells == {"too-many-parameters", "unused-import"}

    assert with_the_flag.returncode == 0, with_the_flag.stderr
    with_smells = {finding["smell"] for finding in json.loads(with_the_flag.stdout)}
    assert with_smells == {"too-many-parameters"}


def test_a_ruleset_named_in_args_is_still_honoured(tmp_path: Path) -> None:
    (tmp_path / "Project.java").write_text(TWO_PARAMETER_METHOD)
    ruleset = tmp_path / "strict.xml"
    ruleset.write_text(TWO_IS_TOO_MANY_RULESET)

    result = _run(tmp_path, ["--rulesets", str(ruleset), "--", "Project.java"])

    assert result.returncode == 0, result.stderr
    findings = json.loads(result.stdout)
    assert [finding["smell"] for finding in findings] == ["too-many-parameters"]
