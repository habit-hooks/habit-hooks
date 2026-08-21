"""A project whose declared tool is a batch file, and the parts that name it.

Windows is the only platform that runs a ``.bat`` or ``.cmd`` through
``cmd.exe``, and it is the extension alone that decides — never the host — so
these cases run everywhere and write the extension deliberately
(``executable_stub.write_batch_stub``). What they need in common is a project
with one such tool installed, a plugin declaring it, and a part naming it, which
is this module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bare_machine import project_with_no_tools
from detector_declarations import declaring
from executable_stub import write_batch_stub
from plugin_fixture import one_sensor

from habit_hooks.sensors.model import Part

BATCH_TOOL = '{ name = "probe.cmd", kind = "command", install = "npm i -D probe" }'
PLAIN_TOOL = '{ name = "probe", kind = "command", install = "npm i -D probe" }'


def recipe(*handed: str) -> str:
    """A helper reporting a clean run, handed ``handed`` and the scope to spawn."""
    tools = "".join(f', "{argument}"' for argument in handed)
    return f'argv = ["${{python}}", "-c", "print(\'[]\')"{tools}, "${{files}}"]'


def batch_sensor(project: Path) -> Part:
    """A sensor whose helper is handed a batch file to spawn."""
    return one_sensor(project, recipe("${detector:probe.cmd}"), declaring(BATCH_TOOL))


def installing_a_batch_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project whose only installed tool is the batch file ``probe.cmd``."""
    project = project_with_no_tools(tmp_path, monkeypatch)
    write_batch_stub(project / "node_modules" / ".bin", "probe")
    return project
