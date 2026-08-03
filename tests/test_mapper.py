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


def test_a_custom_smell_renders_its_paired_guide(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A smell outside the catalogue, declared in config and paired with a
    ``guides/<smell>.md``, renders that guide — not the uncoached fallback (#98)."""
    write_plugin(
        tmp_path,
        "fixt",
        {
            "config.toml": 'language = "python"',
            "guides/custom-marker.md": "Remove the custom marker.",
        },
    )
    write_project_config(
        tmp_path,
        'plugins = ["fixt"]\n[smells.custom-marker]\nseverity = "enforced"',
    )
    finding = {
        "smell": "custom-marker",
        "language": "python",
        "details": {},
        "issues": [{"key": "src/a.py", "details": {"file": "src/a.py"}}],
    }

    code = mapper.run([finding], tmp_path)

    out = capsys.readouterr().out
    assert "Remove the custom marker." in out
    assert "General guidance" not in out
    assert code == 1


def test_a_language_matching_plugin_wins_over_an_earlier_generic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With ``generic`` listed first, a finding whose language a later plugin
    declares still renders that plugin's guide, not generic's (#98)."""
    write_plugin(
        tmp_path,
        "gen",
        {
            "config.toml": "sensors = []",
            "guides/high-complexity.md": "generic complexity guidance",
        },
    )
    write_plugin(
        tmp_path,
        "py",
        {
            "config.toml": 'language = "python"',
            "guides/high-complexity.md": "python complexity guidance",
        },
    )
    write_project_config(tmp_path, 'plugins = ["gen", "py"]')
    finding = {
        "smell": "high-complexity",
        "language": "python",
        "details": {},
        "issues": [{"key": "src/a.py", "details": {"file": "src/a.py"}}],
    }

    mapper.run([finding], tmp_path)

    out = capsys.readouterr().out
    assert "python complexity guidance" in out
    assert "generic complexity guidance" not in out


def test_an_unconfigured_runner_extension_is_refused_by_name(
    tmp_path: Path,
) -> None:
    """A ``guide`` override with a non-``.md`` extension and no matching runner
    refuses by name instead of crashing with a ``KeyError`` (#98)."""
    write_plugin(
        tmp_path,
        "fixt",
        {
            "config.toml": "sensors = []",
            "guides/fixer.py": "print('never runs')",
        },
    )
    write_project_config(
        tmp_path,
        'plugins = ["fixt"]\n[smells.oversized-file]\nguide = "fixer.py"',
    )
    finding = {
        "smell": "oversized-file",
        "details": {},
        "issues": [{"key": "src/a.py", "details": {"file": "src/a.py"}}],
    }

    with pytest.raises(SystemExit) as excinfo:
        mapper.run([finding], tmp_path)

    message = str(excinfo.value)
    assert "oversized-file" in message
    assert "'py'" in message

