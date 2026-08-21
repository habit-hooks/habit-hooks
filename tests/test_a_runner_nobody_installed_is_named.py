"""A `[runners]` command that is not installed answers in one line.

``[runners]`` lets a project route a smell to an executable guide instead of a
Markdown one. Naming a command nobody has is a first-contact mistake — a typo,
or a tool the reader has yet to install — and #114's rule is that those answer
with a sentence rather than a Python stack trace. That sweep covered the sensors
stage; the mapper's fix runner was left out, so a missing runner escaped as a
`FileNotFoundError` through `cli.run_console`, which catches only `ToolError`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks import mapper
from habit_hooks.cli import ToolError
from plugin_fixture import write_plugin, write_project_config

_FINDING = {
    "smell": "oversized-file",
    "details": {},
    "issues": [{"key": "src/a.py", "details": {"file": "src/a.py"}}],
}


def _project_routing_to(tmp_path: Path, runner: str) -> Path:
    write_plugin(
        tmp_path,
        "fixt",
        {"config.toml": "", "guides/oversized-file.sh": "echo fixed\n"},
    )
    write_project_config(
        tmp_path, f'plugins = ["fixt"]\n[runners]\nsh = "{runner}"'
    )
    return tmp_path


def test_a_runner_that_is_not_installed_is_named_with_what_to_do(
    tmp_path: Path,
) -> None:
    """The refusal names the command, the guide that asked for it, and the way out."""
    project = _project_routing_to(tmp_path, "a-runner-nobody-installed")

    with pytest.raises(ToolError) as refusal:
        mapper.run([_FINDING], project)

    said = str(refusal.value)
    assert "a-runner-nobody-installed" in said
    assert "oversized-file.sh" in said
    assert "Traceback" not in said


def test_a_runner_that_is_installed_still_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The guard answers for a command that is absent, and for nothing else."""
    project = _project_routing_to(tmp_path, "sh")

    mapper.run([_FINDING], project)

    assert "fixed" in capsys.readouterr().out
