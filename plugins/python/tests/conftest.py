"""Load the ruff sensor the way it is actually run — as a loose script.

The sensor spec spells ``${python} ${dir}/ruff_sensor.py``, so the
interpreter puts the helper's own directory first on ``sys.path`` and a unit
test does the same rather than reaching the code as
``habit_hooks_python.sensors.ruff_sensor`` — a load path no run ever takes
(see "A plugin helper imports its neighbours as top-level modules" in
CLAUDE.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

SENSORS = (
    Path(__file__).resolve().parents[1] / "src" / "habit_hooks_python" / "sensors"
)

sys.path.insert(0, str(SENSORS))
