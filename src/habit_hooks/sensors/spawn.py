"""Spawn a part's command as a bounded, isolated subprocess.

Every sensor and transformer is a shell command run against the project's own
tool binaries. Two things keep an unusual-but-real run from turning into a hang
or a lost run: a deadline (a wedged tool must not block the git hook forever) and
an own empty stdin (the child must never inherit the parent's — a ``pre-push``
hook carries refs there). ``run_part`` adds the third at the caller's boundary:
a timeout surfaced as the ``SensorError`` every other failure already is.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .model import Part
from .part_output import part_spawn_failure, part_timeout

# Seconds one invocation may run before it is killed. A wedged tool — waiting on
# input, or churning on a pathological repo — otherwise blocks the hook forever
# with no output; a finite ceiling makes it return.
DEFAULT_SENSOR_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class Spawner:
    """Runs a command against the project's tool bins, bounded and isolated."""

    project_dir: Path
    timeout: float = DEFAULT_SENSOR_TIMEOUT_SECONDS

    def run(self, command: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        """Shell out with the project bins on PATH, an own stdin, and a deadline.

        ``input`` is always a string, never ``None``, so the child cannot inherit
        the parent's stdin — a tool that prompts would otherwise block on it.
        """
        return subprocess.run(
            ["bash", "-c", command],
            cwd=self.project_dir,
            env=self._path_env(),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

    def _path_env(self) -> dict:
        env = dict(os.environ)
        node = self.project_dir / "node_modules" / ".bin"
        venv = self.project_dir / ".venv" / "bin"
        prefix = os.pathsep.join([str(node), str(venv)])
        env["PATH"] = prefix + os.pathsep + env.get("PATH", "")
        return env


def run_part(
    kind: str, part: Part, run: Callable[[], subprocess.CompletedProcess[str]]
) -> subprocess.CompletedProcess[str]:
    """``run()``'s result, its spawn failures raised as the ``SensorError`` they are.

    A wedged tool that never returns must not block the hook: its deadline
    becomes the same notice + failed run any other spawn failure produces. A
    spawn the operating system refuses outright is that failure one step
    earlier, and raises an ``OSError`` nothing between here and ``main`` caught.
    """
    try:
        return run()
    except subprocess.TimeoutExpired as expiry:
        raise part_timeout(kind, part, expiry) from None
    except OSError as refusal:
        raise part_spawn_failure(kind, part, refusal) from None
