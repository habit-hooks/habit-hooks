"""``habit-hooks init``: write the config, say what is missing, offer to fix it.

The flow around :mod:`habit_hooks.init_report`, which decides none of it and
prints none of it: this module is the one that touches the world — the config
file it writes, the question it asks, the installs it runs.

Two things keep the offer honest. It is **one** prompt for the whole list rather
than one per command, because a list of six is a decision about the setup and
six decisions about nothing; and it is only ever asked when **stdin is a
terminal**, because habit-hooks runs inside git hooks and CI, where a prompt is
not answered by anybody and the hook simply stops. Non-interactively the
commands are printed and that is all — the exit stays 0 and the config file is
the only thing that changed.

The default is no. Enter installs nothing, because the reader who pressed it
without reading is the reader who should not be installing anything.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .config import project_config_path
from .init_report import report
from .initialise import plan


def _parse(argv: list[str]) -> None:
    """``init`` takes no arguments; anything else fails as a usage error.

    Spelled with argparse so a mistyped flag answers with a usage line at exit
    2, rather than being silently ignored by a command that then reports on a
    scope the reader did not ask for.
    """
    argparse.ArgumentParser(
        prog="habit-hooks init",
        description="Set this project up: write .habit-hooks/config.toml and "
        "report what habit-hooks still needs installed.",
    ).parse_args(argv)


def _write_config(project_dir: Path, plugins: tuple[str, ...]) -> None:
    """The smallest config that runs: the plugins, and nothing else assumed.

    Only ever called for a project that has none — a re-run must change nothing,
    or the doctor mode would overwrite the settings it was asked about.
    """
    named = ", ".join(f'"{plugin}"' for plugin in plugins)
    path = project_config_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"plugins = [{named}]\n")


def _say(line: str) -> None:
    sys.stdout.write(line + "\n")


def _question(count: int) -> str:
    subject = "this command" if count == 1 else f"these {count} commands"
    return f"\nRun {subject} now? [y/N] "


def _agreed(count: int) -> bool:
    """Whether the reader said yes, where silence and end-of-input say no."""
    sys.stdout.write(_question(count))
    sys.stdout.flush()
    return sys.stdin.readline().strip().lower() in ("y", "yes")


def _succeeded(command: str) -> bool:
    """Run one install through a shell, echoing it first.

    A shell because that is what an ``install`` string is written for — a plugin
    author spells the line they would type — and echoing first because the
    output of several installs in a row is otherwise unattributable. The reader
    has just seen every one of these listed and agreed to them.
    """
    _say(f"\n$ {command}")
    sys.stdout.flush()
    return subprocess.run(command, shell=True).returncode == 0


def _run_all(commands: tuple[str, ...]) -> None:
    """Run every command, and report the ones that failed rather than stop.

    One failure is rarely all of them — a missing tap is not a missing plugin —
    and stopping at the first would hide the rest behind a round trip each.
    """
    failed = []
    for command in commands:
        if not _succeeded(command):
            failed.append(command)
    if not failed:
        return
    _say("\nThese did not succeed, and are still to do:")
    for command in failed:
        _say(f"  {command}")


def _offer(commands: tuple[str, ...]) -> None:
    if not commands or not sys.stdin.isatty():
        return
    if _agreed(len(commands)):
        _run_all(commands)


def run(argv: list[str]) -> int:
    """Set the current directory up, and report on it either way.

    Always 0: init's own job is to configure and report, and it did that even
    where an install it offered to run failed. What failed is said in words, and
    the tool is still missing when the reader runs init again.
    """
    _parse(argv)
    project_dir = Path.cwd()
    planned = plan(project_dir)
    if not planned.already_configured:
        _write_config(project_dir, planned.plugins)
    for line in report(planned):
        _say(line)
    _offer(planned.installs)
    return 0
