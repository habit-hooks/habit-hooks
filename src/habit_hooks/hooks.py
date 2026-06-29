"""The whole tool: ``habit-sensors $ARGS | habit-mapper`` over a Unix pipe."""

from __future__ import annotations

import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    sensors = subprocess.Popen(["habit-sensors", *args], stdout=subprocess.PIPE)
    mapper = subprocess.Popen(["habit-mapper"], stdin=sensors.stdout)
    sensors.stdout.close()
    mapper.wait()
    sensors.wait()
    return mapper.returncode


if __name__ == "__main__":
    sys.exit(main())
