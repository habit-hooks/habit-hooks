"""The runtime: a Context holding run state, and the steps that mutate it."""

from __future__ import annotations

import os
import string
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import SpecError, SpecFailure
from .text import normalize


class Context:
    """Mutable state shared by one test's steps as they run."""

    def __init__(self, workdir: Path, repo_root: Path):
        self.workdir = workdir
        self.repo_root = repo_root
        self.env = dict(os.environ)
        self.stdin: str | None = None
        self.last: subprocess.CompletedProcess[str] | None = None
        self.exit_checked = False

    def run(self, script: str) -> None:
        self.check_default_exit()  # the previous command must have succeeded
        self.last = subprocess.run(
            ["bash", "-c", "set -o pipefail; " + script],
            cwd=self.workdir,
            env=self.env,
            input=self.stdin,
            capture_output=True,
            encoding="utf-8",
            errors="replace",  # sensors.spawn's policy
        )
        self.stdin = None
        self.exit_checked = False

    def require_last(self, marker: str) -> subprocess.CompletedProcess[str]:
        if self.last is None:
            raise SpecError(f"{marker} assertion with no preceding command")
        return self.last

    def check_default_exit(self) -> None:
        """A command with no explicit exit assertion must still have exited 0."""
        if self.last is not None and not self.exit_checked and self.last.returncode != 0:
            raise SpecFailure(f"command exited {self.last.returncode}, expected 0\n{self.last.stderr}")

    def assert_stream(self, name: str, actual: str, expected: str | None) -> None:
        if expected is None or normalize(actual) == normalize(expected):
            return
        raise SpecFailure(f"{name} mismatch\n--- expected ---\n{normalize(expected)}\n"
                          f"--- actual ---\n{normalize(actual)}")


@dataclass
class WriteFile:
    path: str
    block: str | None = None  # the file's content, filled when its fence is paired

    def apply(self, c: Context) -> None:
        dest = c.workdir / self.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.block + "\n", encoding="utf-8")


@dataclass
class CopyFile:
    dst: str
    src: str

    def apply(self, c: Context) -> None:
        dest = c.workdir / self.dst
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((c.repo_root / self.src).read_bytes())


@dataclass
class SetEnv:
    var: str
    block: str | None = None

    def apply(self, c: Context) -> None:
        mapping = {**c.env, "PWD": str(c.workdir)}
        c.env[self.var] = string.Template(self.block).safe_substitute(mapping)


@dataclass
class Stdin:
    block: str | None = None

    def apply(self, c: Context) -> None:
        c.stdin = self.block + "\n"


@dataclass
class Command:
    script: str

    def apply(self, c: Context) -> None:
        c.run(self.script)


@dataclass
class Screen:
    exit_code: int
    block: str | None = None  # expected stdout

    def apply(self, c: Context) -> None:
        result = c.require_last("🖥️")
        c.exit_checked = True
        if result.returncode != self.exit_code:
            raise SpecFailure(f"exit {result.returncode}, expected {self.exit_code}\n{result.stderr}")
        c.assert_stream("stdout", result.stdout, self.block)


@dataclass
class Stderr:
    exit_code: int | None = None
    block: str | None = None  # expected stderr

    def apply(self, c: Context) -> None:
        result = c.require_last("🚨")
        if self.exit_code is not None:
            c.exit_checked = True
            if result.returncode != self.exit_code:
                raise SpecFailure(f"exit {result.returncode}, expected {self.exit_code}")
        c.assert_stream("stderr", result.stderr, self.block)
