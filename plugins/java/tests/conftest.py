"""Load the pmd sensor the way it is actually run — as a loose script.

The sensor spec spells ``${python} ${dir}/pmd_sensor.py``, so the interpreter
puts the helper's own directory first on ``sys.path`` and its neighbour
``pmd_ruleset`` is a plain top-level import. A unit test here does the same
rather than reaching the code as ``habit_hooks_java.sensors.pmd_sensor`` — a
load path no run takes, and the only one that import fails under.
"""

from __future__ import annotations

import sys
from pathlib import Path

SENSORS = Path(__file__).resolve().parents[1] / "src" / "habit_hooks_java" / "sensors"

sys.path.insert(0, str(SENSORS))
