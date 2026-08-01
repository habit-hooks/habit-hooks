"""The whole tool: ``habit-sensors $ARGS | habit-mapper`` over a Unix pipe."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def sibling(name: str) -> str:
    """Resolve a sibling console script next to this executable, else by name."""
    beside = Path(sys.argv[0]).resolve().parent / name
    return str(beside) if beside.is_file() else name


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    sensors = subprocess.Popen([sibling("habit-sensors"), *args], stdout=subprocess.PIPE)
    mapper = subprocess.Popen([sibling("habit-mapper")], stdin=sensors.stdout)
    sensors.stdout.close()
    mapper.wait()
    sensors.wait()
    # A failed sensor contributes no findings, so a clean mapper alone would
    # report a green run over broken tooling; either stage failing fails the run.
    return mapper.returncode or sensors.returncode


if __name__ == "__main__":
    sys.exit(main())
