"""End-to-end tests for habit-mapper's consumption of plugin-shipped config.

The mapper reads ``[runners]`` from the merged config. A plugin that ships its
own ``[runners]`` (resolved through the override chain, like ``files``) must have
its language-specific fix runner registered without the project configuring it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from habit_hooks import mapper
from plugin_fixture import write_plugin, write_project_config

_GUIDE = """\
import sys, json
json.load(sys.stdin)
print("ran the plugin fixer")
"""

_FINDING = {
    "smell": "oversized-file",
    "details": {},
    "issues": [{"key": "src/a.py", "details": {"file": "src/a.py"}}],
}


def test_a_plugin_shipped_runner_executes_its_guide(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_plugin(
        tmp_path,
        "fixt",
        {
            "config.toml": f'[runners]\npy = "{sys.executable}"',
            "guides/oversized-file.py": _GUIDE,
        },
    )
    write_project_config(tmp_path, 'plugins = ["fixt"]')

    mapper.run([_FINDING], tmp_path)

    assert "ran the plugin fixer" in capsys.readouterr().out
