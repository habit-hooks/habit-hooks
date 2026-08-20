"""What platform this run is on — the one place that asks.

Everything else that needs a platform-specific fact — the venv's executable
directory (:mod:`habit_hooks.project_paths`), the argv budget
(:mod:`habit_hooks.argv_budget`) — keeps that fact in the module that already
owns it, and asks *this* module the one question underneath all of them.

A caller does ``from . import host_platform`` and calls
``host_platform.is_windows()`` through the module, never
``from .host_platform import is_windows``. The second form binds the function
at import time, so a test that monkeypatches ``host_platform.is_windows``
afterwards would be patching a name nothing still looks up — the Windows
branch would never run outside a real Windows machine. Importing the module
and calling through it is what keeps both branches reachable from here.
"""

from __future__ import annotations

import sys


def is_windows() -> bool:
    """Whether this run is on Windows."""
    return sys.platform == "win32"
