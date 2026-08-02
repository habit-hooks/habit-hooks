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

_INCOMPLETE_RUN_FINDING = {
    "smell": "incomplete-run",
    "details": {},
    "issues": [
        {
            "key": "habit-sensors: sensor 'comment' failed: boom",
            "details": {"content": "habit-sensors: sensor 'comment' failed: boom"},
        }
    ],
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


def test_an_incomplete_run_finding_is_coached_not_rendered_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run carrying the reserved ``incomplete-run`` finding never renders the
    clean guide, and its enforced severity fails the run (#88)."""
    write_project_config(tmp_path, 'plugins = ["fixt"]')

    code = mapper.run([_INCOMPLETE_RUN_FINDING], tmp_path)

    out = capsys.readouterr().out
    assert "✅" not in out
    assert "── incomplete-run (1 issue) ──" in out
    # The tuned core guide, not the uncoached fallback, coaches the break.
    assert "this run did not complete — a tool broke" in out
    assert "sensor 'comment' failed: boom" in out
    assert code == 1


def test_a_clean_run_still_renders_the_clean_guide(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no findings the mapper renders the core clean guide and exits 0 —
    the reserved smell must not disturb a genuinely clean run (#88)."""
    write_project_config(tmp_path, 'plugins = ["fixt"]')

    code = mapper.run([], tmp_path)

    assert "✅ Habit Hooks: automated checks passed." in capsys.readouterr().out
    assert code == 0
