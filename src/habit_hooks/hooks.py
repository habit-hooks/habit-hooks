"""The whole tool: ``habit-sensors $ARGS | habit-mapper`` over a Unix pipe.

Everything a stage would print on stdout lands on that pipe, where the mapper
expects findings JSON — so the few things that are the *pipeline's* own to say
(``--version``, ``--help``, and setting a project up with ``init``) are answered
here, before either stage is spawned.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .cli import run_console, version_line
from .init_command import run as run_init
from .sensors import build_parser

INIT = "init"

# The audience for `init` is whoever is typing `--help`, and the scan flags
# beside it are no use to a project with nothing configured yet. It is said here
# rather than by the sensors parser, which lists only what this pipeline
# forwards — and `init` is never forwarded.
INIT_HELP = (
    "Set a project up with `habit-hooks init`: it writes .habit-hooks/config.toml "
    "and reports what is still missing."
)


def sibling(name: str) -> str:
    """Resolve a sibling console script next to this executable, else by name."""
    beside = Path(sys.argv[0]).resolve().parent / name
    return str(beside) if beside.is_file() else name


def mapper_args(args: list[str]) -> list[str]:
    """The pipeline flags the mapper also needs — just ``--config``, so one
    ``--config`` answers every stage instead of the mapper silently falling back
    to ``.habit-hooks/config.toml`` (#86). The sensors stage still gets them all.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config")
    known, _ = parser.parse_known_args(args)
    return ["--config", known.config] if known.config else []


def print_usage() -> None:
    """The flags a run is spelled with, and the one command that is not one."""
    parser = build_parser("habit-hooks")
    parser.epilog = INIT_HELP
    parser.print_help()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    # All three are answered here, before anything is spawned: forwarded to
    # habit-sensors they print onto the pipe where habit-mapper expects findings
    # JSON, so the version arrived as an unparseable line and the usage text as a
    # JSONDecodeError the user read instead of the help they asked for (#114).
    # `init` goes first so `habit-hooks init --help` answers for init rather than
    # for the pipeline; the sensors parser has no positionals, so nothing else
    # can mean it.
    if args[:1] == [INIT]:
        return run_console("habit-hooks", run_init, args[1:])
    if "--version" in args:
        sys.stdout.write(version_line() + "\n")
        return 0
    if any(flag in args for flag in ("--help", "-h")):
        print_usage()
        return 0
    sensors = subprocess.Popen([sibling("habit-sensors"), *args], stdout=subprocess.PIPE)
    mapper = subprocess.Popen(
        [sibling("habit-mapper"), *mapper_args(args)], stdin=sensors.stdout
    )
    sensors.stdout.close()
    mapper.wait()
    sensors.wait()
    # A failed sensor contributes no findings, so a clean mapper alone would
    # report a green run over broken tooling; either stage failing fails the run.
    return mapper.returncode or sensors.returncode


if __name__ == "__main__":
    sys.exit(main())
